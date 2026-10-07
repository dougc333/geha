"""Evaluate the chat safety guard: labelled cases plus the 62 benchmark questions that must pass.

    PYTHONPATH=aws_rag/query python aws_rag/evals/run_guard_eval.py          # from the repo root

Reports misses (unsafe text let through), false blocks (safe text refused) and wrong
categories. Backends other than the deterministic patterns plug in through BACKENDS.
Exits non-zero if any case fails, so it can gate CI.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "query"))

import guard  # noqa: E402

BACKENDS = {"patterns": guard.check}  # add e.g. "jev": jev_check, "nemotron": nemotron_check


def outcome(verdict) -> str:
    return "allow" if verdict.allowed and verdict.category == "ok" else ("redact" if verdict.allowed else "block")


def evaluate(check) -> int:
    cases = [json.loads(line) for line in open(HERE / "guard_cases.jsonl")]
    tally, failures = Counter(), []
    for c in cases:
        v = check(c["text"], c["direction"])
        got = outcome(v)
        if got == c["expect"] and (c["expect"] != "block" or v.category == c["category"]):
            tally["pass"] += 1
        else:
            kind = ("miss" if c["expect"] == "block" and got != "block" else
                    "false block" if got == "block" else "wrong outcome/category")
            tally[kind] += 1
            failures.append((c["id"], kind, c["expect"], got, v.category, c["text"][:90]))
    bench = [json.loads(line) for line in open(HERE / "questions.jsonl")]
    blocked_q = [(q["id"], check(q["question"], "input").category) for q in bench if not check(q["question"], "input").allowed]
    blocked_a = [(q["id"], check(q["evidence"], "output").category) for q in bench if not check(q["evidence"], "output").allowed]
    print(f"labelled cases: {tally['pass']}/{len(cases)} pass; misses {tally['miss']}, "
          f"false blocks {tally['false block']}, other {tally['wrong outcome/category']}")
    for f in failures:
        print(f"  FAIL {f[0]} ({f[1]}): expected {f[2]}, got {f[3]} [{f[4]}] :: {f[5]}")
    print(f"benchmark questions blocked: {len(blocked_q)}/{len(bench)} {blocked_q}")
    print(f"benchmark evidence passages blocked as answers: {len(blocked_a)}/{len(bench)} {blocked_a}")
    return len(failures) + len(blocked_q) + len(blocked_a)


if __name__ == "__main__":
    bad = 0
    for name in (sys.argv[1:] or BACKENDS):
        print(f"== backend: {name}")
        bad += evaluate(BACKENDS[name])
    sys.exit(1 if bad else 0)
