#!/usr/bin/env python3
"""Fail CI when the agentic_search retrieval benchmark regresses."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--expected-questions", type=int, default=14)
    parser.add_argument("--min-recall-at-5", type=float, default=0.90)
    parser.add_argument("--min-mrr-at-10", type=float, default=0.80)
    parser.add_argument("--min-ndcg-at-10", type=float, default=0.82)
    parser.add_argument("--max-median-latency-ms", type=float, default=2000.0)
    args = parser.parse_args()

    summary = json.loads(args.report.read_text(encoding="utf-8"))["summary"]
    checks = [
        (summary["questions"] == args.expected_questions, "question count", summary["questions"], args.expected_questions),
        (summary["Recall@5"] >= args.min_recall_at_5, "Recall@5", summary["Recall@5"], args.min_recall_at_5),
        (summary["MRR@10"] >= args.min_mrr_at_10, "MRR@10", summary["MRR@10"], args.min_mrr_at_10),
        (summary["nDCG@10"] >= args.min_ndcg_at_10, "nDCG@10", summary["nDCG@10"], args.min_ndcg_at_10),
        (
            summary["median_latency_ms"] <= args.max_median_latency_ms,
            "median latency (maximum)",
            summary["median_latency_ms"],
            args.max_median_latency_ms,
        ),
    ]
    failures = []
    for passed, label, actual, threshold in checks:
        print(f"{'PASS' if passed else 'FAIL'} {label}: actual={actual} threshold={threshold}")
        if not passed:
            failures.append(label)
    if failures:
        raise SystemExit(f"Retrieval benchmark failed: {', '.join(failures)}")


if __name__ == "__main__":
    main()
