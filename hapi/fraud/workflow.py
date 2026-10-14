#!/usr/bin/env python3
"""Runs a compiled fraud workflow (workflow_spec.json), and the router in front of it.

    python workflow.py run [--questions rules|llm|jev|auto] [--no-research]     # workflow only
    python workflow.py routed [--no-escalate]                                   # workflow, then the agent if unsure
    python workflow.py replay traces/<run id>.json [--spec other.json] [--reclassify rules]

The spec (written by compile_workflow.py) is a list of typed steps:

  code      a check from workflow_ops.py over the claims table (no model)
  question  one yes/no question per provider the code step flagged ("is this consistent
            with upcoding?"), answered with a probability by a classifier (questions.py)
  research  a small create_agent sub-agent with only fhir_search / fhir_read, run only for
            provider-scheme pairs whose probability is in the uncertain band
  escalate  the router: below `min_confidence`, or when a provider is outside the profile
            limits and no question explains it, the case goes to the full agent (agent.py)

A run emits the same trace events as agent.investigate() (run_start, text, tool_call,
tool_result, final with findings, done), so server.py, the app and scoring.py work
unchanged. It also emits `workflow_node` events: the spec, each code step's output, each
question's evidence and probabilities, each research answer, and the route. decide()
turns those records into findings and the route, and replay() runs decide() again on a
saved trace without calling any model (optionally with another spec's thresholds).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Awaitable, Callable

import workflow_ops
from questions import Classifier, RulesClassifier, make_classifier

HERE = Path(__file__).resolve().parent
DEFAULT_SPEC = HERE / "workflow_spec.json"
NODE_TYPES = {"code", "question", "research", "escalate"}
Emit = Callable[[dict], Awaitable[None]]


# ---------------------------------------------------------------- spec

class SpecError(ValueError):
    """The workflow spec is malformed."""


def validate_spec(spec: dict) -> dict:
    nodes = spec.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise SpecError("spec needs a non-empty 'nodes' list")
    seen: dict[str, dict] = {}
    for node in nodes:
        nid, kind = node.get("id"), node.get("type")
        if not nid or nid in seen:
            raise SpecError(f"node ids must be present and unique: {nid!r}")
        if kind not in NODE_TYPES:
            raise SpecError(f"{nid}: unknown type {kind!r} (expected one of {sorted(NODE_TYPES)})")
        if kind == "code" and node.get("op") not in workflow_ops.OPS:
            raise SpecError(f"{nid}: unknown op {node.get('op')!r} (expected one of {sorted(workflow_ops.OPS)})")
        if kind == "question":
            source = seen.get(node.get("input"))
            if not source or source["type"] != "code":
                raise SpecError(f"{nid}: input must name an earlier code node, got {node.get('input')!r}")
            if not {"yes", "no"} <= set(node.get("choices", {})):
                raise SpecError(f"{nid}: choices must include yes and no")
            prior = node.get("prior", {})
            if not isinstance(prior.get("center"), (int, float)) or not prior.get("scale", 0) > 0:
                raise SpecError(f"{nid}: prior needs a numeric center and a positive scale")
            if not node.get("scheme") or not node.get("question"):
                raise SpecError(f"{nid}: question nodes need a scheme and a question")
        if kind == "research":
            lo, hi = node.get("band", [None, None])
            if not (isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and 0 <= lo < hi <= 1):
                raise SpecError(f"{nid}: band must be [low, high] with 0 <= low < high <= 1")
        if kind == "escalate" and not 0 <= node.get("min_confidence", -1) <= 1:
            raise SpecError(f"{nid}: min_confidence must be between 0 and 1")
        seen[nid] = node
    for kind in ("research", "escalate"):
        if sum(n["type"] == kind for n in nodes) > 1:
            raise SpecError(f"at most one {kind} node")
    if not 0 < spec.get("report_threshold", 0.5) < 1:
        raise SpecError("report_threshold must be between 0 and 1")
    return spec


def load_spec(path: Path | str = DEFAULT_SPEC) -> dict:
    path = Path(path)
    if not path.exists():
        raise SpecError(f"{path} not found: run compile_workflow.py first")
    return validate_spec(json.loads(path.read_text()))


def spec_hash(spec: dict) -> str:
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:12]


def nodes_of(spec: dict, kind: str) -> list[dict]:
    return [n for n in spec["nodes"] if n["type"] == kind]


def node_of(spec: dict, kind: str) -> dict | None:
    return next(iter(nodes_of(spec, kind)), None)


# ---------------------------------------------------------------- decisions (shared by run and replay)

class _Missing(dict):
    def __missing__(self, key):
        return "?"


def _confidence(p: float) -> str:
    return "high" if p >= 0.85 else "medium" if p >= 0.65 else "low"


def decide(spec: dict, records: list[dict]) -> dict:
    """Findings and route from the workflow_node records of one run. Pure: no data access,
    no model calls, so a saved run can be decided again (replay)."""
    threshold = spec.get("report_threshold", 0.5)
    research_node = node_of(spec, "research") or {"band": [0.3, 0.7]}
    escalate_node = node_of(spec, "escalate")
    questions = {n["id"]: n for n in nodes_of(spec, "question")}
    researched = {(r["provider"], r["scheme"]): r for r in records if r.get("kind") == "research" and r.get("p_yes") is not None}
    items = []
    for rec in records:
        if rec.get("kind") != "question" or rec["node"] not in questions:
            continue
        node = questions[rec["node"]]
        if rec["evidence"].get("score", 0) < node.get("screen", float("-inf")):
            continue  # a later spec may screen more strictly than the one the run used
        p = rec["probabilities"]["yes"]
        r = researched.get((rec["provider"], node["scheme"]))
        items.append({"provider": rec["provider"], "name": rec.get("name", ""), "scheme": node["scheme"], "node": node,
                      "evidence": rec["evidence"], "p_question": p, "p": r["p_yes"] if r else p,
                      "research": r["evidence_text"] if r else ""})
    findings = []
    for it in sorted(items, key=lambda i: -i["p"]):
        if it["p"] < threshold:
            continue
        ev = it["evidence"]
        text = it["node"].get("describe", "").format_map(_Missing(ev))
        findings.append({"provider": it["provider"], "name": it["name"],
                         "scheme": f"{it['node'].get('label', it['scheme'])}: {text}".strip(": "),
                         "claims": ev.get("claims", 0), "amount_at_risk": ev.get("amount", 0.0),
                         "confidence": _confidence(it["p"]), "probability": round(it["p"], 3),
                         "evidence": "; ".join(x for x in (", ".join(ev.get("eobs", [])[:5]), it["research"]) if x)})
    lo, hi = research_node["band"]
    uncertain = [{"provider": i["provider"], "scheme": i["scheme"], "p": round(i["p"], 3)} for i in items if lo <= i["p"] < hi]
    confidence = min((max(i["p"], 1 - i["p"]) for i in items), default=1.0)
    reported = {f["provider"] for f in findings}
    profile = [r for r in records if r.get("kind") == "code" and r.get("op") == "profile"]
    unexplained = sorted({prov for r in profile for prov in r["output"]["providers"]} - reported)
    reasons = []
    if escalate_node:
        if confidence < escalate_node["min_confidence"]:
            reasons.append(f"least certain decision {confidence:.2f} < {escalate_node['min_confidence']}")
        if escalate_node.get("on_unexplained", True) and unexplained:
            reasons.append(f"{len(unexplained)} provider(s) outside the profile limits that no question explains")
    return {"findings": findings, "items": [{k: v for k, v in i.items() if k != "node"} for i in items],
            "route": {"confidence": round(confidence, 3), "uncertain": uncertain, "unexplained": unexplained,
                      "escalate": bool(reasons), "reasons": reasons}}


def report_text(decision: dict, spec: dict) -> str:
    f, route = decision["findings"], decision["route"]
    lines = [f"Compiled workflow (spec {spec_hash(spec)}): {len(decision['items'])} provider-scheme questions asked, "
             f"{len(f)} reported at p >= {spec.get('report_threshold', 0.5)}."]
    for x in f:
        lines.append(f"- {x['name'] or x['provider']} ({x['provider']}): {x['scheme']}; {x['claims']} claims, "
                     f"${x['amount_at_risk']:,.2f} at risk; p={x['probability']} ({x['confidence']})")
    if not f:
        lines.append("- No provider reached the reporting threshold.")
    if route["uncertain"]:
        lines.append("Uncertain: " + ", ".join(f"{u['provider']} {u['scheme']} p={u['p']}" for u in route["uncertain"]))
    if route["unexplained"]:
        lines.append("Outside the profile limits, unexplained: " + ", ".join(route["unexplained"]))
    lines.append("```json\n" + json.dumps({"findings": [{k: v for k, v in x.items() if k != "probability"} for x in f]}) + "\n```")
    return "\n".join(lines)


# ---------------------------------------------------------------- research sub-agent

RESEARCH_SYSTEM = """You check one suspicion about one provider in a health plan's FHIR R4 claims
data (synthetic). You have fhir_search and fhir_read only. Read a few of the claims named in
the evidence (ExplanationOfBenefit) and, if it helps, the patient or practitioner. Make at
most {max_calls} tool calls; keep searches narrow (_count, _elements). Synthetic data has
noise: an isolated oddity is not a pattern.
{hints}
Then reply with only this JSON:
{{"answer": "yes" | "no", "p_yes": <probability the answer is yes>, "evidence": "<one or two sentences citing claim ids>"}}"""


def research_agent(node: dict, tools: list, model, hints: list[str]):
    """The research step: create_agent with FHIR reads only, behind PermissionMiddleware
    with the fraud policy (anything else is refused, as in the full agent)."""
    from langchain.agents import create_agent
    from agent import PermissionMiddleware, fraud_policy
    allowed = set(node.get("tools", ["fhir_search", "fhir_read"]))
    hint_text = ("Notes from earlier investigations:\n" + "\n".join(f"- {h}" for h in hints[:6])) if hints else ""
    return create_agent(model, [t for t in tools if t.name in allowed],
                        system_prompt=RESEARCH_SYSTEM.format(max_calls=node.get("max_calls", 6), hints=hint_text),
                        middleware=[PermissionMiddleware(fraud_policy(), agent_name="fraud-research")],
                        name="fraud-research")


def parse_answer(text: str) -> dict:
    match = re.search(r"\{.*\}", text or "", re.S)
    try:
        data = json.loads(match.group(0)) if match else {}
        p = float(data.get("p_yes"))
    except (json.JSONDecodeError, TypeError, ValueError):
        return {"answer": None, "p_yes": None, "evidence": (text or "")[:300]}
    return {"answer": data.get("answer"), "p_yes": min(1.0, max(0.0, p)), "evidence": str(data.get("evidence", ""))[:600]}


# ---------------------------------------------------------------- runner

def _preview(output: dict, limit: int = 1500) -> str:
    rows = sorted(output["providers"].items(), key=lambda kv: -kv[1]["score"])
    slim = {"summary": output["summary"], "providers": [
        {"provider": p, **{k: v for k, v in f.items() if k not in ("eobs", "examples")}} for p, f in rows[:8]]}
    return json.dumps(slim, default=str)[:limit]


async def run_workflow(question: str, emit: Emit, spec: dict | None = None, classifier: Classifier | None = None,
                       research_model="haiku", research_tools: list | None = None, claims=None,
                       finish: bool = True, announce: bool = True) -> dict:
    """Executes the spec. research_model: a MODELS name, a chat model object, or None for
    no research (then uncertain items stay uncertain). claims: callable returning
    (rows, names, deaths); default tools.claims. finish=False leaves out final/done (the
    router adds them)."""
    started = time.perf_counter()
    spec = spec or load_spec()
    classifier = classifier or make_classifier("auto")
    if claims is None:
        import tools as analytics
        claims = analytics.claims
    research_node = node_of(spec, "research")
    use_research = research_node is not None and research_model is not None
    if announce:
        await emit({"type": "run_start", "question": question, "model": f"workflow/{classifier.name}",
                    "model_option": "workflow",
                    "tools": [{"name": n["op"], "source": "analytics", "description": (workflow_ops.OPS[n["op"]].__doc__ or "").split("\n")[0]}
                              for n in nodes_of(spec, "code")]
                    + ([{"name": t, "source": "fhir-mcp", "description": "research sub-agent (FHIR reads)"}
                        for t in research_node.get("tools", ["fhir_search", "fhir_read"])] if use_research else [])})
    records: list[dict] = []

    async def record(rec: dict) -> None:
        records.append(rec)
        await emit({"type": "workflow_node", **rec})

    await record({"kind": "spec", "node": "spec", "hash": spec_hash(spec), "spec": spec, "classifier": classifier.name,
                  "research": use_research})
    rows, names, deaths = await asyncio.to_thread(claims)
    step, calls, model_calls = 0, 0, 0
    usage = {"input_tokens": 0, "output_tokens": 0}
    outputs: dict[str, dict] = {}

    for node in spec["nodes"]:
        if node["type"] == "code":
            step += 1
            calls += 1
            call_id = f"wf-{node['id']}"
            await emit({"type": "tool_call", "step": step, "call_id": call_id, "name": node["op"], "source": "analytics",
                        "args": node.get("params", {})})
            t0 = time.perf_counter()
            out = workflow_ops.OPS[node["op"]](rows, names, deaths, **node.get("params", {}))
            outputs[node["id"]] = out
            text = _preview(out)
            await emit({"type": "tool_result", "step": step, "call_id": call_id, "name": node["op"], "source": "analytics",
                        "ms": round((time.perf_counter() - t0) * 1000), "is_error": False, "size": len(text),
                        "preview": text, "truncated": False})
            await record({"kind": "code", "node": node["id"], "op": node["op"], "params": node.get("params", {}), "output": out})
        elif node["type"] == "question":
            step += 1
            candidates = sorted(((p, f) for p, f in outputs[node["input"]]["providers"].items()
                                 if f["score"] >= node.get("screen", float("-inf"))), key=lambda pf: -pf[1]["score"])
            candidates = candidates[:node.get("max_candidates", 10)]
            answers = await asyncio.gather(*(classifier.ask(node, f) for _, f in candidates))
            lines = []
            for (prov, f), ans in zip(candidates, answers):
                model_calls += ans["backend"] != "rules"
                for k in usage:
                    usage[k] += ans.get("usage", {}).get(k, 0)
                lines.append(f"{f.get('name') or prov}: p(yes)={ans['probabilities']['yes']:.2f}")
                await record({"kind": "question", "node": node["id"], "scheme": node["scheme"], "provider": prov,
                              "name": f.get("name", ""), "evidence": f, **ans})
            await emit({"type": "text", "step": step, "text": f"Question [{node['scheme']}] {node['question']} "
                        f"({classifier.name}, {len(candidates)} provider(s)): " + ("; ".join(lines) or "no provider flagged")})
        elif node["type"] == "research" and use_research:
            lo, hi = node["band"]
            pending = [r for r in records if r.get("kind") == "question" and lo <= r["probabilities"]["yes"] < hi]
            pending = sorted(pending, key=lambda r: abs(r["probabilities"]["yes"] - 0.5))[:node.get("max_items", 4)]
            if not pending:
                continue
            from agent import MODELS, capped, chat_model, fhir_client, stream_agent
            if research_tools is None:
                research_tools = [capped(t, 15_000) for t in await fhir_client().get_tools()
                                  if t.name in {"fhir_search", "fhir_read"}]
            model = chat_model(research_model) if isinstance(research_model, str) else research_model
            qnodes = {n["id"]: n for n in nodes_of(spec, "question")}
            for rec in pending:
                q = qnodes[rec["node"]]
                await emit({"type": "text", "step": step + 1, "text": f"Research: {rec['name'] or rec['provider']} "
                            f"[{rec['scheme']}] is uncertain (p={rec['probabilities']['yes']:.2f}); checking the raw records."})
                app = research_agent(node, research_tools, model, spec.get("hints", []))
                prompt = (f"Provider {rec['provider']} ({rec['name']}). Question: {q['question']}\n"
                          f"Evidence from the claims analytics: {json.dumps(rec['evidence'], default=str)[:3000]}")
                run = await stream_agent(app, prompt, emit, step, recursion_limit=node.get("recursion_limit", 16))
                step += run["model_steps"]
                calls += run["tool_calls"]
                model_calls += run["model_steps"]
                for k in usage:
                    usage[k] += run["usage"][k]
                ans = parse_answer(run["final_text"])
                await record({"kind": "research", "node": node["id"], "scheme": rec["scheme"], "provider": rec["provider"],
                              "p_question": rec["probabilities"]["yes"], "p_yes": ans["p_yes"], "answer": ans["answer"],
                              "evidence_text": ans["evidence"], "tool_calls": run["tool_calls"], "usage": run["usage"],
                              "model": getattr(model, "model", None) or getattr(model, "model_name", None)
                              or (MODELS[research_model]["model"] if isinstance(research_model, str) else "scripted")})

    decision = decide(spec, records)
    await record({"kind": "route", "node": (node_of(spec, "escalate") or {}).get("id", "route"), **decision["route"]})
    summary = {"findings": decision["findings"], "route": decision["route"], "tool_calls": calls,
               "model_steps": model_calls, "usage": usage, "seconds": round(time.perf_counter() - started, 1),
               "report": report_text(decision, spec), "steps": step}
    if finish:
        await emit({"type": "final", "text": summary["report"], "findings": decision["findings"]})
        await emit({"type": "done", "tool_calls": calls, "model_steps": model_calls, "seconds": summary["seconds"],
                    "usage": usage, "mode": "workflow", "escalated": False})
    return summary


def handoff_question(question: str, wf: dict) -> str:
    """The question for the full agent when the router escalates: the original question
    plus what the workflow already established and where it was unsure."""
    route = wf["route"]
    lines = [question, "", "A compiled screening workflow ran first. Treat its output as leads to verify, not conclusions."]
    if wf["findings"]:
        lines.append("Its findings: " + "; ".join(f"{f['provider']} {f['scheme']} (p={f['probability']})" for f in wf["findings"]))
    if route["uncertain"]:
        lines.append("Uncertain: " + "; ".join(f"{u['provider']} {u['scheme']} p={u['p']}" for u in route["uncertain"]))
    if route["unexplained"]:
        lines.append("Billing profile outside normal limits, with no scheme the workflow checks: " + ", ".join(route["unexplained"]))
    lines.append("Your report replaces the workflow's; include its findings only if you confirm them.")
    return "\n".join(lines)


async def run_routed(question: str, emit: Emit, spec: dict | None = None, classifier: Classifier | None = None,
                     research_model="haiku", agent_model: str = "claude", escalate: bool = True, escalate_fn=None,
                     **kwargs) -> dict:
    """Workflow first; the full agent only when the escalate node says so. escalate=False
    records the decision but keeps the workflow's answer (offline evaluation).
    escalate_fn(question, emit, step0) replaces agent.investigate (tests)."""
    started = time.perf_counter()
    wf = await run_workflow(question, emit, spec, classifier, research_model, finish=False, **kwargs)
    route = wf["route"]
    if not route["escalate"] or not escalate:
        if route["escalate"]:
            await emit({"type": "text", "step": wf["steps"] + 1,
                        "text": "Router: would escalate (" + "; ".join(route["reasons"]) + "), but escalation is off."})
        await emit({"type": "final", "text": wf["report"], "findings": wf["findings"]})
        await emit({"type": "done", "tool_calls": wf["tool_calls"], "model_steps": wf["model_steps"],
                    "seconds": round(time.perf_counter() - started, 1), "usage": wf["usage"], "mode": "routed",
                    "escalated": False, "would_escalate": route["escalate"]})
        return {**wf, "escalated": False}
    await emit({"type": "text", "step": wf["steps"] + 1, "text": "Router: escalating to the full agent ("
                + "; ".join(route["reasons"]) + ")."})
    agent_done: dict = {}

    async def relay(event: dict) -> None:  # one run_start / done per run: merge the agent's into the workflow's
        if event["type"] == "done":
            agent_done.update(event)
        elif event["type"] != "run_start":
            await emit(event)

    if escalate_fn is None:
        from agent import investigate

        async def escalate_fn(q, e, step0):
            return await investigate(q, e, agent_model, announce=False, step0=step0)
    await escalate_fn(handoff_question(question, wf), relay, wf["steps"] + 1)
    usage = {k: wf["usage"][k] + (agent_done.get("usage") or {}).get(k, 0) for k in wf["usage"]}
    await emit({"type": "done", "tool_calls": wf["tool_calls"] + agent_done.get("tool_calls", 0),
                "model_steps": wf["model_steps"] + agent_done.get("model_steps", 0),
                "seconds": round(time.perf_counter() - started, 1), "usage": usage, "mode": "routed", "escalated": True,
                "workflow_usage": wf["usage"], "agent_usage": agent_done.get("usage")})
    return {**wf, "escalated": True}


# ---------------------------------------------------------------- replay

def records_of(trace: dict) -> list[dict]:
    return [e for e in trace["events"] if e.get("type") == "workflow_node"]


async def _reclassify(spec: dict, records: list[dict]) -> list[dict]:
    """Recomputes question probabilities with the rules classifier and `spec`'s priors."""
    nodes = {n["id"]: n for n in nodes_of(spec, "question")}
    rules, out = RulesClassifier(), []
    for rec in records:
        if rec.get("kind") == "question" and rec["node"] in nodes:
            rec = {**rec, **await rules.ask(nodes[rec["node"]], rec["evidence"])}
        out.append(rec)
    return out


