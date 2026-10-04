#!/usr/bin/env python3
"""Extract FEHB and PSHB single-page PDFs to table-preserving Markdown.

Default input/output mapping:

    fehb/single_pages/**/<name>.pdf -> fehb/markdown/**/<name>.md
    pshb/single_pages/**/<name>.pdf -> pshb/markdown/**/<name>.md

The PDFs are born-digital, so OCR is disabled. Docling's accurate table
structure model and cell matching are enabled. Each detected table is checked
against the full Markdown export; a missing table is appended as a recovery
section rather than silently discarded.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
from docling.document_converter import DocumentConverter, PdfFormatOption


MEDICAL_ROOT = Path("/Users/dc/geha/downloads/medical")
DEFAULT_PLANS = ("fehb", "pshb")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp"
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def build_converter(table_mode: str) -> DocumentConverter:
    options = PdfPipelineOptions()
    options.do_ocr = False
    options.force_backend_text = True
    options.do_table_structure = True
    options.table_structure_options.do_cell_matching = True
    options.table_structure_options.mode = TableFormerMode(table_mode)
    options.generate_page_images = False
    options.generate_picture_images = False
    options.enable_remote_services = False
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )


def normalized_markdown(value: str) -> str:
    """Normalize harmless spacing when checking that table exports survived."""
    return re.sub(r"\s+", " ", value).strip()


def export_markdown(document: Any, source: Path) -> tuple[str, int, int]:
    """Return Markdown, detected table count, and recovered table count."""
    if not document.export_to_text().strip():
        raise ValueError(f"No embedded text was extracted from {source}")

    markdown = document.export_to_markdown(
        strict_text=False,
        escape_html=True,
        escape_underscores=True,
        image_placeholder="<!-- image omitted; see source PDF -->",
        enable_chart_tables=True,
        compact_tables=False,
    ).strip()

    tables = list(getattr(document, "tables", []))
    searchable = normalized_markdown(markdown)
    recovered: list[str] = []
    for table in tables:
        table_markdown = table.export_to_markdown(doc=document).strip()
        if table_markdown and normalized_markdown(table_markdown) not in searchable:
            recovered.append(table_markdown)
    if recovered:
        markdown += (
            "\n\n<!-- TABLE RECOVERY: Docling detected these tables but they were not "
            "present in the full-document Markdown export. -->\n\n"
            + "\n\n".join(recovered)
        )
    return markdown.rstrip() + "\n", len(tables), len(recovered)


def discover(plan: str) -> tuple[Path, Path, list[Path]]:
    input_root = MEDICAL_ROOT / plan / "single_pages"
    output_root = MEDICAL_ROOT / plan / "markdown"
    pdfs = sorted(input_root.rglob("*.pdf"), key=lambda path: str(path).lower())
    return input_root, output_root, pdfs


def output_path(pdf: Path, input_root: Path, output_root: Path) -> Path:
    return (output_root / pdf.relative_to(input_root)).with_suffix(".md")


def process_plan(
    *, plan: str, converter: DocumentConverter, overwrite: bool, limit: int | None
) -> dict[str, Any]:
    input_root, output_root, pdfs = discover(plan)
    if limit is not None:
        pdfs = pdfs[:limit]
    output_root.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "plan": plan,
        "input_root": str(input_root),
        "output_root": str(output_root),
        "started_at": utc_now(),
        "completed_at": None,
        "pdf_count": len(pdfs),
        "converted": 0,
        "skipped_existing": 0,
        "failed": 0,
        "detected_tables": 0,
        "recovered_tables": 0,
        "files": [],
    }
    manifest_path = output_root / "batch.json"
    atomic_json(manifest_path, manifest)

    for index, pdf in enumerate(pdfs, 1):
        destination = output_path(pdf, input_root, output_root)
        print(f"[{plan} {index}/{len(pdfs)}] {pdf.name}", flush=True)
        if destination.exists() and not overwrite:
            manifest["skipped_existing"] += 1
            manifest["files"].append({
                "source_pdf": str(pdf),
                "markdown": str(destination),
                "status": "skipped_existing",
            })
            atomic_json(manifest_path, manifest)
            continue

        started = time.perf_counter()
        try:
            result = converter.convert(str(pdf), raises_on_error=True)
            markdown, table_count, recovered_count = export_markdown(result.document, pdf)
            atomic_text(destination, markdown)
            manifest["converted"] += 1
            manifest["detected_tables"] += table_count
            manifest["recovered_tables"] += recovered_count
            record = {
                "source_pdf": str(pdf),
                "markdown": str(destination),
                "status": "converted",
                "characters": len(markdown),
                "detected_tables": table_count,
                "recovered_tables": recovered_count,
                "seconds": round(time.perf_counter() - started, 3),
            }
            print(
                f"  wrote {destination} ({table_count} table(s), "
                f"{recovered_count} recovered)",
                flush=True,
            )
        except Exception as exc:
            manifest["failed"] += 1
            record = {
                "source_pdf": str(pdf),
                "markdown": str(destination),
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
                "seconds": round(time.perf_counter() - started, 3),
            }
            print(f"  failed: {exc}", file=sys.stderr, flush=True)
        manifest["files"].append(record)
        atomic_json(manifest_path, manifest)

    manifest["completed_at"] = utc_now()
    atomic_json(manifest_path, manifest)
    return manifest


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plan", action="append", choices=DEFAULT_PLANS,
        help="Plan to process; repeatable. Defaults to both fehb and pshb.",
    )
    parser.add_argument(
        "--table-mode", choices=("fast", "accurate"), default="accurate",
        help="Docling TableFormer mode (default: accurate).",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--limit", type=int, help="Limit PDFs per plan for testing")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    plans = args.plan or list(DEFAULT_PLANS)
    if args.dry_run:
        total = 0
        for plan in plans:
            input_root, output_root, pdfs = discover(plan)
            if args.limit is not None:
                pdfs = pdfs[:args.limit]
            print(f"{plan}: {len(pdfs)} PDF(s) from {input_root} -> {output_root}")
            total += len(pdfs)
        print(f"total: {total} PDF(s)")
        return 0

    converter = build_converter(args.table_mode)
    manifests = [
        process_plan(
            plan=plan,
            converter=converter,
            overwrite=args.overwrite,
            limit=args.limit,
        )
        for plan in plans
    ]
    converted = sum(item["converted"] for item in manifests)
    skipped = sum(item["skipped_existing"] for item in manifests)
    failed = sum(item["failed"] for item in manifests)
    tables = sum(item["detected_tables"] for item in manifests)
    print(
        f"Complete: {converted} converted, {skipped} skipped, {failed} failed, "
        f"{tables} table(s) preserved."
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
