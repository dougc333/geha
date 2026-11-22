#!/usr/bin/env python3
"""Check a candidate bill-of-lading spec against local geometry and saved OCR.

The saved OCR was cropped with the approved layout. Parser scoring here does not
prove that fresh OCR from candidate boxes would be correct.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

from PIL import Image

from bol_parser import parse, score
from generate_candidate_spec import validate_spec


HERE = Path(__file__).resolve().parent
DEFAULT_CANDIDATE = HERE / "spec_candidate/candidate_spec.json"
DEFAULT_PAGE = HERE / "spec_candidate/source.png"
DEFAULT_LAYOUT = HERE / "vision_layout_run_detector/refined_layout.py"
DEFAULT_OCR = HERE / "refined_ocr_test_20261118/gpt4o_only_run_20261119T001933Z/gpt4o_only_results.json"
DEFAULT_GOLD = HERE / "bill_of_lading_gold_fields.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--page-png", type=Path, default=DEFAULT_PAGE)
    parser.add_argument("--layout", type=Path, default=DEFAULT_LAYOUT,
                        help="Refined layout used as the block geometry reference")
    parser.add_argument("--ocr-results", type=Path, default=DEFAULT_OCR)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-coordinate-delta", type=int, default=20)
    args = parser.parse_args()
    if args.max_coordinate_delta < 0:
        parser.error("max-coordinate-delta must be nonnegative")
    spec = json.loads(args.candidate.read_text(encoding="utf-8"))
    layout_path = args.layout.expanduser().resolve()
    layout_spec = importlib.util.spec_from_file_location("bol_validation_refined_layout", layout_path)
    if layout_spec is None or layout_spec.loader is None:
        parser.error(f"Cannot load layout: {layout_path}")
    layout = importlib.util.module_from_spec(layout_spec)
    layout_spec.loader.exec_module(layout)
    layout_hash = hashlib.sha256(layout_path.read_bytes()).hexdigest()
    provenance_path = args.ocr_results.parent / "layout_provenance.json"
    provenance_match = None
    if provenance_path.is_file():
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance_match = provenance.get("layout_sha256") == layout_hash
    with Image.open(args.page_png) as image:
        width, height = image.size
    structural_errors: list[str] = []
    try:
        validate_spec(spec, width, height)
    except ValueError as exc:
        structural_errors = str(exc).splitlines()[1:]

    geometry: list[dict] = []
    candidate_blocks = {b.get("block"): b for b in spec.get("blocks", []) if isinstance(b, dict)}
    for number, reference in layout.BLOCKS.items():
        item = candidate_blocks.get(number)
        actual = item.get("box_px") if item else None
        expected = [reference[0], reference[1], reference[2] - reference[0], reference[3] - reference[1]]
        if not (isinstance(actual, list) and len(actual) == 4 and all(isinstance(x, int) for x in actual)):
            geometry.append({"block": number, "candidate": actual, "reference": expected,
                             "max_coordinate_delta": None, "passed": False})
            continue
        delta = max(abs(a - b) for a, b in zip(actual, expected))
        geometry.append({"block": number, "candidate": actual, "reference": expected,
                         "max_coordinate_delta": delta,
                         "passed": delta <= args.max_coordinate_delta})

    saved_ocr = {int(block["block"]): "\n\n".join(str(value) for value in block["cells"].values())
                 for block in json.loads(args.ocr_results.read_text(encoding="utf-8"))["blocks"]}
    parsing: dict = {"status": "skipped", "reason": "candidate structure is invalid"}
    if not structural_errors:
        try:
            result = parse(saved_ocr, spec)
            evaluation = score(result, json.loads(args.gold.read_text(encoding="utf-8")))
            parsing = {"status": "passed" if result["valid"] and evaluation["correct"] == evaluation["total"] else "failed",
                       "parsed_valid": result["valid"], "row_count": len(result["containers"]),
                       "gold_correct": evaluation["correct"], "gold_total": evaluation["total"],
                       "parse_errors": result["errors"], "silent_errors": evaluation["silent_errors"],
                       "scope": "Saved OCR from approved crops; parser compatibility only."}
        except (KeyError, TypeError, ValueError) as exc:
            parsing = {"status": "failed", "error": str(exc),
                       "scope": "Saved OCR from approved crops; parser compatibility only."}
    geometry_passed = all(row["passed"] for row in geometry)
    report = {
        "status": "passed_local_checks" if not structural_errors and geometry_passed and parsing["status"] == "passed" and provenance_match is not False else "failed_local_checks",
        "candidate": str(args.candidate.resolve()), "page_png": str(args.page_png.resolve()),
        "structural_errors": structural_errors,
        "geometry": {"status": "passed" if geometry_passed else "failed",
                     "reference": str(layout_path), "reference_sha256": layout_hash,
                     "max_coordinate_delta_px": args.max_coordinate_delta, "blocks": geometry,
                     "scope": "Block coordinate comparison, not independent image alignment proof."},
        "parsing": parsing,
        "saved_ocr": {"path": str(args.ocr_results.resolve()),
                      "layout_provenance_match": provenance_match,
                      "scope": "Saved OCR from the refined layout; no new model call."},
        "remaining_check": "Fresh crop/OCR with candidate boxes and visual row association review.",
    }
    output = args.output or args.candidate.parent / "local_validation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(output)
    print(report["status"])


if __name__ == "__main__":
    main()
