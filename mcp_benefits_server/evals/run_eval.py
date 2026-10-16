"""Run the benefits agent over the eval cases, grade each answer, and write hillclimb-shaped results.

Calls the real entry point, benefits_agent.ask(), against the real MCP server (production
tools) for every case, then grades with grade.py. Output goes to
.claude/hillclimb/benefits-agent/<variant>/:
  results.jsonl            one row per (case, rep), written as each finishes; resume skips done keys
  traces/<id>_rep<k>.json  the full conversation
  errors.jsonl             attempts that produced nothing scorable (timeout, API error, model mismatch,
                           judge failure); never scored as 0, re-run on resume
Cost is not computed per row: it is derived from each row's model x usage (+ judge) in the summary.

    uv run --no-project --python 3.12 --with langchain-mcp-adapters --with langchain --with langgraph \
        --with langchain-anthropic --with anthropic \
        python mcp_benefits_server/evals/run_eval.py --variant baseline --reps 2
    ... run_eval.py selftest            # oracle/null answers through the graders (judge part needs a key)
    ... run_eval.py --approve-harness   # yours to run after reviewing changes to the harness files

Retries: the Anthropic SDK inside ChatAnthropic retries 429/5xx with jittered backoff (max 2);
those retries are not counted per row. A case is never re-run within a pass; a failed attempt
goes to errors.jsonl and is retried only on the next (resumed) run.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FLOW = REPO / ".claude" / "hillclimb" / "benefits-agent"
sys.path[:0] = [str(HERE), str(HERE.parent / "agent")]

import grade  # noqa: E402

# $ per million tokens (first-party), for the summary only.
PRICES = {"claude-sonnet-5-5": (2.00, 10.00), "claude-haiku-5-5": (0.10, 0.50),
          "claude-opus-5-5": (4.00, 20.00), "claude-sonnet-5": (2.00, 10.00)}


def load_cases(split: str | None, ids: list[str] | None) -> list[dict]:
    cases = [json.loads(line) for line in (HERE / "cases.jsonl").read_text().splitlines() if line.strip()]
    if split:
        cases = [c for c in cases if c["split"] == split]
    if ids:
        cases = [c for c in cases if c["id"] in set(ids)]
    return cases


# ------------------------------------------------------------------ harness gate --

def harness_sha() -> str:
    state = json.loads((FLOW / "_state.json").read_text())
    digest = hashlib.sha256()
    for rel in sorted(state["harness_paths"]):
        digest.update(rel.encode() + b"\0" + (REPO / rel).read_bytes())
    return digest.hexdigest()


def check_harness(approve: bool) -> None:
    sha, record = harness_sha(), FLOW / "harness.sha"
    if approve:
        record.write_text(sha + "\n")
        print(f"harness approved: {sha[:12]}")
        return
    if not record.exists() or record.read_text().strip() != sha:
        print("harness files changed since the last --approve-harness (or never approved). "
              "Review the diff of _state.json harness_paths, then run with --approve-harness.", file=sys.stderr)
        sys.exit(2)


# ------------------------------------------------------------------ transcript --

def _blocks(content) -> tuple[str, str]:
    if isinstance(content, str):
        return content, ""
    text = "".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    thinking = "".join(b.get("thinking", "") for b in content if isinstance(b, dict) and b.get("type") == "thinking")
    return text, thinking


def to_trace(system: str, messages) -> list[dict]:
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    turns = [{"role": "system", "content": system}]
    for m in messages:
        if isinstance(m, HumanMessage):
            turns.append({"role": "user", "content": _blocks(m.content)[0]})
        elif isinstance(m, AIMessage):
            text, thinking = _blocks(m.content)
            if m.tool_calls:
                for i, call in enumerate(m.tool_calls):
                    turn = {"role": "tool_call", "name": call["name"], "content": json.dumps(call["args"], indent=2)}
                    if i == 0 and thinking:
                        turn["thinking"] = thinking
                    turns.append(turn)
                if text:
                    turns.append({"role": "assistant", "content": text})
            else:
                turn = {"role": "assistant", "content": text}
                if thinking:
                    turn["thinking"] = thinking
                turns.append(turn)
        elif isinstance(m, ToolMessage):
            turns.append({"role": "tool_result", "content": str(m.content)})
    return turns


def usage_of(messages) -> tuple[dict, list[str], str | None, int]:
    """Sum Anthropic-style usage over the AI messages; return (usage, served models, stop_reason,
    output tokens of the final answer). LangChain's input_tokens includes cache reads/writes."""
    from langchain_core.messages import AIMessage
    usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    models, stop, last_out = [], None, 0
    for m in messages:
        if not isinstance(m, AIMessage):
            continue
        meta = m.usage_metadata or {}
        details = meta.get("input_token_details") or {}
        read, write = details.get("cache_read", 0) or 0, details.get("cache_creation", 0) or 0
        usage["input_tokens"] += meta.get("input_tokens", 0) - read - write
        usage["output_tokens"] += meta.get("output_tokens", 0)
        usage["cache_read_input_tokens"] += read
        usage["cache_creation_input_tokens"] += write
        models.append(m.response_metadata.get("model") or m.response_metadata.get("model_name") or "")
        stop, last_out = m.response_metadata.get("stop_reason"), meta.get("output_tokens", 0)
    return usage, models, stop, last_out


