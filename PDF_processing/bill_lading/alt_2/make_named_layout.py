#!/usr/bin/env python3
"""Convert alt-2 coordinate extraction into a reviewed named-cell layout draft.

The JSON uses absolute [left, top, right, bottom] pixels. This program writes
the block-relative [x, y, width, height] shape used by schema_manifest() in the
existing bill-of-lading React workflow, plus crops and a review overlay. It
does not approve the geometry or change OCR text.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def bounds(box: list[int], width: int, height: int, label: str) -> list[int]:
    if (not isinstance(box, list) or len(box) != 4 or
            any(type(value) is not int for value in box)):
        raise ValueError(f"{label}: box must contain four integers")
    left, top, right, bottom = box
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise ValueError(f"{label}: box {box} is outside the {width}x{height} page")
    return box


def section(items: list[dict], name: str) -> dict:
    matches = [item for item in items if item.get("name") == name]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {name!r} region; found {len(matches)}")
    return matches[0]


def cell(name: str, box: list[int], origin: str = "extracted") -> dict:
    return {"id": name, "bbox_px": box, "origin": origin}


def make_blocks(data: dict) -> list[dict]:
    regions = data["text_regions"]
    tables = data["tables"]
    cargo = section(tables, "particulars_furnished_by_shipper")
    charges = section(tables, "freight_and_charges")
    if len(cargo["rows"]) != 1 or charges["rows"]:
        raise ValueError("This alt-2 template requires one cargo row and no charge rows")

    def region(name: str) -> dict:
        item = section(regions, name)
        return cell(name, item["bbox_px"])

    def listed(items: list[dict]) -> list[dict]:
        return [cell(item["name"], item["bbox_px"]) for item in items]

    def block(number: int, name: str, box: list[int], cells: list[dict]) -> dict:
        return {"block": number, "name": name, "bbox_px": box, "cells": cells}

    # Adjacent table boxes include the same 2–3 pixels of printed border.
    # Half-open blocks share that border exactly once; cell crops are clipped.
    cargo_start = cargo["headers"][0]["bbox_px"][1]
    body_start = cargo["rows"][0]["cells"][0]["bbox_px"][1]
    charges_start = charges["bbox_px"][1]
    bottom_start = charges["bbox_px"][3] - 3
    page_end = section(regions, "shipped_on_board_date")["bbox_px"][3]
    left = cargo["bbox_px"][0]
    right = max(item["bbox_px"][2] for item in regions)
    header_end = section(regions, "shipper")["bbox_px"][1]
    parties_end = section(regions, "notify_parties")["bbox_px"][3]
    routing_end = section(regions, "place_of_delivery")["bbox_px"][3]
    notice_end = section(regions, "particulars_notice")["bbox_px"][3]

    cargo_cells = listed(cargo["rows"][0]["cells"])
    cargo_cells += listed(list(cargo["totals"].values()))
    for item in cargo_cells:
        item["bbox_px"] = [*item["bbox_px"][:3], min(item["bbox_px"][3], charges_start)]
    charges_headers = listed(charges["headers"])
    charges_header_bottom = max(item["bbox_px"][3] for item in charges_headers)
    charges_right = charges["bbox_px"][2]
    charges_cells = [
        cell("charges_caption", [left, charges_start, charges_right, charges["headers"][0]["bbox_px"][1]],
             "derived_from_table_rules"),
        *charges_headers,
        cell("charges_body", [left, charges_header_bottom, charges_right, bottom_start],
             "derived_blank_area"),
        cell("legal_terms", [charges_right, charges_start, right, bottom_start],
             "derived_adjacent_area"),
    ]
    bottom_names = ["declared_value", "carrier_receipt", "signature",
                    "place_and_date_of_issue", "shipped_on_board_date"]
    bottom_cells = [region(name) for name in bottom_names]
    for item in bottom_cells:
        item["bbox_px"][1] = max(item["bbox_px"][1], bottom_start)

    return [
        block(1, "header", [left, 60, right, header_end],
              [region("carrier_header"), region("bill_of_lading_number")]),
        block(2, "parties", [left, header_end, right, parties_end],
              [region(name) for name in ("shipper", "carrier_agent_endorsements",
                                        "consignee", "discharge_agent", "notify_parties")]),
        block(3, "routing", [left, parties_end, right, routing_end],
              [region(name) for name in ("vessel_and_voyage", "port_of_loading",
                                        "place_of_receipt", "booking_and_shipper_reference",
                                        "port_of_discharge", "place_of_delivery")]),
        block(4, "particulars_notice", [left, routing_end, right, notice_end],
              [region("particulars_notice")]),
        block(5, "cargo_headers", [left, cargo_start, right, body_start],
              listed(cargo["headers"])),
        block(6, "cargo_body_and_totals", [left, body_start, right, charges_start],
              cargo_cells),
        block(7, "charges_and_legal", [left, charges_start, right, bottom_start],
              charges_cells),
        block(8, "issue_and_signature", [left, bottom_start, right, page_end],
              bottom_cells),
    ]


def schema_from_blocks(blocks: list[dict], width: int, height: int) -> dict:
    schema = {
        "template_id": "hemisphere_bill_of_lading_alt_2_draft",
        "coordinate_system": "top-left half-open pixels",
        "source_canvas": {"width": width, "height": height},
        "blocks": [],
    }
    names: set[str] = set()
    for item in blocks:
        left, top, right, bottom = bounds(item["bbox_px"], width, height, item["name"])
        output = {"block": item["block"], "name": item["name"],
                  "box": {"x": left, "y": top, "width": right - left, "height": bottom - top},
                  "cells": []}
        for index, source in enumerate(item["cells"], start=1):
            name = source["id"]
            if name in names:
                raise ValueError(f"Duplicate cell id: {name}")
            names.add(name)
            x0, y0, x1, y1 = bounds(source["bbox_px"], width, height, name)
            if not (left <= x0 < x1 <= right and top <= y0 < y1 <= bottom):
                raise ValueError(f"{name}: cell {source['bbox_px']} exceeds block {item['name']}")
            output["cells"].append({
                "id": name, "reading_order": index,
                "box": {"x": x0 - left, "y": y0 - top,
                        "width": x1 - x0, "height": y1 - y0},
                "origin": source["origin"],
            })
        schema["blocks"].append(output)
    if [block["block"] for block in schema["blocks"]] != list(range(1, 9)):
        raise ValueError("Blocks must be numbered 1 through 8")
    return schema


def write_review(image: Image.Image, schema: dict, output: Path) -> None:
    crops = output / "crops"
    crops.mkdir(parents=True, exist_ok=True)
    overlay = image.copy()
    draw = ImageDraw.Draw(overlay)
    font = ImageFont.load_default()
    cards: list[str] = []
    for block in schema["blocks"]:
        box = block["box"]
        bx, by = box["x"], box["y"]
        for cell_record in block["cells"]:
            region = cell_record["box"]
            x0, y0 = bx + region["x"], by + region["y"]
            x1, y1 = x0 + region["width"], y0 + region["height"]
            name = cell_record["id"]
            filename = f"block-{block['block']:02d}--{name}.png"
            image.crop((x0, y0, x1, y1)).save(crops / filename)
            draw.rectangle((x0, y0, x1 - 1, y1 - 1), outline=(0, 190, 220), width=3)
            draw.text((x0 + 4, y0 + 4), name, fill=(0, 95, 110), font=font,
                      stroke_width=2, stroke_fill="white")
            cards.append(f"<article><h2>{html.escape(name)}</h2><p>Block {block['block']} · "
                         f"{[x0, y0, x1, y1]} · {cell_record['origin']}</p>"
                         f"<img src='crops/{filename}' alt='{html.escape(name)}'></article>")
    overlay.save(output / "named-cell-overlay.png")
    (output / "review.html").write_text(
        "<!doctype html><meta charset='utf-8'><title>Alt 2 crop review</title>"
        "<style>body{font:16px system-ui;background:#eef2f5;margin:24px}"
        "main{max-width:1200px;margin:auto}article{background:white;padding:16px;"
        "margin:12px 0;border-radius:8px}img{max-width:100%;border:1px solid #ccd}"
        "p{color:#456}</style><main><h1>Bill of lading alt 2 named cells</h1>"
        "<p>Cyan boxes are proposed crop boundaries. Check every crop against the source page."
        " Derived regions require extra review.</p>" + "".join(cards) + "</main>",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coordinates", required=True, type=Path)
    parser.add_argument("--source-png", type=Path,
                        help="Defaults to source-page-001.png beside the coordinates")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    coordinates = args.coordinates.expanduser().resolve()
    source = (args.source_png or coordinates.parent / "source-page-001.png").expanduser().resolve()
    if not coordinates.is_file() or not source.is_file():
        parser.error("Coordinate JSON and source page PNG must exist")
    data = json.loads(coordinates.read_text(encoding="utf-8"))
    with Image.open(source) as opened:
        image = opened.convert("RGB")
    if data.get("page_size_px") != list(image.size):
        parser.error(f"Coordinate page size {data.get('page_size_px')} does not match {image.size}")
    blocks = make_blocks(data)
    schema = schema_from_blocks(blocks, *image.size)
    output = args.output_dir.expanduser().resolve()
    if output.exists() and any(output.iterdir()):
        parser.error(f"Output directory must be empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    (output / "layout.json").write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    write_review(image, schema, output)
    report = {
        "status": "needs_visual_review",
        "source_coordinates": str(coordinates),
        "source_png": str(source),
        "source_png_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "block_count": len(schema["blocks"]),
        "cell_count": sum(len(block["cells"]) for block in schema["blocks"]),
        "derived_cells": [cell["id"] for block in schema["blocks"] for cell in block["cells"]
                          if cell["origin"] != "extracted"],
        "review_flags": [
            {"cells": ["place_of_receipt", "place_of_delivery"],
             "reason": "The source's GREAT BRITAIN text visibly crosses their printed divider; a strict crop may split one field across both cells."},
            {"cells": ["discharge_agent"],
             "reason": "The source region also contains the Lloyds/IMO number; parsing must keep those as separate fields."},
        ],
        "review": ["Compare named-cell-overlay.png with the PDF",
                   "Inspect every crop in review.html, especially derived cells",
                   "Confirm no text is clipped or assigned to a neighboring cell"],
        "react_compatibility": "schema shape only; alt-1 OCR, HTML, and parser callbacks still require adaptation",
    }
    (output / "validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(output / "layout.json")
    print(output / "review.html")
    print(output / "validation.json")


if __name__ == "__main__":
    main()
