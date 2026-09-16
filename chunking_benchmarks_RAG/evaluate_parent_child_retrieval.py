"""Test semantic child-row hits and retrieval of their complete parent tables."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from .table_rag import (
        DEFAULT_DATABASE_URL,
        DEFAULT_EMBEDDING_MODEL,
        connect,
        load_embedding_model,
        retrieve_tables,
    )
except ImportError:  # pragma: no cover - direct CLI execution
    from table_rag import (
        DEFAULT_DATABASE_URL,
        DEFAULT_EMBEDDING_MODEL,
        connect,
        load_embedding_model,
        retrieve_tables,
    )


HERE = Path(__file__).resolve().parent
POLICY_DIR = HERE.parent / "downloads" / "coverage-policies"
DEFAULT_EVALS = HERE / "parent_child_retrieval_evals.json"


def _row_contains(row: dict[str, Any], term: str) -> bool:
    return term.casefold() in " ".join(str(value) for value in row.values()).casefold()


def run_evaluation(
    eval_file: Path,
    database_url: str,
    embedding_model_name: str,
    top_tables: int = 3,
    candidate_rows: int = 30,
) -> dict[str, Any]:
    cases = json.loads(eval_file.read_text(encoding="utf-8"))["cases"]
    model = load_embedding_model(embedding_model_name)
    results = []
    with connect(database_url) as connection:
        for case in cases:
            source_path = POLICY_DIR / case["source"].replace(".pdf", ".docling.md")
            lines = source_path.read_text(encoding="utf-8").splitlines()
            source_line = lines[case["docling_line"] - 1]
            source_verified = case["child_term"].casefold() in source_line.casefold()

            parents = retrieve_tables(
                connection, model, case["query"], top_tables, candidate_rows
            )
            expected_parent = next(
                (
                    (rank, parent)
                    for rank, parent in enumerate(parents, 1)
                    if parent["source"] == case["source"]
                    and parent["table_number"] == case["table_number"]
                    and parent["title"] == case["table_title"]
                ),
                None,
            )
            parent_rank = expected_parent[0] if expected_parent else None
            parent = expected_parent[1] if expected_parent else None

            query_embedding = model.encode(case["query"], normalize_embeddings=True)
            child_hits = connection.execute(
                """
                SELECT table_id, row_number, search_text
                FROM policy_table_vectors
                ORDER BY embedding <=> %s
                LIMIT %s
                """,
                (query_embedding, candidate_rows),
            ).fetchall()
            child_rank = next(
                (
                    rank
                    for rank, hit in enumerate(child_hits, 1)
                    if parent and hit["table_id"] == parent["id"]
                    and case["child_term"].casefold() in hit["search_text"].casefold()
                ),
                None,
            )
            rows = parent["rows_json"] if parent else []
            child_rows = [index for index, row in enumerate(rows) if _row_contains(row, case["child_term"])]
            sibling_rows = [index for index, row in enumerate(rows) if _row_contains(row, case["sibling_term"])]
            complete_parent = bool(
                parent
                and len(rows) > 1
                and any(child != sibling for child in child_rows for sibling in sibling_rows)
                and case["child_term"].casefold() in parent["full_csv"].casefold()
                and case["sibling_term"].casefold() in parent["full_csv"].casefold()
            )
            passed = source_verified and parent_rank is not None and child_rank is not None and complete_parent
            results.append({
                "id": case["id"],
                "query": case["query"],
                "expected_source": case["source"],
                "expected_table_number": case["table_number"],
                "parent_rank": parent_rank,
                "child_row_rank": child_rank,
                "source_line_verified": source_verified,
                "complete_parent_with_distinct_sibling": complete_parent,
                "returned_parent_tables": [
                    {"source": item["source"], "table_number": item["table_number"], "title": item["title"]}
                    for item in parents
                ],
                "pass": passed,
            })
            print(f"{'PASS' if passed else 'FAIL'} {case['id']}: "
                  f"parent rank {parent_rank}, child rank {child_rank}", flush=True)

    return {
        "eval_file": str(eval_file),
        "top_tables": top_tables,
        "candidate_rows": candidate_rows,
        "cases": len(results),
        "passed": sum(item["pass"] for item in results),
        "top1_parent": sum(item["parent_rank"] == 1 for item in results),
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-file", type=Path, default=DEFAULT_EVALS)
    parser.add_argument("--database-url", default=DEFAULT_DATABASE_URL)
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_evaluation(args.eval_file, args.database_url, args.embedding_model)
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {args.output}")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, indent=2))
    if report["passed"] != report["cases"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
