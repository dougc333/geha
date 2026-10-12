from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pymupdf
from PIL import Image, ImageDraw, ImageFont

from crawl_dir.src.pipeline.artifact_io import atomic_json
from crawl_dir.src.pipeline.figure_segmentation import (
    MAX_FIGURE_ITERATIONS,
    generate_page_html_with_corrected_figures,
)
from crawl_dir.src.pipeline.scanned_ingestion import render_pdf_page_with_pymupdf

from .backend import (
    ANNOTATION_PATH,
    CRAWL_DIR,
    DOCUMENT_ID,
    SOURCE_PDF,
    load_annotations,
)


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def safe_name(value: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", value.lower()).strip("-") or "figure"


def annotation_sha256() -> str:
    return hashlib.sha256(ANNOTATION_PATH.read_bytes()).hexdigest()


def screenshot_crop_with_playwright(
    source_png: Path,
    pixel_box: list[int],
    output_png: Path,
) -> Path:
    """Use headless Chromium to capture an exact rectangle from a page PNG."""
    from playwright.sync_api import sync_playwright

    with Image.open(source_png) as opened:
        width, height = opened.size
    x1, y1, x2, y2 = pixel_box
    if not (0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height):
        raise ValueError(f"Crop {pixel_box} is outside source image {width}x{height}")
    preview = output_png.with_name(f".{output_png.stem}-playwright-source.html")
    relative_source = source_png.resolve().as_uri()
    preview.write_text(
        "<!doctype html><meta charset='utf-8'><style>"
        "html,body{margin:0;padding:0;background:#fff;overflow:hidden}"
        f"img{{display:block;width:{width}px;height:{height}px;max-width:none}}"
        f"</style><img src='{relative_source}' alt='PDF page raster'>",
        encoding="utf-8",
    )
    output_png.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(
                    viewport={"width": width, "height": min(height, 4096)},
                    device_scale_factor=1,
                )
                page.goto(preview.resolve().as_uri(), wait_until="load", timeout=30_000)
                page.locator("img").wait_for(state="visible", timeout=30_000)
                page.screenshot(
                    path=str(output_png),
                    clip={"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1},
                    animations="disabled",
                )
            finally:
                browser.close()
    finally:
        preview.unlink(missing_ok=True)
    return output_png


def prepare_page_artifacts(
    page_number: int,
    run_dir: Path,
    *,
    dpi: int = 180,
) -> tuple[Path, dict[str, Any], Path]:
    if not 144 <= dpi <= 600:
        raise ValueError("dpi must be between 144 and 600")
    annotations = load_annotations()
    boxes = annotations.get("pages", {}).get(str(page_number), [])
    if not boxes:
        raise ValueError(f"Page {page_number} has no saved bounding boxes")

    page_dir = run_dir / "pages" / f"page-{page_number:03d}"
    segment_dir = page_dir / "segments"
    segment_dir.mkdir(parents=True, exist_ok=True)
    page_pdf = page_dir / "source.pdf"
    with pymupdf.open(SOURCE_PDF) as source:
        if not 1 <= page_number <= source.page_count:
            raise ValueError(f"Page must be in 1..{source.page_count}")
        target = pymupdf.open()
        try:
            target.insert_pdf(source, from_page=page_number - 1, to_page=page_number - 1)
            target.save(page_pdf)
        finally:
            target.close()

    source_png = render_pdf_page_with_pymupdf(page_pdf, page_dir / "source.png", dpi)
    with Image.open(source_png) as opened:
        source_image = opened.convert("RGB")
    width, height = source_image.size
    overlay = source_image.copy()
    draw = ImageDraw.Draw(overlay)
    font = ImageFont.load_default()
    regions: list[dict[str, Any]] = []
    for index, box in enumerate(boxes, start=1):
        pixel_box = [
            round(float(box["x1"]) * width / 1000),
            round(float(box["y1"]) * height / 1000),
            round(float(box["x2"]) * width / 1000),
            round(float(box["y2"]) * height / 1000),
        ]
        if pixel_box[2] - pixel_box[0] < 8 or pixel_box[3] - pixel_box[1] < 8:
            raise ValueError(f"Box {box['id']} is too small after pixel conversion")
        filename = f"figure-{index:02d}-{safe_name(box['id'])}.png"
        screenshot_crop_with_playwright(
            source_png, pixel_box, segment_dir / filename
        )
        title = str(box.get("label") or f"Figure {index}")
        label = f"{index}: {title}"
        draw.rectangle(tuple(pixel_box), outline=(34, 211, 238), width=max(3, width // 350))
        draw.text(
            (pixel_box[0] + 6, pixel_box[1] + 6),
            label.encode("ascii", "replace").decode(),
            fill=(8, 47, 73), font=font, stroke_width=2, stroke_fill=(255, 255, 255),
        )
        regions.append({
            "id": safe_name(box["id"]),
            "kind": "chart" if box.get("kind") == "chart" else "figure",
            "title": title,
            "reading_order": index,
            "x1": round(float(box["x1"])),
            "y1": round(float(box["y1"])),
            "x2": round(float(box["x2"])),
            "y2": round(float(box["y2"])),
            "label": label,
            "pixel_box": pixel_box,
            "image": filename,
            "annotation_id": box["id"],
            "screenshot_tool": "playwright_chromium",
        })
    overlay.save(segment_dir / "figures-overlay.png")
    segmentation = {
        "schema_version": 1,
        "page_type": "manual_figure_regions",
        "reason": "Authoritative regions supplied by manual bounding-box annotation",
        "regions": regions,
        "coordinate_system": "normalized_0_1000",
        "source_image": str(source_png),
        "overlay": "figures-overlay.png",
        "tool_id": "manual_figure_bbox_html_correction",
        "annotation_source": str(ANNOTATION_PATH),
        "render_dpi": dpi,
        "source_pixel_dimensions": [width, height],
        "crop_screenshot_tool": "playwright_chromium",
    }
    atomic_json(segment_dir / "regions.json", segmentation)
    return source_png, segmentation, segment_dir


def create_result_report(page_number: int, segment_dir: Path, batch: dict[str, Any]) -> Path:
    cards: list[str] = []
    for record in batch["figures"]:
        selected = int(record["selected_iteration"])
        crop = html.escape(record["source_png"])
        rendered = html.escape(record["final_rendered_png"])
        final_html = html.escape(record["final_html"])
        iterations = "".join(
            f"<tr><td>{attempt['iteration']}</td><td>{html.escape(attempt['verdict'])}</td>"
            f"<td>{attempt['error_count']}</td><td><code>{html.escape(attempt['html'])}</code></td></tr>"
            for attempt in record["iterations"]
        )
        cards.append(f"""
        <article>
          <header><div><small>PAGE {page_number} · FIGURE {record['figure']}</small><h2>{html.escape(record['title'])}</h2></div>
          <span class=\"status {record['status']}\">{record['status']}</span></header>
          <div class=\"compare\"><section><h3>Authoritative PNG crop</h3><img src=\"{crop}\"></section>
          <section><h3>Selected HTML render · iteration {selected}</h3><img src=\"{rendered}\"></section></div>
          <p><a href=\"{final_html}\">Open final semantic HTML</a></p>
          <table><thead><tr><th>Iteration</th><th>Verdict</th><th>Errors</th><th>HTML</th></tr></thead><tbody>{iterations}</tbody></table>
        </article>""")
    report = segment_dir / "index.html"
    report.write_text(f"""<!doctype html><html><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width\">
    <title>Page {page_number} figure correction result</title><style>
    :root{{font:15px system-ui;color:#eaf3ff;background:#07101e}}body{{margin:0;padding:28px}}main{{max-width:1500px;margin:auto}}
    h1{{margin:0 0 8px}}.lede{{color:#91a5bf;margin:0 0 24px}}article{{border:1px solid #2a3d58;border-radius:16px;overflow:hidden;background:#0d1829}}
    article>header{{padding:18px 22px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #2a3d58}}small{{color:#55ddf4;font-weight:800;letter-spacing:.13em}}h2{{margin:5px 0 0}}
    .status{{padding:7px 11px;border-radius:999px;font-weight:800;text-transform:uppercase;font-size:11px}}.status.passed{{background:#153f35;color:#7ef0bd}}.status.failed{{background:#4b1f2b;color:#ff9cab}}
    .compare{{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:#2a3d58}}section{{background:#101d30;padding:18px}}h3{{font-size:13px;margin:0 0 12px;color:#adbed3}}img{{width:100%;height:auto;display:block;background:white;border-radius:8px}}
    article>p,article>table{{margin:18px 22px}}a{{color:#62e5f6}}table{{width:calc(100% - 44px);border-collapse:collapse}}th,td{{padding:9px;border-bottom:1px solid #2a3d58;text-align:left}}code{{color:#8fa7c3}}
    </style></head><body><main><h1>Manual bounding box → semantic HTML</h1><p class=\"lede\">One-page checkpoint. No other PDF pages were processed.</p>{''.join(cards)}</main></body></html>""", encoding="utf-8")
    return report


def process_page(
    page_number: int,
    model: str,
    max_iterations: int,
    run_id: str | None,
    *,
    dpi: int = 180,
) -> Path:
    if not 1 <= max_iterations <= MAX_FIGURE_ITERATIONS:
        raise ValueError(f"max_iterations must be in 1..{MAX_FIGURE_ITERATIONS}")
    run_name = run_id or f"manual-figure-{utc_stamp()}"
    run_dir = CRAWL_DIR / "runs" / "research" / DOCUMENT_ID / run_name
    if run_dir.exists():
        raise FileExistsError(f"Run already exists: {run_dir}")
    source_png, segmentation, segment_dir = prepare_page_artifacts(
        page_number, run_dir, dpi=dpi
    )
    events: list[dict[str, Any]] = []
    manifest = {
        "schema_version": 1,
        "run_id": run_name,
        "workflow": "manual_figure_bbox_html_correction",
        "document_id": DOCUMENT_ID,
        "source_pdf": str(SOURCE_PDF),
        "annotation_file": str(ANNOTATION_PATH),
        "annotation_sha256": annotation_sha256(),
        "pages_requested": [page_number],
        "max_iterations": max_iterations,
        "model": model,
        "render_dpi": dpi,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
    }
    atomic_json(run_dir / "run-manifest.json", manifest)
    try:
        generate_page_html_with_corrected_figures(
            source_png,
            segmentation,
            segment_dir,
            model,
            max_iterations=max_iterations,
            assemble_page=False,
            event_sink=events.append,
        )
        batch = json.loads((segment_dir / "batch.json").read_text(encoding="utf-8"))
        manifest["status"] = batch["status"]
        manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
        manifest["batch"] = str(segment_dir / "batch.json")
        manifest["report"] = str(create_result_report(page_number, segment_dir, batch))
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        atomic_json(run_dir / "events.json", events)
        atomic_json(run_dir / "run-manifest.json", manifest)
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Process one manually annotated figure page")
    parser.add_argument("--page", type=int, required=True)
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--max-iterations", type=int, default=6)
    parser.add_argument("--dpi", type=int, default=180)
    parser.add_argument("--run-id")
    args = parser.parse_args()
    output = process_page(
        args.page, args.model, args.max_iterations, args.run_id, dpi=args.dpi
    )
    print(output)


if __name__ == "__main__":
    main()
