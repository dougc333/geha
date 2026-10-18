"""Browser-use agent that draws figure bounding boxes in the annotator UI.

Starts the annotator backend for any PDF, opens it in Playwright Chromium, and lets
Claude look at each rendered page and drag boxes around figures, logos, charts,
tables and images, exactly as a person would with the mouse. After every action
the agent gets a fresh screenshot showing its boxes, so it can fix a bad one.
The UI autosaves through its normal API, so the boxes land in the same
figure-bounding-boxes.json format (normalized 0..1000) the human workflow uses.

    cd /Users/dc/geha
    .venv/bin/python -m bounding_box.figure_bbox_app.browser_bbox_agent \
        --pdf /Users/dc/ocr-mini-bench/bench_documents/Invoices/medical_bill_en.pdf --headed
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anthropic
import pymupdf as fitz
from PIL import Image
from playwright.sync_api import Page, sync_playwright

APP_DIR = Path(__file__).resolve().parent
REPO_DIR = APP_DIR.parents[1]
MAX_IMAGE_EDGE = 1568
KINDS = ["figure", "chart", "table", "image", "other"]
USAGE = {"calls": 0, "input_tokens": 0, "output_tokens": 0}

SYSTEM = """You are a document-layout annotator operating a bounding-box web app.
You see one rendered PDF page. Draw a box around every region that is not plain
running text: charts and graphs, tables (including bordered key/value panels),
logos, photos and other images, diagrams, stamps, signatures, barcodes and QR codes.
Do not box headings, paragraphs, addresses or footers on their own.

