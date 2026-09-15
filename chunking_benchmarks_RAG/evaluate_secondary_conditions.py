"""Evaluate condition-to-policy retrieval without calling OpenAI."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from medical_claims_advisor import (
    build_policy_summary,
    is_revision_table,
    retrieve_claims_evidence,
    retrieve_tables_for_named_condition,
)
from table_rag import (
    DEFAULT_DATABASE_URL,
    DEFAULT_EMBEDDING_MODEL,
    load_embedding_model,
)


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def unique_source_rankings(results: list[dict[str, Any]]) -> list[str]:
    sources: list[str] = []
    for result in results:
        if result["source"] not in sources:
            sources.append(result["source"])
    return sources


def run_evaluation(
    eval_path: Path,
    database_url: str,
    embedding_model_name: str,
    top_tables: int,
    candidate_rows: int,
) -> dict[str, Any]:
    cases = json.loads(eval_path.read_text(encoding="utf-8"))
    embedding_model = None
    evaluated: list[dict[str, Any]] = []

    for index, case in enumerate(cases, 1):
        results = retrieve_tables_for_named_condition(case["query"], database_url)
        route = "condition_metadata"
        if not results:
            route = "semantic_table_rag"
            if embedding_model is None:
                embedding_model = load_embedding_model(embedding_model_name)
            results = retrieve_claims_evidence(
                case["query"],
                database_url=database_url,
                embedding_model=embedding_model,
                top_tables=top_tables,
                candidate_rows=candidate_rows,
            )

        source_rankings = unique_source_rankings(results)
        expected_rank = next(
            (
                rank
                for rank, source in enumerate(source_rankings, 1)
                if source == case["source"]
            ),
            None,
        )
        summary = build_policy_summary(case["query"], results)
        actual_source = summary["source"] if summary else None
        actual_condition = summary["matched_condition"] if summary else None
        answer = summary["answer"] if summary else ""
        expected_answer_terms = case.get(
            "expected_answer_terms", [case["expected_condition"]]
        )
        term_matches = {
            term: normalized(term) in normalized(answer)
            for term in expected_answer_terms
        }
        displayed_tables = [
            result
            for result in results
            if result["source"] == actual_source
            and not is_revision_table(result["title"])
        ]
        revision_excluded = all(
            not is_revision_table(result["title"]) for result in displayed_tables
        )
        source_pass = (
            expected_rank is not None
            and expected_rank <= case.get("source_rank_max", 1)
        )
        condition_pass = normalized(actual_condition or "") == normalized(
            case["expected_condition"]
        )
        answer_pass = all(term_matches.values())
        revision_pass = (
            revision_excluded
            if case.get("exclude_revision_history", True)
            else True
        )
        passed = source_pass and condition_pass and answer_pass and revision_pass

        evaluated.append(
            {
                "id": case["id"],
                "condition_id": case.get("condition_id"),
                "query": case["query"],
                "route": route,
                "expected_source": case["source"],
                "actual_source": actual_source,
                "expected_source_rank": expected_rank,
                "expected_condition": case["expected_condition"],
                "actual_condition": actual_condition,
                "term_matches": term_matches,
                "revision_history_excluded": revision_excluded,
                "source_pass": source_pass,
                "condition_pass": condition_pass,
                "answer_pass": answer_pass,
                "revision_pass": revision_pass,
                "pass": passed,
            }
        )
        print(
            f"[{index:02d}/{len(cases)}] {'PASS' if passed else 'FAIL'} "
            f"{case['id']} ({route})",
            flush=True,
        )

    passed_count = sum(result["pass"] for result in evaluated)
    source_passed = sum(result["source_pass"] for result in evaluated)
    condition_passed = sum(result["condition_pass"] for result in evaluated)
    answer_passed = sum(result["answer_pass"] for result in evaluated)
    revision_passed = sum(result["revision_pass"] for result in evaluated)
    condition_scores: dict[str, dict[str, int]] = {}
    for result in evaluated:
        key = str(result["condition_id"] or result["expected_condition"])
        score = condition_scores.setdefault(key, {"passed": 0, "cases": 0})
        score["cases"] += 1
        score["passed"] += int(result["pass"])

    return {
        "eval_file": str(eval_path),
        "summary": {
            "cases": len(evaluated),
            "passed": passed_count,
            "failed": len(evaluated) - passed_count,
            "pass_rate": passed_count / len(evaluated) if evaluated else 0.0,
            "expected_source_at_rank_1": source_passed,
            "expected_source_at_rank_1_rate": (
                source_passed / len(evaluated) if evaluated else 0.0
            ),
            "expected_condition_returned": condition_passed,
            "expected_condition_returned_rate": (
                condition_passed / len(evaluated) if evaluated else 0.0
            ),
            "expected_answer_terms_returned": answer_passed,
            "expected_answer_terms_returned_rate": (
                answer_passed / len(evaluated) if evaluated else 0.0
            ),
            "revision_history_excluded": revision_passed,
            "revision_history_excluded_rate": (
                revision_passed / len(evaluated) if evaluated else 0.0
            ),
            "by_condition": condition_scores,
        },
        "results": evaluated,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--eval-file",
        type=Path,
        default=Path(__file__).with_name("secondary_condition_evals.json"),
    )
    parser.add_argument("--database-url", default=DEFAULT_DATABASE_URL)
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--top-tables", type=int, default=5)
    parser.add_argument("--candidate-rows", type=int, default=50)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = run_evaluation(
        args.eval_file,
        args.database_url,
        args.embedding_model,
        args.top_tables,
        args.candidate_rows,
    )
    rendered = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"Wrote {args.output}")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
