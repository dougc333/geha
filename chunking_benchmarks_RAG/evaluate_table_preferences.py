"""Evaluate preference-table retrieval without calling an external LLM."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from table_rag import (
    DEFAULT_DATABASE_URL,
    DEFAULT_EMBEDDING_MODEL,
    connect,
    load_embedding_model,
    retrieve_tables,
)


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def extract_products(full_csv: str, preference: str) -> list[str]:
    """Extract products with a preference label from a retrieved parent table."""
    rows = list(csv.reader(io.StringIO(full_csv)))
    target = normalized(preference)
    for header_index, header in enumerate(rows):
        normalized_header = [normalized(cell) for cell in header]
        if "preference" not in normalized_header:
            continue
        preference_index = normalized_header.index("preference")
        name_index = next(
            (
                index
                for index, value in enumerate(normalized_header)
                if value in {"drugname", "name"}
            ),
            None,
        )
        if name_index is None:
            continue

        products: list[str] = []
        for row in rows[header_index + 1 :]:
            if not row or all(not cell.strip() for cell in row):
                break
            if max(preference_index, name_index) >= len(row):
                continue
            if normalized(row[preference_index]) == target:
                product = row[name_index].strip()
                if product and product not in products:
                    products.append(product)
        return products
    return []


def score_products(actual: list[str], expected: list[str]) -> dict[str, Any]:
    actual_set = {normalized(value) for value in actual}
    expected_set = {normalized(value) for value in expected}
    matches = actual_set & expected_set
    recall = len(matches) / len(expected_set) if expected_set else 1.0
    precision = (
        len(matches) / len(actual_set) if actual_set else float(not expected_set)
    )
    return {
        "matched": len(matches),
        "expected": len(expected_set),
        "returned": len(actual_set),
        "recall": recall,
        "precision": precision,
        "exact_match": actual_set == expected_set,
    }


def run_evaluation(
    eval_path: Path,
    database_url: str,
    embedding_model_name: str,
    top_tables: int,
    candidate_rows: int,
) -> dict[str, Any]:
    cases = json.loads(eval_path.read_text(encoding="utf-8"))
    embedding_model = load_embedding_model(embedding_model_name)
    results: list[dict[str, Any]] = []

    with connect(database_url) as connection:
        for index, case in enumerate(cases, 1):
            retrieved = retrieve_tables(
                connection,
                embedding_model,
                case["query"],
                top_tables=top_tables,
                candidate_rows=candidate_rows,
            )
            rankings = [
                {
                    "rank": rank,
                    "source": row["source"],
                    "table_number": row["table_number"],
                    "table_title": row["title"],
                    "similarity": float(row["similarity"]),
                }
                for rank, row in enumerate(retrieved, 1)
            ]
            expected_rank = next(
                (
                    rank
                    for rank, row in enumerate(retrieved, 1)
                    if row["source"] == case["source"]
                ),
                None,
            )
            expected_table_rank = next(
                (
                    rank
                    for rank, row in enumerate(retrieved, 1)
                    if row["source"] == case["source"]
                    and row["table_number"] == case["table_number"]
                ),
                None,
            )
            top_result = retrieved[0] if retrieved else None
            actual_products = (
                extract_products(top_result["full_csv"], case["preference"])
                if top_result
                else []
            )
            product_score = score_products(actual_products, case["gold_phrases"])
            result = {
                "id": case["id"],
                "query": case["query"],
                "preference": case["preference"],
                "expected_source": case["source"],
                "expected_table_number": case["table_number"],
                "expected_products": case["gold_phrases"],
                "top_result_source": top_result["source"] if top_result else None,
                "top_result_table_number": top_result["table_number"]
                if top_result
                else None,
                "top_result_table_title": top_result["title"] if top_result else None,
                "top_result_similarity": (
                    float(top_result["similarity"]) if top_result else None
                ),
                "expected_source_rank": expected_rank,
                "expected_table_rank": expected_table_rank,
                "source_match_top_1": expected_rank == 1,
                "source_match_top_3": expected_rank is not None and expected_rank <= 3,
                "source_match_top_5": expected_rank is not None and expected_rank <= 5,
                "table_match_top_1": expected_table_rank == 1,
                "table_match_top_3": (
                    expected_table_rank is not None and expected_table_rank <= 3
                ),
                "table_match_top_5": (
                    expected_table_rank is not None and expected_table_rank <= 5
                ),
                "actual_products_from_top_result": actual_products,
                "product_score": product_score,
                "rankings": rankings,
            }
            results.append(result)
            status = (
                "PASS"
                if result["table_match_top_1"] and product_score["exact_match"]
                else "FAIL"
            )
            print(f"[{index:02d}/{len(cases)}] {status} {case['id']}", flush=True)

    total = len(results)
    summary = {
        "cases": total,
        "source_recall_at_1": sum(row["source_match_top_1"] for row in results) / total,
        "source_recall_at_3": sum(row["source_match_top_3"] for row in results) / total,
        "source_recall_at_5": sum(row["source_match_top_5"] for row in results) / total,
        "table_recall_at_1": sum(row["table_match_top_1"] for row in results) / total,
        "table_recall_at_3": sum(row["table_match_top_3"] for row in results) / total,
        "table_recall_at_5": sum(row["table_match_top_5"] for row in results) / total,
        "answer_exact_match": sum(
            row["product_score"]["exact_match"] for row in results
        )
        / total,
        "mean_product_recall": sum(row["product_score"]["recall"] for row in results)
        / total,
    }
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "configuration": {
            "eval_file": str(eval_path),
            "embedding_model": embedding_model_name,
            "top_tables": top_tables,
            "candidate_rows": candidate_rows,
            "answer_mode": "deterministic extraction from the top retrieved table",
        },
        "summary": summary,
        "results": results,
    }


def markdown_list(values: list[str]) -> str:
    return ", ".join(values) if values else "_(none)_"


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    config = report["configuration"]
    lines = [
        "# Preferred and non-preferred table evaluation results",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        "This report covers 34 queries across 17 policy preference tables. Answers are extracted deterministically from the top retrieved table, so these results isolate retrieval and table interpretation without an LLM grader.",
        "",
        "## Summary",
        "",
        f"- Source recall@1: **{summary['source_recall_at_1']:.1%}**",
        f"- Source recall@3: **{summary['source_recall_at_3']:.1%}**",
        f"- Source recall@5: **{summary['source_recall_at_5']:.1%}**",
        f"- Exact table recall@1: **{summary['table_recall_at_1']:.1%}**",
        f"- Exact table recall@3: **{summary['table_recall_at_3']:.1%}**",
        f"- Exact table recall@5: **{summary['table_recall_at_5']:.1%}**",
        f"- Exact product-list match from top result: **{summary['answer_exact_match']:.1%}**",
        f"- Mean product recall from top result: **{summary['mean_product_recall']:.1%}**",
        f"- Embedding model: `{config['embedding_model']}`",
        f"- Candidate rows: `{config['candidate_rows']}`",
        "",
        "## All query comparisons",
        "",
    ]

    for index, result in enumerate(report["results"], 1):
        source_status = "PASS" if result["source_match_top_1"] else "FAIL"
        table_status = "PASS" if result["table_match_top_1"] else "FAIL"
        answer_status = "PASS" if result["product_score"]["exact_match"] else "FAIL"
        source_rank = result["expected_source_rank"] or "not in top 5"
        table_rank = result["expected_table_rank"] or "not in top 5"
        lines += [
            f"### {index}. `{result['id']}`",
            "",
            f"- **Query:** {result['query']}",
            f"- **Expected source:** `{result['expected_source']}`",
            f"- **Expected table:** `{result['expected_source']}` table {result['expected_table_number']}",
            f"- **Top result:** `{result['top_result_source']}` table {result['top_result_table_number']} ({result['top_result_table_title']}; similarity {result['top_result_similarity']:.4f})",
            f"- **Expected-source rank:** {source_rank} — **{source_status} at top 1**",
            f"- **Expected-table rank:** {table_rank} — **{table_status} at top 1**",
            f"- **Expected products:** {markdown_list(result['expected_products'])}",
            f"- **Products from top result:** {markdown_list(result['actual_products_from_top_result'])}",
            f"- **Product comparison:** **{answer_status}**; recall {result['product_score']['recall']:.1%}, precision {result['product_score']['precision']:.1%}",
            "- **Top-five search results:**",
            "",
        ]
        for ranking in result["rankings"]:
            marker = (
                " ← expected table"
                if ranking["source"] == result["expected_source"]
                and ranking["table_number"] == result["expected_table_number"]
                else ""
            )
            lines.append(
                f"  {ranking['rank']}. `{ranking['source']}` table {ranking['table_number']} ({ranking['table_title']}) — {ranking['similarity']:.4f}{marker}"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    load_dotenv(override=True)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--eval-file",
        type=Path,
        default=Path(__file__).with_name("table_preference_evals.json"),
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path(__file__).with_name("table_preference_eval_results.json"),
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=Path(__file__).with_name("table_preference_eval_results.md"),
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("GEHA_RAG_DATABASE_URL", DEFAULT_DATABASE_URL),
    )
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--top-tables", type=int, default=5)
    parser.add_argument("--candidate-rows", type=int, default=20)
    args = parser.parse_args()

    report = run_evaluation(
        args.eval_file,
        args.database_url,
        args.embedding_model,
        args.top_tables,
        args.candidate_rows,
    )
    args.json_output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"JSON: {args.json_output}")
    print(f"Markdown: {args.markdown_output}")


if __name__ == "__main__":
    main()
