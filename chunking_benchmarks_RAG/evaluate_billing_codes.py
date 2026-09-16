"""Check every Docling billing-code fixture against the Streamlit backend lookup."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

try:
    from .generate_billing_code_evals import generate
    from .medical_claims_advisor import (
        format_billing_code_matches,
        retrieve_billing_code_matches,
    )
    from .table_rag import DEFAULT_DATABASE_URL
except ImportError:  # pragma: no cover - direct CLI execution
    from generate_billing_code_evals import generate
    from medical_claims_advisor import format_billing_code_matches, retrieve_billing_code_matches
    from table_rag import DEFAULT_DATABASE_URL


DEFAULT_EVAL_FILE = Path(__file__).with_name("billing_code_evals.json")


def run_evaluation(eval_file: Path, database_url: str) -> dict:
    fixture = json.loads(eval_file.read_text(encoding="utf-8"))
    expected_by_code: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for case in fixture["cases"]:
        expected_by_code[case["billing_code"]].add(
            (case["source_document"], case["table_name"])
        )
    code_results = {}
    for code, expected in sorted(expected_by_code.items()):
        matches = retrieve_billing_code_matches(code, database_url)
        actual = {(item["source_document"], item["table_name"]) for item in matches}
        answer = format_billing_code_matches(code, matches)
        code_results[code] = {
            "expected_sources": sorted(expected),
            "returned_sources": sorted(actual),
            "exact_source_set_pass": actual == expected,
            "answer": answer,
        }
    results = []
    for case in fixture["cases"]:
        outcome = code_results[case["billing_code"]]
        passed = (
            outcome["exact_source_set_pass"]
            and case["expected_answer"] in outcome["answer"]
        )
        results.append({
            "id": case["id"],
            "query": case["query"],
            "source_document": case["source_document"],
            "table_name": case["table_name"],
            "pass": passed,
        })
    source_fixture_pass = fixture == generate()
    return {
        "summary": {
            "documents": len(fixture["documents"]),
            "documents_without_billing_table": [
                item["source_document"] for item in fixture["documents"]
                if not item["has_billing_code_table"]
            ],
            "cases": len(results),
            "passed": sum(item["pass"] for item in results),
            "distinct_codes": len(code_results),
            "exact_code_source_sets_passed": sum(
                item["exact_source_set_pass"] for item in code_results.values()
            ),
            "source_fixture_pass": source_fixture_pass,
        },
        "results": results,
        "code_results": code_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-file", type=Path, default=DEFAULT_EVAL_FILE)
    parser.add_argument("--database-url", default=DEFAULT_DATABASE_URL)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_evaluation(args.eval_file, args.database_url)
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {args.output}")
    print(json.dumps(report["summary"], indent=2))
    if report["summary"]["passed"] != report["summary"]["cases"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
