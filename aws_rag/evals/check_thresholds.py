#!/usr/bin/env python3
"""Fail CI when an aws_rag retrieval result falls below its quality budget."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def check_report(
    report: dict,
    *,
    setup: str,
    expected_questions: int,
    min_recall5: float,
    min_mrr10: float,
    min_ndcg10: float,
    max_median_ms: float,
) -> list[str]:
    """Return human-readable failures; an empty list means the gate passed."""
    failures: list[str] = []
    question_count = report["cost_evidence"]["question_count"]
    if question_count != expected_questions:
        failures.append(
            f"question count {question_count} != expected {expected_questions}"
        )

    if setup not in report["summary"]:
        return failures + [f"setup {setup!r} is missing from the report"]

    row = report["summary"][setup]
    minimums = {
        "Recall@5": min_recall5,
        "MRR@10": min_mrr10,
        "nDCG@10": min_ndcg10,
    }
    for metric, minimum in minimums.items():
        actual = float(row[metric])
        if actual < minimum:
            failures.append(f"{metric} {actual:.3f} < minimum {minimum:.3f}")

    latency = float(row["median ms"])
    if latency > max_median_ms:
        failures.append(
            f"median latency {latency:.1f} ms > maximum {max_median_ms:.1f} ms"
        )

    rerank_calls = report["cost_evidence"]["rerank"]["calls"]
    if rerank_calls:
        failures.append(
            f"retrieval-only gate unexpectedly made {rerank_calls} reranker calls"
        )
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("--setup", default="pg-hybrid-bm25")
    parser.add_argument("--questions", type=int, default=62)
    parser.add_argument("--min-recall5", type=float, default=0.88)
    parser.add_argument("--min-mrr10", type=float, default=0.71)
    parser.add_argument("--min-ndcg10", type=float, default=0.76)
    parser.add_argument("--max-median-ms", type=float, default=2000.0)
    args = parser.parse_args()

    report = json.loads(args.results.read_text(encoding="utf-8"))
    failures = check_report(
        report,
        setup=args.setup,
        expected_questions=args.questions,
        min_recall5=args.min_recall5,
        min_mrr10=args.min_mrr10,
        min_ndcg10=args.min_ndcg10,
        max_median_ms=args.max_median_ms,
    )

    row = report.get("summary", {}).get(args.setup, {})
    print(f"setup: {args.setup}")
    for metric in ("Recall@5", "MRR@10", "nDCG@10", "median ms"):
        if metric in row:
            print(f"{metric}: {row[metric]:.3f}")

    if failures:
        print("\nRetrieval quality gate failed:")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)
    print("\nRetrieval quality gate passed.")


if __name__ == "__main__":
    main()
