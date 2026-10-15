"""Run reference-aware generation evaluations for flat and hierarchical RAG."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

try:
    from .chunking_compare import compare_contexts
    from .eval_queries import load_eval_queries
    from .generation_eval import reference_answer
    from .llm_judge import evaluate_path, flat_context, hierarchical_context
    from .table_rag import (
        DEFAULT_DATABASE_URL,
        DEFAULT_EMBEDDING_MODEL,
        connect,
        expand_hybrid_tables,
        load_embedding_model,
        retrieve_hybrid_rows,
    )
except ImportError:
    from chunking_compare import compare_contexts
    from eval_queries import load_eval_queries
    from generation_eval import reference_answer
    from llm_judge import evaluate_path, flat_context, hierarchical_context
    from table_rag import (
        DEFAULT_DATABASE_URL,
        DEFAULT_EMBEDDING_MODEL,
        connect,
        expand_hybrid_tables,
        load_embedding_model,
        retrieve_hybrid_rows,
    )


DIRECTORY = Path(__file__).resolve().parent
README_RESULTS_START = "<!-- CHUNKING_JUDGE_RESULTS_START -->"
README_RESULTS_END = "<!-- CHUNKING_JUDGE_RESULTS_END -->"
EVALUATION_VERSION = 2


def expected_rank(results: list[dict[str, Any]], case: dict[str, Any]) -> int | None:
    return next(
        (
            rank
            for rank, result in enumerate(results, 1)
            if result["source"] == case["source"]
            and int(result["table_number"]) == int(case["table_number"])
        ),
        None,
    )


def winner(record: dict[str, Any]) -> str:
    flat_yes = record["flat"]["verdict"]["answers_query"] == "yes"
    hierarchy_yes = record["hierarchical"]["verdict"]["answers_query"] == "yes"
    if flat_yes and hierarchy_yes:
        return "both"
    if flat_yes:
        return "flat"
    if hierarchy_yes:
        return "hierarchical"
    return "neither"


def average_generation_flag(
    records: list[dict[str, Any]], path: str, field: str
) -> float:
    values = [
        bool(record[path]["generation_metrics"][field])
        for record in records
        if record[path].get("generation_metrics") is not None
    ]
    return sum(values) / len(values) if values else 0.0


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [record for record in records if not record.get("error")]
    total = len(completed)
    outcomes = {name: 0 for name in ("both", "flat", "hierarchical", "neither")}
    for record in completed:
        outcomes[winner(record)] += 1

    def rate(path: str, field: str, expected: Any = True) -> float:
        if not total:
            return 0.0
        return (
            sum(record[path]["verdict"][field] == expected for record in completed)
            / total
        )

    def average(path: str, field: str) -> float:
        if not total:
            return 0.0
        return sum(record[path][field] for record in completed) / total

    return {
        "queries_requested": len(records),
        "queries_completed": total,
        "queries_failed": len(records) - total,
        "flat_answer_yes_rate": rate("flat", "answers_query", "yes"),
        "hierarchical_answer_yes_rate": rate("hierarchical", "answers_query", "yes"),
        "flat_grounded_rate": rate("flat", "grounded_in_context"),
        "hierarchical_grounded_rate": rate("hierarchical", "grounded_in_context"),
        "flat_reference_complete_rate": rate("flat", "reference_complete"),
        "hierarchical_reference_complete_rate": rate(
            "hierarchical", "reference_complete"
        ),
        "flat_extraneous_claim_rate": rate("flat", "has_extraneous_claims"),
        "hierarchical_extraneous_claim_rate": rate(
            "hierarchical", "has_extraneous_claims"
        ),
        "flat_deterministic_pass_rate": average_generation_flag(
            completed, "flat", "deterministic_pass"
        ),
        "hierarchical_deterministic_pass_rate": average_generation_flag(
            completed, "hierarchical", "deterministic_pass"
        ),
        "paired_outcomes": outcomes,
        "flat_average_llm_tokens": average("flat", "total_tokens"),
        "hierarchical_average_llm_tokens": average("hierarchical", "total_tokens"),
        "total_llm_tokens": sum(
            record[path]["total_tokens"]
            for record in completed
            for path in ("flat", "hierarchical")
        ),
    }


def markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Flat semantic chunks vs hierarchical table RAG — generation evaluation",
        "",
        f"- Queries completed: {summary['queries_completed']}/{summary['queries_requested']}",
        f"- Flat judge YES: {summary['flat_answer_yes_rate']:.1%}",
        f"- Hierarchical judge YES: {summary['hierarchical_answer_yes_rate']:.1%}",
        f"- Flat grounded: {summary['flat_grounded_rate']:.1%}",
        f"- Hierarchical grounded: {summary['hierarchical_grounded_rate']:.1%}",
        f"- Flat reference complete: {summary['flat_reference_complete_rate']:.1%}",
        f"- Hierarchical reference complete: {summary['hierarchical_reference_complete_rate']:.1%}",
        f"- Flat deterministic generation pass: {summary['flat_deterministic_pass_rate']:.1%}",
        f"- Hierarchical deterministic generation pass: {summary['hierarchical_deterministic_pass_rate']:.1%}",
        f"- Flat extraneous-claim rate: {summary['flat_extraneous_claim_rate']:.1%}",
        f"- Hierarchical extraneous-claim rate: {summary['hierarchical_extraneous_claim_rate']:.1%}",
        f"- Total answer + judge tokens: {summary['total_llm_tokens']:,}",
        "",
        "| # | Query | Flat judge | Hierarchical judge | Flat generation | Hierarchical generation | Outcome | Flat evidence | Hierarchical evidence |",
        "| ---: | --- | :---: | :---: | :---: | :---: | --- | ---: | ---: |",
    ]
    for index, record in enumerate(report["results"], 1):
        if record.get("error"):
            lines.append(
                f"| {index} | {record['query'].replace('|', '/')} | ERROR | ERROR | ERROR | ERROR | failed | — | — |"
            )
            continue
        flat = record["flat"]
        hierarchical = record["hierarchical"]
        query = record["query"].replace("|", "/")
        flat_generation = (
            "PASS" if flat["generation_metrics"]["deterministic_pass"] else "FAIL"
        )
        hierarchical_generation = (
            "PASS"
            if hierarchical["generation_metrics"]["deterministic_pass"]
            else "FAIL"
        )
        lines.append(
            f"| {index} | {query} | {flat['verdict']['answers_query'].upper()} | "
            f"{hierarchical['verdict']['answers_query'].upper()} | {flat_generation} | "
            f"{hierarchical_generation} | {winner(record)} | "
            f"{record['context_metrics']['flat']['expected_evidence_coverage']:.0%} | "
            f"{record['context_metrics']['hierarchical']['expected_evidence_coverage']:.0%} |"
        )
    lines.extend(
        (
            "",
            (
                "The same answer model and strategy-blind judge rubric were used for both paths. "
                "For labeled questions, the judge also receives the verified reference answer. "
                "Deterministic generation checks measure expected-value coverage and unexpected "
                "HCPCS codes. Full answers, reasons, provenance, ranks, and token usage are "
                "retained in the JSON report. LLM judgments remain evaluation signals rather "
                "than ground truth."
            ),
            "",
        )
    )
    return "\n".join(lines)


def update_readme(path: Path, report: dict[str, Any]) -> None:
    """Replace only the generated judge-results block in the project README."""
    text = path.read_text()
    if README_RESULTS_START not in text or README_RESULTS_END not in text:
        raise RuntimeError(f"README result markers are missing from {path}")
    generated = markdown_report(report).replace(
        "# Flat semantic chunks vs hierarchical table RAG — generation evaluation",
        "### Recorded generation-evaluation results",
        1,
    )
    block = f"{README_RESULTS_START}\n{generated}\n{README_RESULTS_END}"
    before, remainder = text.split(README_RESULTS_START, 1)
    _, after = remainder.split(README_RESULTS_END, 1)
    path.write_text(f"{before}{block}{after}")


def load_partial(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    records = [
        json.loads(line) for line in path.read_text().splitlines() if line.strip()
    ]
    return {
        record["id"]: record
        for record in records
        if record.get("evaluation_version") == EVALUATION_VERSION
    }


def append_record(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record) + "\n")


def main() -> None:
    load_dotenv(DIRECTORY / ".env", override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.getenv("GEHA_RAG_DATABASE_URL", DEFAULT_DATABASE_URL),
    )
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument(
        "--answer-model", default=os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    )
    parser.add_argument(
        "--judge-model", default=os.getenv("OPENAI_JUDGE_MODEL", "gpt-4o-mini")
    )
    parser.add_argument("--top-chunks", type=int, default=5)
    parser.add_argument("--top-tables", type=int, default=3)
    parser.add_argument("--candidate-rows", type=int, default=30)
    parser.add_argument(
        "--partial", type=Path, default=DIRECTORY / "chunking_judge_partial.jsonl"
    )
    parser.add_argument(
        "--output", type=Path, default=DIRECTORY / "chunking_judge_results.json"
    )
    parser.add_argument(
        "--markdown", type=Path, default=DIRECTORY / "chunking_judge_results.md"
    )
    parser.add_argument("--readme", type=Path, default=DIRECTORY / "README.md")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not configured")
    if args.partial.exists() and not args.resume:
        raise FileExistsError(
            f"Partial report exists: {args.partial}; use --resume or remove it"
        )

    cases = load_eval_queries(DIRECTORY)
    completed = load_partial(args.partial) if args.resume else {}
    embedding_model = load_embedding_model(args.embedding_model)
    client = OpenAI()

    with connect(args.database_url) as connection:
        counts = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM policy_tables) AS parents,
                (SELECT COUNT(*) FROM policy_table_vectors) AS children
            """
        ).fetchone()
        for index, case in enumerate(cases, 1):
            if case["id"] in completed:
                print(f"[{index}/{len(cases)}] cached {case['id']}", flush=True)
                continue
            print(f"[{index}/{len(cases)}] evaluating {case['id']}", flush=True)
            try:
                hybrid_rows = retrieve_hybrid_rows(
                    connection,
                    embedding_model,
                    case["query"],
                    limit=max(args.candidate_rows, args.top_chunks),
                    vector_candidates=max(100, args.candidate_rows * 3),
                )
                flat_chunks = hybrid_rows[: args.top_chunks]
                parent_tables = expand_hybrid_tables(
                    connection, hybrid_rows, args.top_tables
                )
                metrics = compare_contexts(flat_chunks, parent_tables, case)
                reference = reference_answer(case)
                flat = evaluate_path(
                    client,
                    answer_model=args.answer_model,
                    judge_model=args.judge_model,
                    query=case["query"],
                    context=flat_context(flat_chunks),
                    reference=reference,
                    case=case,
                )
                hierarchical = evaluate_path(
                    client,
                    answer_model=args.answer_model,
                    judge_model=args.judge_model,
                    query=case["query"],
                    context=hierarchical_context(parent_tables),
                    reference=reference,
                    case=case,
                )
                record = {
                    "evaluation_version": EVALUATION_VERSION,
                    "id": case["id"],
                    "kind": case["kind"],
                    "query": case["query"],
                    "expected_source": case["source"],
                    "expected_table_number": case["table_number"],
                    "reference": reference,
                    "flat_expected_chunk_rank": expected_rank(flat_chunks, case),
                    "hierarchical_expected_parent_rank": expected_rank(
                        parent_tables, case
                    ),
                    "context_metrics": metrics,
                    "flat": flat,
                    "hierarchical": hierarchical,
                    "error": None,
                }
            except Exception as error:  # noqa: BLE001 - checkpoint failures and continue the batch
                record = {
                    "evaluation_version": EVALUATION_VERSION,
                    "id": case["id"],
                    "kind": case["kind"],
                    "query": case["query"],
                    "error": f"{type(error).__name__}: {error}",
                }
                print(f"  error: {record['error']}", flush=True)
            append_record(args.partial, record)
            completed[case["id"]] = record

    ordered = [completed[case["id"]] for case in cases]
    report = {
        "configuration": {
            "answer_model": args.answer_model,
            "judge_model": args.judge_model,
            "embedding_model": args.embedding_model,
            "top_chunks": args.top_chunks,
            "top_tables": args.top_tables,
            "candidate_rows": args.candidate_rows,
            "retrieval": "BM25 + pgvector fused with reciprocal-rank fusion",
            "parent_tables": int(counts["parents"]),
            "child_vectors": int(counts["children"]),
            "judge_calls_per_query": 2,
            "answer_calls_per_query": 2,
            "evaluation_version": EVALUATION_VERSION,
        },
        "summary": summarize(ordered),
        "results": ordered,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    args.markdown.write_text(markdown_report(report))
    update_readme(args.readme, report)
    print(json.dumps(report["summary"], indent=2), flush=True)
    print(f"JSON: {args.output}", flush=True)
    print(f"Markdown: {args.markdown}", flush=True)
    print(f"README: {args.readme}", flush=True)


if __name__ == "__main__":
    main()
