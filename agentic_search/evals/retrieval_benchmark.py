#!/usr/bin/env python3
"""Benchmark agentic_search's dense parent-document retrieval path.

The gold labels are source PDF filenames. Retrieved parent chunks are
deduplicated by source before document-level ranking metrics are calculated.
Model loading and indexing are deliberately excluded from query latency.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Iterable


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
SRC_ROOT = PROJECT_ROOT / "src"


def load_questions(path: Path) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            query = record.get("query")
            relevant = record.get("relevant_sources")
            if not isinstance(query, str) or not query.strip():
                raise ValueError(f"{path}:{line_number}: query must be a non-empty string")
            if not isinstance(relevant, list) or not relevant or not all(
                isinstance(value, str) and value for value in relevant
            ):
                raise ValueError(
                    f"{path}:{line_number}: relevant_sources must be a non-empty string list"
                )
            questions.append({"query": query, "relevant_sources": relevant})
    if not questions:
        raise ValueError(f"No benchmark questions found in {path}")
    return questions


def unique_source_names(documents: Iterable[Any]) -> list[str]:
    """Return source filenames in rank order, dropping duplicate parent chunks."""

    sources: list[str] = []
    seen: set[str] = set()
    for document in documents:
        source = Path(str(document.metadata.get("source", ""))).name
        if source and source not in seen:
            seen.add(source)
            sources.append(source)
    return sources


def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    return len(set(ranked[:k]) & relevant) / len(relevant) if relevant else 0.0


def reciprocal_rank_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    for rank, source in enumerate(ranked[:k], start=1):
        if source in relevant:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, source in enumerate(ranked[:k], start=1)
        if source in relevant
    )
    ideal_count = min(len(relevant), k)
    ideal_dcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_count + 1))
    return dcg / ideal_dcg


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "questions": len(rows),
        "Recall@5": statistics.fmean(row["recall_at_5"] for row in rows),
        "MRR@10": statistics.fmean(row["reciprocal_rank_at_10"] for row in rows),
        "nDCG@10": statistics.fmean(row["ndcg_at_10"] for row in rows),
        "median_latency_ms": statistics.median(row["latency_ms"] for row in rows),
        "p95_latency_ms": sorted(row["latency_ms"] for row in rows)[
            max(0, math.ceil(0.95 * len(rows)) - 1)
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# agentic_search retrieval benchmark",
        "",
        f"Embedding model: `{report['embedding_model']}`",
        "",
        "| Questions | Recall@5 | MRR@10 | nDCG@10 | Median latency | p95 latency |",
        "|---:|---:|---:|---:|---:|---:|",
        (
            f"| {summary['questions']} | {summary['Recall@5']:.4f} | "
            f"{summary['MRR@10']:.4f} | {summary['nDCG@10']:.4f} | "
            f"{summary['median_latency_ms']:.1f} ms | {summary['p95_latency_ms']:.1f} ms |"
        ),
        "",
        "| Query | Gold source | First relevant rank | Latency |",
        "|---|---|---:|---:|",
    ]
    for row in report["results"]:
        query = row["query"].replace("|", "\\|")
        gold = ", ".join(row["relevant_sources"])
        rank = row["first_relevant_rank"] if row["first_relevant_rank"] is not None else "miss"
        lines.append(f"| {query} | {gold} | {rank} | {row['latency_ms']:.1f} ms |")
    return "\n".join(lines) + "\n"


def run_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    sys.path.insert(0, str(SRC_ROOT))
    from rag_class import Rag

    questions = load_questions(args.questions)
    source_names = sorted(
        {source for question in questions for source in question["relevant_sources"]}
    )
    pdf_paths = [args.data_dir / source for source in source_names]
    missing = [str(path) for path in pdf_paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing benchmark PDFs: {', '.join(missing)}")

    rag = Rag()
    documents = rag.load_pdf(pdf_paths)
    embeddings = rag.load_embedding_model(args.embedding_model)
    retriever = rag.create_parent_retriever(
        documents,
        embeddings,
        collection_name=f"agentic-search-ci-{uuid.uuid4().hex}",
        top_k=args.retrieval_k,
    )

    rows: list[dict[str, Any]] = []
    for question in questions:
        started = time.perf_counter()
        retrieved = retriever.invoke(question["query"])
        latency_ms = (time.perf_counter() - started) * 1000.0
        ranked = unique_source_names(retrieved)
        relevant = set(question["relevant_sources"])
        first_rank = next(
            (rank for rank, source in enumerate(ranked[:10], start=1) if source in relevant),
            None,
        )
        rows.append(
            {
                **question,
                "retrieved_sources": ranked,
                "first_relevant_rank": first_rank,
                "recall_at_5": recall_at_k(ranked, relevant, 5),
                "reciprocal_rank_at_10": reciprocal_rank_at_k(ranked, relevant, 10),
                "ndcg_at_10": ndcg_at_k(ranked, relevant, 10),
                "latency_ms": latency_ms,
            }
        )

    return {
        "embedding_model": args.embedding_model,
        "retrieval_k": args.retrieval_k,
        "summary": summarize(rows),
        "results": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=HERE / "retrieval_questions.jsonl")
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    parser.add_argument("--embedding-model", default="BAAI/bge-large-en-v1.5")
    parser.add_argument("--retrieval-k", type=int, default=40)
    parser.add_argument("--out", type=Path, default=HERE / "retrieval_results")
    args = parser.parse_args()
    if args.retrieval_k < 10:
        parser.error("--retrieval-k must be at least 10 for MRR@10 and nDCG@10")
    return args


def main() -> None:
    args = parse_args()
    report = run_benchmark(args)
    json_path = args.out.with_suffix(".json")
    markdown_path = args.out.with_suffix(".md")
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    print(render_markdown(report))
    print(f"Wrote {json_path} and {markdown_path}")


if __name__ == "__main__":
    main()
