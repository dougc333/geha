"""Export LlamaParse table items as one CSV per logical table."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables-jsonl", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    tables = [
        json.loads(line)
        for line in args.tables_jsonl.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    page_indexes: Counter[int] = Counter()
    manifest: list[dict[str, object]] = []

    for table in tables:
        page = int(table["page_number"])
        merged_into = table.get("merged_into_page")
        if merged_into is not None:
            manifest.append(
                {
                    "page_number": page,
                    "merged_into_page": int(merged_into),
                    "csv_file": None,
                    "status": "merged_fragment",
                }
            )
            continue

        csv_text = str(table.get("csv") or "").strip()
        if not csv_text:
            manifest.append(
                {
                    "page_number": page,
                    "csv_file": None,
                    "status": "empty",
                }
            )
            continue

        page_indexes[page] += 1
        merged_pages = [int(value) for value in table.get("merged_from_pages") or []]
        suffix = ""
        if len(merged_pages) > 1:
            suffix = f"_pages-{min(merged_pages):03d}-{max(merged_pages):03d}"
        filename = f"page-{page:03d}_table-{page_indexes[page]:03d}{suffix}.csv"
        (args.output_dir / filename).write_text(csv_text + "\n", encoding="utf-8")

        rows = table.get("rows") or []
        manifest.append(
            {
                "page_number": page,
                "item_number": table.get("item_number"),
                "csv_file": filename,
                "status": "exported",
                "row_count": len(rows),
                "column_count": max((len(row) for row in rows), default=0),
                "merged_from_pages": merged_pages,
                "parse_concerns": table.get("parse_concerns") or [],
            }
        )

    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    exported = sum(record["status"] == "exported" for record in manifest)
    fragments = sum(record["status"] == "merged_fragment" for record in manifest)
    print(f"Exported {exported} logical tables; skipped {fragments} merged fragments")


if __name__ == "__main__":
    main()