def rescore(trace: dict, findings: list[dict]) -> dict | None:
    """Scores findings against the answer key saved (as a score event) in the trace."""
    import seed_fraud
    from scoring import score
    saved = next((e for e in trace["events"] if e.get("type") == "score"), None)
    if not saved:
        return None
    key = {"level": saved.get("level"), "guilty": {
        p["provider"]: {"name": p["name"], "schemes": {s: {"keywords": seed_fraud.KEYWORDS.get(s, [])} for s in p["schemes"]}}
        for p in saved["providers"]}}
    return score(findings, key)


def replay(trace: dict, spec: dict | None = None, reclassify: bool = False) -> dict:
    """Decides a saved workflow run again from its records: no model calls, no data access.
    spec: another spec's thresholds (default: the spec the run used). reclassify: also
    recompute question probabilities with the rules classifier and that spec's priors."""
    records = records_of(trace)
    used = next((r for r in records if r.get("kind") == "spec"), None)
    if used is None:
        raise SpecError("not a workflow trace: no workflow_node spec record")
    spec = validate_spec(spec or used["spec"])
    if reclassify:
        records = asyncio.run(_reclassify(spec, records))
    decision = decide(spec, records)
    return {**decision, "spec": spec_hash(spec), "original_spec": used["hash"], "score": rescore(trace, decision["findings"])}