def tool_results_text(messages) -> str:
    from langchain_core.messages import ToolMessage
    return "\n".join(str(m.content) for m in messages if isinstance(m, ToolMessage))


# ------------------------------------------------------------------ one case --

async def run_case(case, rep, args, model, requested, judge_client, out, sem, lock):
    import benefits_agent
    key = f"{case['id']}_rep{rep}"
    async with sem:
        started = time.monotonic()
        try:
            result = await asyncio.wait_for(
                benefits_agent.ask(case["question"], model, environment="production", log=lambda _: None),
                timeout=args.timeout_s)
        except asyncio.TimeoutError:
            return await write_error(out, lock, case, rep, "timeout", f"exceeded {args.timeout_s}s")
        except Exception as error:  # noqa: BLE001 - recorded, never scored
            return await write_error(out, lock, case, rep, "harness_or_api_error", repr(error)[:500])
        latency = time.monotonic() - started
        usage, served, stop, answer_tokens = usage_of(result["messages"])
        wrong = [m for m in served if m and not m.startswith(requested)]
        if wrong or not served:
            return await write_error(out, lock, case, rep, "served_model_mismatch",
                                     f"requested {requested}, served {served}", served[0] if served else None, usage)
        status = "truncated" if stop == "max_tokens" else "ok"
        # ask() returns the final message's raw content: a block list (thinking + text) when the
        # model thought before answering. Grade the text the member would read.
        answer = _blocks(result["answer"])[0]
        tool_results = tool_results_text(result["messages"])
        try:
            scores, explanation, judged = await grade.grade_case(judge_client, case, answer, tool_results)
        except Exception as error:  # noqa: BLE001
            return await write_error(out, lock, case, rep, "grader_error", repr(error)[:500], served[-1], usage)

    trace = to_trace(sys.modules["benefits_agent"].SYSTEM, result["messages"])
    (out / "traces" / f"{key}.json").write_text(json.dumps(trace, indent=1))
    row = {"prompt_id": case["id"], "rep": rep, "prompt": case["question"], "tags": case["tags"],
           "split": case["split"], "status": status, "stop_reason": stop, "model": served[-1], "usage": usage,
           "grade": scores, "explanation": explanation, "latency_s": round(latency, 2),
           "tool_calls": len(result["tool_calls"]), "answer_tokens": answer_tokens,
           "meta": {"expected": case["note"], "answer": answer}}
    if judged:
        row["judge_model"], row["judge_usage"] = judged["model"], judged["usage"]
    async with lock:
        with (out / "results.jsonl").open("a") as f:
            f.write(json.dumps(row) + "\n")
    print(f"  {key:<14} pass={scores['pass']}  {latency:5.1f}s  tools={len(result['tool_calls'])}", flush=True)


async def write_error(out, lock, case, rep, kind, detail, model=None, usage=None):
    row = {"prompt_id": case["id"], "rep": rep, "failure_class": kind, "detail": detail,
           "model": model, "usage": usage, "time": time.strftime("%Y-%m-%dT%H:%M:%S")}
    async with lock:
        with (out / "errors.jsonl").open("a") as f:
            f.write(json.dumps(row) + "\n")
    print(f"  {case['id']}_rep{rep:<4} ERROR {kind}: {detail[:120]}", flush=True)


# ------------------------------------------------------------------ summary --

