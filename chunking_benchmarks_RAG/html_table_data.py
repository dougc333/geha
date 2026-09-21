"""Read the reviewed, one-table-per-file GEHA HTML extraction artifacts."""

from __future__ import annotations

import html
import re
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd

HTML_TABLE_DIR = "html_tables"


def _plain_text(markup: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", markup)).split())


def _cell_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def parse_html_table(path: Path) -> dict[str, Any]:
    """Parse one reviewed standalone HTML table into retrieval-ready fields."""
    document = path.read_text(encoding="utf-8")
    table_match = re.search(r"<table\b[^>]*>.*?</table>", document, re.IGNORECASE | re.DOTALL)
    if not table_match:
        raise ValueError(f"No HTML table found in {path}")

    title_match = re.search(r"<h1\b[^>]*>(.*?)</h1>", document, re.IGNORECASE | re.DOTALL)
    metadata_match = re.search(
        r"<p\b[^>]*class=[\"'][^\"']*metadata[^\"']*[\"'][^>]*>(.*?)</p>",
        document,
        re.IGNORECASE | re.DOTALL,
    )
    title = _plain_text(title_match.group(1)) if title_match else path.stem
    metadata = _plain_text(metadata_match.group(1)) if metadata_match else ""
    source_match = re.search(r"\bSource:\s*(.+?\.pdf)\b", metadata, re.IGNORECASE)
    table_number_match = re.search(r"\bTable\s+(\d+)\b", metadata, re.IGNORECASE)
    page_match = re.search(r"\bPage\s+(\d+)\b", metadata, re.IGNORECASE)
    if not source_match or not table_number_match:
        raise ValueError(f"Missing source/table metadata in {path}")

    frames = pd.read_html(StringIO(table_match.group(0)))
    if len(frames) != 1:
        raise ValueError(f"Expected exactly one table in {path}, found {len(frames)}")
    frame = frames[0]
    headers = [_cell_text(column) for column in frame.columns]
    rows = [[_cell_text(value) for value in row] for row in frame.itertuples(index=False)]
    numeric_headers = headers == [str(index) for index in range(len(headers))]
    if numeric_headers and rows:
        promoted = {re.sub(r"[^a-z0-9]", "", value.casefold()) for value in rows[0]}
        if promoted & {"preference", "drugname", "hcpcscode", "requirespriorauth"}:
            headers, rows = rows[0], rows[1:]
    records = [dict(zip(headers, row, strict=True)) for row in rows]
    return {
        "source": source_match.group(1),
        "table_number": int(table_number_match.group(1)),
        "page": int(page_match.group(1)) if page_match else None,
        "title": title,
        "headers": headers,
        "rows": rows,
        "rows_json": records,
        "full_html": table_match.group(0),
        "path": path,
    }


def load_policy_html_tables(input_dir: Path) -> list[dict[str, Any]]:
    """Load reviewed tables from ``input_dir/html_tables`` with unique identities."""
    table_dir = input_dir / HTML_TABLE_DIR
    paths = sorted(table_dir.glob("*.html"))
    if not paths:
        raise FileNotFoundError(f"No HTML table files found in {table_dir}")
    tables = [parse_html_table(path) for path in paths]
    identities: set[tuple[str, int]] = set()
    for table in tables:
        identity = (table["source"], table["table_number"])
        if identity in identities:
            raise ValueError(f"Duplicate HTML table identity {identity}")
        identities.add(identity)
    return tables
