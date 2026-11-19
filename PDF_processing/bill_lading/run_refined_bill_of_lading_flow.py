#!/usr/bin/env python3
"""Run saved refined-layout OCR through parsing and HTML fidelity review.

The original gpt4o_only_8block_ocr.py is never edited. To create a fresh OCR
result first, use run_refined_layout_ocr.py and pass its results JSON here.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from bol_parser import parse, score
from run_refined_layout_ocr import DEFAULT_LAYOUT, ORIGINAL, load_module, sha256


HERE = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ocr-results", required=True, type=Path)
    parser.add_argument("--layout", type=Path, default=DEFAULT_LAYOUT)
    parser.add_argument("--output-root", type=Path, default=HERE)
    parser.add_argument("--model", default="gpt-4o")
    parser.add_argument("--max-data-iterations", type=int, default=4)
    parser.add_argument("--max-visual-iterations", type=int, default=4)
    parser.add_argument("--no-vision", action="store_true")
    args = parser.parse_args()
    ocr_path = args.ocr_results.expanduser().resolve()
    layout_path = args.layout.expanduser().resolve()
    if not ocr_path.is_file() or not layout_path.is_file():
        parser.error("OCR results and refined layout must both exist")
    if args.max_data_iterations < 1 or args.max_visual_iterations < 1:
        parser.error("iteration limits must be positive")
    ocr = json.loads(ocr_path.read_text(encoding="utf-8"))
    provenance_path = ocr_path.parent / "layout_provenance.json"
    if not provenance_path.is_file():
        parser.error(f"refined-layout provenance is missing: {provenance_path}")
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    if provenance.get("layout_sha256") != sha256(layout_path):
        parser.error("OCR was generated with a different layout version")
    if provenance.get("ocr_script_sha256") != sha256(ORIGINAL):
        parser.error("Original OCR script changed since the saved run")
    blocks = {int(item["block"]): "\n\n".join(str(value) for value in item["cells"].values())
              for item in ocr["blocks"]}
    if sorted(blocks) != list(range(1, 9)):
        parser.error("OCR result must contain blocks 1 through 8")
    spec = json.loads((HERE / "bill_of_lading_spec.json").read_text(encoding="utf-8"))
    gold = json.loads((HERE / "bill_of_lading_gold_fields.json").read_text(encoding="utf-8"))
    parsed = parse(blocks, spec)
    evaluation = score(parsed, gold)

    run_dir = args.output_root.expanduser().resolve() / (
        "refined_full_flow_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "parsed_fields.json").write_text(
        json.dumps(parsed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (run_dir / "gold_comparison.json").write_text(
        json.dumps(evaluation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    run_manifest = {
        "ocr_results": str(ocr_path), "layout": str(layout_path),
        "layout_sha256": sha256(layout_path), "original_ocr_script": str(ORIGINAL),
        "original_ocr_script_sha256": sha256(ORIGINAL),
        "ocr_summary": ocr.get("summary"), "parsed_valid": parsed["valid"],
        "parsed_row_count": len(parsed["containers"]),
        "gold_fields_correct": evaluation["correct"],
        "gold_fields_total": evaluation["total"],
    }
    (run_dir / "flow_manifest.json").write_text(
        json.dumps(run_manifest, indent=2) + "\n", encoding="utf-8")

    # The graph imports original geometry at module load. Override its in-memory
    # geometry only for this run; neither Python source file is modified.
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    graph = importlib.import_module("bill_of_lading_html_graph")
    layout = load_module("bol_refined_layout_full_flow", layout_path)
    graph.BLOCKS = layout.BLOCKS
    graph.CELLS = layout.CELLS
    result = graph.build_graph().invoke({
        "ocr_results_path": str(ocr_path),
        "output_root": str(run_dir), "model": args.model,
        "use_vision": not args.no_vision,
        "max_data_iterations": args.max_data_iterations,
        "max_visual_iterations": args.max_visual_iterations,
    })
    summary = {
        "run_dir": str(run_dir), "row_count": len(parsed["containers"]),
        "parsed_valid": parsed["valid"],
        "gold_fields": f"{evaluation['correct']}/{evaluation['total']}",
        "html_status": result["status"], "html_report": result["report_path"],
        "html": result["reconstructed_html"],
    }
    (run_dir / "flow_result.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
