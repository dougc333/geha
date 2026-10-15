"""Compare flat semantic chunks with table-aware context using one hybrid ranker."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from chunking_compare import context_metrics, expected_values
from dotenv import load_dotenv
from eval_queries import load_eval_queries
from table_rag import (
    DEFAULT_DATABASE_URL,
    DEFAULT_EMBEDDING_MODEL,
    connect,
    expand_hybrid_tables,
    load_embedding_model,
    retrieve_hybrid_rows,
)

DIRECTORY = Path(__file__).resolve().parent
README_START = "<!-- HYBRID_CONTEXT_RESULTS_START -->"
README_END = "<!-- HYBRID_CONTEXT_RESULTS_END -->"


def score_context(
    *,
    texts: list[str],
    sources: list[str],
    values: list[str],
    expected_source: str,
    expected_table_number: int,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    metrics = context_metrics(texts, sources, values)
    expected_present = any(
        item["source"] == expected_source
        and int(item["table_number"]) == int(expected_table_number)
        for item in items
    )
    return {
        **metrics,
        "complete_evidence": metrics["expected_evidence_coverage"] == 1.0,
        "expected_table_present": expected_present,
    }


def summarize(
    results: list[dict[str, Any]], mode: str, kind: str | None
) -> dict[str, Any]:
    selected = [
        result[mode] for result in results if kind is None or result["kind"] == kind
    ]
    count = len(selected)
    return {
        "cases": count,
        "average_evidence_coverage": sum(
            row["expected_evidence_coverage"] for row in selected
        )
        / count,
        "complete_evidence_rate": sum(row["complete_evidence"] for row in selected)
        / count,
        "expected_table_present_rate": sum(
            row["expected_table_present"] for row in selected
        )
        / count,
        "average_estimated_tokens": sum(row["estimated_tokens"] for row in selected)
        / count,
        "evidence_per_1k_tokens": (
            sum(row["expected_values_found"] for row in selected)
            / max(sum(row["estimated_tokens"] for row in selected), 1)
            * 1000
        ),
    }


def compare(
    connection,
    embedding_model,
    cases: list[dict[str, Any]],
    *,
    top_chunks: int,
    top_tables: int,
    candidate_rows: int,
    vector_candidates: int,
) -> dict[str, Any]:
    results = []
    for index, case in enumerate(cases, 1):
        print(f"[{index}/{len(cases)}] {case['id']}", flush=True)
        ranked_rows = retrieve_hybrid_rows(
            connection,
            embedding_model,
            case["query"],
            limit=max(candidate_rows, top_chunks),
            vector_candidates=vector_candidates,
        )
        flat_rows = ranked_rows[:top_chunks]
        parent_tables = expand_hybrid_tables(connection, ranked_rows, top_tables)
        values = expected_values(case)
        common = {
            "values": values,
            "expected_source": case["source"],
            "expected_table_number": int(case["table_number"]),
        }
        results.append(
            {
                "id": case["id"],
                "kind": case["kind"],
                "query": case["query"],
                "expected_source": case["source"],
                "expected_table_number": case["table_number"],
                "flat_semantic_chunks": score_context(
                    texts=[str(row["search_text"]) for row in flat_rows],
                    sources=[str(row["source"]) for row in flat_rows],
                    items=flat_rows,
                    **common,
                ),
                "table_aware_rag": score_context(
                    texts=[str(table["full_csv"]) for table in parent_tables],
                    sources=[str(table["source"]) for table in parent_tables],
                    items=parent_tables,
                    **common,
                ),
            }
        )

    modes = ("flat_semantic_chunks", "table_aware_rag")
    slices = (
        ("overall", None),
        ("preference", "Preference lookup"),
        ("relation", "Row-to-column relationship"),
    )
    report_summary = {
        mode: {label: summarize(results, mode, kind) for label, kind in slices}
        for mode in modes
    }
    return {"summary": report_summary, "results": results}


def percentage(value: float) -> str:
    return f"{value:.1%}"


def markdown_table(report: dict[str, Any]) -> str:
    labels = {
        "flat_semantic_chunks": "Flat semantic chunks",
        "table_aware_rag": "Table-aware RAG",
    }
    lines = [
        "### Hybrid retrieval context comparison",
        "",
        "Both cases use the same BM25 + pgvector RRF child ranking.",
        "",
        "| Question slice | Context strategy | Cases | Avg evidence coverage | Complete evidence | Expected table present | Avg estimated tokens | Evidence / 1k tokens |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for slice_name in ("overall", "preference", "relation"):
        for mode in ("flat_semantic_chunks", "table_aware_rag"):
            values = report["summary"][mode][slice_name]
            lines.append(
                f"| {slice_name.title()} | {labels[mode]} | {values['cases']} | "
                f"{percentage(values['average_evidence_coverage'])} | "
                f"{percentage(values['complete_evidence_rate'])} | "
                f"{percentage(values['expected_table_present_rate'])} | "
                f"{values['average_estimated_tokens']:.0f} | "
                f"{values['evidence_per_1k_tokens']:.2f} |"
            )

    flat = report["summary"]["flat_semantic_chunks"]["overall"]
    table = report["summary"]["table_aware_rag"]["overall"]
    lines.extend(
        [
            "",
            (
                "Table-aware change versus flat chunks: average evidence coverage "
                f"{table['average_evidence_coverage'] - flat['average_evidence_coverage']:+.1%}, "
                f"complete evidence {table['complete_evidence_rate'] - flat['complete_evidence_rate']:+.1%}, "
                f"and average context tokens "
                f"{table['average_estimated_tokens'] - flat['average_estimated_tokens']:+.0f}."
            ),
            "",
            (
                "This is a retrieval/context benchmark over labeled expected values. It does not "
                "use an LLM judge and does not measure generation quality."
            ),
        ]
    )
    return "\n".join(lines)


def update_readme(path: Path, content: str) -> None:
    text = path.read_text()
    if README_START not in text or README_END not in text:
        raise RuntimeError(f"README context-comparison markers are missing from {path}")
    block = f"{README_START}\n{content}\n{README_END}"
    before, remainder = text.split(README_START, 1)
    _, after = remainder.split(README_END, 1)
    path.write_text(f"{before}{block}{after}")


def main() -> None:
    load_dotenv(DIRECTORY / ".env", override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.getenv("GEHA_RAG_DATABASE_URL", DEFAULT_DATABASE_URL),
    )
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--top-chunks", type=int, default=5)
    parser.add_argument("--top-tables", type=int, default=3)
    parser.add_argument("--candidate-rows", type=int, default=30)
    parser.add_argument("--vector-candidates", type=int, default=100)
    parser.add_argument(
        "--output", type=Path, default=DIRECTORY / "hybrid_context_results.json"
    )
    parser.add_argument(
        "--markdown", type=Path, default=DIRECTORY / "hybrid_context_results.md"
    )
    parser.add_argument("--readme", type=Path, default=DIRECTORY / "README.md")
    args = parser.parse_args()

    model = load_embedding_model(args.embedding_model)
    cases = load_eval_queries(DIRECTORY)
    with connect(args.database_url) as connection:
        counts = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM policy_tables) AS parents,
                (SELECT COUNT(*) FROM policy_table_vectors) AS children
            """
        ).fetchone()
        report = compare(
            connection,
            model,
            cases,
            top_chunks=args.top_chunks,
            top_tables=args.top_tables,
            candidate_rows=args.candidate_rows,
            vector_candidates=args.vector_candidates,
        )

    report["configuration"] = {
        "embedding_model": args.embedding_model,
        "retrieval": "BM25 + pgvector reciprocal-rank fusion for both cases",
        "top_chunks": args.top_chunks,
        "top_tables": args.top_tables,
        "candidate_rows": args.candidate_rows,
        "vector_candidates": args.vector_candidates,
        "parent_tables": int(counts["parents"]),
        "child_vectors": int(counts["children"]),
    }
    content = markdown_table(report)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    args.markdown.write_text(f"# Hybrid retrieval context comparison\n\n{content}\n")
    update_readme(args.readme, content)
    print(json.dumps(report["summary"], indent=2))
    print(f"JSON: {args.output}")
    print(f"Markdown: {args.markdown}")
    print(f"README: {args.readme}")


if __name__ == "__main__":
    main()
