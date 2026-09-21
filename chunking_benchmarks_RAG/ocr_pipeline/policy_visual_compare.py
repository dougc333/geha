"""Opt-in OpenAI visual checks for staged, synthetic policy artifacts.

Only page PNGs, one contextualized Docling chunk or one rendered HTML table,
and comparison instructions are sent to the OpenAI Responses API. Findings are
model-generated QC suggestions; they are never written into GEHA policy data.
"""

from __future__ import annotations

import base64
import html
import json
import re
import textwrap
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
from PIL import Image, ImageDraw, ImageFont


ISSUE_TYPES = (
    "heading_mismatch", "numeric_header_row", "missing_content",
    "extra_content", "cell_mismatch", "other",
)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def render_html_table_png(html_path: Path, output_path: Path, *, rows: int) -> Path:
    """Render all cells from staged HTML into a legible PNG without a browser.

    This is a faithful rendering of the extracted table data, not a pixel-exact
    screenshot of its CSS. The source HTML remains the review artifact.
    """
    source = html_path.read_text(encoding="utf-8")
    match = re.search(r"<table\b[^>]*>.*?</table>", source, re.I | re.S)
    if not match:
        raise ValueError(f"No table found in {html_path}")
    frames = pd.read_html(StringIO(match.group(0)))
    if len(frames) != 1:
        raise ValueError(f"Expected one table in {html_path}")
    frame = frames[0].fillna("")
    if frame.shape[0] != rows:
        raise ValueError("HTML row count differs from extraction metadata")
    headings = [str(column) for column in frame.columns]
    values = [[str(value) for value in row] for row in frame.itertuples(index=False, name=None)]
    title_match = re.search(r"<h1\b[^>]*>(.*?)</h1>", source, re.I | re.S)
    title = html.unescape(re.sub(r"<[^>]+>", "", title_match.group(1))).strip() \
        if title_match else html_path.stem

    width, margin, font_size, line_height = 1800, 40, 20, 27
    font = ImageFont.load_default(size=font_size)
    title_font = ImageFont.load_default(size=30)
    usable = width - 2 * margin
    minimum = max(120, usable // (len(headings) * 2))
    if minimum * len(headings) > usable:
        raise ValueError("Too many columns for a legible single-image comparison")
    weights = [
        max(12, min(48, max([len(headings[index]), *[
            len(row[index]) for row in values
        ]]))) for index in range(len(headings))
    ]
    remaining = usable - minimum * len(headings)
    column_widths = [minimum + remaining * weight // sum(weights) for weight in weights]
    column_widths[-1] += usable - sum(column_widths)

    def wrap(value: str, cell_width: int) -> list[str]:
        # DejaVu's default font is approximately 11 px per character at size 20.
        limit = max(8, (cell_width - 24) // 11)
        lines: list[str] = []
        for paragraph in value.splitlines() or [""]:
            lines.extend(textwrap.wrap(paragraph, width=limit, break_long_words=True) or [""])
        return lines

    all_rows = [headings, *values]
    wrapped = [[wrap(cell, column_widths[index]) for index, cell in enumerate(row)]
               for row in all_rows]
    heights = [max(50, max(len(cell_lines) for cell_lines in row) * line_height + 24)
               for row in wrapped]
    height = 125 + sum(heights) + 40
    if height > 16000:
        raise ValueError("Table is too tall for a complete single-image comparison")
    image = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(image)
    draw.text((margin, 28), title, font=title_font, fill="#071f36")
    y = 125
    for row_index, (cells, row_height) in enumerate(zip(wrapped, heights)):
        background = "#06233d" if row_index == 0 else (
            "#f4f7f9" if row_index % 2 == 0 else "#ffffff"
        )
        x = margin
        for col_index, lines in enumerate(cells):
            cell_width = column_widths[col_index]
            draw.rectangle((x, y, x + cell_width, y + row_height),
                           fill=background, outline="#d6dee6", width=1)
            for line_index, line in enumerate(lines):
                draw.text((x + 12, y + 12 + line_index * line_height), line,
                          font=font, fill="#ffffff" if row_index == 0 else "#071f36")
            x += cell_width
        y += row_height
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG")
    if not output_path.is_file() or output_path.read_bytes()[:8] != PNG_SIGNATURE:
        raise ValueError("Chrome did not produce a valid HTML-table screenshot")
    return output_path


def _schema() -> dict[str, Any]:
    issue = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "type": {"type": "string", "enum": list(ISSUE_TYPES)},
            "location": {"type": "string"},
            "pdf_value": {"type": "string"},
            "extracted_value": {"type": "string"},
            "explanation": {"type": "string"},
        },
        "required": ["type", "location", "pdf_value", "extracted_value", "explanation"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "verdict": {"type": "string", "enum": ["match", "mismatch", "uncertain"]},
            "issues": {"type": "array", "items": issue},
        },
        "required": ["verdict", "issues"],
    }


def _image_item(path: Path) -> dict[str, str]:
    if path.read_bytes()[:8] != PNG_SIGNATURE:
        raise ValueError(f"Not a PNG image: {path}")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return {"type": "input_image", "image_url": f"data:image/png;base64,{encoded}"}


def compare_with_openai(
    *, kind: str, pdf_images: list[Path], model: str,
    extracted_text: str = "", extracted_image: Path | None = None,
    heading: str = "", identifier: str = "",
) -> dict[str, Any]:
    """Compare one chunk or table with its source pages; never auto-correct it."""
    if kind not in {"chunk", "table"} or not pdf_images:
        raise ValueError("kind must be chunk/table and at least one PDF image is required")
    if kind == "table" and extracted_image is None:
        raise ValueError("A table comparison requires a rendered HTML image")
    if not model:
        raise ValueError("Specify a vision-capable model")

    from openai import OpenAI

    if kind == "chunk":
        instructions = (
            "Compare the assigned Docling heading(s) and this chunk's section "
            "association with the source PDF page image(s). Check whether the "
            "heading actually labels the visible source content. The chunk body "
            "is context only; do not flag wording/formatting differences in it. "
            "If a heading may appear on a prior page not supplied, say uncertain. "
            "Do not infer diagnoses or policy facts."
        )
    else:
        instructions = (
            "Compare the rendered extracted HTML table with the corresponding "
            "source PDF page image(s). Check the closest source heading, column "
            "labels, rows, and visible cell values. The PDF is the source of truth. "
            "Use numeric_header_row only if numeric placeholder columns in the "
            "HTML correspond to actual labels shown as the first data row. "
            "If a full table is not visible or legible, say uncertain."
        )
    content: list[dict[str, str]] = [{
        "type": "input_text",
        "text": (
            f"{instructions}\nIdentifier: {identifier}\nAssigned heading: {heading}\n"
            f"Extracted chunk text (context only):\n{extracted_text}" if kind == "chunk"
            else f"{instructions}\nIdentifier: {identifier}\nExtracted table heading: {heading}"
        ),
    }]
    for page_image in pdf_images:
        content.append({"type": "input_text", "text": f"Source PDF page: {page_image.name}"})
        content.append(_image_item(page_image))
    if extracted_image is not None:
        content.append({"type": "input_text", "text": "Rendered extracted HTML table:"})
        content.append(_image_item(extracted_image))

    response = OpenAI(max_retries=1, timeout=90).responses.create(
        model=model,
        store=False,
        input=[{"role": "user", "content": content}],
        text={"format": {
            "type": "json_schema", "name": "policy_visual_qc", "strict": True,
            "schema": _schema(),
        }},
    )
    result = json.loads(response.output_text)
    if result.get("verdict") not in {"match", "mismatch", "uncertain"}:
        raise ValueError("Invalid model verdict")
    issues = result.get("issues")
    if not isinstance(issues, list) or any(
        not isinstance(item, dict) or item.get("type") not in ISSUE_TYPES
        for item in issues
    ):
        raise ValueError("Invalid model issue list")
    if result["verdict"] == "mismatch" and not issues:
        raise ValueError("Mismatch verdict without issue details")
    if result["verdict"] == "match" and issues:
        raise ValueError("Match verdict cannot include issues")
    return result
