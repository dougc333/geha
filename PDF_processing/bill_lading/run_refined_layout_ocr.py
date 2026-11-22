#!/usr/bin/env python3
"""Run the existing GPT-4o OCR with a separate refined layout, without editing it."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ORIGINAL = HERE / "gpt4o_only_8block_ocr.py"
DEFAULT_LAYOUT = HERE / "vision_layout_run_retry_20261118" / "refined_layout.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page-png", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--layout", type=Path, default=DEFAULT_LAYOUT)
    parser.add_argument("--model", default="gpt-4o")
    args = parser.parse_args()
    if not args.page_png.is_file():
        parser.error(f"Page image not found: {args.page_png}")
    if not args.layout.is_file():
        parser.error(f"Layout not found: {args.layout}")
    if args.output_root.exists() and any(args.output_root.iterdir()):
        parser.error(f"Output root must be empty to preserve previous runs: {args.output_root}")

    original = load_module("bol_original_ocr", ORIGINAL)
    layout = load_module("bol_refined_layout", args.layout)
    if set(original.BLOCKS) != set(layout.BLOCKS):
        parser.error("Refined layout has different block numbers")
    for number in original.BLOCKS:
        if set(original.CELLS[number]) != set(layout.CELLS[number]):
            parser.error(f"Refined layout has different cell names in block {number}")

    # Replace only module variables in this process. The source file remains untouched.
    original.BLOCKS = layout.BLOCKS
    original.CELLS = layout.CELLS
    previous_argv = sys.argv
    sys.argv = [str(ORIGINAL), "--page-png", str(args.page_png),
                "--output-root", str(args.output_root), "--model", args.model]
    try:
        original.main()
    finally:
        sys.argv = previous_argv

    runs = list(args.output_root.glob("gpt4o_only_run_*/gpt4o_only_results.json"))
    if len(runs) != 1:
        raise RuntimeError(f"Expected one OCR run, found {len(runs)} under {args.output_root}")
    provenance = {
        "ocr_script": str(ORIGINAL.resolve()),
        "ocr_script_sha256": sha256(ORIGINAL),
        "layout": str(args.layout.resolve()),
        "layout_sha256": sha256(args.layout),
        "page_png": str(args.page_png.resolve()),
        "page_png_sha256": sha256(args.page_png),
        "original_script_modified": False,
    }
    (runs[0].parent / "layout_provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n")
    print(f"Refined-layout OCR results: {runs[0]}")


if __name__ == "__main__":
    main()
