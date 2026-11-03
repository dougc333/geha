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
import atexit
import hashlib
import inspect
import json
import os
import subprocess
from datetime import datetime, timezone
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
        generate_answer,
        hierarchical_context,
        judge_answer,
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
        generate_answer,
        hierarchical_context,
        judge_answer,
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
EVALUATION_VERSION = 4
PATHS = ("flat", "hierarchical", "hierarchical_notes")
LABELS = {
    "flat": "Flat semantic chunks",
    "hierarchical": "Table-aware RAG",
    "hierarchical_notes": "Table-aware + attached notes",
}
CELLS = ("correct", "generation_drop", "assembly_error", "unsupported")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_files(paths: list[Path], *, relative_to: Path) -> tuple[str, int]:
    """Hash file names and bytes in stable order, returning the digest and file count."""
    digest = hashlib.sha256()
    files = sorted({path.resolve() for path in paths if path.is_file()})
    for path in files:
        try:
            name = path.relative_to(relative_to.resolve()).as_posix()
        except ValueError:
            name = path.as_posix()
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest(), len(files)


def git_metadata(repo: Path) -> dict[str, Any]:
    def run(*arguments: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", "-C", str(repo), *arguments],
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return None
        return result.stdout.strip()

    commit = run("rev-parse", "HEAD")
    status = run("status", "--porcelain")
    return {"commit": commit, "dirty": bool(status) if status is not None else None}


def prompt_hashes() -> dict[str, str]:
    """Fingerprint the exact answer/judge and qualifier-check implementation in use."""
    return {
        "answer_prompt_sha256": sha256_bytes(inspect.getsource(generate_answer).encode("utf-8")),
        "judge_prompt_sha256": sha256_bytes(inspect.getsource(judge_answer).encode("utf-8")),
        "qualifier_fact_checker_sha256": sha256_bytes(
            inspect.getsource(check_qualifier_facts).encode("utf-8")
        ),
        "evaluation_pipeline_sha256": sha256_bytes(
            inspect.getsource(evaluate_path).encode("utf-8")
        ),
    }


def resolve_artifact_paths(args: argparse.Namespace) -> None:
    """Apply --run-dir defaults while preserving the legacy file locations."""
    if args.run_dir:
        args.run_dir = args.run_dir.resolve()
        args.run_dir.mkdir(parents=True, exist_ok=True)
        args.partial = args.partial or args.run_dir / "partial.jsonl"
        args.output = args.output or args.run_dir / "results.json"
        args.markdown = args.markdown or args.run_dir / "results.md"
        args.manifest = args.run_dir / "run.json"
    else:
        args.partial = args.partial or DIRECTORY / "chunking_judge_partial.jsonl"
        args.output = args.output or DIRECTORY / "chunking_judge_results.json"
        args.markdown = args.markdown or DIRECTORY / "chunking_judge_results.md"
        args.manifest = None
    for path in (args.partial, args.output, args.markdown):
        path.parent.mkdir(parents=True, exist_ok=True)


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


def run_metadata(args: argparse.Namespace, cases: list[dict[str, Any]]) -> dict[str, Any]:
    repo = DIRECTORY.parent
    corpus_root = repo / "crawl_dir" / "verified" / "coverage-policies"
    corpus_hash, corpus_files = sha256_files(
        list(corpus_root.rglob("*.docling.md")), relative_to=repo
    )
    eval_hash = sha256_bytes(
        json.dumps(cases, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    started_at = utc_timestamp()
    return {
        "run_id": (
            args.run_dir.name
            if args.run_dir
            else started_at.replace(":", "").replace("-", "")
        ),
        "started_at": started_at,
        "completed_at": None,
        "status": "running",
        "git": git_metadata(repo),
        "models": {
            "answer": args.answer_model,
            "judge_and_fact_check": args.judge_model,
            "embedding": args.embedding_model,
        },
        "retrieval_parameters": {
            "top_chunks": args.top_chunks,
            "top_tables": args.top_tables,
            "candidate_rows": args.candidate_rows,
            "method": "BM25 + pgvector fused with reciprocal-rank fusion",
        },
        "hashes": {
            "corpus_sha256": corpus_hash,
            "corpus_files": corpus_files,
            "evaluation_cases_sha256": eval_hash,
            **prompt_hashes(),
        },
        "artifacts": {
            "checkpoint": str(args.partial),
            "results_json": str(args.output),
            "results_markdown": str(args.markdown),
        },
    }


def write_manifest(path: Path | None, metadata: dict[str, Any]) -> None:
    if path:
        path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


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
    parser.add_argument(
        "--run-dir",
        type=Path,
        help="save partial.jsonl, results.json, results.md, and run.json in this directory",
    )
    parser.add_argument("--partial", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown", type=Path)
    parser.add_argument("--readme", type=Path, default=DIRECTORY / "README.md")
    parser.add_argument(
        "--no-update-readme",
        action="store_true",
        help="do not replace the generated benchmark block in README.md after a full run",
    )
    parser.add_argument("--limit", type=int, help="only the first N cases (for a pilot)")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    resolve_artifact_paths(args)

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not configured")
    if args.partial.exists() and not args.resume:
        raise FileExistsError(f"Partial report exists: {args.partial}; use --resume or remove it")

    cases = load_eval_queries(DIRECTORY)
    if args.limit:
        cases = cases[: args.limit]
    metadata = run_metadata(args, cases)
    if args.resume and args.manifest and args.manifest.exists():
        previous = json.loads(args.manifest.read_text(encoding="utf-8"))
        metadata["run_id"] = previous.get("run_id", metadata["run_id"])
        metadata["started_at"] = previous.get("started_at", metadata["started_at"])
        metadata["resume_count"] = int(previous.get("resume_count", 0)) + 1
    write_manifest(args.manifest, metadata)

    def mark_incomplete_run() -> None:
        if metadata["status"] == "running":
            metadata["status"] = "failed_or_interrupted"
            metadata["completed_at"] = utc_timestamp()
            write_manifest(args.manifest, metadata)

    atexit.register(mark_incomplete_run)
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
    metadata["completed_at"] = utc_timestamp()
    metadata["status"] = "completed"
    report = {
        "run": metadata,
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
    metadata["token_usage"] = {
        "total_llm_tokens": report["summary"]["total_llm_tokens"],
        "average_llm_tokens_by_strategy": {
            path: report["summary"][path]["overall"]["average_llm_tokens"] for path in PATHS
        },
    }
    metadata["queries"] = {
        "requested": report["summary"]["queries_requested"],
        "completed": report["summary"]["queries_completed"],
        "failed": report["summary"]["queries_failed"],
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    args.markdown.write_text(markdown_report(report))
    write_manifest(args.manifest, metadata)
    if not args.limit and not args.no_update_readme:
        update_readme(args.readme, report)
    print(json.dumps({path: report["summary"][path].get("overall") for path in PATHS}, indent=2), flush=True)
    print(f"JSON: {args.output}", flush=True)
    print(f"Markdown: {args.markdown}", flush=True)
    if args.manifest:
        print(f"Run manifest: {args.manifest}", flush=True)


if __name__ == "__main__":
    main()
