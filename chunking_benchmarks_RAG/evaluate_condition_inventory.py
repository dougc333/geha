"""Evaluate corpus-wide condition inventory queries without calling an LLM."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from medical_claims_advisor import (
    canonical_condition,
    condition_inventory,
    format_condition_inventory,
    is_condition_inventory_query,
    is_preferred_condition_query,
)
from table_rag import DEFAULT_DATABASE_URL


HERE = Path(__file__).resolve().parent
DEFAULT_EVALS = HERE / "condition_inventory_evals.json"


def selected_inventory(
    inventory: list[dict[str, Any]], *, preferred_only: bool
) -> list[dict[str, Any]]:
    return [
        item
        for item in inventory
        if item["preferred_treatments"] or not preferred_only
    ]


def inventory_counts(items: list[dict[str, Any]]) -> tuple[int, int]:
    conditions = {
        canonical_condition(item["source"], item["condition"]) for item in items
    }
    sources = {item["source"] for item in items}
    return len(conditions), len(sources)


def run_evaluation(eval_path: Path, database_url: str) -> dict[str, Any]:
    fixture = json.loads(eval_path.read_text(encoding="utf-8"))
    inventory = condition_inventory(database_url)
    results: list[dict[str, Any]] = []

    for case in fixture["cases"]:
        preferred_only = is_preferred_condition_query(case["query"])
        selected = selected_inventory(inventory, preferred_only=preferred_only)
        condition_count, source_count = inventory_counts(selected)
        answer = format_condition_inventory(
            inventory, preferred_only=preferred_only
        )

        # The current formatter groups first by condition, then lists source policies.
        # Keeping this explicit makes a request for policy-first grouping visible as an
        # evaluation failure until that presentation mode is implemented.
        actual_grouping = "condition"
        checks = {
            "route": is_condition_inventory_query(case["query"]),
            "preferred_filter": preferred_only == case["preferred_only"],
            "grouping": actual_grouping == case["expected_grouping"],
            "unique_conditions": (
                condition_count == case["expected_unique_conditions"]
            ),
            "source_policies": source_count == case["expected_source_policies"],
            "required_terms": all(
                term.casefold() in answer.casefold()
                for term in case.get("required_terms", [])
            ),
        }
        passed = all(checks.values())
        results.append(
            {
                "id": case["id"],
                "query": case["query"],
                "expected_route": case["expected_route"],
                "expected_grouping": case["expected_grouping"],
                "actual_grouping": actual_grouping,
                "actual_unique_conditions": condition_count,
                "actual_source_policies": source_count,
                "checks": checks,
                "pass": passed,
            }
        )
        print(f"{'PASS' if passed else 'FAIL'} {case['id']}", flush=True)

    passed_count = sum(result["pass"] for result in results)
    return {
        "eval_file": str(eval_path),
        "summary": {
            "cases": len(results),
            "passed": passed_count,
            "failed": len(results) - passed_count,
            "pass_rate": passed_count / len(results) if results else 0.0,
        },
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-file", type=Path, default=DEFAULT_EVALS)
    parser.add_argument("--database-url", default=DEFAULT_DATABASE_URL)
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE / "condition_inventory_eval_results.json",
    )
    args = parser.parse_args()

    report = run_evaluation(args.eval_file, args.database_url)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"Wrote {args.output}")
    if report["summary"]["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
