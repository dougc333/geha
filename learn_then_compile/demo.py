"""Learn-then-compile: turn graded agent runs into a cheap workflow, route the rest.

The pattern behind hapi/fraud's workflow mode (PR #69), reduced to one offline file.

  1. LEARN    run an (expensive) agent on training cases; record each run's tool calls
              and grade its verdict against the answer key
  2. COMPILE  from the correct runs, keep the checks that decided verdicts and learn a
              threshold for each, plus the normal range of a cheap "profile" of each case
  3. RUN      the compiled workflow runs the checks as plain code (no model). If a case
              is clearly guilty or clearly clean it answers; if a value sits between the
              learned thresholds, or the profile looks unlike anything seen in training,
              it escalates to the agent (the router)
  4. COMPARE  agent-only vs workflow-only vs routed on HELD-OUT cases, including a
              fraud scheme that never appeared in training

The domain is toy provider-fraud data and the agent is simulated (it calls tools in a
random order, judges with some noise, and is charged tokens per call), so the demo runs
offline with no API key. The point is the mechanics and the evaluation, not the agent.

Run:  python learn_then_compile/demo.py [--seed N]
"""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass, field

# Sonnet $ per million tokens (no prompt caching, to keep the arithmetic visible).
PRICE_IN, PRICE_OUT = 3.00, 15.00

# Known schemes: which tool reveals each one, and the agent's own judgment threshold.
CHECKS = {
    "check_duplicates": ("duplicate_billing", "dup_rate", 0.10),
    "check_peer_cost": ("upcoding", "cost_ratio", 1.50),
    "check_after_death": ("billing_after_death", "after_death", 3),
}
PROFILE = ("claims_per_day", "weekend_share")   # cheap stats code can compute for any case


@dataclass
class Case:
    id: str
    features: dict
    scheme: str | None          # answer key: None means innocent


@dataclass
class Trace:
    case_id: str
    calls: list = field(default_factory=list)   # (tool, value)
    verdict: str | None = None                  # scheme name, or None for innocent
    tokens_in: int = 0
    tokens_out: int = 0


# ------------------------------------------------------------------- data --

def make_cases(n: int, seed: int, schemes: list[str], prefix: str) -> list[Case]:
    rng = random.Random(seed)
    cases = []
    for i in range(n):
        f = {
            "dup_rate": rng.uniform(0.0, 0.04),
            "cost_ratio": rng.gauss(1.0, 0.12),
            "after_death": 1 if rng.random() < 0.05 else 0,   # data noise, like Synthea dates
            "claims_per_day": rng.gauss(20, 4),
            "weekend_share": rng.uniform(0.05, 0.20),
        }
        scheme = schemes[i % len(schemes)] if rng.random() < 0.35 else None
        if scheme == "duplicate_billing":
            f["dup_rate"] = rng.uniform(0.12, 0.30)
        elif scheme == "upcoding":
            f["cost_ratio"] = rng.uniform(1.6, 2.5)
        elif scheme == "billing_after_death":
            f["after_death"] = rng.randint(3, 10)
        elif scheme == "phantom_weekend_visits":        # novel: no check tool covers it
            f["weekend_share"] = rng.uniform(0.45, 0.70)
            f["claims_per_day"] += rng.uniform(6, 12)
        cases.append(Case(f"{prefix}{i:02d}", f, scheme))
    return cases


# ------------------------------------------------------------------ agent --

def run_agent(case: Case, rng: random.Random) -> Trace:
    """Simulated ReAct agent: tries the checks in random order, may research, then decides."""
    t = Trace(case.id)

    def call(tool: str, value, extra_in: int = 0):
        t.calls.append((tool, value))
        t.tokens_in += 3000 + 2500 * len(t.calls) + extra_in   # the prompt grows every call
        t.tokens_out += 300

    tools = list(CHECKS)
    rng.shuffle(tools)
    for tool in tools:
        scheme, feat, threshold = CHECKS[tool]
        value = case.features[feat]
        call(tool, value)
        if value > threshold and rng.random() > 0.05:         # 5%: misreads a real signal
            t.verdict = scheme
            return t
    if rng.random() < 0.7:                                     # nothing found: dig deeper
        call("research", case.features["weekend_share"], extra_in=20000)
        if case.features["weekend_share"] > 0.4:
            t.verdict = "phantom_weekend_visits"
            return t
    if rng.random() < 0.03:                                    # 3%: false accusation
        t.verdict = "upcoding"
    return t


def agent_cost(trace: Trace) -> float:
    return (trace.tokens_in * PRICE_IN + trace.tokens_out * PRICE_OUT) / 1e6


# -------------------------------------------------------------- compiler --