Coordinates are pixels in the most recent screenshot, origin top-left. Make each box
tight but include the whole region (table borders, header row, legend, axis labels).
After each draw_box you get a new screenshot with your boxes drawn in the overlay and
numbered; if one is wrong, delete_box it and redraw. Call finish when every region is
boxed exactly once."""

TOOLS = [
    {
        "name": "draw_box",
        "description": "Drag a rectangle on the page and set its type and label.",
        "input_schema": {
            "type": "object",
            "properties": {
                "x1": {"type": "number"}, "y1": {"type": "number"},
                "x2": {"type": "number"}, "y2": {"type": "number"},
                "kind": {"type": "string", "enum": KINDS},
                "label": {"type": "string", "description": "short name, e.g. 'Itemized charges table'"},
            },
            "required": ["x1", "y1", "x2", "y2", "kind", "label"],
        },
    },
    {
        "name": "delete_box",
        "description": "Delete a box by the number shown on it.",
        "input_schema": {"type": "object", "properties": {"number": {"type": "integer"}}, "required": ["number"]},
    },
    {
        "name": "finish",
        "description": "Every region on this page is boxed.",
        "input_schema": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]},
    },
]


class PageView:
    """The rendered page surface: screenshots out, mouse drags in, same pixel frame."""

    def __init__(self, page: Page):
        self.page = page
        self.scale = 1.0  # screenshot pixels per CSS pixel

    def screenshot(self) -> tuple[dict[str, Any], tuple[int, int]]:
        self.page.wait_for_selector(".page-surface.ready")
        self.page.wait_for_timeout(300)
        surface = self.page.locator(".page-surface")
        image = Image.open(io.BytesIO(surface.screenshot()))
        css_width = surface.bounding_box()["width"]
        if max(image.size) > MAX_IMAGE_EDGE:
            ratio = MAX_IMAGE_EDGE / max(image.size)
            image = image.resize((round(image.width * ratio), round(image.height * ratio)), Image.LANCZOS)
        self.scale = image.width / css_width
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png",
                       "data": base64.b64encode(buffer.getvalue()).decode()},
        }, image.size

    def drag(self, x1: float, y1: float, x2: float, y2: float) -> None:
        surface = self.page.locator(".page-surface")
        surface.scroll_into_view_if_needed()
        box = surface.bounding_box()
        to_view = lambda x, y: (box["x"] + x / self.scale, box["y"] + y / self.scale)  # noqa: E731
        start, end = to_view(min(x1, x2), min(y1, y2)), to_view(max(x1, x2), max(y1, y2))
        self.page.mouse.move(*start)
        self.page.mouse.down()
        self.page.mouse.move(*end, steps=12)
        self.page.mouse.up()

    def label_selected(self, kind: str, label: str) -> None:
        self.page.get_by_label("Type").select_option(kind)
        self.page.get_by_label("Label").fill(label[:160])
        self.page.keyboard.press("Escape")

    def delete(self, number: int) -> bool:
        cards = self.page.locator(".region-card")
        if not 1 <= number <= cards.count():
            return False
        cards.nth(number - 1).click()
        self.page.get_by_role("button", name="Delete selected region").click()
        return True

    def box_count(self) -> int:
        return self.page.locator(".region-card").count()


def annotate_page(client: anthropic.Anthropic, model: str, view: PageView, page_number: int,
                  max_turns: int) -> str:
    image, (width, height) = view.screenshot()
    messages: list[dict[str, Any]] = [{"role": "user", "content": [
        image,
        {"type": "text", "text": f"Page {page_number}. Screenshot is {width}x{height} px. "
                                 f"{view.box_count()} boxes already drawn. Box every figure-like region."},
    ]}]
    for _ in range(max_turns):
        response = client.messages.create(model=model, max_tokens=4096, system=SYSTEM, tools=TOOLS,
                                          messages=messages)
        USAGE["calls"] += 1
        USAGE["input_tokens"] += response.usage.input_tokens
        USAGE["output_tokens"] += response.usage.output_tokens
        messages.append({"role": "assistant", "content": response.content})
        calls = [block for block in response.content if block.type == "tool_use"]
        if not calls:
            return "".join(block.text for block in response.content if block.type == "text")
        results = []
        for call in calls:
            args = call.input
            if call.name == "finish":
                return args.get("summary", "")
            if call.name == "draw_box":
                before = view.box_count()
                view.drag(args["x1"], args["y1"], args["x2"], args["y2"])
                if view.box_count() > before:
                    view.label_selected(args["kind"], args["label"])
                    text = f"Drew box {before + 1}: {args['kind']} '{args['label']}'."
                else:
                    text = "No box was created (too small or off the page)."
            else:
                text = f"Deleted box {args['number']}." if view.delete(args["number"]) else "No such box."
            print(f"  page {page_number}: {text}")
            results.append({"type": "tool_result", "tool_use_id": call.id, "content": text})
        image, _ = view.screenshot()
        results[-1]["content"] = [{"type": "text", "text": results[-1]["content"]}, image]
        messages.append({"role": "user", "content": results})
    return f"stopped after {max_turns} turns"


def wait_for_backend(url: str, process: subprocess.Popen, timeout: float = 30) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError("annotator backend exited; see its output above")
        try:
            urllib.request.urlopen(f"{url}/api/document", timeout=2)
            return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError(f"annotator backend did not start at {url}")


def write_summary(annotation_path: Path, pdf: Path, model: str, summaries: dict[int, str]) -> Path:
    """Sidecar with PDF-point coordinates next to the normalized ones the UI saves."""
    annotations = json.loads(annotation_path.read_text())
    with fitz.open(pdf) as document:
        sizes = {n + 1: (document[n].rect.width, document[n].rect.height) for n in range(document.page_count)}
    regions = []
    for page_key, boxes in annotations["pages"].items():
        width, height = sizes[int(page_key)]
        for box in boxes:
            regions.append({
                "page": int(page_key), "id": box["id"], "kind": box["kind"], "label": box["label"],
                "box_normalized_0_1000": [box["x1"], box["y1"], box["x2"], box["y2"]],
                "box_pdf_pt": [round(box["x1"] * width / 1000, 2), round(box["y1"] * height / 1000, 2),
                               round(box["x2"] * width / 1000, 2), round(box["y2"] * height / 1000, 2)],
            })
    out = annotation_path.with_name("browser-agent-run.json")
    out.write_text(json.dumps({
        "source_pdf": str(pdf), "model": model,
        "finished_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "annotation_file": str(annotation_path),
        "page_summaries": {str(k): v for k, v in summaries.items()},
        "usage": USAGE,
        "regions": regions,
    }, indent=2) + "\n")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, help="default: bounding_box/annotations/other/<pdf stem>")
    parser.add_argument("--pages", help="comma-separated 1-based pages (default: all)")
    parser.add_argument("--model", default="claude-opus-5-5")
    parser.add_argument("--port", type=int, default=8512)
    parser.add_argument("--max-turns", type=int, default=15)
    parser.add_argument("--headed", action="store_true", help="show the browser window")
    args = parser.parse_args()

    pdf = args.pdf.resolve()
    out_dir = (args.out_dir or REPO_DIR / "bounding_box" / "annotations" / "other" / pdf.stem).resolve()
    with fitz.open(pdf) as document:
        page_count = document.page_count
    pages = [int(p) for p in args.pages.split(",")] if args.pages else list(range(1, page_count + 1))

    url = f"http://127.0.0.1:{args.port}"
    backend = subprocess.Popen(
        [sys.executable, "-m", "bounding_box.figure_bbox_app.backend", "--pdf", str(pdf),
         "--out-dir", str(out_dir), "--port", str(args.port)],
        cwd=REPO_DIR, env=os.environ.copy(),
    )
    client = anthropic.Anthropic()
    summaries: dict[int, str] = {}
    try:
        wait_for_backend(url, backend)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            # Tall viewport so the whole page surface is on screen for mouse drags.
            page = browser.new_page(viewport={"width": 1600, "height": 2400})
            page.goto(url)
            view = PageView(page)
            for number in pages:
                page.locator("nav select").select_option(str(number))
                print(f"page {number}/{page_count}")
                summaries[number] = annotate_page(client, args.model, view, number, args.max_turns)
            page.get_by_text("All changes saved").wait_for(timeout=10_000)
            browser.close()
    finally:
        backend.terminate()
        backend.wait(timeout=10)

    annotation_path = out_dir / "figure-bounding-boxes.json"
    summary_path = write_summary(annotation_path, pdf, args.model, summaries)
    print(f"boxes:   {annotation_path}\nsummary: {summary_path}")
    print(f"usage:   {USAGE['calls']} calls, {USAGE['input_tokens']:,} input / {USAGE['output_tokens']:,} output tokens")


if __name__ == "__main__":
    main()
