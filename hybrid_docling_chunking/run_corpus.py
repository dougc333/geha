"""Run full-document Docling HybridChunker over the 50-document corpus."""

from __future__ import annotations

import argparse
import json
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from count_hybrid_chunks import DEFAULT_TOKENIZER, count_document


RUN_LABEL = "hybrid_chunker_fulldoc"
DEFAULT_MAX_TOKENS = 512


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def runtime_documents(runtime_root: Path) -> dict[str, dict[str, Any]]:
    """Index runtime records by literal and URL-decoded source filenames."""
    indexed: dict[str, dict[str, Any]] = {}
    for job_path in sorted(runtime_root.glob("doc-*/job.json")):
        record = json.loads(job_path.read_text(encoding="utf-8"))
        filename = str(record.get("filename") or "")
        source = job_path.parent / "source.pdf"
        if not filename or not source.is_file():
            continue
        item = {
            "document_id": record["id"],
            "filename": filename,
            "pages": int(record.get("pages") or 0),
            "source": str(source.resolve()),
        }
        indexed[filename] = item
        indexed[unquote(filename)] = item
    return indexed


def build_plan(
    *, manifest_path: Path, runtime_root: Path, run_root: Path
) -> list[dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    available = runtime_documents(runtime_root)
    plan: list[dict[str, Any]] = []
    missing: list[str] = []

    for entry in manifest["documents"]:
        manifest_filename = Path(entry["path"]).name
        runtime = available.get(manifest_filename) or available.get(
            unquote(manifest_filename)
        )
        if runtime is None:
            missing.append(entry["path"])
            continue
        plan.append(
            {
                **runtime,
                "cluster": entry["cluster"],
                "manifest_path": entry["path"],
                "run_label": RUN_LABEL,
                "chunker": "docling.HybridChunker",
                "chunking_scope": "full_document",
                "hierarchy_aware": True,
                "token_aware": True,
                "annotation_status": "not_started",
                "llm_calls_made": 0,
                "output_dir": str(
                    (run_root / "documents" / runtime["document_id"]).resolve()
                ),
                "status": "pending",
            }
        )

    if missing:
        raise RuntimeError(
            "Manifest documents missing from runtime:\n" + "\n".join(missing)
        )
    if len(plan) != 50:
        raise RuntimeError(f"Expected 50 corpus documents, resolved {len(plan)}")
    return plan


def process_document(
    item: dict[str, Any], *, tokenizer: str, max_tokens: int, run_label: str
) -> dict[str, Any]:
    output_dir = Path(item["output_dir"])
    completion_path = output_dir / "document-run.json"
    if completion_path.is_file():
        existing = json.loads(completion_path.read_text(encoding="utf-8"))
        if (
            existing.get("status") == "complete"
            and existing.get("run_label") == run_label
            and existing.get("tokenizer") == tokenizer
            and existing.get("max_tokens") == max_tokens
        ):
            return existing

    started_at = utc_now()
    try:
        summary = count_document(
            Path(item["source"]),
            output_dir,
            tokenizer_model=tokenizer,
            token_budgets=[max_tokens],
        )
        budget = summary["budgets"][0]
        result = {
            **item,
            "run_label": run_label,
            "chunker": "docling.HybridChunker",
            "chunking_scope": "full_document",
            "hierarchy_aware": True,
            "token_aware": True,
            "tokenizer": tokenizer,
            "max_tokens": max_tokens,
            "chunks": budget["chunks"],
            "chunks_spanning_pages": budget["chunks_spanning_pages"],
            "llm_calls_made": 0,
            "annotation_status": "not_started",
            "status": "complete",
            "started_at": started_at,
            "completed_at": utc_now(),
            "error": None,
        }
    except Exception as error:  # Persist enough information for exact retries.
        result = {
            **item,
            "run_label": run_label,
            "chunker": "docling.HybridChunker",
            "chunking_scope": "full_document",
            "hierarchy_aware": True,
            "token_aware": True,
            "tokenizer": tokenizer,
            "max_tokens": max_tokens,
            "llm_calls_made": 0,
            "annotation_status": "not_started",
            "status": "failed",
            "started_at": started_at,
            "completed_at": utc_now(),
            "error": f"{type(error).__name__}: {error}",
            "traceback": traceback.format_exc(),
        }
    write_json_atomic(completion_path, result)
    return result


def batch_summary(
    *,
    plan: list[dict[str, Any]],
    completed: dict[str, dict[str, Any]],
    run_label: str,
    tokenizer: str,
    max_tokens: int,
    started_at: str,
) -> dict[str, Any]:
    records = [completed.get(item["document_id"], item) for item in plan]
    complete = sum(item.get("status") == "complete" for item in records)
    failed = sum(item.get("status") == "failed" for item in records)
    running = sum(item.get("status") == "running" for item in records)
    return {
        "schema_version": "1.0",
        "run_label": run_label,
        "chunker": "docling.HybridChunker",
        "chunking_scope": "full_document",
        "hierarchy_aware": True,
        "token_aware": True,
        "tokenizer": tokenizer,
        "max_tokens": max_tokens,
        "document_count": len(plan),
        "complete": complete,
        "failed": failed,
        "running": running,
        "pending": len(plan) - complete - failed - running,
        "total_chunks": sum(
            int(item.get("chunks") or 0)
            for item in records
            if item.get("status") == "complete"
        ),
        "llm_calls_made": 0,
        "annotation_status": "not_started",
        "status": (
            "complete" if complete == len(plan)
            else "complete_with_errors" if complete + failed == len(plan)
            else "running" if running or complete or failed
            else "planned"
        ),
        "started_at": started_at,
        "updated_at": utc_now(),
        "documents": records,
    }


def run_corpus(
    *,
    manifest_path: Path,
    runtime_root: Path,
    run_root: Path,
    tokenizer: str,
    max_tokens: int,
    workers: int,
    plan_only: bool,
    limit: int | None,
) -> dict[str, Any]:
    plan = build_plan(
        manifest_path=manifest_path, runtime_root=runtime_root, run_root=run_root
    )
    if limit is not None:
        plan = plan[:limit]
    started_at = utc_now()
    completed: dict[str, dict[str, Any]] = {}
    summary_path = run_root / "run.json"

    initial = batch_summary(
        plan=plan,
        completed=completed,
        run_label=RUN_LABEL,
        tokenizer=tokenizer,
        max_tokens=max_tokens,
        started_at=started_at,
    )
    write_json_atomic(summary_path, initial)
    if plan_only:
        return initial

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {}
        for item in plan:
            running_item = {**item, "status": "running"}
            completed[item["document_id"]] = running_item
            future = executor.submit(
                process_document,
                item,
                tokenizer=tokenizer,
                max_tokens=max_tokens,
                run_label=RUN_LABEL,
            )
            futures[future] = item

        write_json_atomic(
            summary_path,
            batch_summary(
                plan=plan,
                completed=completed,
                run_label=RUN_LABEL,
                tokenizer=tokenizer,
                max_tokens=max_tokens,
                started_at=started_at,
            ),
        )

        for future in as_completed(futures):
            result = future.result()
            completed[result["document_id"]] = result
            summary = batch_summary(
                plan=plan,
                completed=completed,
                run_label=RUN_LABEL,
                tokenizer=tokenizer,
                max_tokens=max_tokens,
                started_at=started_at,
            )
            write_json_atomic(summary_path, summary)
            print(
                f"[{summary['complete'] + summary['failed']}/{len(plan)}] "
                f"{result['filename']}: {result['status']} "
                f"({result.get('chunks', 0)} chunks)",
                flush=True,
            )
    return json.loads(summary_path.read_text(encoding="utf-8"))


def main() -> None:
    default_workflow = Path(__file__).resolve().parents[1] / "aws_data_workflow"
    default_run = Path(__file__).resolve().parent / "runs" / RUN_LABEL
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=default_workflow / "evals/cluster_manifest.json"
    )
    parser.add_argument(
        "--runtime-root", type=Path, default=default_workflow / "runtime/documents"
    )
    parser.add_argument("--run-root", type=Path, default=default_run)
    parser.add_argument("--tokenizer", default=DEFAULT_TOKENIZER)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--plan", action="store_true")
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    summary = run_corpus(
        manifest_path=args.manifest.expanduser().resolve(),
        runtime_root=args.runtime_root.expanduser().resolve(),
        run_root=args.run_root.expanduser().resolve(),
        tokenizer=args.tokenizer,
        max_tokens=args.max_tokens,
        workers=args.workers,
        plan_only=args.plan,
        limit=args.limit,
    )
    print(json.dumps({key: summary[key] for key in (
        "run_label", "status", "document_count", "complete", "failed",
        "pending", "total_chunks", "llm_calls_made"
    )}, indent=2))


if __name__ == "__main__":
    main()