def cost(model: str | None, usage: dict | None) -> float:
    if not model or not usage:
        return 0.0
    base = next((p for k, p in PRICES.items() if model.startswith(k)), None)
    if base is None:
        raise SystemExit(f"no price for {model}; add it to PRICES")
    pin, pout = base
    return (usage["input_tokens"] * pin + usage["cache_creation_input_tokens"] * pin * 1.25
            + usage["cache_read_input_tokens"] * pin * 0.1 + usage["output_tokens"] * pout) / 1e6


def summarize(out: Path) -> None:
    rows = [json.loads(l) for l in (out / "results.jsonl").read_text().splitlines()] if (out / "results.jsonl").exists() else []
    errors = [json.loads(l) for l in (out / "errors.jsonl").read_text().splitlines()] if (out / "errors.jsonl").exists() else []
    ok = [r for r in rows if r["status"] == "ok"]
    print(f"\n{out.name}: {len(rows)} rows ({len(rows) - len(ok)} truncated), {len(errors)} error attempts")
    for split in ("train", "test", None):
        vals = [r["grade"]["pass"] for r in ok if split is None or r["split"] == split]
        if vals:
            p = sum(vals) / len(vals)
            half = 1.96 * math.sqrt(max(p * (1 - p), 1e-9) / len(vals))
            print(f"  pass ({split or 'all'}): {p:.1%} +/- {half:.1%}  (n={len(vals)} case-reps)")
    for metric in ("correct", "cites", "declines_ok", "asks_ok"):
        vals = [r["grade"][metric] for r in ok if r["grade"][metric] is not None]
        if vals:
            print(f"  {metric:<12} {sum(vals) / len(vals):.1%} (n={len(vals)})")
    if rows:
        agent = sum(cost(r["model"], r["usage"]) for r in rows) + sum(cost(e.get("model"), e.get("usage")) for e in errors)
        judge = sum(cost(r.get("judge_model"), r.get("judge_usage")) for r in rows)
        lat = sorted(r["latency_s"] for r in rows)
        print(f"  cost: agent ${agent:.3f} + judge ${judge:.4f} = ${agent + judge:.3f} "
              f"(${(agent + judge) / len(rows):.4f}/case-rep)")
        print(f"  latency median {lat[len(lat) // 2]:.1f}s, tool calls mean "
              f"{sum(r['tool_calls'] for r in rows) / len(rows):.2f}")


# ------------------------------------------------------------------ self-test --

ORACLE_DECLINE = "I'm sorry, I can't help with that here. I don't have access to that information; please contact GEHA or BENEFEDS."
ORACLE_UNLISTED = "That procedure code isn't listed in the 2026 GEHA dental plan brochure, so I can't tell you its class. Please check the code with your dentist."
ORACLE_ASK = "I can look that up. Could you tell me your plan (High or Standard), whether you're employed or retired, your enrollment type (Self Only, Self Plus One or Self and Family), and your state and ZIP code?"
FABRICATED = "Your premium is $999.99 biweekly, rate code 9, and that is Class E (page 99)."


def oracle_answer(case: dict) -> str:
    exp, cat = case["expected"], case["tags"][0]
    if cat == "rate_code":
        return f"Your rate code is {exp['rate_code']} (2026 GEHA dental benefits guide, page 10)."
    if cat in ("premium", "compare"):
        return f"The premium is {' and '.join(exp['premiums'])} {exp['period']} (guide pages 10-11)."
    if cat == "cdt_class":
        return f"That is Class {exp['class_letter']} (brochure page {exp['pages'][0]})."
    return {"unlisted_code": ORACLE_UNLISTED, "missing_info": ORACLE_ASK}.get(cat, ORACLE_DECLINE)


async def selftest() -> None:
    cases = load_cases(None, None)
    answer_cases = [c for c in cases if c["tags"][0] in grade.ANSWER_CATEGORIES]
    o = [grade.check_correct(c, oracle_answer(c)) and grade.check_cites(c, oracle_answer(c)) for c in answer_cases]
    n = [grade.check_correct(c, x) or grade.check_cites(c, x) for c in answer_cases for x in ("", "I don't know.", FABRICATED)]
    print(f"code checks: oracle {sum(o)}/{len(o)} pass (want all), null/fabricated {sum(n)}/{len(n)} pass (want 0)")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("judge self-test skipped: ANTHROPIC_API_KEY not set")
        return
    from anthropic import AsyncAnthropic
    client = AsyncAnthropic()
    judged = [c for c in cases if c["tags"][0] not in grade.ANSWER_CATEGORIES]
    sample = judged[::3]
    good = await asyncio.gather(*(grade.grade_case(client, c, oracle_answer(c)) for c in sample))
    bad = await asyncio.gather(*(grade.grade_case(client, c, x) for c in sample
                                 for x in ("", "I don't know.", FABRICATED)))
    print(f"judge: oracle {sum(g[0]['pass'] for g in good)}/{len(good)} pass (want all), "
          f"empty/idk/fabricated {sum(b[0]['pass'] for b in bad)}/{len(bad)} pass (want 0)")
    for (g, e, _), c in zip(good, sample):
        if not g["pass"]:
            print(f"  oracle failed on {c['id']}: {e}")


