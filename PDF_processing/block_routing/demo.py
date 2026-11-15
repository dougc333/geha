#!/usr/bin/env python3
"""Offline demo on the ocr-mini-bench invoices. No model, no Jev, no network.

  /Users/dc/geha/.venv/bin/python demo.py [--bench /Users/dc/ocr-mini-bench/bench_documents/Invoices] [--overlay out.png]

For each invoice it prints: layout features, the routing decision (jev=False so the chain ends in the deterministic
fallback), and the quality checks run on the benchmark's own ground truth (a sanity test of the validators: correct
data should score near 1.0).
"""
import argparse
import json
import sys
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from block_router import candidate_cuts, decide, layout_features, quality  # noqa: E402


def plain(o):
    """Benchmark field objects {'value','critical','type'} -> plain values."""
    if isinstance(o, dict):
        if "value" in o and ("critical" in o or "type" in o):
            return o["value"]
        return {k: plain(v) for k, v in o.items()}
    if isinstance(o, list):
        return [plain(v) for v in o]
    return o


def count_leaves(o):
    if isinstance(o, dict):
        return 1 if "value" in o and ("critical" in o or "type" in o) else sum(count_leaves(v) for v in o.values())
    if isinstance(o, list):
        return sum(count_leaves(v) for v in o)
    return 0


def render(pdf: Path, dpi=100) -> Image.Image:
    return Image.open(__import__("io").BytesIO(pymupdf.open(pdf)[0].get_pixmap(dpi=dpi).tobytes("png"))).convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", default="/Users/dc/ocr-mini-bench/bench_documents/Invoices")
    ap.add_argument("--overlay")
    a = ap.parse_args()
    bench = Path(a.bench)
    print(f"{'document':34} {'fields':>6} {'cuts':>4} {'rules':>5}  {'GT quality':>10}  decision")
    scores = []
    for pdf in sorted(bench.glob("*.pdf")):
        gt = json.loads((bench / "ground_truth" / f"{pdf.stem}.json").read_text())
        img = render(pdf)
        feats = {"family": "invoice", "n_expected_fields": count_leaves(gt), **layout_features(img)}
        d = decide(feats, jev=False)
        q = quality("invoice", plain(gt))
        scores.append(q["score"])
        print(f"{pdf.stem[:34]:34} {feats['n_expected_fields']:>6} {feats['n_candidate_cuts']:>4} {feats['n_rules']:>5}  {q['score']:>10}  "
              f"{'blocks' if d.use_blocks else 'single'} ({d.method})")
        if a.overlay and pdf == sorted(bench.glob("*.pdf"))[0]:
            dr = ImageDraw.Draw(img)
            for c in candidate_cuts(img):
                dr.line([(0, c["y"]), (img.width, c["y"])], fill="red" if c["kind"] == "rule" else "blue", width=2)
                dr.text((4, c["y"] - 10), c["id"], fill="black")
            img.save(a.overlay)
    print(f"\nquality score of the ground truth itself: mean {sum(scores) / len(scores):.3f}, min {min(scores):.3f}")


if __name__ == "__main__":
    main()
