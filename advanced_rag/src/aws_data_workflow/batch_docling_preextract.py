"""Run resumable Docling pre-extraction across documents in parallel."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from .docling_preextract import preextract_docling_pages
from .table_postprocess import postprocess_runtime


def _document_directory(runtime_root: Path, document_id: str) -> Path:
    return runtime_root / "documents" / document_id


def _load_record(runtime_root: Path, document_id: str) -> dict[str, Any]:
    return json.loads(
        (_document_directory(runtime_root, document_id) / "job.json").read_text(
            encoding="utf-8"
        )
    )


def _save_record(runtime_root: Path, record: dict[str, Any]) -> None:
    path = _document_directory(runtime_root, record["id"]) / "job.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _extract_document(
    runtime_root: str,
    document_id: str,
    document_index: int,
    document_total: int,
) -> dict[str, Any]:
    root = Path(runtime_root)
    directory = _document_directory(root, document_id)
    record = _load_record(root, document_id)
    name = record["filename"]
    started_pages: set[int] = set()

    def on_start(page_number: int, processed: int, total: int) -> None:
        started_pages.add(page_number)
        print(
            f"[{document_index:02d}/{document_total}] {name} - processing "
            f"page {page_number}/{total}",
            flush=True,
        )
        current = _load_record(root, document_id)
        _save_record(root, {
            **current,
            "doclingPageProgress": {
                "completed": processed - 1,
                "total": total,
                "currentPage": page_number,
            },
        })

    def on_page(
        page_number: int,
        decision: dict[str, Any],
        processed: int,
        total: int,
    ) -> None:
        if page_number in started_pages:
            route = "accepted" if decision["accepted"] else "fallback"
            print(
                f"[{document_index:02d}/{document_total}] {name} - completed "
                f"page {page_number}/{total}: {route}",
                flush=True,
            )
        current = _load_record(root, document_id)
        _save_record(root, {
            **current,
            "doclingPageProgress": {
                "completed": processed,
                "total": total,
                "currentPage": page_number,
            },
        })

    report = preextract_docling_pages(
        directory / record.get("sourceName", "source.pdf"),
        directory / "pages",
        on_page_start=on_start,
        on_page=on_page,
    )
    summary = {
        "document_id": document_id,
        "filename": name,
        "total": int(report["page_count"]),
        "accepted": int(report["accepted_pages"]),
        "fallback": len(report["fallback_pages"]),
        "cached": not started_pages,
    }
    current = _load_record(root, document_id)
    _save_record(root, {
        **current,
        "doclingPreflight": {
            "total": summary["total"],
            "accepted": summary["accepted"],
            "fallback": summary["fallback"],
        },
        "doclingPageProgress": {
            "completed": summary["total"],
            "total": summary["total"],
            "currentPage": summary["total"],
        },
    })
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, default=Path("runtime"))
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("evals/cluster_manifest.json"),
    )
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument(
        "--skip-table-postprocess",
        action="store_true",
        help="Do not run table header normalization after all first-pass jobs finish",
    )
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        parser.error("--workers must be between 1 and 4")

    records = {}
    for job_path in (args.runtime_root / "documents").glob("*/job.json"):
        record = json.loads(job_path.read_text(encoding="utf-8"))
        records[unquote(record["filename"])] = record
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))["documents"]
    targets: list[tuple[int, str]] = []
    for index, item in enumerate(manifest, 1):
        name = unquote(Path(item["path"]).name)
        if name not in records:
            raise KeyError(f"Manifest document is not registered: {name}")
        targets.append((index, records[name]["id"]))

    totals = {
        "documents": 0,
        "pages": 0,
        "accepted": 0,
        "fallback": 0,
        "failed_documents": 0,
    }
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                _extract_document,
                str(args.runtime_root),
                document_id,
                index,
                len(targets),
            ): (index, document_id)
            for index, document_id in targets
        }
        try:
            for future in as_completed(futures):
                index, document_id = futures[future]
                try:
                    summary = future.result()
                except Exception as exc:
                    totals["failed_documents"] += 1
                    print(
                        f"[{index:02d}/{len(targets)}] ERROR {document_id}: "
                        f"{type(exc).__name__}: {exc}",
                        flush=True,
                    )
                    continue
                totals["documents"] += 1
                totals["pages"] += summary["total"]
                totals["accepted"] += summary["accepted"]
                totals["fallback"] += summary["fallback"]
                mode = "cached" if summary["cached"] else "extracted"
                print(
                    f"[{index:02d}/{len(targets)}] DONE {summary['filename']}: "
                    f"{summary['accepted']}/{summary['total']} accepted, "
                    f"{summary['fallback']} fallback ({mode})",
                    flush=True,
                )
        except KeyboardInterrupt:
            for future in futures:
                future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            raise

    if not args.skip_table_postprocess:
        table_summary = postprocess_runtime(
            args.runtime_root,
            [document_id for _, document_id in targets],
        )
        print(
            "TABLE_POSTPROCESS " + json.dumps(table_summary, sort_keys=True),
            flush=True,
        )
    print("TOTALS " + json.dumps(totals, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