def compile_workflow(cases: list[Case], traces: list[Trace]) -> dict:
    """Keep checks that decided correct verdicts; learn thresholds and the normal profile."""
    key = {c.id: c for c in cases}
    correct = [t for t in traces if t.verdict == key[t.case_id].scheme]
    steps = []
    for tool, (scheme, feat, _) in CHECKS.items():
        decided = sum(1 for t in correct if t.verdict == scheme and t.calls[-1][0] == tool)
        if not decided:
            continue
        guilty = [v for t in correct if t.verdict == scheme for tl, v in t.calls if tl == tool]
        clean = [v for t in correct if t.verdict is None for tl, v in t.calls if tl == tool]
        # Between the highest clean value and the lowest guilty value we can't tell: escalate.
        steps.append({"tool": tool, "scheme": scheme, "feature": feat, "decided": decided,
                      "clean_below": max(clean), "guilty_above": min(guilty)})
    steps.sort(key=lambda s: -s["decided"])
    clean_cases = [key[t.case_id] for t in correct if t.verdict is None]
    profile = {}
    for feat in PROFILE:
        values = [c.features[feat] for c in clean_cases]
        slack = 0.1 * (max(values) - min(values))
        profile[feat] = (min(values) - slack, max(values) + slack)
    uncovered = sorted({t.verdict for t in correct if t.verdict} - {s["scheme"] for s in steps})
    return {"steps": steps, "profile": profile, "uncovered": uncovered, "learned_from": len(correct)}


def run_workflow(spec: dict, case: Case) -> tuple[str | None, bool, str]:
    """Returns (verdict, escalate, reason). Plain code: no model calls."""
    for s in spec["steps"]:
        v = case.features[s["feature"]]
        if v >= s["guilty_above"]:
            return s["scheme"], False, f"{s['tool']}={v:.2f}"
        if v > s["clean_below"]:
            return None, True, f"{s['tool']}={v:.2f} between learned limits"
    for feat, (lo, hi) in spec["profile"].items():
        v = case.features[feat]
        if not lo <= v <= hi:
            return None, True, f"{feat}={v:.2f} outside the normal profile"
    return None, False, "all checks clean"


# -------------------------------------------------------------- evaluate --

def score(cases: list[Case], verdicts: dict) -> dict:
    guilty = [c for c in cases if c.scheme]
    return {
        "found": sum(1 for c in guilty if verdicts[c.id] == c.scheme),
        "guilty": len(guilty),
        "false_acc": sum(1 for c in cases if not c.scheme and verdicts[c.id]),
    }


def evaluate(name: str, cases: list[Case], spec: dict, seed: int) -> None:
    rng = random.Random(seed)
    agent = {c.id: run_agent(c, rng) for c in cases}
    agent_verdicts = {cid: t.verdict for cid, t in agent.items()}
    agent_usd = sum(agent_cost(t) for t in agent.values())

    wf_verdicts, routed_verdicts, escalated, routed_usd = {}, {}, [], 0.0
    for c in cases:
        verdict, escalate, reason = run_workflow(spec, c)
        wf_verdicts[c.id] = verdict
        if escalate:
            escalated.append((c, reason))
            routed_verdicts[c.id] = agent[c.id].verdict      # the agent handles it
            routed_usd += agent_cost(agent[c.id])
        else:
            routed_verdicts[c.id] = verdict

    print(f"\n{name}  ({len(cases)} providers, schemes: "
          f"{', '.join(sorted({c.scheme for c in cases if c.scheme}))})")
    print(f"  {'mode':<14}{'guilty found':>13}{'false acc.':>11}{'agent runs':>11}{'cost $':>9}")
    for mode, verdicts, runs, usd in (("agent only", agent_verdicts, len(cases), agent_usd),
                                      ("workflow only", wf_verdicts, 0, 0.0),
                                      ("routed", routed_verdicts, len(escalated), routed_usd)):
        s = score(cases, verdicts)
        print(f"  {mode:<14}{s['found']:>8}/{s['guilty']:<4}{s['false_acc']:>11}{runs:>11}{usd:>9.2f}")
    for c, reason in escalated:
        print(f"    escalated {c.id} ({c.scheme or 'innocent'}): {reason}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()
    known = ["duplicate_billing", "upcoding", "billing_after_death"]

    # 1. LEARN: the agent investigates training cases; every run is graded.
    train = make_cases(80, args.seed, known, "T")
    rng = random.Random(args.seed + 100)
    traces = [run_agent(c, rng) for c in train]
    right = sum(t.verdict == c.scheme for t, c in zip(traces, train))
    print(f"LEARN    {len(traces)} agent runs on training cases, {right} graded correct, "
          f"${sum(agent_cost(t) for t in traces):.2f}")

    # 2. COMPILE
    spec = compile_workflow(train, traces)
    print(f"COMPILE  from {spec['learned_from']} correct runs:")
    for s in spec["steps"]:
        print(f"           {s['tool']:<18} guilty >= {s['guilty_above']:.2f}, clean <= {s['clean_below']:.2f}"
              f"  (decided {s['decided']} runs)")
    for feat, (lo, hi) in spec["profile"].items():
        print(f"           profile {feat:<15} normal {lo:.2f} .. {hi:.2f}")

    # 3-4. RUN + COMPARE on held-out cases (different seeds, never seen by the compiler).
    evaluate("HELD-OUT, known schemes", make_cases(60, args.seed + 1, known, "A"), spec, args.seed + 201)
    evaluate("HELD-OUT, plus a NEW scheme", make_cases(60, args.seed + 2, known + ["phantom_weekend_visits"], "B"),
             spec, args.seed + 202)


if __name__ == "__main__":
    main()