# ---------------------------------------------------------------- CLI

async def _cli_run(args) -> None:
    from agent import QUESTION

    async def emit(event: dict) -> None:
        if event["type"] == "text":
            print(f"  {event['text'][:300]}")
        elif event["type"] == "tool_call":
            print(f"  [{event['step']}] {event['name']} {json.dumps(event['args'])[:120]}")
        elif event["type"] == "final":
            print(event["text"])
        elif event["type"] == "done":
            print({k: v for k, v in event.items() if k != "type"})

    spec = load_spec(args.spec)
    research = None if args.no_research else args.research_model
    if args.command == "run":
        await run_workflow(QUESTION, emit, spec, make_classifier(args.questions), research)
    else:
        await run_routed(QUESTION, emit, spec, make_classifier(args.questions), research, args.model,
                         escalate=not args.no_escalate)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("run", "routed"):
        p = sub.add_parser(name)
        p.add_argument("--spec", default=str(DEFAULT_SPEC))
        p.add_argument("--questions", default="auto", choices=["auto", "jev", "llm", "rules"])
        p.add_argument("--research-model", default="haiku", help="MODELS name for the research sub-agent")
        p.add_argument("--no-research", action="store_true", help="no research sub-agent (no model calls with --questions rules)")
        if name == "routed":
            p.add_argument("--model", default="claude", help="MODELS name for the full agent")
            p.add_argument("--no-escalate", action="store_true", help="record the route but never run the full agent")
    r = sub.add_parser("replay")
    r.add_argument("trace")
    r.add_argument("--spec", default=None, help="decide with this spec's thresholds instead of the one the run used")
    r.add_argument("--reclassify", action="store_true", help="recompute probabilities with the rules classifier")
    args = parser.parse_args()
    if args.command == "replay":
        trace = json.loads(Path(args.trace).read_text())
        out = replay(trace, load_spec(args.spec) if args.spec else None, args.reclassify)
        print(json.dumps({k: out[k] for k in ("spec", "original_spec", "route", "findings", "score")}, indent=1, default=str))
    else:
        asyncio.run(_cli_run(args))


if __name__ == "__main__":
    sys.exit(main())