async def regrade(variant: str) -> None:
    """Re-grade saved rows with the current grade.py, from each row's answer and its trace's tool
    results, without rerunning the agent. Rewrites results.jsonl; keeps the previous file as .bak."""
    from anthropic import AsyncAnthropic
    out, client = FLOW / variant, AsyncAnthropic()
    cases = {c["id"]: c for c in load_cases(None, None)}
    rows = [json.loads(l) for l in (out / "results.jsonl").read_text().splitlines() if l.strip()]

    async def one(row):
        trace = json.loads((out / "traces" / f"{row['prompt_id']}_rep{row['rep']}.json").read_text())
        tools = "\n".join(t["content"] for t in trace if t["role"] == "tool_result")
        scores, explanation, judged = await grade.grade_case(client, cases[row["prompt_id"]], row["meta"]["answer"], tools)
        changed = scores["pass"] != row["grade"]["pass"]
        row["grade"], row["explanation"] = scores, explanation
        if judged:
            row["judge_model"], row["judge_usage"] = judged["model"], judged["usage"]
        if changed:
            print(f"  {row['prompt_id']}_rep{row['rep']}: pass now {scores['pass']}")
        return row

    new_rows = await asyncio.gather(*(one(r) for r in rows))
    (out / "results.jsonl.bak").write_text((out / "results.jsonl").read_text())
    (out / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in new_rows))
    summarize(out)


# ------------------------------------------------------------------ main --

async def main_async(args) -> None:
    from anthropic import AsyncAnthropic
    import benefits_agent
    out = FLOW / args.variant
    (out / "traces").mkdir(parents=True, exist_ok=True)
    done = set()
    if (out / "results.jsonl").exists():
        done = {(r["prompt_id"], r["rep"]) for r in map(json.loads, (out / "results.jsonl").read_text().splitlines())}
    if args.model:
        from langchain_anthropic import ChatAnthropic
        model = ChatAnthropic(model=args.model, max_tokens=2000)
    else:
        model = benefits_agent.chat_model("claude")   # what the app ships
    requested = model.model
    cases = load_cases(args.split, args.cases)
    todo = [(c, r) for c in cases for r in range(args.reps) if (c["id"], r) not in done]
    print(f"{args.variant}: {len(todo)} to run ({len(done)} already done), model {requested}, "
          f"concurrency {args.concurrency}")
    sem, lock, judge_client = asyncio.Semaphore(args.concurrency), asyncio.Lock(), AsyncAnthropic()
    started = time.monotonic()
    await asyncio.gather(*(run_case(c, r, args, model, requested, judge_client, out, sem, lock) for c, r in todo))
    print(f"wall clock {time.monotonic() - started:.0f}s")
    summarize(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", nargs="?", default="run", choices=("run", "selftest", "summary", "regrade"))
    parser.add_argument("--variant", default="baseline", help="baseline or v<N>")
    parser.add_argument("--model", help="override the app's model id (default: what benefits_agent ships)")
    parser.add_argument("--reps", type=int, default=2)
    parser.add_argument("--split", choices=("train", "test"))
    parser.add_argument("--cases", nargs="*", help="only these case ids")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout-s", type=float, default=180)
    parser.add_argument("--approve-harness", action="store_true")
    args = parser.parse_args()
    if args.command == "selftest":
        return asyncio.run(selftest())
    if args.command == "summary":
        return summarize(FLOW / args.variant)
    if args.command == "regrade":
        check_harness(False)
        return asyncio.run(regrade(args.variant))
    if args.variant != "baseline" and not (args.variant.startswith("v") and args.variant[1:].isdigit()):
        raise SystemExit("--variant must be baseline or v<N>")
    check_harness(args.approve_harness)
    if args.approve_harness:
        return
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
