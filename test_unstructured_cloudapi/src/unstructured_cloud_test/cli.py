"""Command-line entry point for testing managed document extraction."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from .client import DEFAULT_API_URL, extract_document


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract document elements with the Unstructured managed API."
    )
    parser.add_argument("document", type=Path, help="PDF, image, DOCX, or other input document")
    parser.add_argument("--output", "-o", type=Path, help="JSON output path")
    parser.add_argument(
        "--strategy",
        choices=("auto", "fast", "hi_res", "ocr_only", "vlm"),
        default="hi_res",
    )
    parser.add_argument(
        "--no-table-structure",
        action="store_true",
        help="Disable table-structure inference",
    )
    parser.add_argument(
        "--api-url",
        help="Override UNSTRUCTURED_API_URL for this invocation",
    )
    return parser


def main() -> None:
    load_dotenv()
    args = build_parser().parse_args()

    api_key = os.environ.get("UNSTRUCTURED_API_KEY", "")
    api_url = args.api_url or os.environ.get("UNSTRUCTURED_API_URL", DEFAULT_API_URL)
    output = args.output or Path("results") / f"{args.document.stem}.elements.json"

    elements = extract_document(
        args.document,
        api_key=api_key,
        api_url=api_url,
        strategy=args.strategy,
        infer_table_structure=not args.no_table_structure,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(elements, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    type_counts: dict[str, int] = {}
    for element in elements:
        element_type = str(element.get("type", "Unknown"))
        type_counts[element_type] = type_counts.get(element_type, 0) + 1

    print(f"Extracted {len(elements)} elements to {output.resolve()}")
    print("Element types:", json.dumps(type_counts, sort_keys=True))


if __name__ == "__main__":
    main()

