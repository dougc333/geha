#!/usr/bin/env python3
"""Extract page-1 rule coordinates and OCR for the Hemisphere bill of lading.

This is a document-specific, local baseline. It detects printed black rules from
the rendered page; it does not copy coordinates or text from a reviewed answer.
Requires pdftoppm, tesseract, Pillow, NumPy, and OpenCV.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw


def render_page(pdf: Path, output: Path, dpi: int) -> Image.Image:
    prefix = output / "source-page-001"
    subprocess.run(
        ["pdftoppm", "-f", "1", "-l", "1", "-singlefile", "-r", str(dpi),
         "-png", str(pdf), str(prefix)],
        check=True, capture_output=True, text=True,
    )
    with Image.open(prefix.with_suffix(".png")) as image:
        return image.convert("RGB")


def tesseract_words(image: Image.Image, box: list[int] | None = None,
                    psm: int = 6) -> list[dict[str, Any]]:
    left, top, right, bottom = box or [0, 0, *image.size]
    crop = image.crop((left, top, right, bottom))
    with io.BytesIO() as stream:
        crop.save(stream, format="PNG")
        result = subprocess.run(
            ["tesseract", "stdin", "stdout", "tsv", "--psm", str(psm)],
            input=stream.getvalue(), check=True, capture_output=True,
        )
    words: list[dict[str, Any]] = []
    tsv_lines = result.stdout.decode("utf-8").splitlines()
    columns = tsv_lines[0].split("\t")
    for line in tsv_lines[1:]:
        fields = line.split("\t", len(columns) - 1)
        if len(fields) != len(columns):
            continue
        row = dict(zip(columns, fields))
        text = row.get("text", "").strip()
        if not text or int(row["level"]) != 5:
            continue
        x = left + int(row["left"])
        y = top + int(row["top"])
        words.append({
            "text": text, "page": 1,
            "bbox_px": [x, y, x + int(row["width"]), y + int(row["height"])],
            "confidence": round(float(row["conf"]), 1),
            "line_id": [int(row[key]) for key in ("block_num", "par_num", "line_num")],
        })
    return words


def ocr_lines(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[int, ...], list[dict[str, Any]]] = defaultdict(list)
    for word in words:
        groups[tuple(word["line_id"])].append(word)
    ordered = sorted(groups.values(), key=lambda group: (
        min(word["bbox_px"][1] for word in group),
        min(word["bbox_px"][0] for word in group),
    ))
    return [{"text": " ".join(word["text"] for word in sorted(
                group, key=lambda word: word["bbox_px"][0])),
             "page": 1,
             "bbox_px": [min(w["bbox_px"][0] for w in group),
                         min(w["bbox_px"][1] for w in group),
                         max(w["bbox_px"][2] for w in group),
                         max(w["bbox_px"][3] for w in group)]}
            for group in ordered]


def ocr_region(image: Image.Image, name: str, box: list[int],
               *, inset: int = 6) -> dict[str, Any]:
    left, top, right, bottom = box
    inner = [left + inset, top + inset, right - inset, bottom - inset]
    if inner[0] >= inner[2] or inner[1] >= inner[3]:
        inner = box
    words = tesseract_words(image, inner)
    lines = ocr_lines(words)
    return {"name": name, "page": 1, "bbox_px": box,
            "text": "\n".join(line["text"] for line in lines),
            "lines": lines, "words": words}


def detected_rules(image: Image.Image) -> tuple[list[dict[str, int]], list[dict[str, int]]]:
    gray = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2GRAY)
    dark = (gray < 80).astype(np.uint8)

    def contours(kernel: np.ndarray, horizontal: bool) -> list[dict[str, int]]:
        opened = cv2.morphologyEx(dark, cv2.MORPH_OPEN, kernel)
        found, _ = cv2.findContours(opened, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        rows = []
        for contour in found:
            x, y, width, height = map(int, cv2.boundingRect(contour))
            if (horizontal and width >= 150 and height <= 12) or (
                not horizontal and height >= 35 and width <= 10
            ):
                rows.append({"x": x, "y": y, "width": width, "height": height})
        return sorted(rows, key=lambda row: (row["y"], row["x"]))

    horizontal = contours(np.ones((1, 120), np.uint8), True)
    vertical = contours(np.ones((35, 1), np.uint8), False)
    # A dark letter stroke or signature bar can resemble a short vertical rule.
    # Printed dividers meet horizontal borders at BOTH ends. Descenders in
    # "Agent Signature" touch the lower rule at only one end.
    def meets_border(rule: dict[str, int]) -> bool:
        center_x = rule_x(rule)
        endpoints = (rule["y"], rule["y"] + rule["height"] - 1)
        return all(any(h["x"] - 3 <= center_x <= h["x"] + h["width"] + 2
                       and abs(endpoint - rule_y(h)) <= 5
                       for h in horizontal) for endpoint in endpoints)
    return horizontal, [rule for rule in vertical if meets_border(rule)]


def rule_y(rule: dict[str, int]) -> int:
    return rule["y"] + rule["height"] // 2


def rule_x(rule: dict[str, int]) -> int:
    return rule["x"] + rule["width"] // 2


def locate_tables(image: Image.Image, horizontal: list[dict[str, int]],
                  vertical: list[dict[str, int]],
                  page_words: list[dict[str, Any]]) -> dict[str, Any]:
    width, height = image.size
    full = sorted((rule for rule in horizontal
                   if rule["x"] < width * 0.08 and rule["width"] > width * 0.75),
                  key=rule_y)
    anchors = [word for word in page_words
               if word["text"].upper().startswith("PARTICULARS")
               and word["bbox_px"][1] > height * 0.4]
    if not anchors:
        raise ValueError("Particulars heading was not found; inspect OCR before cropping")
    anchor_y = min(word["bbox_px"][1] for word in anchors)
    above = [rule for rule in full if rule_y(rule) < anchor_y]
    if not above:
        raise ValueError("No full-width rule above the Particulars heading")
    start = full.index(above[-1])
    if len(full) < start + 5:
        raise ValueError("Could not locate both cargo and charges table boundaries")
    cargo_top, title_bottom, header_bottom, cargo_bottom = map(
        rule_y, full[start:start + 4])
    # All four body dividers run continuously from the header into the body.
    cargo_v = [rule for rule in vertical
               if rule["y"] <= title_bottom + 4
               and rule["y"] + rule["height"] >= cargo_bottom - 3
               and rule["x"] < width - 30]
    xs = sorted(set(rule_x(rule) for rule in cargo_v))
    if len(xs) != 5:
        raise ValueError(f"Expected 4 cargo columns (5 borders), found {xs}")
    short = sorted((rule for rule in horizontal
                    if cargo_bottom < rule_y(rule) < height * 0.84
                    and rule["x"] < width * 0.08
                    and rule["width"] > width * 0.45), key=rule_y)
    if len(short) < 2:
        raise ValueError("Freight & Charges header rules were not found")
    charges_header_top, charges_header_bottom = map(rule_y, short[:2])
    charges_bottom = next((rule_y(rule) for rule in full
                           if rule_y(rule) > charges_header_bottom), None)
    if charges_bottom is None:
        raise ValueError("Freight & Charges bottom rule was not found")
    charges_right = next((rule_x(rule) for rule in vertical
                          if abs(rule["y"] - cargo_bottom) < 5
                          and rule["y"] + rule["height"] >= charges_bottom), None)
    if charges_right is None:
        raise ValueError("Freight & Charges right border was not found")
    charges_v = [rule for rule in vertical
                 if rule["y"] <= charges_header_top + 2
                 and rule["y"] + rule["height"] >= charges_header_bottom - 1
                 and xs[0] <= rule_x(rule) <= charges_right]
    charges_xs = sorted(set([xs[0], charges_right] + [rule_x(rule) for rule in charges_v]))
    if len(charges_xs) != 6:
        raise ValueError(f"Expected 5 charges columns (6 borders), found {charges_xs}")
    totals = [rule for rule in horizontal
              if header_bottom < rule_y(rule) < cargo_bottom
              and 0.07 * width < rule["width"] < 0.2 * width
              and rule["x"] >= xs[2]]
    if len(totals) != 2:
        raise ValueError(f"Expected 2 short total rules, found {len(totals)}")
    total_y = round(sum(rule_y(rule) for rule in totals) / 2)
    return {
        "cargo": {"bbox_px": [xs[0], cargo_top, xs[-1] + 1, cargo_bottom + 2],
                  "title_bottom_y": title_bottom, "header_bottom_y": header_bottom,
                  "column_boundaries_x_px": xs, "total_rule_y": total_y},
        "charges": {"bbox_px": [xs[0], cargo_bottom, charges_right + 1, charges_bottom + 2],
                    "header_top_y": charges_header_top,
                    "header_bottom_y": charges_header_bottom,
                    "column_boundaries_x_px": charges_xs},
        "total_dividers": totals,
    }


def table_data(image: Image.Image, layout: dict[str, Any]) -> list[dict[str, Any]]:
    cargo = layout["cargo"]
    xs = cargo["column_boundaries_x_px"]
    title_y = cargo["title_bottom_y"]
    body_y = cargo["header_bottom_y"]
    bottom = cargo["bbox_px"][3]
    total_y = cargo["total_rule_y"]
    headers = [ocr_region(image, f"cargo_header_{index + 1}",
                          [left, title_y, right, body_y])
               for index, (left, right) in enumerate(zip(xs, xs[1:]))]
    cells = [ocr_region(image, f"cargo_cell_{index + 1}",
                        [left, body_y, right, total_y if index >= 2 else bottom])
             for index, (left, right) in enumerate(zip(xs, xs[1:]))]
    totals = [ocr_region(image, f"{name}_total", [xs[index], total_y, xs[index + 1], bottom])
              for index, name in ((2, "weight"), (3, "measurement"))]
    charge = layout["charges"]
    cx = charge["column_boundaries_x_px"]
    charge_headers = [ocr_region(image, f"charge_header_{index + 1}",
                                 [left, charge["header_top_y"], right, charge["header_bottom_y"]],
                                 inset=4)
                      for index, (left, right) in enumerate(zip(cx, cx[1:]))]
    charge_body = ocr_region(image, "charges_body", [cx[0], charge["header_bottom_y"],
                                                      cx[-1], charge["bbox_px"][3]], inset=10)
    flags = []
    for region in [*headers, *cells, *totals, *charge_headers]:
        low = [word for word in region["words"] if word["confidence"] < 60]
        if low:
            flags.append({"region": region["name"], "reason": "low-confidence OCR",
                          "words": [word["text"] for word in low]})
    if charge_body["words"]:
        flags.append({"region": "charges_body", "reason": "nonempty OCR in expected blank body"})
    return [
        {"name": "particulars_furnished_by_shipper", "page": 1,
         "bbox_px": cargo["bbox_px"], "headers": headers,
         "rows": [{"row_number": 1, "page": 1,
                   "bbox_px": [xs[0], body_y, xs[-1] + 1, bottom], "cells": cells}],
         "totals": {item["name"]: item for item in totals},
         "review_flags": flags,
         "note": "One physical cargo row; short rules separate totals within weight and measurement columns."},
        {"name": "freight_and_charges", "page": 1,
         "bbox_px": charge["bbox_px"], "headers": charge_headers,
         "rows": [] if not charge_body["words"] else [{"row_number": 1,
             "page": 1, "bbox_px": charge_body["bbox_px"], "cells": [charge_body]}],
         "review_flags": ([flags[-1]] if charge_body["words"] else []),
         "note": "Header-only table; no values are inferred from an empty body."},
    ]


def make_overlay(image: Image.Image, horizontal: list[dict[str, int]],
                 vertical: list[dict[str, int]], output: Path) -> None:
    marked = image.copy()
    draw = ImageDraw.Draw(marked)
    for rule in horizontal:
        y = rule_y(rule)
        draw.line((rule["x"], y, rule["x"] + rule["width"] - 1, y),
                  fill=(255, 0, 0), width=3)
    for rule in vertical:
        x = rule_x(rule)
        draw.line((x, rule["y"], x, rule["y"] + rule["height"] - 1),
                  fill=(255, 0, 0), width=3)
    marked.save(output)


def page_regions(image: Image.Image, horizontal: list[dict[str, int]],
                 vertical: list[dict[str, int]], layout: dict[str, Any]
                 ) -> list[dict[str, Any]]:
    """OCR the named form areas, using detected dividers for their boxes."""
    page_width = image.width
    cargo_top = layout["cargo"]["bbox_px"][1]
    full = sorted((rule_y(h) for h in horizontal
                   if h["x"] < page_width * .08 and h["width"] > page_width * .75
                   and rule_y(h) < cargo_top))
    if len(full) != 4:
        raise ValueError(f"Expected four full-width rules before cargo, found {full}")
    party_top, party_mid, party_bottom, voyage_mid = full
    voyage_bottom = cargo_top
    notify_lines = [rule_y(h) for h in horizontal if party_mid < rule_y(h) < party_bottom
                    and h["x"] < page_width * .08 and
                    page_width * .35 < h["width"] < page_width * .6]
    if len(notify_lines) != 1:
        raise ValueError(f"Expected one notify-party divider, found {notify_lines}")
    notify_top = notify_lines[0]
    left_border = layout["cargo"]["column_boundaries_x_px"][0]
    right_border = layout["cargo"]["column_boundaries_x_px"][-1]
    party_split = rule_x(next(v for v in vertical if abs(v["y"] - party_top) < 4
                              and left_border + 300 < rule_x(v) < right_border - 300))
    voyage_splits = sorted(rule_x(v) for v in vertical
                            if abs(v["y"] - party_bottom) < 4
                            and left_border + 100 < rule_x(v) < right_border - 100)
    if len(voyage_splits) != 2:
        raise ValueError(f"Expected two voyage-column dividers, found {voyage_splits}")
    header_right = min(h["x"] for h in horizontal if rule_y(h) < party_top)
    bottom_rules = sorted((rule_y(h) for h in horizontal
                           if h["x"] < page_width * .08 and h["width"] > page_width * .75
                           and rule_y(h) > layout["charges"]["bbox_px"][3]))
    if len(bottom_rules) < 2:
        raise ValueError("Bottom form dividers were not detected")
    bottom_start = layout["charges"]["bbox_px"][3] - 3
    bottom_mid, bottom_end = bottom_rules[:2]
    bottom_splits = sorted(rule_x(v) for v in vertical
                           if v["y"] <= bottom_start + 4 and
                           v["y"] + v["height"] >= bottom_mid - 2 and
                           left_border + 100 < rule_x(v) < right_border - 100)
    if len(bottom_splits) != 2:
        raise ValueError(f"Expected two bottom-form dividers, found {bottom_splits}")
    definitions = [
        ("carrier_header", [left_border, 60, header_right, party_top]),
        ("bill_of_lading_number", [header_right, 60, right_border + 1, party_top]),
        ("shipper", [left_border, party_top, party_split, party_mid]),
        ("carrier_agent_endorsements", [party_split, party_top, right_border + 1, party_mid]),
        ("consignee", [left_border, party_mid, party_split, notify_top]),
        ("notify_parties", [left_border, notify_top, party_split, party_bottom]),
        ("discharge_agent", [party_split, party_mid, right_border + 1, party_bottom]),
        ("vessel_and_voyage", [left_border, party_bottom, voyage_splits[0], voyage_mid]),
        ("port_of_loading", [voyage_splits[0], party_bottom, voyage_splits[1], voyage_mid]),
        ("place_of_receipt", [voyage_splits[1], party_bottom, right_border + 1, voyage_mid]),
        ("booking_and_shipper_reference", [left_border, voyage_mid, voyage_splits[0], voyage_bottom]),
        ("port_of_discharge", [voyage_splits[0], voyage_mid, voyage_splits[1], voyage_bottom]),
        ("place_of_delivery", [voyage_splits[1], voyage_mid, right_border + 1, voyage_bottom]),
        ("particulars_notice", [left_border, voyage_bottom, right_border + 1,
                                layout["cargo"]["title_bottom_y"]]),
        ("declared_value", [left_border, bottom_start, bottom_splits[0], bottom_mid]),
        ("carrier_receipt", [bottom_splits[0], bottom_start, bottom_splits[1], bottom_mid]),
        ("signature", [bottom_splits[1], bottom_start, right_border + 1, bottom_mid]),
        ("place_and_date_of_issue", [left_border, bottom_mid, bottom_splits[0], bottom_end]),
        ("shipped_on_board_date", [bottom_splits[0], bottom_mid, right_border + 1, bottom_end]),
    ]
    return [ocr_region(image, name, box) for name, box in definitions]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dpi", type=int, default=144)
    args = parser.parse_args()
    for program in ("pdftoppm", "tesseract"):
        if not shutil.which(program):
            parser.error(f"{program} is required on PATH")
    if not args.pdf.is_file() or args.pdf.suffix.lower() != ".pdf":
        parser.error(f"Not a PDF file: {args.pdf}")
    if args.dpi < 100:
        parser.error("--dpi must be at least 100 for reliable line detection")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    image = render_page(args.pdf, args.output_dir, args.dpi)
    horizontal, vertical = detected_rules(image)
    page_words = tesseract_words(image, psm=3)
    layout = locate_tables(image, horizontal, vertical, page_words)
    tables = table_data(image, layout)
    make_overlay(image, horizontal, vertical, args.output_dir / "red-rule-overlay.png")
    result = {
        "source_pdf": str(args.pdf.resolve()), "document_type": "bill_of_lading",
        "page_count": 1, "render_dpi": args.dpi,
        "page_size_px": list(image.size),
        "coordinate_system": "page 1, top-left pixels, [left, top, right, bottom]",
        "detected_rules": {"horizontal": horizontal, "vertical": vertical},
        "text_regions": page_regions(image, horizontal, vertical, layout),
        "tables": tables, "figures": [],
        "review_flags": [flag for table in tables for flag in table["review_flags"]],
    }
    target = args.output_dir / "coordinate-extraction.json"
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(target)
    print(args.output_dir / "red-rule-overlay.png")


if __name__ == "__main__":
    main()
