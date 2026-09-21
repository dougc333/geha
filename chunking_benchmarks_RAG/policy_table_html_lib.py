"""Reusable PDF-to-HTML table extraction with nearby headings.

The extractor reads each PDF directly with Docling, disables OCR, associates
each table with the closest preceding title/section heading in document order,
and omits revision-history/change-log tables. Each output is a complete HTML
document with embedded CSS and can be opened directly in a browser.
"""

from __future__ import annotations

import html
import re
import unicodedata
from pathlib import Path
from typing import Any

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

try:  # Support package imports and direct script execution.
    from .pdf_conversion import native_text_converter, require_embedded_text
except ImportError:  # pragma: no cover - direct script execution
    from pdf_conversion import native_text_converter, require_embedded_text


HEADING_LABELS = {"caption", "section_header", "title"}
GENERIC_HEADINGS = {
    "corporate medical policy",
    "for internal use only",
    "g.e.h.a",
    "geha",
}
KNOWN_COLUMN_HEADERS = {
    "preference",
    "requirespriorauth",
    "drugname",
    "hcpcscode",
    "cpthcpcscode",
    "cpthcpcscodes",
    "description",
    "date",
    "update",
    "updates",
    "ndc",
    "ndccode",
    "productname",
    "brandname",
    "genericname",
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


def promote_embedded_header(frame: Any) -> tuple[Any, bool]:
    """Promote a recognizable first row when Docling supplies 0, 1, 2 columns.

    Numeric column names alone are insufficient: the candidate header must be
    nonempty, unique, and contain multiple known policy-table column labels.
    Return a new frame so the raw Docling output remains available for review.
    """
    column_count = frame.shape[1]
    if frame.shape[0] < 2 or column_count < 2:
        return frame, False
    if [str(column).strip() for column in frame.columns] != [
        str(index) for index in range(column_count)
    ]:
        return frame, False

    candidate = [str(value).strip() for value in frame.iloc[0].fillna("")]
    keys = [normalized(value) for value in candidate]
    if not all(candidate) or len(set(keys)) != column_count:
        return frame, False
    recognized = sum(key in KNOWN_COLUMN_HEADERS for key in keys)
    if recognized < max(2, (column_count + 1) // 2):
        return frame, False

    repaired = frame.iloc[1:].copy().reset_index(drop=True)
    repaired.columns = candidate
    return repaired, True


def inherit_continuation_header(
    frame: Any,
    previous_frame: Any | None,
    *,
    heading: str,
    previous_heading: str | None,
    page_number: int | None,
    previous_page: int | None,
) -> tuple[Any, bool]:
    """Carry a prior table's schema to an unlabeled next-page fragment.

    A numeric or data-valued DataFrame header alone is not evidence of a
    continuation. Require adjacent pages, the same non-generic section heading,
    matching column count, and recognizable named columns on the prior table.
    If Docling used the first billing data row as column names, restore that row.
    """
    if previous_frame is None or previous_frame.empty or frame.shape[1] == 0:
        return frame, False
    if (
        not isinstance(page_number, int)
        or not isinstance(previous_page, int)
        or page_number != previous_page + 1
        or not heading
        or normalized(heading) in {"table", "extractedtable"}
        or normalized(heading) != normalized(previous_heading)
        or frame.shape[1] != previous_frame.shape[1]
    ):
        return frame, False
    prior_labels = [str(column).strip() for column in previous_frame.columns]
    prior_keys = [normalized(label) for label in prior_labels]
    if (
        not all(prior_labels)
        or len(set(prior_keys)) != len(prior_keys)
        or sum(key in KNOWN_COLUMN_HEADERS for key in prior_keys) < 2
    ):
        return frame, False
    current_labels = [str(column).strip() for column in frame.columns]
    numeric_labels = current_labels == [str(index) for index in range(frame.shape[1])]
    if numeric_labels:
        if frame.empty:
            return frame, False
        first_row_keys = [normalized(value) for value in frame.iloc[0].fillna("")]
        if sum(key in KNOWN_COLUMN_HEADERS for key in first_row_keys) >= 2:
            return frame, False
        inherited = frame.copy()
        inherited.columns = previous_frame.columns.copy()
        return inherited, True

    # A headerless billing fragment may be parsed with its first *data* row as
    # column names. Require a code in the prior code column before restoring it.
    code_positions = [
        index for index, key in enumerate(prior_keys)
        if key in {"hcpcscode", "cpthcpcscode", "cpthcpcscodes"}
    ]
    if not code_positions or not all(current_labels):
        return frame, False
    if sum(normalized(label) in KNOWN_COLUMN_HEADERS for label in current_labels) >= 2:
        return frame, False
    if not any(re.fullmatch(r"[A-Z]\d{4}", current_labels[index], re.IGNORECASE)
               for index in code_positions):
        return frame, False
    restored_rows = [current_labels, *frame.itertuples(index=False, name=None)]
    inherited = frame.__class__(restored_rows, columns=prior_labels)
    return inherited, True


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
    previous_frame: Any | None = None
    previous_heading: str | None = None
    previous_page: int | None = None
    previous_table_number: int | None = None

    for table_number, item in enumerate(document.tables, 1):
        frame = item.export_to_dataframe(doc=document)
        frame, header_promoted = promote_embedded_header(frame)
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
            previous_frame = None
            previous_heading = None
            previous_page = None
            previous_table_number = None
            continue

        frame, header_inherited = inherit_continuation_header(
            frame,
            previous_frame,
            heading=heading,
            previous_heading=previous_heading,
            page_number=page_number,
            previous_page=previous_page,
        )

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
                "header_promoted": header_promoted,
                "header_inherited_from_table": previous_table_number if header_inherited else None,
                "html": output_path.name,
            }
        )
        previous_frame = frame
        previous_heading = heading
        previous_page = page_number
        previous_table_number = table_number

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
