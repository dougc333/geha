"""Build exact-code evals from top-level GEHA Docling billing tables."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

try:
    from .billing_code_data import docling_billing_rows
except ImportError:  # pragma: no cover - direct CLI execution
    from billing_code_data import docling_billing_rows


ROOT = Path(__file__).resolve().parents[1] / "downloads" / "coverage-policies"
OUTPUT = Path(__file__).with_name("billing_code_evals.json")


def generate(root: Path = ROOT) -> dict:
    documents = []
    cases = []
    for markdown in sorted(root.glob("*.docling.md")):
        source = markdown.name.removesuffix(".docling.md") + ".pdf"
        grouped = defaultdict(lambda: {"items": [], "source_lines": [], "raw_code_cells": []})
        for row in docling_billing_rows(markdown):
            entry = grouped[(row["code"], row["table_name"])]
            if row["item_name"] and row["item_name"] not in entry["items"]:
                entry["items"].append(row["item_name"])
            entry["source_lines"].append(row["line"])
            if row["raw_code_cell"] not in entry["raw_code_cells"]:
                entry["raw_code_cells"].append(row["raw_code_cell"])
        documents.append({
            "source_document": source,
            "docling_markdown": markdown.name,
            "billing_code_count": len(grouped),
            "has_billing_code_table": bool(grouped),
        })
        for (code, table_name), details in sorted(grouped.items()):
            cases.append({
                "id": f"{markdown.stem.removesuffix('.docling')}-{code.lower()}",
                "query": code,
                "billing_code": code,
                "source_document": source,
                "docling_markdown": markdown.name,
                "table_name": table_name,
                "expected_answer": (
                    f"Billing Code: {code}; Source document: {source}; Table: {table_name}"
                ),
                **details,
            })
    return {
        "purpose": "Exact billing-code search must return every matching source document and its code table, without vector ranking.",
        "source_scope": "Top-level downloads/coverage-policies/*.docling.md only",
        "documents": documents,
        "cases": cases,
    }


def main() -> None:
    fixture = generate()
    OUTPUT.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"Wrote {len(fixture['cases'])} code cases from {len(fixture['documents'])} "
        f"Docling documents to {OUTPUT}"
    )


if __name__ == "__main__":
    main()
