"""Run a whole-document LlamaParse table extraction test."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llama_cloud import LlamaCloud


def as_json(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--tier", default="agentic")
    args = parser.parse_args()

    api_key = os.environ.get("LLAMA_CLOUD_API_KEY", "")
    if not api_key:
        raise SystemExit("LLAMA_CLOUD_API_KEY is not set")
    if not args.input.is_file():
        raise SystemExit(f"Input PDF does not exist: {args.input}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    request = {
        "input": str(args.input),
        "tier": args.tier,
        "version": "latest",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "output_options": {
            "markdown": {
                "tables": {
                    "output_tables_as_markdown": False,
                    "merge_continued_tables": True,
                    "compact_markdown_tables": True,
                }
            },
            "tables_as_spreadsheet": {
                "enable": True,
                "guess_sheet_name": True,
            },
            "granular_bboxes": ["cell"],
        },
        "expand": ["markdown", "items", "xlsx_content_metadata"],
    }
    (args.output_dir / "request.json").write_text(
        json.dumps(request, indent=2) + "\n", encoding="utf-8"
    )

    client = LlamaCloud(api_key=api_key)
    uploaded = client.files.create(file=str(args.input), purpose="parse")
    (args.output_dir / "upload.json").write_text(
        json.dumps({"file_id": str(uploaded.id)}, indent=2) + "\n",
        encoding="utf-8",
    )

    result = client.parsing.parse(
        file_id=uploaded.id,
        tier=args.tier,
        version="latest",
        output_options=request["output_options"],
        expand=request["expand"],
        timeout=7200,
        verbose=True,
    )
    raw = as_json(result)
    (args.output_dir / "response.json").write_text(
        json.dumps(raw, indent=2) + "\n", encoding="utf-8"
    )

    markdown_pages = getattr(getattr(result, "markdown", None), "pages", None) or []
    markdown_dir = args.output_dir / "pages"
    markdown_dir.mkdir(exist_ok=True)
    for fallback_page, page in enumerate(markdown_pages, start=1):
        page_number = int(getattr(page, "page_number", fallback_page))
        markdown = str(getattr(page, "markdown", ""))
        (markdown_dir / f"page-{page_number:03d}.md").write_text(
            markdown.rstrip() + "\n", encoding="utf-8"
        )

    item_pages = getattr(getattr(result, "items", None), "pages", None) or []
    tables: list[dict[str, Any]] = []
    concern_count = 0
    for fallback_page, page in enumerate(item_pages, start=1):
        page_number = int(getattr(page, "page_number", fallback_page))
        for item_number, item in enumerate(getattr(page, "items", None) or [], start=1):
            if getattr(item, "type", None) != "table":
                continue
            record = as_json(item)
            record["page_number"] = page_number
            record["item_number"] = item_number
            concerns = record.get("parse_concerns") or []
            concern_count += len(concerns)
            tables.append(record)

    with (args.output_dir / "tables.jsonl").open("w", encoding="utf-8") as output:
        for table in tables:
            output.write(json.dumps(table, ensure_ascii=False) + "\n")

    summary = {
        "status": "complete",
        "input": str(args.input),
        "tier": args.tier,
        "pages_returned": len(markdown_pages),
        "tables_returned": len(tables),
        "table_parse_concerns": concern_count,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
