"""Extract embedded PDF tables into one CSV per PDF, with OCR disabled.

Multiple tables from the same PDF are separated by exactly two empty CSV rows.
Image-only PDFs fail validation instead of silently invoking an OCR engine.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from pathlib import Path
from typing import Any

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption


def native_text_converter() -> DocumentConverter:
    """Build a PDF converter that is prohibited from running OCR."""
    options = PdfPipelineOptions()
    options.do_ocr = False
    options.do_table_structure = True
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=options),
        }
    )


def require_embedded_text(document: Any, pdf_name: str) -> None:
    """Reject image-only input; this pipeline intentionally has no OCR fallback."""
    text = document.export_to_text().strip()
    if not text:
        raise ValueError(
            f"{pdf_name} has no extractable embedded text; OCR is disabled"
        )


def clean_cell(value: Any) -> Any:
    """Return a CSV-safe value while preserving text inside table cells."""
    if value is None:
        return ""
    try:
        if math.isnan(value):
            return ""
    except (TypeError, ValueError):
        pass
    return value


def write_tables(
    output_path: Path, tables: list[Any], document: Any
) -> list[dict[str, int]]:
    table_stats: list[dict[str, int]] = []
    with output_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        for table_index, table in enumerate(tables):
            frame = table.export_to_dataframe(doc=document)
            columns = [clean_cell(column) for column in frame.columns.tolist()]
            rows = [
                [clean_cell(value) for value in row]
                for row in frame.itertuples(index=False, name=None)
            ]
            writer.writerow(columns)
            writer.writerows(rows)
            table_stats.append(
                {
                    "table_number": table_index + 1,
                    "rows_excluding_header": len(rows),
                    "columns": len(columns),
                }
            )

            if table_index != len(tables) - 1:
                writer.writerow([])
                writer.writerow([])
    return table_stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("--suffix", default="_table_openai.csv")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("table_extraction_summary.json"),
    )
    args = parser.parse_args()

    input_dir = args.input_dir.expanduser().resolve()
    pdfs = sorted(input_dir.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"No PDFs found in {input_dir}")

    converter = native_text_converter()
    results: list[dict[str, Any]] = []

    print(f"Found {len(pdfs)} PDFs in {input_dir}", flush=True)
    for pdf_index, pdf_path in enumerate(pdfs, 1):
        output_path = pdf_path.with_name(f"{pdf_path.stem}{args.suffix}")
        if output_path.exists() and not args.overwrite:
            print(
                f"[{pdf_index}/{len(pdfs)}] Skipping existing {output_path.name}",
                flush=True,
            )
            continue

        started = time.perf_counter()
        print(f"[{pdf_index}/{len(pdfs)}] Parsing {pdf_path.name}", flush=True)
        try:
            conversion = converter.convert(pdf_path)
            document = conversion.document
            require_embedded_text(document, pdf_path.name)
            table_stats = write_tables(output_path, list(document.tables), document)
            result = {
                "pdf": pdf_path.name,
                "csv": output_path.name,
                "status": "ok",
                "extraction_method": "embedded_pdf_text",
                "ocr_used": False,
                "tables": len(table_stats),
                "table_shapes": table_stats,
                "elapsed_seconds": round(time.perf_counter() - started, 3),
            }
        # A batch should record one malformed PDF and continue with the rest.
        except Exception as exc:  # noqa: BLE001
            result = {
                "pdf": pdf_path.name,
                "csv": output_path.name,
                "status": "error",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "elapsed_seconds": round(time.perf_counter() - started, 3),
            }
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)

    summary_path = args.summary.expanduser().resolve()
    summary_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    errors = [result for result in results if result["status"] == "error"]
    print(
        f"Finished: {len(results) - len(errors)} succeeded, {len(errors)} failed. "
        f"Summary: {summary_path}",
        flush=True,
    )
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
