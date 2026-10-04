#!/usr/bin/env python3
"""Compare table extraction by PyMuPDF and Docling on one PDF.

Run with the geha environment (it has both libraries):

    /Users/dc/geha/.venv/bin/python run_test.py [path/to/paper.pdf]

Writes, next to this script:
    pymupdf_lines/tables.md  PyMuPDF find_tables(strategy="lines")  (ruling lines)
    pymupdf_text/tables.md   PyMuPDF find_tables(strategy="text")   (word alignment)
    docling/tables.md        Docling table structure model
    docling/document.md      Docling's full-document Markdown
    */tables.json            per-table page, shape, caption and cells
    summary.json             counts and timings for all three
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pymupdf

HERE = Path(__file__).resolve().parent
PDF = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "data" / "1706.03762v7.pdf"


def write(name: str, tables: list[dict], extra: dict) -> dict:
    out = HERE / name
    out.mkdir(exist_ok=True)
    (out / "tables.json").write_text(json.dumps(tables, indent=2, ensure_ascii=False))
    md = [f"# {name}: {len(tables)} tables from {PDF.name}\n"]
    for i, t in enumerate(tables, 1):
        md.append(f"## Table {i} (page {t['page']}, {t['rows']}x{t['cols']})")
        if t.get("caption"):
            md.append(f"Caption: {t['caption']}\n")
        md.append(t["markdown"] + "\n")
    (out / "tables.md").write_text("\n".join(md))
    return {"tables": len(tables), **extra,
            "per_table": [{"page": t["page"], "shape": f"{t['rows']}x{t['cols']}",
                           "caption": (t.get("caption") or "")[:80]} for t in tables]}


def run_pymupdf(strategy: str) -> dict:
    started = time.perf_counter()
    tables = []
    with pymupdf.open(PDF) as doc:
        for page in doc:
            for tab in page.find_tables(strategy=strategy):
                cells = tab.extract()
                tables.append({
                    "page": page.number + 1,
                    "bbox": [round(v, 1) for v in tab.bbox],
                    "rows": tab.row_count,
                    "cols": tab.col_count,
                    "header": tab.header.names,
                    "markdown": tab.to_markdown(),
                    "cells": cells,
                })
    return write(f"pymupdf_{strategy}", tables,
                 {"seconds": round(time.perf_counter() - started, 2)})


def run_docling() -> dict:
    from docling.document_converter import DocumentConverter

    started = time.perf_counter()
    result = DocumentConverter().convert(str(PDF))
    doc = result.document
    seconds = round(time.perf_counter() - started, 2)
    tables = []
    for table in doc.tables:
        frame = table.export_to_dataframe(doc=doc)
        tables.append({
            "page": table.prov[0].page_no if table.prov else None,
            "rows": table.data.num_rows,
            "cols": table.data.num_cols,
            "caption": table.caption_text(doc),
            "markdown": table.export_to_markdown(doc=doc),
            "cells": [list(map(str, frame.columns))] + frame.astype(str).values.tolist(),
        })
    out = HERE / "docling"
    out.mkdir(exist_ok=True)
    (out / "document.md").write_text(doc.export_to_markdown())
    return write("docling", tables, {"seconds": seconds})


if __name__ == "__main__":
    summary = {"pdf": PDF.name, "pages": pymupdf.open(PDF).page_count}
    for strategy in ("lines", "text"):
        summary[f"pymupdf_{strategy}"] = run_pymupdf(strategy)
        print(f"pymupdf {strategy}: {summary[f'pymupdf_{strategy}']['tables']} tables", flush=True)
    summary["docling"] = run_docling()
    print(f"docling: {summary['docling']['tables']} tables", flush=True)
    (HERE / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk != "per_table"})
                      for k, v in summary.items()}, indent=2))
