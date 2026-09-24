"""Browser-ready HTML for *raw* extracted tables; no structural repairs.

The CSS follows the existing extract_pdf_tables_html.py style. This module
deliberately does not infer headings, promote data rows into headers, inherit
headers across pages, join fragments, or omit revision-history tables.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Iterable


# Same visual design as the earlier extract_pdf_tables_html.py, shared by the
# single-table and combined-document raw previews.
RAW_TABLE_CSS = """
    :root {
      color-scheme: light;
      --ink: #071f36;
      --muted: #5f6f7f;
      --line: #d6dee6;
      --header: #06233d;
      --header-ink: #ffffff;
      --stripe: #f4f7f9;
      --canvas: #edf2f6;
      --paper: #ffffff;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--canvas);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
    }
    main {
      width: min(1440px, calc(100% - 32px));
      margin: 32px auto;
      padding: clamp(24px, 4vw, 56px);
      background: var(--paper);
      border-radius: 14px;
      box-shadow: 0 8px 28px rgba(7, 31, 54, 0.10);
    }
    h1 {
      margin: 0 0 10px;
      font-family: Georgia, "Times New Roman", serif;
      font-size: clamp(1.8rem, 4vw, 3rem);
      line-height: 1.1;
    }
    .metadata { margin: 0 0 28px; color: var(--muted); }
    .table-source { margin: 0 0 12px; color: var(--muted); font-size: 0.78rem; line-height: 1.35; }
    .table-source code, .metadata code { overflow-wrap: anywhere; }
    .table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 10px; }
    .policy-table { width: 100%; border-collapse: collapse; min-width: 680px; }
    .policy-table th {
      padding: 14px 16px;
      background: var(--header);
      color: var(--header-ink);
      text-align: left;
      vertical-align: top;
      font-weight: 700;
    }
    .policy-table td {
      padding: 13px 16px;
      border-top: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      overflow-wrap: anywhere;
    }
    .policy-table tbody tr:nth-child(even) { background: var(--stripe); }
    .raw-section { margin: 36px 0; }
    .raw-section h2 { margin: 0 0 12px; }
    .note { margin: 24px 0 0; color: var(--muted); font-size: 0.9rem; }
    @media print {
      body { background: #fff; }
      main { width: 100%; margin: 0; padding: 0; box-shadow: none; }
      .table-wrap { overflow: visible; }
    }
"""


def raw_table_markup(columns: list[str], rows: list[list[str]]) -> str:
    """Create table markup without inferring or changing header semantics."""
    import pandas as pd

    if any(len(row) != len(columns) for row in rows):
        raise ValueError("Extracted table rows have inconsistent column counts")
    frame = pd.DataFrame(rows, columns=columns)
    return frame.to_html(
        index=False, na_rep="", border=0, classes=["policy-table"],
        justify="left", escape=True,
    )


def combined_raw_html(
    source: str,
    extractor: str,
    tables: list[dict[str, Any]],
    *,
    html_path: str | None = None,
    pdf_path: str | None = None,
) -> str:
    """One self-contained HTML file with every raw table from one extractor."""
    if extractor not in {"pdfplumber", "docling"}:
        raise ValueError(f"Unknown extractor: {extractor}")
    sections: list[str] = []
    for table in tables:
        if table["extractor"] != extractor:
            raise ValueError("Mixed extractor tables")
        number = int(table["number"])
        page = int(table["page"])
        nearest_heading = table.get("nearest_heading") or ""
        markup = raw_table_markup(table["columns"], table["rows"])
        sections.append(
            f'<section class="raw-section" id="table-{number}" '
            f'data-page="{page}">\n'
            f'  <h2>{html.escape(extractor)} table {number} · PDF page {page}</h2>\n'
            f'  <p class="table-source">Nearest heading: '
            f'<strong>{html.escape(nearest_heading or "none")}</strong></p>\n'
            f'  <p class="table-source">HTML source: '
            f'<code>{html.escape(html_path or "(in-memory)")}</code><br>'
            f'PDF source: <code>{html.escape(pdf_path or source)}</code> · '
            f'PDF page: {page}</p>\n'
            f'  <div class="table-wrap">{markup}</div>\n'
            f'</section>'
        )
    body = "\n".join(sections) or "<p>No tables were extracted.</p>"
    title = f"Raw {extractor} tables - {source}"
    source_line = (
        f'HTML source: <code>{html.escape(html_path)}</code> · '
        if html_path else ""
    )
    pdf_line = f'PDF source: <code>{html.escape(pdf_path)}</code> · ' if pdf_path else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>{RAW_TABLE_CSS}</style>
</head>
<body>
  <main>
    <h1>{html.escape(title)}</h1>
    <p class="metadata">{source_line}{pdf_line}Extractor: {html.escape(extractor)}
      · {len(tables)} raw table(s)</p>
    {body}
    <p class="note">Uncorrected first-pass extraction. Numeric column names,
      split tables, and missing headers are intentionally preserved for review
      against the source PDF.</p>
  </main>
</body>
</html>
"""


def table_filename(pdf_path: Path, extractor: str, number: int, page: int) -> str:
    if extractor not in {"pdfplumber", "docling"}:
        raise ValueError(f"Unknown extractor: {extractor}")
    return f"{pdf_path.stem}_{extractor}_table_{number:03d}_page_{page}.html"


def standalone_raw_html(
    *, source: str, extractor: str, number: int, page: int, frame: Any,
) -> str:
    """Format a DataFrame without changing its columns or cell positions."""
    title = f"Raw {extractor} table {number}"
    table_html = frame.to_html(
        index=False, na_rep="", border=0, classes=["policy-table"],
        justify="left", escape=True,
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} - {html.escape(source)}</title>
  <style>{RAW_TABLE_CSS}</style>
</head>
<body>
  <main>
    <h1>{html.escape(title)}</h1>
    <p class="metadata">Source: {html.escape(source)} &middot; Page {page}
      &middot; Table {number} &middot; Extractor: {html.escape(extractor)}</p>
    <div class="table-wrap">
      {table_html}
    </div>
    <p class="note">Uncorrected first-pass extraction. Numeric column names,
      split tables, and missing headers are intentionally preserved for review
      against the source PDF.</p>
  </main>
</body>
</html>
"""


def save_raw_tables(
    pdf_path: Path, output_dir: Path, extractor: str,
    tables: Iterable[tuple[int, Any]],
) -> list[Path]:
    """Write one self-contained HTML file per table, never overwriting files."""
    numbered = [(number, page, frame) for number, (page, frame) in enumerate(tables, 1)]
    paths = [
        output_dir / table_filename(pdf_path, extractor, number, page)
        for number, page, _frame in numbered
    ]
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        raise FileExistsError(f"Raw HTML already exists; no files changed: {', '.join(existing)}")
    output_dir.mkdir(parents=True, exist_ok=True)
    for path, (number, page, frame) in zip(paths, numbered):
        with path.open("x", encoding="utf-8") as output:
            output.write(standalone_raw_html(
                source=pdf_path.name, extractor=extractor, number=number,
                page=page, frame=frame,
            ))
    return paths
