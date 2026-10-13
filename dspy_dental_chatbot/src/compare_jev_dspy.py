"""Run JEV and DSPy against the same held-out dental-routing cases."""

from __future__ import annotations

import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "dental_enrollment_chatbot" / ".env")
load_dotenv(ROOT / "dspy_dental_chatbot" / ".env")

from shared_graph import DentalEnrollmentGraph  # noqa: E402
from compare_parsers import CASES, shown  # noqa: E402
from enrollment_graph import (  # noqa: E402
    parse_member_type,
    parse_need,
    parse_opportunity,
    parse_opportunity_detail,
    parse_qle_event,
    parse_state_local,
)
from jev_router import JevExtractor  # noqa: E402
from dspy_router import DspyExtractor  # noqa: E402


HELD_OUT = [
    *CASES,
    ("state", "I live near Modesto in california and love the farmers market.", {"CA"}),
    ("state", "Austin texas is home, but I travel constantly for work.", {"TX"}),
    ("state", "I split my time between California and Texas.", {"ASK:CA+TX"}),
    ("need", "We mostly need ordinary checkups, though my kid may want braces someday.",
     {"ASK:orthodontia+routine", "routine"}),
]

PARSERS = {
    "member_type": parse_member_type,
    "opportunity": parse_opportunity,
    "opportunity_detail": parse_opportunity_detail,
    "qle_event": parse_qle_event,
    "need": parse_need,
    "state": parse_state_local,
}


def usage_after(extractor, before: int) -> tuple[int | None, float | None]:
    """Read usage exposed by DSPy's LM history; JEV does not expose it here."""
    lm = getattr(extractor, "lm", None)
    history = getattr(lm, "history", None)
    if not history or len(history) <= before:
        return None, None
    item = history[-1]
    usage = item.get("usage") or {}
    tokens = usage.get("total_tokens") or usage.get("totalTokens")
    cost = item.get("cost")
    return int(tokens) if tokens is not None else None, float(cost) if cost is not None else None


def run_extractor(extractor) -> dict:
    graph = DentalEnrollmentGraph(jev=lambda *_: None, extractor=extractor)
    rows = []
    for stage, message, accepted in HELD_OUT:
        history = getattr(getattr(extractor, "lm", None), "history", []) or []
        before = len(history)
        started = time.perf_counter()
        error = None
        try:
            result = shown(graph._parse(stage, message, PARSERS[stage]))
        except Exception as exc:  # Preserve the failed case in the saved comparison.
            result, error = "ERROR", f"{type(exc).__name__}: {exc}"
        latency = time.perf_counter() - started
        tokens, cost = usage_after(extractor, before)
        rows.append({
            "stage": stage,
            "message": message,
            "accepted": sorted(accepted),
            "result": result,
            "correct": result in accepted,
            "latency_seconds": round(latency, 4),
            "tokens": tokens,
            "cost_usd": cost,
            "error": error,
        })
    latencies = [row["latency_seconds"] for row in rows]
    token_values = [row["tokens"] for row in rows if row["tokens"] is not None]
    costs = [row["cost_usd"] for row in rows if row["cost_usd"] is not None]
    return {
        "name": extractor.name,
        "cases": len(rows),
        "correct": sum(row["correct"] for row in rows),
        "clarifications": sum(str(row["result"]).startswith("ASK:") for row in rows),
        "no_match": sum(row["result"] == "" for row in rows),
        "errors": sum(row["error"] is not None for row in rows),
        "median_latency_seconds": round(statistics.median(latencies), 4),
        "max_latency_seconds": round(max(latencies), 4),
        "total_tokens": sum(token_values) if token_values else None,
        "total_cost_usd": round(sum(costs), 6) if costs else None,
        "rows": rows,
    }


def main() -> None:
    results = [run_extractor(JevExtractor()), run_extractor(DspyExtractor())]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(__file__).parents[1] / "runs" / f"jev-vs-dspy-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "results.json").write_text(json.dumps(results, indent=2))

    print("\nJEV vs DSPy — identical held-out inputs")
    print(f"{'model':<8} {'correct':>9} {'ask':>5} {'none':>6} {'errors':>7} "
          f"{'median':>9} {'max':>9} {'tokens':>9} {'cost':>10}")
    for result in results:
        tokens = str(result["total_tokens"]) if result["total_tokens"] is not None else "n/a"
        cost = (f"${result['total_cost_usd']:.4f}"
                if result["total_cost_usd"] is not None else "n/a")
        print(f"{result['name']:<8} {result['correct']:>3}/{result['cases']:<5} "
              f"{result['clarifications']:>5} {result['no_match']:>6} {result['errors']:>7} "
              f"{result['median_latency_seconds']:>8.2f}s {result['max_latency_seconds']:>8.2f}s "
              f"{tokens:>9} {cost:>10}")

    print("\nDisagreements / failures")
    for index, case in enumerate(HELD_OUT):
        left, right = results[0]["rows"][index], results[1]["rows"][index]
        if left["result"] != right["result"] or not (left["correct"] and right["correct"]):
            print(f"- {case[0]}: {case[1]}")
            print(f"  expected={sorted(case[2])}; JEV={left['result'] or '(none)'}; "
                  f"DSPy={right['result'] or '(none)'}")
    print(f"\nSaved raw results: {run_dir / 'results.json'}")


if __name__ == "__main__":
    main()
