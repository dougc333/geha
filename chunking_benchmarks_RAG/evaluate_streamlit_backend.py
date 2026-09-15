"""Run all condition eval fixtures through the Streamlit advisor backend."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:  # Support module and direct-script execution.
    from .evaluate_secondary_conditions import run_evaluation
    from .table_rag import DEFAULT_DATABASE_URL, DEFAULT_EMBEDDING_MODEL
except ImportError:  # pragma: no cover - exercised by direct CLI use
    from evaluate_secondary_conditions import run_evaluation
    from table_rag import DEFAULT_DATABASE_URL, DEFAULT_EMBEDDING_MODEL


ROOT = Path(__file__).resolve().parent
SUITES = (
    ("indication_specific", ROOT / "indication_specific_criteria_evals.json"),
    ("secondary_semantic", ROOT / "secondary_condition_evals.json"),
)


def combined_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)

    def measurement(field: str) -> dict[str, float | int]:
        passed = sum(bool(result[field]) for result in results)
        return {
            "passed": passed,
            "total": total,
            "rate": passed / total if total else 0.0,
        }

    return {
        "cases": total,
        "complete_pass": measurement("pass"),
        "expected_source_at_rank_1": measurement("source_pass"),
        "expected_condition_returned": measurement("condition_pass"),
        "expected_answer_terms_returned": measurement("answer_pass"),
        "revision_history_excluded": measurement("revision_pass"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=DEFAULT_DATABASE_URL)
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--top-tables", type=int, default=5)
    parser.add_argument("--candidate-rows", type=int, default=50)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "streamlit_backend_eval_results.json",
    )
    args = parser.parse_args()

    suite_reports: dict[str, Any] = {}
    combined_results: list[dict[str, Any]] = []
    for suite_name, eval_path in SUITES:
        print(f"\n=== {suite_name}: {eval_path.name} ===", flush=True)
        report = run_evaluation(
            eval_path,
            args.database_url,
            args.embedding_model,
            args.top_tables,
            args.candidate_rows,
        )
        suite_reports[suite_name] = report["summary"]
        for result in report["results"]:
            combined_results.append({"suite": suite_name, **result})

    report = {
        "eval_files": [str(path) for _, path in SUITES],
        "summary": combined_summary(combined_results),
        "suites": suite_reports,
        "results": combined_results,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {args.output}")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
