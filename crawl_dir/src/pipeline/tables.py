"""Canonical table extraction and multi-page consolidation."""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
from bs4 import BeautifulSoup

from .table_extraction import (
    extract_pdf,
    native_text_converter,
    ocr_table_converter,
    standalone_html,
)


def merge_table_fragments(
    outputs: list[dict[str, Any]], frames: dict[int, pd.DataFrame]
) -> list[dict[str, Any]]:
    """Combine verified continuation fragments into logical parent tables."""
    logical: list[dict[str, Any]] = []
    table_to_logical: dict[int, int] = {}
    for output in outputs:
        number = int(output["table_number"])
        frame = frames[number]
        inherited_from = output.get("header_inherited_from_table")
        if inherited_from is not None and int(inherited_from) in table_to_logical:
            logical_index = table_to_logical[int(inherited_from)]
            target = logical[logical_index]
            target["frame"] = pd.concat([target["frame"], frame], ignore_index=True)
            target["source_pages"].append(int(output["page"]))
            target["source_table_numbers"].append(number)
            target["repairs"].append(f"inherited_header_from_table_{int(inherited_from)}")
            table_to_logical[number] = logical_index
            continue
        table_to_logical[number] = len(logical)
        logical.append({
            "section": str(output["heading"]),
            "source_pages": [int(output["page"])] if output.get("page") else [],
            "source_table_numbers": [number],
            "repairs": ["promoted_embedded_header"] if output.get("header_promoted") else [],
            "frame": frame.copy(),
        })
    return logical


def extract_logical_tables(
    pdf_path: Path,
    fragments_dir: Path,
    tables_dir: Path,
    *,
    document_id: str,
    document_version: str,
    plan_year: int | None,
    start_ordinal: int = 1,
    source_page_map: dict[int, int] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fragments_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    result = extract_pdf(
        pdf_path, fragments_dir, native_text_converter(), ocr_table_converter()
    )
    frames: dict[int, pd.DataFrame] = {}
    for output in result["outputs"]:
        html_path = fragments_dir / output["html"]
        frames[int(output["table_number"])] = pd.read_html(StringIO(html_path.read_text()))[0]
    logical = merge_table_fragments(result["outputs"], frames)
    records: list[dict[str, Any]] = []
    for ordinal, item in enumerate(logical, start_ordinal):
        if source_page_map:
            item["source_pages"] = [
                source_page_map.get(page, page) for page in item["source_pages"]
            ]
        table_id = f"table-{ordinal:03d}"
        frame = item.pop("frame")
        record = {
            "table_id": table_id,
            "document_id": document_id,
            "document_version": document_version,
            "plan_year": plan_year,
            **item,
            "headers": [str(value) for value in frame.columns],
            "rows": [
                {str(key): str(value) for key, value in row.items()}
                for row in frame.fillna("").to_dict(orient="records")
            ],
            "review_status": "pending",
        }
        (tables_dir / f"{table_id}.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (tables_dir / f"{table_id}.html").write_text(
            standalone_html(
                source=pdf_path.name,
                heading=record["section"],
                table_number=ordinal,
                page_number=record["source_pages"][0] if record["source_pages"] else None,
                frame=frame,
            ),
            encoding="utf-8",
        )
        records.append(record)
    return records, result


def extract_logical_tables_from_html(
    page_html: list[tuple[int, Path]],
    tables_dir: Path,
    *,
    document_id: str,
    document_version: str,
    plan_year: int | None,
    start_ordinal: int = 1,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Extract structured tables from page HTML that already passed visual review."""
    tables_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    ordinal = start_ordinal
    for page_number, html_path in page_html:
        source_html = html_path.read_text(encoding="utf-8")
        soup = BeautifulSoup(source_html, "lxml")
        page_tables = [table for table in soup.find_all("table")
                       if table.find_parent("table") is None]
        for page_table_number, table in enumerate(page_tables, 1):
            frames = pd.read_html(StringIO(str(table)))
            if not frames:
                continue
            frame = frames[0].fillna("")
            if frame.empty and frame.shape[1] == 0:
                continue
            if isinstance(frame.columns, pd.MultiIndex):
                frame.columns = [" | ".join(
                    str(part) for part in column if str(part) and not str(part).startswith("Unnamed:")
                ) or f"column_{index + 1}" for index, column in enumerate(frame.columns)]
            else:
                frame.columns = [
                    str(column) if not str(column).startswith("Unnamed:") else f"column_{index + 1}"
                    for index, column in enumerate(frame.columns)
                ]
            heading_tag = table.find_previous(["h1", "h2", "h3", "h4", "h5", "h6"])
            caption = table.find("caption")
            section = ((caption or heading_tag).get_text(" ", strip=True)
                       if caption or heading_tag else f"Page {page_number} table {page_table_number}")
            table_id = f"table-{ordinal:03d}"
            record = {
                "table_id": table_id,
                "document_id": document_id,
                "document_version": document_version,
                "plan_year": plan_year,
                "section": section,
                "source_pages": [page_number],
                "source_table_numbers": [page_table_number],
                "repairs": [],
                "headers": [str(value) for value in frame.columns],
                "rows": [
                    {str(key): str(value) for key, value in row.items()}
                    for row in frame.to_dict(orient="records")
                ],
                "review_status": "pending",
                "extraction_source": "visually_verified_html",
            }
            (tables_dir / f"{table_id}.json").write_text(
                json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            (tables_dir / f"{table_id}.html").write_text(
                standalone_html(
                    source=html_path.name,
                    heading=section,
                    table_number=ordinal,
                    page_number=page_number,
                    frame=frame,
                    note=("Extracted from semantic HTML after visual verification against the "
                          "source PDF page. Verify before operational use."),
                ),
                encoding="utf-8",
            )
            records.append(record)
            outputs.append({
                "table_id": table_id,
                "page": page_number,
                "page_table_number": page_table_number,
                "rows": int(frame.shape[0]),
                "columns": int(frame.shape[1]),
                "source_html": str(html_path),
            })
            ordinal += 1
    return records, {
        "source": "visually_verified_html",
        "outputs": outputs,
        "table_count": len(records),
    }
