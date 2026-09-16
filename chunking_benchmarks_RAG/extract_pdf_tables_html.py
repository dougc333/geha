"""Extract PDF tables into standalone HTML files with nearby headings.

The extractor reads each PDF directly with Docling, disables OCR, associates
each table with the closest preceding title/section heading in document order,
and omits revision-history/change-log tables. Each output is a complete HTML
document with embedded CSS and can be opened directly in a browser.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import time
import unicodedata
from pathlib import Path
from typing import Any

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

try:  # Support package imports and direct script execution.
    from .extract_pdf_tables import native_text_converter, require_embedded_text
except ImportError:  # pragma: no cover - direct script execution
    from extract_pdf_tables import native_text_converter, require_embedded_text


HEADING_LABELS = {"caption", "section_header", "title"}
GENERIC_HEADINGS = {
    "corporate medical policy",
    "for internal use only",
    "g.e.h.a",
    "geha",
}
MONTHS = (
    "january|february|march|april|may|june|july|august|september|"
    "october|november|december"
)
DATE_RE = re.compile(
    rf"^(?:\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}}|(?:{MONTHS})\s+\d{{4}}|"
    rf"(?:{MONTHS})\s+\d{{1,2}},?\s+\d{{4}}|\d{{4}})$",
    re.IGNORECASE,
)
CHANGE_RE = re.compile(
    r"\b(?:annual review|origination|policy creation|draft policy|presented at|"
    r"updated?|added|removed|revised?|revision|changed|effective)\b",
    re.IGNORECASE,
)


def normalized(value: Any) -> str:
    """Normalize a value for structural comparisons."""
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


def slugify(value: str, *, limit: int = 90) -> str:
    """Create a stable browser- and Git-friendly filename component."""
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.casefold()).strip("-")
    return (slug[:limit].rstrip("-") or "table")


def infer_heading(frame: Any) -> str:
    """Supply a meaningful heading when the PDF has no nearby section label."""
    keys = {normalized(column) for column in frame.columns}
    if {"preference", "drugname"}.issubset(keys):
        return "Drug preference and prior authorization"
    if "hcpcscode" in keys or "cpthcpcscodes" in keys:
        return "Billing codes"
    return "Extracted table"


def ocr_table_converter() -> DocumentConverter:
    """Build the targeted fallback used only when a detected table is empty."""
    options = PdfPipelineOptions()
    options.do_ocr = True
    options.do_table_structure = True
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=options),
        }
    )


def heading_map(document: Any, pdf_path: Path) -> dict[str, str]:
    """Map table references to their closest preceding meaningful heading."""
    current_heading = pdf_path.stem
    generic = {normalized(value) for value in GENERIC_HEADINGS}
    mapped: dict[str, str] = {}
    for item, _level in document.iterate_items():
        label = str(getattr(item, "label", "")).casefold()
        text = str(getattr(item, "text", "")).strip()
        if label in HEADING_LABELS and text:
            if normalized(text) not in generic:
                current_heading = text
        elif label == "table":
            mapped[str(item.self_ref)] = current_heading
    return mapped


def nearest_heading_by_position(document: Any, table: Any, pdf_path: Path) -> str:
    """Fallback for tables not exposed by Docling's regular item traversal."""
    if not table.prov:
        return pdf_path.stem
    table_prov = table.prov[0]
    generic = {normalized(value) for value in GENERIC_HEADINGS}
    candidates: list[tuple[int, float, str]] = []
    for text_item in document.texts:
        label = str(getattr(text_item, "label", "")).casefold()
        text = str(getattr(text_item, "text", "")).strip()
        if label not in HEADING_LABELS or not text or normalized(text) in generic:
            continue
        for prov in text_item.prov:
            if prov.page_no > table_prov.page_no:
                continue
            if prov.page_no == table_prov.page_no and prov.bbox.t < table_prov.bbox.t:
                continue
            page_distance = table_prov.page_no - prov.page_no
            vertical_distance = (
                prov.bbox.t - table_prov.bbox.t if page_distance == 0 else 10_000.0
            )
            candidates.append((page_distance, vertical_distance, text))
    if not candidates:
        return pdf_path.stem
    return min(candidates, key=lambda item: (item[0], item[1]))[2]


def appropriate_heading(raw_heading: str, frame: Any, pdf_path: Path) -> str:
    """Avoid assigning a criteria/disclaimer heading to an obvious code table."""
    inferred = infer_heading(frame)
    heading_key = normalized(raw_heading)
    misleading = {
        "disclaimer",
        "forinternaluseonly",
        "references",
        "universalapprovalcriteria",
    }
    if heading_key == normalized(pdf_path.stem) or heading_key in misleading:
        return inferred
    return raw_heading


def looks_like_revision_history(frame: Any, heading: str) -> bool:
    """Recognize clean and malformed policy revision-history tables."""
    columns = [normalized(column) for column in frame.columns]
    if "date" in columns and any(column in {"update", "updates"} for column in columns):
        return True

    heading_key = normalized(heading)
    if any(token in heading_key for token in ("revisionhistory", "changehistory")):
        return True

    if frame.shape[1] < 2:
        return False
    first_column = [str(frame.columns[0]), *frame.iloc[:, 0].fillna("").astype(str).tolist()]
    second_column = [str(frame.columns[1]), *frame.iloc[:, 1].fillna("").astype(str).tolist()]
    nonempty_dates = [value.strip() for value in first_column if value.strip()]
    if not nonempty_dates:
        return False
    date_ratio = sum(bool(DATE_RE.match(value)) for value in nonempty_dates) / len(nonempty_dates)
    change_ratio = sum(bool(CHANGE_RE.search(value)) for value in second_column) / max(
        1, len(second_column)
    )
    return date_ratio >= 0.6 and change_ratio >= 0.4


