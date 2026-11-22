#!/usr/bin/env python3
"""Build a visual old-vs-refined bill-of-lading crop and OCR comparison."""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw


HERE = Path(__file__).resolve().parent


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower().replace("°", ""))


def draw_layout(source: Image.Image, module, title: str, output: Path) -> Image.Image:
    page = source.convert("RGB").copy()
    pen = ImageDraw.Draw(page)
    for number, (left, top, right, bottom) in module.BLOCKS.items():
        pen.rectangle((left, top, right, bottom), outline="#ed3030", width=6)
        pen.text((left + 8, top + 8), f"BLOCK {number}", fill="#b00000")
        for name, (x1, y1, x2, y2) in module.CELLS[number].items():
            absolute = (left + x1, top + y1, left + x2, top + y2)
            pen.rectangle(absolute, outline="#0565e8", width=3)
            pen.text((absolute[0] + 5, absolute[1] + 24), name, fill="#0245a7")
    page.save(output)
    return page


def labeled_pair(old: Image.Image, new: Image.Image, *, crop_bottom: int | None,
                 output: Path) -> None:
    if crop_bottom is not None:
        old = old.crop((0, 0, old.width, crop_bottom))
        new = new.crop((0, 0, new.width, crop_bottom))
    margin, caption = 24, 72
    combined = Image.new("RGB", (old.width + new.width + margin * 3,
                                 max(old.height, new.height) + caption + margin * 2), "#f2f5fa")
    draw = ImageDraw.Draw(combined)
    draw.text((margin, margin + 8), "ORIGINAL OCR COORDINATES", fill="#162338")
    draw.text((old.width + margin * 2, margin + 8), "REFINED COORDINATES", fill="#162338")
    combined.paste(old, (margin, caption))
    combined.paste(new, (old.width + margin * 2, caption))
    combined.save(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--old-layout", type=Path, required=True)
    parser.add_argument("--new-layout", type=Path, required=True)
    parser.add_argument("--old-results", type=Path, required=True)
    parser.add_argument("--new-results", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    source = Image.open(args.source)
    old = load_module("old_layout", args.old_layout)
    new = load_module("new_layout", args.new_layout)
    old_image = draw_layout(source, old, "Original", args.output_dir / "original_overlay.png")
    new_image = draw_layout(source, new, "Refined", args.output_dir / "refined_overlay.png")
    labeled_pair(old_image, new_image, crop_bottom=None,
                 output=args.output_dir / "full_comparison.png")
    labeled_pair(old_image, new_image, crop_bottom=420,
                 output=args.output_dir / "header_comparison.png")

    old_run = json.loads(args.old_results.read_text())
    new_run = json.loads(args.new_results.read_text())
    def source_path(record: dict, layout_path: Path) -> Path:
        path = Path(record["page_png"])
        return (path if path.is_absolute() else layout_path.parent / path).resolve()

    if (source_path(old_run, args.old_layout) != args.source.resolve()
            or source_path(new_run, args.new_layout) != args.source.resolve()
            or old_run["model"] != new_run["model"]):
        raise ValueError("OCR runs used different source images or models")
    rows = []
    exact = normalized = 0
    for old_block, new_block in zip(old_run["blocks"], new_run["blocks"]):
        if old_block["block"] != new_block["block"]:
            raise ValueError("OCR block numbering differs")
        for name, old_text in old_block["cells"].items():
            new_text = new_block["cells"][name]
            exact += old_text == new_text
            normalized += normalize(old_text) == normalize(new_text)
            if old_text != new_text:
                label = "Formatting only" if normalize(old_text) == normalize(new_text) else "Text changed"
                rows.append(
                    f"<tr><td>{old_block['block']}.{html.escape(name)}</td><td>{label}</td>"
                    f"<td><pre>{html.escape(old_text)}</pre></td>"
                    f"<td><pre>{html.escape(new_text)}</pre></td></tr>"
                )
    total = sum(len(block["cells"]) for block in old_run["blocks"])
    summary = {
        "old_expected_match": old_run["summary"],
        "refined_expected_match": new_run["summary"],
        "total_cells": total,
        "exactly_equal_cells": exact,
        "normalized_equal_cells": normalized,
        "changed_cells": len(rows),
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bill-of-lading layout comparison</title>
<style>body{{font:16px system-ui,sans-serif;color:#152238;background:#f3f6fa;margin:0;padding:24px}}
h1,h2{{margin:0 0 16px}}p{{line-height:1.5}}.panels{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
figure{{margin:0;background:#fff;padding:12px;border:1px solid #ccd6e4;border-radius:8px}}
figure img{{width:100%;height:auto}}figcaption{{font-weight:700;margin:0 0 10px}}
table{{border-collapse:collapse;width:100%;background:white}}td,th{{border:1px solid #ccd6e4;padding:10px;text-align:left;vertical-align:top}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;margin:0;font:13px/1.4 ui-monospace,monospace}}
.key{{color:#355275}}@media(max-width:1000px){{.panels{{grid-template-columns:1fr}}}}</style></head><body>
<h1>Bill-of-lading layout comparison</h1>
<p class="key">Red: block boundaries. Blue: cell boundaries. The same source page appears in both panels.</p>
<p>Original: {old_run['summary']['matched_items']}/{old_run['summary']['expected_items']} expected strings.
Refined: {new_run['summary']['matched_items']}/{new_run['summary']['expected_items']}.
Cell text: {exact}/{total} exactly equal; {normalized}/{total} equal after normalization.</p>
<div class="panels"><figure><figcaption>Original OCR coordinates</figcaption><img src="original_overlay.png" alt="Original crop boundaries"></figure>
<figure><figcaption>Refined coordinates</figcaption><img src="refined_overlay.png" alt="Refined crop boundaries"></figure></div>
<h2>Cells with different OCR formatting or text</h2>
<table><thead><tr><th>Cell</th><th>Difference</th><th>Original OCR</th><th>Refined OCR</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<p>The expected-string score checks configured values; it is not a character-by-character ground-truth evaluation.</p>
</body></html>"""
    (args.output_dir / "index.html").write_text(page)
    print(args.output_dir / "index.html")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
