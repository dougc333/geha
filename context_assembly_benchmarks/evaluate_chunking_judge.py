"""Answer completeness for three context strategies, joined per fact with context completeness.

For every labelled question the same hybrid ranking (BM25 + pgvector RRF) builds three contexts:
  flat                top-k flat row chunks
  hierarchical        top parent tables (table-aware RAG)
  hierarchical_notes  the same tables plus the text linked to them in the policy (footnotes,
                      exceptions, authorization period) - see context_attachments.py
Each context gets one answer (answer model) and one strategy-blind verdict (judge model). Then
every required fact is checked twice - in the context, and in the answer - and placed in a cell:
  correct          in context, in answer
  generation_drop  in context, missing from answer      -> the model had it and left it out
  assembly_error   missing from context and answer      -> context assembly never sent it
  unsupported      missing from context, in answer      -> from memory or invented
Table values are matched by text; qualifier facts (often paraphrased) by an LLM fact check.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

try:
    from .chunking_compare import compare_contexts, fact_present, required_facts
    from .eval_queries import load_eval_queries
    from .generation_eval import reference_answer
    from .llm_judge import (
        check_qualifier_facts,
        evaluate_path,
        flat_context,
        hierarchical_context,
        notes_context,
    )
    from .table_rag import (
        DEFAULT_DATABASE_URL,
        DEFAULT_EMBEDDING_MODEL,
        connect,
        expand_hybrid_tables,
        load_embedding_model,
        retrieve_hybrid_rows,
    )
except ImportError:
    from chunking_compare import compare_contexts, fact_present, required_facts
    from eval_queries import load_eval_queries
    from generation_eval import reference_answer
    from llm_judge import (
        check_qualifier_facts,
        evaluate_path,
        flat_context,
        hierarchical_context,
        notes_context,
    )
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
EVALUATION_VERSION = 3
PATHS = ("flat", "hierarchical", "hierarchical_notes")
LABELS = {
    "flat": "Flat semantic chunks",
    "hierarchical": "Table-aware RAG",
    "hierarchical_notes": "Table-aware + attached notes",
}
CELLS = ("correct", "generation_drop", "assembly_error", "unsupported")


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


def cell(in_context: bool, in_answer: bool) -> str:
    if in_context:
        return "correct" if in_answer else "generation_drop"
    return "unsupported" if in_answer else "assembly_error"


def join_facts(
    client: OpenAI,
    *,
    model: str,
    case: dict[str, Any],
    context: str,
    answer: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    facts = required_facts(case)
    in_context = [fact_present(fact, context) for fact in facts]
    in_answer = [fact_present(fact, answer) if fact["type"] == "value" else False for fact in facts]
    reasons = ["text match" if fact["type"] == "value" else "" for fact in facts]
    qualifier_index = [i for i, fact in enumerate(facts) if fact["type"] == "qualifier"]
    stated, why, usage = check_qualifier_facts(
        client, model=model, query=case["query"], answer=answer,
        facts=[facts[i] for i in qualifier_index],
    )
    for position, index in enumerate(qualifier_index):
        in_answer[index], reasons[index] = stated[position], why[position]
    joined = [
        {
            "text": fact["text"],
            "type": fact["type"],
            "in_context": ctx,
            "in_answer": ans,
            "cell": cell(ctx, ans),
            "reason": reason,
        }
        for fact, ctx, ans, reason in zip(facts, in_context, in_answer, reasons)
    ]
    return joined, usage


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [record for record in records if not record.get("error")]
    summary: dict[str, Any] = {
        "queries_requested": len(records),
        "queries_completed": len(completed),
        "queries_failed": len(records) - len(completed),
    }
    slices = {"overall": completed}
    for kind in ("Preference lookup", "Row-to-column relationship", "Qualifier"):
        slices[kind] = [record for record in completed if record["kind"] == kind]
    for path in PATHS:
        per_slice = {}
        for name, selected in slices.items():
            total = len(selected)
            if not total:
                continue
            facts = [fact for record in selected for fact in record[path]["facts"]]
            per_slice[name] = {
                "cases": total,
                "judge_yes_rate": sum(r[path]["verdict"]["answers_query"] == "yes" for r in selected) / total,
                "grounded_rate": sum(bool(r[path]["verdict"]["grounded_in_context"]) for r in selected) / total,
                "answer_complete_rate": sum(all(f["in_answer"] for f in r[path]["facts"]) for r in selected) / total,
                "context_complete_rate": sum(all(f["in_context"] for f in r[path]["facts"]) for r in selected) / total,
                "cases_with_assembly_error": sum(
                    any(f["cell"] == "assembly_error" for f in r[path]["facts"]) for r in selected) / total,
                "cases_with_generation_drop": sum(
                    any(f["cell"] == "generation_drop" for f in r[path]["facts"]) for r in selected) / total,
                "fact_cells": {name_: sum(f["cell"] == name_ for f in facts) for name_ in CELLS},
                "facts": len(facts),
                "average_context_tokens": sum(
                    r["context_metrics"][path]["estimated_tokens"] for r in selected) / total,
                "average_llm_tokens": sum(r[path]["total_tokens"] for r in selected) / total,
            }
        summary[path] = per_slice
    summary["total_llm_tokens"] = sum(
        record[path]["total_tokens"] for record in completed for path in PATHS
    )
    return summary


def markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Answer completeness by context strategy (per-fact join with context completeness)",
        "",
        f"- Queries completed: {summary['queries_completed']}/{summary['queries_requested']}",
        f"- Answer model: {report['configuration']['answer_model']}; judge and fact-check model: "
        f"{report['configuration']['judge_model']}",
        f"- Total answer + judge + fact-check tokens: {summary['total_llm_tokens']:,}",
        "",
        "| Slice | Strategy | Cases | Context complete | Answer complete | Judge YES | Cases with assembly error | Cases with generation drop | Facts: correct / drop / assembly / unsupported | Avg context tokens |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |",
    ]
    for slice_name in ("overall", "Preference lookup", "Row-to-column relationship", "Qualifier"):
        for path in PATHS:
            values = summary[path].get(slice_name)
            if not values:
                continue
            cells = values["fact_cells"]
            lines.append(
                f"| {slice_name} | {LABELS[path]} | {values['cases']} | "
                f"{values['context_complete_rate']:.1%} | {values['answer_complete_rate']:.1%} | "
                f"{values['judge_yes_rate']:.1%} | {values['cases_with_assembly_error']:.1%} | "
                f"{values['cases_with_generation_drop']:.1%} | "
                f"{cells['correct']} / {cells['generation_drop']} / {cells['assembly_error']} / "
                f"{cells['unsupported']} | {values['average_context_tokens']:.0f} |"
            )
    lines.extend(
        (
            "",
            "Each required fact is checked in the context and in the answer: an assembly error is a "
            "fact the context never contained; a generation drop is a fact the model had and left "
            "out. The same answer model, judge rubric and fact checker are used for every strategy. "
            "LLM judgments remain evaluation signals rather than ground truth.",
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
        "# Answer completeness by context strategy (per-fact join with context completeness)",
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
    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return {
        record["id"]: record
        for record in records
        if record.get("evaluation_version") == EVALUATION_VERSION and not record.get("error")
    }


def append_record(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record) + "\n")


def main() -> None:
    load_dotenv(DIRECTORY / ".env", override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("GEHA_RAG_DATABASE_URL", DEFAULT_DATABASE_URL))
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--answer-model", default=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    parser.add_argument("--judge-model", default=os.getenv("OPENAI_JUDGE_MODEL", "gpt-4o-mini"))
    parser.add_argument("--top-chunks", type=int, default=5)
    parser.add_argument("--top-tables", type=int, default=3)
    parser.add_argument("--candidate-rows", type=int, default=30)
    parser.add_argument("--partial", type=Path, default=DIRECTORY / "chunking_judge_partial.jsonl")
    parser.add_argument("--output", type=Path, default=DIRECTORY / "chunking_judge_results.json")
    parser.add_argument("--markdown", type=Path, default=DIRECTORY / "chunking_judge_results.md")
    parser.add_argument("--readme", type=Path, default=DIRECTORY / "README.md")
    parser.add_argument("--limit", type=int, help="only the first N cases (for a pilot)")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not configured")
    if args.partial.exists() and not args.resume:
        raise FileExistsError(f"Partial report exists: {args.partial}; use --resume or remove it")

    cases = load_eval_queries(DIRECTORY)
    if args.limit:
        cases = cases[: args.limit]
    completed = load_partial(args.partial) if args.resume else {}
    embedding_model = load_embedding_model(args.embedding_model)
    client = OpenAI()

    with connect(args.database_url) as connection:
        counts = connection.execute(
            "SELECT (SELECT COUNT(*) FROM policy_tables) AS parents, "
            "(SELECT COUNT(*) FROM policy_table_vectors) AS children"
        ).fetchone()
        for index, case in enumerate(cases, 1):
            if case["id"] in completed:
                print(f"[{index}/{len(cases)}] cached {case['id']}", flush=True)
                continue
            print(f"[{index}/{len(cases)}] evaluating {case['id']}", flush=True)
            try:
                hybrid_rows = retrieve_hybrid_rows(
                    connection, embedding_model, case["query"],
                    limit=max(args.candidate_rows, args.top_chunks),
                    vector_candidates=max(100, args.candidate_rows * 3),
                )
                flat_chunks = hybrid_rows[: args.top_chunks]
                parent_tables = expand_hybrid_tables(connection, hybrid_rows, args.top_tables)
                contexts = {
                    "flat": flat_context(flat_chunks),
                    "hierarchical": hierarchical_context(parent_tables),
                    "hierarchical_notes": notes_context(parent_tables),
                }
                metrics = compare_contexts(flat_chunks, parent_tables, case)
                metrics["hierarchical_notes"] = {
                    **metrics["hierarchical"],
                    "characters": len(contexts["hierarchical_notes"]),
                    "estimated_tokens": -(-len(contexts["hierarchical_notes"]) // 4),
                }
                reference = reference_answer(case)
                record: dict[str, Any] = {
                    "evaluation_version": EVALUATION_VERSION,
                    "id": case["id"],
                    "kind": case["kind"],
                    "query": case["query"],
                    "expected_source": case["source"],
                    "expected_table_number": case["table_number"],
                    "reference": reference,
                    "flat_expected_chunk_rank": expected_rank(flat_chunks, case),
                    "hierarchical_expected_parent_rank": expected_rank(parent_tables, case),
                    "context_metrics": metrics,
                    "error": None,
                }
                for path in PATHS:
                    result = evaluate_path(
                        client, answer_model=args.answer_model, judge_model=args.judge_model,
                        query=case["query"], context=contexts[path], reference=reference, case=case,
                    )
                    facts, check_usage = join_facts(
                        client, model=args.judge_model, case=case,
                        context=contexts[path], answer=result["answer"],
                    )
                    result["facts"] = facts
                    result["fact_check_usage"] = check_usage
                    result["total_tokens"] += check_usage["total_tokens"]
                    record[path] = result
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
            "strategies": list(PATHS),
            "parent_tables": int(counts["parents"]),
            "child_vectors": int(counts["children"]),
            "calls_per_query": "3 answers + 3 judge verdicts + 3 qualifier fact checks",
            "evaluation_version": EVALUATION_VERSION,
        },
        "summary": summarize(ordered),
        "results": ordered,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    args.markdown.write_text(markdown_report(report))
    if not args.limit:
        update_readme(args.readme, report)
    print(json.dumps({path: report["summary"][path].get("overall") for path in PATHS}, indent=2), flush=True)
    print(f"JSON: {args.output}", flush=True)
    print(f"Markdown: {args.markdown}", flush=True)


if __name__ == "__main__":
    main()
