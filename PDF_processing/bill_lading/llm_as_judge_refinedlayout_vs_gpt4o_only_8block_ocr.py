#!/usr/bin/env python3
"""Ask a vision LLM to judge the material old-vs-refined layout difference.

Run compare_layouts_visual.py first. This judge uses its header comparison PNG,
checks coordinate facts in Python, and saves the prompt and model response.
It does not modify either OCR script or create cargo rows.
"""

from __future__ import annotations

import argparse
import base64
import importlib.util
import json
from pathlib import Path

from openai import OpenAI


HERE = Path(__file__).resolve().parent
DEFAULT_OLD = HERE / "gpt4o_only_8block_ocr.py"
DEFAULT_REFINED = HERE / "vision_layout_run_retry_20261118" / "refined_layout.py"
DEFAULT_COMPARISON = HERE / "refined_ocr_test_20261118" / "visual_comparison"

JUDGE_PROMPT = """Inspect this side-by-side header image of the same bill-of-lading page.
The left panel uses the original OCR layout; the right panel uses the refined layout.
Red outlines mark blocks and blue outlines mark cells.

Measured coordinate facts (do not infer other differences):
- All {block_count} red block boxes have exactly the same coordinates.
- {near_equal_cells} of {cell_count} cells differ by at most 2 pixels.
- The material difference is the vertical blue split between carrier_header and
  bill_of_lading_box: original page x={old_split}, refined page x={new_split}.

Using the image, identify which blue split lies closer to the printed black left
border of the BILL OF LADING box. State whether either blue split crosses the
words MERIDIAN SHIPPING or BILL OF LADING. Restrict your answer to the header;
the supplied image cannot establish extraction accuracy or cargo-row correctness.
Return JSON with keys preferred_split (original/refined/tie/unclear),
printed_border_alignment, text_crossing, and uncertainty."""


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def image_url(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def coordinate_facts(old, refined) -> dict:
    if set(old.BLOCKS) != set(refined.BLOCKS):
        raise ValueError("Block numbers differ")
    block_count = len(old.BLOCKS)
    blocks_equal = all(old.BLOCKS[n] == refined.BLOCKS[n] for n in old.BLOCKS)
    if not blocks_equal:
        raise ValueError("This focused judge expects identical block boxes")
    differences = []
    for number, old_cells in old.CELLS.items():
        if set(old_cells) != set(refined.CELLS[number]):
            raise ValueError(f"Cell names differ in block {number}")
        for name, old_box in old_cells.items():
            new_box = refined.CELLS[number][name]
            delta = max(abs(a - b) for a, b in zip(old_box, new_box))
            differences.append({"block": number, "cell": name, "max_pixel_delta": delta})
    old_split = old.BLOCKS[1][0] + old.CELLS[1]["carrier_header"][2]
    new_split = refined.BLOCKS[1][0] + refined.CELLS[1]["carrier_header"][2]
    if old_split == new_split:
        raise ValueError("No header split difference to judge")
    return {
        "block_count": block_count,
        "blocks_equal": blocks_equal,
        "cell_count": len(differences),
        "near_equal_cells": sum(item["max_pixel_delta"] <= 2 for item in differences),
        "original_header_split_x": old_split,
        "refined_header_split_x": new_split,
        "cell_differences": differences,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-layout", type=Path, default=DEFAULT_OLD)
    parser.add_argument("--refined-layout", type=Path, default=DEFAULT_REFINED)
    parser.add_argument("--comparison-dir", type=Path, default=DEFAULT_COMPARISON)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--model", default="gpt-4o")
    args = parser.parse_args()
    header_png = args.comparison_dir / "header_comparison.png"
    if not header_png.is_file():
        parser.error(f"Missing {header_png}; run compare_layouts_visual.py first")
    old = load_module("original_layout", args.old_layout)
    refined = load_module("refined_layout", args.refined_layout)
    facts = coordinate_facts(old, refined)
    prompt = JUDGE_PROMPT.format(
        block_count=facts["block_count"],
        near_equal_cells=facts["near_equal_cells"],
        cell_count=facts["cell_count"],
        old_split=facts["original_header_split_x"],
        new_split=facts["refined_header_split_x"],
    )
    response = OpenAI(max_retries=2, timeout=180).responses.create(
        model=args.model, store=False,
        instructions="You are a careful visual QA reviewer of document crop boundaries.",
        input=[{"role": "user", "content": [
            {"type": "input_text", "text": prompt},
            {"type": "input_image", "image_url": image_url(header_png), "detail": "high"},
        ]}],
        text={"format": {"type": "json_object"}},
    )
    review = json.loads(response.output_text)
    result = {
        "model": args.model,
        "response_id": response.id,
        "header_image": str(header_png.resolve()),
        "old_layout": str(args.old_layout.resolve()),
        "refined_layout": str(args.refined_layout.resolve()),
        "prompt": prompt,
        "coordinate_facts": facts,
        "vision_review": review,
    }
    output = args.output or args.comparison_dir / "llm_judge.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(output)
    print(json.dumps(review, indent=2))


if __name__ == "__main__":
    main()
