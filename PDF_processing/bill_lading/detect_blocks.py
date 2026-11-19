#!/usr/bin/env python3
"""Detect the bill-of-lading ruling lines and compare them with the hand-set schema.

Pipeline
  1. Threshold the page and keep only long horizontal / vertical strokes (OpenCV morphology).
  2. Full-width horizontal rules are the band edges; BANDS_PER_BLOCK says how many bands make
     up each of the eight blocks (block 2 spans two bands, so the spec, not the lines alone,
     defines a block).
  3. Cells are the enclosed regions of the line mask (connected components of the background
     with the lines drawn in), so no text or OCR is involved.
  3b. Block 1 has no ruled cells. Its logo square and bordered BILL OF LADING box are found as
     enclosed regions, and the two cells are split in the middle of the empty gutter between
     the header text and the BILL OF LADING box (checked: each cell must contain its object).
  4. Every expected block / cell from BLOCKS and CELLS in gpt4o_only_8block_ocr.py (read with
     ast, not imported, so openai is not needed) is matched to the detected box with the best
     IoU and the per-edge pixel deltas are reported.

Only needs numpy and opencv:  python3 -I detect_blocks.py [--page PAGE.png] [--threshold 0.95]
Exit status is 0 when every expected block and cell reaches the IoU threshold, 1 otherwise,
2 when the page structure cannot be recovered (wrong number of rules).
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
DEFAULT_PAGE = HERE.parent / "blocking_demo" / "interactive" / "bill-of-lading-source.png"
SCHEMA_SRC = HERE / "gpt4o_only_8block_ocr.py"
DEFAULT_OUT = HERE / "detect_blocks_output"

# Template knowledge from blocking_demo/interactive/prompt.md: block 2 (parties) is drawn as
# two ruled rows but is one block; every other block is a single band.
BANDS_PER_BLOCK = [1, 2, 1, 1, 1, 1, 1, 1]

Box = tuple[int, int, int, int]  # left, top, right, bottom (pixels, top-left origin)


def load_expected(path: Path) -> tuple[dict[int, Box], dict[str, Box]]:
    """Read BLOCKS and CELLS literals from the schema file and make cells absolute."""
    wanted = {"BLOCKS", "CELLS"}
    values: dict[str, dict] = {}
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id in wanted):
            values[node.targets[0].id] = ast.literal_eval(node.value)
    missing = wanted - values.keys()
    if missing:
        raise SystemExit(f"{path} has no literal {sorted(missing)}")
    blocks = {int(k): tuple(v) for k, v in values["BLOCKS"].items()}
    cells: dict[str, Box] = {}
    for number, group in values["CELLS"].items():
        left, top, _, _ = blocks[int(number)]
        for name, (x0, y0, x1, y1) in group.items():
            cells[f"{number}.{name}"] = (left + x0, top + y0, left + x1, top + y1)
    return blocks, cells


def components(mask: np.ndarray) -> list[tuple[int, int, int, int, int]]:
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    return [tuple(int(v) for v in stats[i]) for i in range(1, count)]  # x, y, w, h, area


def ink_mask(gray: np.ndarray) -> np.ndarray:
    return cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]


def detect_lines(ink: np.ndarray, hmin: int, vmin: int) -> tuple[np.ndarray, np.ndarray]:
    horizontal = cv2.morphologyEx(
        ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (hmin, 1)))
    vertical = cv2.morphologyEx(
        ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, vmin)))
    return horizontal, vertical


def form_edges(vertical: np.ndarray, page_height: int) -> tuple[int, int]:
    """Left/right form borders: the outermost near-page-height vertical strokes."""
    tall = [c for c in components(vertical) if c[3] >= 0.8 * page_height]
    if len(tall) < 2:
        raise SystemExit("Could not find the left and right form borders")
    return min(c[0] for c in tall), max(c[0] + c[2] - 1 for c in tall)


def detect_blocks(horizontal: np.ndarray, left: int, right: int,
                  bands_per_block: list[int]) -> tuple[dict[int, Box], list[int]]:
    span = right - left
    rules = sorted(y + h / 2 for x, y, w, h, _ in components(horizontal) if w >= 0.95 * span)
    rules = [round(y) for y in rules]
    if len(rules) != sum(bands_per_block):
        print(f"Expected {sum(bands_per_block)} full-width rules, found {len(rules)}: {rules}",
              file=sys.stderr)
        raise SystemExit(2)
    edges = [0] + rules  # block 1 starts at the top of the page; its top is not ruled
    blocks: dict[int, Box] = {}
    band = 0
    for number, count in enumerate(bands_per_block, start=1):
        blocks[number] = (left, edges[band], right, edges[band + count])
        band += count
    return blocks, rules


def detect_cells(horizontal: np.ndarray, vertical: np.ndarray, left: int, right: int,
                 bottom: int, dilate: int = 2) -> list[Box]:
    """Enclosed regions of the line mask, expanded back to the line centres."""
    mask = cv2.bitwise_or(horizontal, vertical)
    mask[0:3, left:right + 1] = 255  # the page top closes block 1
    mask = cv2.dilate(mask, np.ones((2 * dilate + 1, 2 * dilate + 1), np.uint8))
    count, _, stats, _ = cv2.connectedComponentsWithStats(
        cv2.bitwise_not(mask), connectivity=4)
    pad = dilate + 1
    faces: list[Box] = []
    for i in range(1, count):
        x, y, w, h, area = (int(v) for v in stats[i])
        if area < 400 or x < left - 5 or x + w > right + 5 or y + h > bottom + 5:
            continue  # speck, or the outside of the form
        faces.append((x - pad, y - pad, x + w + pad, y + h + pad))
    return sorted(faces, key=lambda b: (b[1], b[0]))


def contains(outer: Box, inner: Box, slack: int = 3) -> bool:
    return (outer[0] - slack <= inner[0] and outer[1] - slack <= inner[1]
            and inner[2] <= outer[2] + slack and inner[3] <= outer[3] + slack)


def split_header(ink: np.ndarray, block: Box, faces: list[Box],
                 mode: str = "gutter") -> dict | None:
    """Block 1 has no ruled cells: it holds a logo square, free title text and a bordered
    BILL OF LADING box. The boundary between its two cells comes from the page content:
      gutter: the middle of the empty gutter between the header text and the box (default);
      box:    the left edge of the BILL OF LADING box (what recreate_bol_layout.py uses)."""
    left, top, right, bottom = block
    objects = [f for f in faces if f[1] >= top - 3 and f[3] <= bottom + 3]
    if len(objects) < 2:
        return None
    logo, bill = min(objects, key=lambda f: f[0]), max(objects, key=lambda f: f[0])
    gutter_start = logo[2] + 5
    # skip the rule closing the block so it is not read as header text
    columns = ink[top:bottom - 8, gutter_start:bill[0] - 5].any(axis=0)
    ink_x = np.nonzero(columns)[0]
    text_right = gutter_start + int(ink_x.max()) + 1 if len(ink_x) else logo[2]
    split = bill[0] if mode == "box" else round((text_right + bill[0]) / 2)
    cells = {"1.carrier_header": (left, top, split, bottom),
             "1.bill_of_lading_box": (split, top, right, bottom)}
    return {
        "logo": logo, "bill_box": bill, "text_right": text_right, "split_x": split,
        "cells": cells,
        "checks": {
            "logo box inside carrier_header": contains(cells["1.carrier_header"], logo),
            "BILL OF LADING box inside bill_of_lading_box": contains(
                cells["1.bill_of_lading_box"], bill),
        },
    }


def iou(a: Box, b: Box) -> float:
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union else 0.0


def best_match(expected: Box, candidates: list[Box]) -> tuple[Box | None, float]:
    if not candidates:
        return None, 0.0
    box = max(candidates, key=lambda c: iou(expected, c))
    return box, iou(expected, box)


def compare(expected: dict, candidates: list[Box], threshold: float) -> list[dict]:
    rows = []
    for name, box in expected.items():
        found, score = best_match(box, candidates)
        rows.append({
            "name": str(name), "expected": list(box),
            "detected": list(found) if found else None,
            "iou": round(score, 4),
            "delta": [f - e for f, e in zip(found, box)] if found else None,
            "pass": score >= threshold,
        })
    return rows


def detect_layout(page: np.ndarray, expected_cells: dict[str, Box],
                  bands: list[int] | None = None, hmin: int = 150, vmin: int = 60,
                  header_split: str = "gutter") -> dict:
    """Measure blocks and named cells from the page image alone.

    expected_cells (name -> absolute box) is used only to NAME the detected regions, by
    best IoU; every coordinate returned comes from the image. Cells that cannot be matched
    (IoU < 0.5) are omitted so the caller can tell the detection failed.
    """
    ink = ink_mask(page)
    horizontal, vertical = detect_lines(ink, hmin, vmin)
    left, right = form_edges(vertical, page.shape[0])
    blocks, rules = detect_blocks(horizontal, left, right, bands or BANDS_PER_BLOCK)
    faces = detect_cells(horizontal, vertical, left, right, rules[-1])
    header = split_header(ink, blocks[1], faces, header_split)
    pool = faces
    if header:
        objects = {header["logo"], header["bill_box"]}
        pool = [f for f in faces if f not in objects] + list(header["cells"].values())
    cells: dict[str, Box] = {}
    for name, box in expected_cells.items():
        found, score = best_match(box, pool)
        if found is not None and score >= 0.5:
            cells[name] = found
    return {"blocks": blocks, "cells": cells, "rules": rules, "header": header}


def draw_overlay(page: np.ndarray, expected_cells: dict[str, Box], faces: list[Box],
                 blocks: dict[int, Box], path: Path) -> None:
    out = cv2.cvtColor(page, cv2.COLOR_GRAY2BGR)
    for box in faces:
        cv2.rectangle(out, box[:2], box[2:], (0, 160, 0), 3)
    for box in expected_cells.values():
        cv2.rectangle(out, box[:2], box[2:], (0, 0, 255), 1)
    for number, box in blocks.items():
        cv2.rectangle(out, box[:2], box[2:], (255, 120, 0), 4)
        cv2.putText(out, str(number), (box[0] + 10, box[1] + 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 120, 0), 4)
    cv2.imwrite(str(path), out)


def print_rows(title: str, rows: list[dict]) -> None:
    print(f"\n{title}")
    print(f"{'name':30} {'IoU':>6}  delta [dl, dt, dr, db]")
    for r in rows:
        flag = "" if r["pass"] else "  <-- below threshold"
        print(f"{r['name']:30} {r['iou']:6.3f}  {r['delta']}{flag}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--page", type=Path, default=DEFAULT_PAGE,
                    help="2136x3584 page PNG (144 DPI render of the bill of lading)")
    ap.add_argument("--schema", type=Path, default=SCHEMA_SRC,
                    help="Python file with the BLOCKS and CELLS literals")
    ap.add_argument("--bands", default=",".join(map(str, BANDS_PER_BLOCK)),
                    help="ruled bands per block, comma separated (default: %(default)s)")
    ap.add_argument("--threshold", type=float, default=0.95, help="minimum IoU to pass")
    ap.add_argument("--hmin", type=int, default=150, help="min horizontal stroke length, px")
    ap.add_argument("--vmin", type=int, default=60, help="min vertical stroke length, px")
    ap.add_argument("--header-split", choices=["gutter", "box"], default="gutter",
                    help="block 1 boundary: gutter midpoint (default) or left edge of the "
                         "BILL OF LADING box")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    page = cv2.imread(str(args.page), cv2.IMREAD_GRAYSCALE)
    if page is None:
        raise SystemExit(f"Cannot read {args.page}")
    height, width = page.shape
    print(f"page {args.page} {width}x{height}")

    expected_blocks, expected_cells = load_expected(args.schema)
    ink = ink_mask(page)
    horizontal, vertical = detect_lines(ink, args.hmin, args.vmin)
    left, right = form_edges(vertical, height)
    blocks, rules = detect_blocks(horizontal, left, right, [int(n) for n in args.bands.split(",")])
    faces = detect_cells(horizontal, vertical, left, right, rules[-1])
    print(f"form borders x={left}..{right}; {len(rules)} full-width rules at y={rules}")

    # Block 1's cells come from its logo and BILL OF LADING objects, not from ruled regions.
    header = split_header(ink, blocks[1], faces, args.header_split)
    pool = faces
    checks: dict[str, bool] = {}
    if header:
        objects = {header["logo"], header["bill_box"]}
        pool = [f for f in faces if f not in objects] + list(header["cells"].values())
        checks = header["checks"]
        print(f"block 1: logo box {header['logo']}, BILL OF LADING box {header['bill_box']}, "
              f"header text ends x={header['text_right']}, split at x={header['split_x']}")
    else:
        print("block 1: logo / BILL OF LADING boxes not found", file=sys.stderr)
    print(f"{len(pool)} cell regions; {len(expected_cells)} expected")

    block_rows = compare(expected_blocks, list(blocks.values()), args.threshold)
    cell_rows = compare(expected_cells, pool, args.threshold)
    matched = {tuple(r["detected"]) for r in cell_rows if r["detected"]}
    unmatched = [list(f) for f in pool if f not in matched]
    print_rows("Blocks", block_rows)
    print_rows("Cells", cell_rows)
    for name, ok in checks.items():
        print(f"check: {name}: {'ok' if ok else 'FAILED'}")
    print(f"\ndetected regions matching no expected cell: {len(unmatched)}")
    for box in unmatched:
        print("  ", box)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    draw_overlay(page, expected_cells, pool, blocks, args.out_dir / "overlay.png")
    report = {
        "page": str(args.page), "threshold": args.threshold,
        "form_edges": [left, right], "rules_y": rules,
        "header": header and {k: (list(v) if isinstance(v, tuple) else v)
                              for k, v in header.items() if k != "cells"},
        "blocks": block_rows, "cells": cell_rows, "unmatched_regions": unmatched,
    }
    (args.out_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    failed = [r["name"] for r in block_rows + cell_rows if not r["pass"]]
    failed += [name for name, ok in checks.items() if not ok]
    total = len(block_rows) + len(cell_rows) + len(checks)
    print(f"\n{total - len(failed)}/{total} checks at IoU >= {args.threshold}; "
          f"wrote {args.out_dir}/report.json and overlay.png")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
