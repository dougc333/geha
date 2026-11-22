#!/usr/bin/env python3
"""Apply human OCR/field corrections while preserving the raw extraction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def apply_review(extraction: dict, review: dict) -> dict:
    if review.get("schema_version") != 1 or review.get("status") != "human_reviewed":
        raise ValueError("Expected a version 1 human-reviewed override file")
    if review.get("source_extraction") != "coordinate-extraction.json":
        raise ValueError("Override file targets a different extraction filename")
    regions = {item["name"]: item for item in extraction.get("text_regions", [])}
    applied: set[str] = set()
    for correction in review.get("corrections", []):
        name = correction["region"]
        if name not in regions or name in applied:
            raise ValueError(f"Missing or duplicate review region: {name}")
        region = regions[name]
        if region["text"] != correction["raw_text"]:
            raise ValueError(f"Raw OCR changed since review for {name}; review again")
        if correction["evidence_page"] != region["page"]:
            raise ValueError(f"Evidence page does not match region {name}")
        region["ocr_text"] = region["text"]
        region["text"] = correction["reviewed_text"]
        region["review"] = {
            "status": "human_reviewed",
            "evidence_page": correction["evidence_page"],
            "evidence_bbox_px": correction["evidence_bbox_px"],
            "reason": correction["reason"],
            "note": "lines and words retain the original Tesseract OCR",
        }
        applied.add(name)
    extraction["review_status"] = "partially_human_reviewed"
    extraction["reviewed_regions"] = sorted(applied)
    return extraction


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extraction", required=True, type=Path)
    parser.add_argument("--overrides", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    source = args.extraction.expanduser().resolve()
    overrides = args.overrides.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if source == output or overrides == output:
        parser.error("Output must be separate from both input files")
    if output.exists():
        parser.error(f"Output already exists: {output}")
    reviewed = apply_review(json.loads(source.read_text(encoding="utf-8")),
                            json.loads(overrides.read_text(encoding="utf-8")))
    output.write_text(json.dumps(reviewed, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
