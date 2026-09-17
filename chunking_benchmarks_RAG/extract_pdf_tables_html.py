"""Command-line entry point for the reusable PDF table-to-HTML library.

The re-exports keep existing callers working; new code can import directly
from :mod:`policy_table_html_lib`.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

try:
    from .policy_table_html_lib import (  # noqa: F401 - compatibility re-exports
        appropriate_heading,
        extract_pdf,
        heading_map,
        infer_heading,
        inherit_continuation_header,
        looks_like_revision_history,
        native_text_converter,
        nearest_heading_by_position,
        normalized,
        ocr_table_converter,
        promote_embedded_header,
        require_embedded_text,
        slugify,
        standalone_html,
    )
except ImportError:  # direct script execution
    from policy_table_html_lib import (  # noqa: F401 - compatibility re-exports
        appropriate_heading,
        extract_pdf,
        heading_map,
        infer_heading,
        inherit_continuation_header,
        looks_like_revision_history,
        native_text_converter,
        nearest_heading_by_position,
        normalized,
        ocr_table_converter,
        promote_embedded_header,
        require_embedded_text,
        slugify,
        standalone_html,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    input_dir = args.input_dir.expanduser().resolve()
    output_dir = (
        args.output_dir.expanduser().resolve()
        if args.output_dir
        else input_dir / "html_tables"
    )
    pdfs = sorted(input_dir.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"No PDFs found in {input_dir}")
    if output_dir.exists() and any(output_dir.iterdir()) and not args.overwrite:
        raise FileExistsError(
            f"{output_dir} is not empty; pass --overwrite to replace generated HTML"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.overwrite:
        for old_html in output_dir.glob("*.html"):
            old_html.unlink()

    converter = native_text_converter()
    fallback_converter = ocr_table_converter()
    results: list[dict[str, Any]] = []
    print(f"Found {len(pdfs)} PDFs", flush=True)
    for index, pdf_path in enumerate(pdfs, 1):
        started = time.perf_counter()
        print(f"[{index}/{len(pdfs)}] {pdf_path.name}", flush=True)
        try:
            result = extract_pdf(pdf_path, output_dir, converter, fallback_converter)
        except Exception as exc:  # noqa: BLE001 - retain batch-level diagnostics
            result = {
                "pdf": pdf_path.name,
                "status": "error",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)

    summary = {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "extraction_method": "Docling embedded PDF text with targeted OCR fallback",
        "ocr_used": any(result.get("ocr_used", False) for result in results),
        "ocr_pdfs": [result["pdf"] for result in results if result.get("ocr_used")],
        "pdfs": len(pdfs),
        "pdfs_succeeded": sum(result["status"] == "ok" for result in results),
        "pdfs_failed": sum(result["status"] == "error" for result in results),
        "tables_written": sum(result.get("tables_written", 0) for result in results),
        "revision_tables_excluded": sum(
            result.get("tables_excluded", 0) for result in results
        ),
        "results": results,
    }
    summary_path = output_dir / "manifest.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)
    if summary["pdfs_failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
