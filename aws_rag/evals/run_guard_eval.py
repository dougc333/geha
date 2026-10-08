"""Evaluate the chat safety guard: labelled cases plus the 62 benchmark questions that must pass.

    PYTHONPATH=aws_rag/query python aws_rag/evals/run_guard_eval.py          # from the repo root

Reports misses (unsafe text let through), false blocks (safe text refused) and wrong
categories. Backends other than the deterministic patterns plug in through BACKENDS.
Exits non-zero if any case fails, so it can gate CI.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "query"))

import guard  # noqa: E402

def _nemotron(text, direction):
    import nemotron_guard  # loads the 4.3B model on first use; local evaluation only
    return nemotron_guard.check(text, direction)


def _layered(text, direction):
    """Patterns first (free, local); the model only sees what the patterns allow."""
    first = guard.check(text, direction)
    return first if not first.allowed else _nemotron(first.text, direction)


# name -> (check, redacts and uses guard.py categories)
BACKENDS = {"patterns": (guard.check, True), "nemotron": (_nemotron, False), "layered": (_layered, True)}


def outcome(verdict) -> str:
    return "allow" if verdict.allowed and verdict.category == "ok" else ("redact" if verdict.allowed else "block")


def evaluate(check, exact: bool) -> int:
    cases = [json.loads(line) for line in open(HERE / "guard_cases.jsonl")]
    tally, failures, seconds = Counter(), [], []
    for c in cases:
        started = time.perf_counter()
        v = check(c["text"], c["direction"])
        seconds.append(time.perf_counter() - started)
        got, want = outcome(v), c["expect"]
        if not exact:  # a model backend neither redacts nor uses guard.py's category names
            got, want = ("block" if got == "block" else "allow"), ("block" if want == "block" else "allow")
        if got == want and (want != "block" or not exact or v.category == c["category"]):
            tally["pass"] += 1
        else:
            kind = ("miss" if want == "block" and got != "block" else
                    "false block" if got == "block" else "wrong outcome/category")
            tally[kind] += 1
            failures.append((c["id"], kind, want, got, v.category, c["text"][:90]))
    bench = [json.loads(line) for line in open(HERE / "questions.jsonl")]
    blocked_q, blocked_a = [], []
    for q in bench:
        for field, direction, sink in (("question", "input", blocked_q), ("evidence", "output", blocked_a)):
            started = time.perf_counter()
            v = check(q[field], direction)
            seconds.append(time.perf_counter() - started)
            if not v.allowed:
                sink.append((q["id"], v.category))
    print(f"labelled cases: {tally['pass']}/{len(cases)} pass; misses {tally['miss']}, "
          f"false blocks {tally['false block']}, other {tally['wrong outcome/category']}")
    for f in failures:
        print(f"  FAIL {f[0]} ({f[1]}): expected {f[2]}, got {f[3]} [{f[4]}] :: {f[5]}")
    print(f"benchmark questions blocked: {len(blocked_q)}/{len(bench)} {blocked_q}")
    print(f"benchmark evidence passages blocked as answers: {len(blocked_a)}/{len(bench)} {blocked_a}")
    print(f"latency per check: median {statistics.median(seconds)*1000:.1f} ms, max {max(seconds)*1000:.1f} ms")
    return len(failures) + len(blocked_q) + len(blocked_a)


if __name__ == "__main__":
    bad = 0
    for name in (sys.argv[1:] or ["patterns"]):
        print(f"== backend: {name}")
        check, exact = BACKENDS[name]
        bad += evaluate(check, exact)
    sys.exit(1 if bad else 0)