def standalone_html(
    *,
    source: str,
    heading: str,
    table_number: int,
    page_number: int | None,
    frame: Any,
) -> str:
    """Render one extracted table as a complete, self-contained HTML page."""
    table_html = frame.fillna("").to_html(
        index=False,
        border=0,
        classes=["policy-table"],
        justify="left",
        escape=True,
    )
    page_text = f"Page {page_number}" if page_number else "Page unavailable"
    title = f"{heading} - {source}"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #071f36;
      --muted: #5f6f7f;
      --line: #d6dee6;
      --header: #06233d;
      --header-ink: #ffffff;
      --stripe: #f4f7f9;
      --canvas: #edf2f6;
      --paper: #ffffff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--canvas);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
    }}
    main {{
      width: min(1440px, calc(100% - 32px));
      margin: 32px auto;
      padding: clamp(24px, 4vw, 56px);
      background: var(--paper);
      border-radius: 14px;
      box-shadow: 0 8px 28px rgba(7, 31, 54, 0.10);
    }}
    h1 {{
      margin: 0 0 10px;
      font-family: Georgia, "Times New Roman", serif;
      font-size: clamp(1.8rem, 4vw, 3rem);
      line-height: 1.1;
    }}
    .metadata {{ margin: 0 0 28px; color: var(--muted); }}
    .table-wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 10px; }}
    .policy-table {{ width: 100%; border-collapse: collapse; min-width: 680px; }}
    .policy-table th {{
      padding: 14px 16px;
      background: var(--header);
      color: var(--header-ink);
      text-align: left;
      vertical-align: top;
      font-weight: 700;
    }}
    .policy-table td {{
      padding: 13px 16px;
      border-top: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }}
    .policy-table tbody tr:nth-child(even) {{ background: var(--stripe); }}
    .note {{ margin: 24px 0 0; color: var(--muted); font-size: 0.9rem; }}
    @media print {{
      body {{ background: #fff; }}
      main {{ width: 100%; margin: 0; padding: 0; box-shadow: none; }}
      .table-wrap {{ overflow: visible; }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>{html.escape(heading)}</h1>
    <p class="metadata">Source: {html.escape(source)} &middot; Table {table_number} &middot; {page_text}</p>
    <div class="table-wrap">
      {table_html}
    </div>
    <p class="note">Extracted directly from the source PDF using embedded text with targeted OCR fallback where needed. Verify against the source policy before operational use.</p>
  </main>
</body>
</html>
"""


def extract_pdf(
    pdf_path: Path,
    output_dir: Path,
    converter: Any,
    fallback_converter: Any,
) -> dict[str, Any]:
    """Extract all non-revision tables from one PDF."""
    conversion = converter.convert(pdf_path)
    document = conversion.document
    require_embedded_text(document, pdf_path.name)
    ocr_used = False
    if any(table.export_to_dataframe(doc=document).shape == (0, 0) for table in document.tables):
        document = fallback_converter.convert(pdf_path).document
        ocr_used = True

    mapped_headings = heading_map(document, pdf_path)
    used_names: dict[str, int] = {}
    outputs: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for table_number, item in enumerate(document.tables, 1):
        frame = item.export_to_dataframe(doc=document)
        raw_heading = mapped_headings.get(str(item.self_ref)) or nearest_heading_by_position(
            document, item, pdf_path
        )
        heading = appropriate_heading(raw_heading, frame, pdf_path)
        page_number = item.prov[0].page_no if item.prov else None
        if looks_like_revision_history(frame, heading):
            excluded.append(
                {
                    "table_number": table_number,
                    "heading": heading,
                    "page": page_number,
                    "reason": "revision_history",
                }
            )
            continue

        # A policy title is often the only heading above the first table. Use a
        # schema-derived suffix to distinguish that table without fabricating a
        # source heading in the visible page.
        name_heading = heading
        if normalized(heading) == normalized(pdf_path.stem.replace("-", " ")):
            name_heading = f"{heading}-{infer_heading(frame)}"
        stem = f"{pdf_path.stem}_{slugify(name_heading)}"
        used_names[stem] = used_names.get(stem, 0) + 1
        suffix = "" if used_names[stem] == 1 else f"_{used_names[stem]}"
        output_path = output_dir / f"{stem}{suffix}.html"
        output_path.write_text(
            standalone_html(
                source=pdf_path.name,
                heading=heading,
                table_number=table_number,
                page_number=page_number,
                frame=frame,
            ),
            encoding="utf-8",
        )
        outputs.append(
            {
                "table_number": table_number,
                "heading": heading,
                "page": page_number,
                "rows": int(frame.shape[0]),
                "columns": int(frame.shape[1]),
                "html": output_path.name,
            }
        )

    return {
        "pdf": pdf_path.name,
        "status": "ok",
        "ocr_used": ocr_used,
        "tables_detected": len(document.tables),
        "tables_written": len(outputs),
        "tables_excluded": len(excluded),
        "outputs": outputs,
        "excluded": excluded,
    }


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
