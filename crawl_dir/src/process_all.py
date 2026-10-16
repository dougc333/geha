"""Process every raw PDF through the canonical candidate pipeline."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .pipeline.artifact_io import FAMILIES, atomic_json, run_id, sha256_file
from .pipeline.runner import process_document


def _existing_run_is_complete(run_dir: Path, source: Path) -> bool:
    required = (
        run_dir / "run-manifest.json",
        run_dir / "qc-report.json",
        run_dir / "candidate" / "document.md",
        run_dir / "candidate" / "chunks.jsonl",
    )
    if not all(path.is_file() for path in required):
        return False
    try:
        manifest = json.loads(required[0].read_text())
        qc = json.loads(required[1].read_text())
    except (OSError, json.JSONDecodeError):
        return False
    return (
        manifest.get("source_sha256") == sha256_file(source)
        and qc.get("status") in {"needs_visual_review", "passed"}
        and not qc.get("structural_errors")
        and len(list((run_dir / "pages").glob("page-*/source.pdf")))
        == qc.get("page_count")
    )


def process_all(
    *, root: Path, batch_id: str, document_version: str, plan_year: int | None,
    families: list[str] | None = None,
    documents: list[str] | None = None,
    event_sink: Callable[[dict[str, Any]], None] | None = None,
) -> Path:
    root = root.resolve()
    selected = sorted(set(families or FAMILIES))
    unknown = set(selected) - FAMILIES
    if unknown:
        raise ValueError(f"Unknown families: {sorted(unknown)}")
    all_sources = [
        (family, path)
        for family in selected
        for path in sorted((root / "raw" / family).rglob("*.pdf"))
    ]
    requested_documents = set(documents or [])
    sources = [
        (family, path) for family, path in all_sources
        if not requested_documents
        or str(path.relative_to(root / "raw" / family)) in requested_documents
    ]
    if requested_documents:
        matched = {
            str(path.relative_to(root / "raw" / family))
            for family, path in sources
        }
        missing = requested_documents - matched
        if missing:
            raise FileNotFoundError(f"Requested raw PDFs were not found: {sorted(missing)}")
    report_path = root / "runs" / f"{batch_id}.json"
    previous: dict[str, object] = {}
    if report_path.is_file():
        previous = json.loads(report_path.read_text())
    report: dict[str, object] = {
        "batch_id": batch_id,
        "started_at": previous.get("started_at") or datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "document_version": document_version,
        "plan_year": plan_year,
        "total": len(sources),
        "results": [],
    }
    results: list[dict[str, object]] = []
    report["results"] = results
    if event_sink:
        event_sink({
            "type": "canonical_batch_started",
            "batch_id": batch_id,
            "total": len(sources),
        })
    for index, (family, source) in enumerate(sources, 1):
        relative = source.relative_to(root / "raw" / family)
        document_id = "--".join(relative.with_suffix("").parts)
        target = root / "runs" / family / document_id / batch_id
        source_key = str(source.relative_to(root))
        print(f"[{index}/{len(sources)}] {source_key}", flush=True)
        if event_sink:
            event_sink({
                "type": "canonical_document_started",
                "index": index,
                "total": len(sources),
                "source": source_key,
                "document_id": document_id,
            })
        if _existing_run_is_complete(target, source):
            item = {"source": source_key, "status": "reused", "run": str(target)}
        else:
            try:
                requested_id = batch_id
                if target.exists():
                    attempt = 1
                    while (target.parent / f"{batch_id}-retry-{attempt:02d}").exists():
                        attempt += 1
                    requested_id = f"{batch_id}-retry-{attempt:02d}"
                output = process_document(
                    root=root,
                    family=family,
                    document=str(relative),
                    document_version=document_version,
                    plan_year=plan_year,
                    requested_run_id=requested_id,
                )
                qc = json.loads((output / "qc-report.json").read_text())
                item = {
                    "source": source_key,
                    "status": "processed",
                    "run": str(output),
                    "qc_status": qc["status"],
                    "pages": qc["page_count"],
                    "chunks": qc["chunk_count"],
                    "tables": qc["table_count"],
                }
            except Exception as exc:  # keep the batch resumable
                item = {
                    "source": source_key,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
        results.append(item)
        report["updated_at"] = datetime.now(timezone.utc).isoformat()
        report["processed"] = sum(x["status"] == "processed" for x in results)
        report["reused"] = sum(x["status"] == "reused" for x in results)
        report["failed"] = sum(x["status"] == "failed" for x in results)
        atomic_json(report_path, report)
        print(json.dumps(item, ensure_ascii=False), flush=True)
        if event_sink:
            event_sink({
                "type": "canonical_document_finished",
                "index": index,
                "total": len(sources),
                **item,
            })
    report["completed_at"] = datetime.now(timezone.utc).isoformat()
    atomic_json(report_path, report)
    if event_sink:
        event_sink({
            "type": "canonical_batch_finished",
            "batch_id": batch_id,
            "report": str(report_path),
            "processed": report.get("processed", 0),
            "reused": report.get("reused", 0),
            "failed": report.get("failed", 0),
        })
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", default=f"batch-{run_id()}")
    parser.add_argument("--document-version", required=True)
    parser.add_argument("--plan-year", type=int)
    parser.add_argument("--family", action="append", choices=sorted(FAMILIES))
    parser.add_argument(
        "--document", action="append",
        help="Optional PDF path relative to its raw family; repeat to select multiple PDFs.",
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(process_all(
        root=args.root,
        batch_id=args.batch_id,
        document_version=args.document_version,
        plan_year=args.plan_year,
        families=args.family,
        documents=args.document,
    ))


if __name__ == "__main__":
    main()
