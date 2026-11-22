"""Time table-only HTML generation, PNG review, and correction on Bendamustine."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
import unicodedata
from pathlib import Path

import anthropic
import pymupdf
from bs4 import BeautifulSoup
from PIL import Image
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "inputs" / "bendamustine-page-001.pdf"
REFERENCE = ROOT / "inputs" / "bendamustine-table-001-reference.json"
OUT = ROOT / "results" / "bendamustine-html-loop-poc"
SPEC_REPORT = ROOT / "results" / "bendamustine-table-spec-poc" / "report.json"
MODEL = os.environ.get("TABLE_SPEC_MODEL", "claude-sonnet-5-5")
HEADERS = ["Preference", "Requires Prior Auth", "Drug Name", "HCPCS Code", "Description"]
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(ROOT / ".browsers"))


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", unicodedata.normalize("NFKD", value).casefold())


def text_response(message: object) -> str:
    return "".join(block.text for block in message.content if block.type == "text")


def un_fence(value: str) -> str:
    value = value.strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return value


def image_part(png: bytes) -> dict:
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                       "data": base64.b64encode(png).decode("ascii")}}


def prepare() -> tuple[dict, bytes, tuple[int, int]]:
    with pymupdf.open(PDF) as doc:
        page = doc[0]
        table = page.find_tables().tables[0]
        grid = table.extract()
        last = next(i for i, row in enumerate(grid) if any("J9056" in str(cell) for cell in row))
        rect = pymupdf.Rect(table.bbox[0] - 4, table.bbox[1] - 4,
                            table.bbox[2] + 4, table.rows[last].bbox[3])
        words = [{"text": w[4], "box": [round(v, 1) for v in w[:4]]}
                 for w in page.get_text("words", clip=rect, sort=True)]
        png = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=rect, alpha=False).tobytes("png")
        native_text = page.get_text("text", clip=rect, sort=True)
        evidence = {"source_sha256": hashlib.sha256(PDF.read_bytes()).hexdigest(),
                    "page": 1, "box_pt": [round(v, 2) for v in rect],
                    "native_text": native_text, "words": words,
                    "raw_pymupdf_grid": grid[:last + 1]}
    import io
    size = Image.open(io.BytesIO(png)).size
    return evidence, png, size


def render(html: str, png_path: Path, size: tuple[int, int]) -> bytes:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": size[0], "height": size[1]}, device_scale_factor=1)
        page.set_content(html, wait_until="load")
        png = page.screenshot(path=str(png_path), full_page=False, animations="disabled")
        browser.close()
    return png


def table_rows(html: str) -> tuple[list[str], list[dict[str, str]]]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if table is None:
        raise ValueError("Generated HTML has no semantic table")
    thead = table.find("thead")
    tbody = table.find("tbody")
    if thead is None or tbody is None:
        raise ValueError("Generated table requires thead and tbody")
    headers = [cell.get_text(" ", strip=True) for cell in thead.find_all(["th", "td"])]
    rows = []
    for tr in tbody.find_all("tr", recursive=False):
        values = [cell.get_text(" ", strip=True) for cell in tr.find_all(["th", "td"], recursive=False)]
        if len(values) != len(headers):
            raise ValueError(f"Row has {len(values)} cells, expected {len(headers)}")
        rows.append(dict(zip(headers, values)))
    return headers, rows


def compare(rows: list[dict[str, str]]) -> list[dict]:
    expected = json.loads(REFERENCE.read_text())["rows"]
    differences = []
    if len(rows) != len(expected):
        differences.append({"row_count": {"actual": len(rows), "expected": len(expected)}})
    for index, (actual, reference) in enumerate(zip(rows, expected), 1):
        for header in HEADERS:
            if norm(actual.get(header, "")) != norm(reference[header]):
                differences.append({"row": index, "column": header,
                                    "actual": actual.get(header), "reference": reference[header]})
    return differences


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    client = anthropic.Anthropic()
    started = time.perf_counter()
    steps = []
    stage = time.perf_counter()
    evidence, source_png, size = prepare()
    (OUT / "source-crop.png").write_bytes(source_png)
    (OUT / "evidence.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n")
    steps.append({"stage": "pymupdf_evidence", "ms": round((time.perf_counter() - stage) * 1000, 2)})

    prompt = (
        "Build a complete standalone semantic HTML document matching ONLY the attached PDF table crop. "
        "Return HTML only, with inline CSS, a visible five-column table using thead and tbody, "
        "and exactly five drug data rows. Preserve all printed table text. "
        "The raw PyMuPDF grid has spurious empty columns; omit them. "
        "Render for an exact viewport of %d by %d CSS pixels. "
        "Do not use any prior spec or HTML. Use this PDF evidence:\n%s"
        % (size[0], size[1], json.dumps(evidence, ensure_ascii=False))
    )
    stage = time.perf_counter()
    generation = client.messages.create(model=MODEL, max_tokens=5000,
        messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, image_part(source_png)]}])
    steps.append({"stage": "generate_html_llm", "ms": round((time.perf_counter() - stage) * 1000, 2),
                  "input_tokens": generation.usage.input_tokens, "output_tokens": generation.usage.output_tokens})
    html = un_fence(text_response(generation))
    last_review = None
    final_rows = []
    status = "max_iterations"
    for iteration in range(1, 4):
        (OUT / f"iteration-{iteration:02d}.html").write_text(html)
        stage = time.perf_counter()
        rendered_png = render(html, OUT / f"iteration-{iteration:02d}.png", size)
        steps.append({"stage": "render_html_png", "iteration": iteration,
                      "ms": round((time.perf_counter() - stage) * 1000, 2)})

        stage = time.perf_counter()
        try:
            headers, rows = table_rows(html)
            differences = compare(rows) if headers == HEADERS else [{"headers": headers}]
            final_rows = rows
        except Exception as exc:
            differences = [{"parse_error": str(exc)}]
        steps.append({"stage": "extract_and_compare_table", "iteration": iteration,
                      "ms": round((time.perf_counter() - stage) * 1000, 2),
                      "differences": differences})

        stage = time.perf_counter()
        review_prompt = (
            "Compare the first image (source PDF table) to the second image (rendered HTML table). "
            "Check all five rows and columns, which value belongs in each cell, missing text, "
            "clipping, and major layout differences. The extracted-table comparison findings are: "
            + json.dumps(differences) + ". Return only JSON: {\"passed\": boolean, \"issues\": [strings]}. "
            "Pass only if data cells match and the table is legible and complete."
        )
        review = client.messages.create(model=MODEL, max_tokens=1200,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": review_prompt}, image_part(source_png), image_part(rendered_png)]}])
        steps.append({"stage": "review_png_llm", "iteration": iteration,
                      "ms": round((time.perf_counter() - stage) * 1000, 2),
                      "input_tokens": review.usage.input_tokens, "output_tokens": review.usage.output_tokens})
        try:
            last_review = json.loads(un_fence(text_response(review)))
        except json.JSONDecodeError:
            last_review = {"passed": False, "issues": [text_response(review)]}
        (OUT / f"review-{iteration:02d}.json").write_text(json.dumps(last_review, indent=2) + "\n")
        if last_review.get("passed") and not differences:
            status = "passed"
            break
        if iteration == 3:
            break
        stage = time.perf_counter()
        correction_prompt = (
            "Correct this standalone HTML table to match the source image. Return only complete HTML. "
            "Reviewer issues: " + json.dumps(last_review.get("issues", [])) +
            ". Table extraction differences: " + json.dumps(differences) +
            ". Current HTML:\n" + html
        )
        correction = client.messages.create(model=MODEL, max_tokens=5000,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": correction_prompt}, image_part(source_png), image_part(rendered_png)]}])
        steps.append({"stage": "correct_html_llm", "iteration": iteration,
                      "ms": round((time.perf_counter() - stage) * 1000, 2),
                      "input_tokens": correction.usage.input_tokens, "output_tokens": correction.usage.output_tokens})
        html = un_fence(text_response(correction))

    total = round((time.perf_counter() - started) * 1000, 2)
    spec_report = json.loads(SPEC_REPORT.read_text())
    spec_ms = spec_report["timings_ms"]["total_ms"]
    report = {"model": MODEL, "status": status, "iterations": iteration,
              "html_total_ms": total, "prior_spec_total_ms": spec_ms,
              "ratio_html_to_spec": round(total / spec_ms, 2),
              "reference_cells_matched": 25 - len(compare(final_rows)) if len(final_rows) == 5 else None,
              "review": last_review, "steps": steps,
              "note": "Spec timing comes from an earlier run; reference table review_status is pending."}
    (OUT / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
