"""Extract tables and figures into reviewable, retrieval-safe artifacts."""

from __future__ import annotations

import json
import re
import urllib.request
from base64 import b64encode
from io import BytesIO
from pathlib import Path
from typing import Any, Callable

from geha_processing.tables import table_headers_are_default as _shared_table_headers_are_default


VisionDescriber = Callable[[bytes, str, str], dict[str, Any]]
PageMarkdownExtractor = Callable[[bytes, int, str], str]
PageExtractionErrorHandler = Callable[[int, Exception], None]
NUMBER_PATTERN = re.compile(r"(?<!\w)[+\-]?\$?\d[\d,]*(?:\.\d+)?%?")
NOUS_API_URL = "https://inference-api.nousresearch.com/v1/chat/completions"
NOUS_DEEPSEEK_VISION_MODEL = "deepseek/deepseek-v4.1-flash-1017"


def _figure_prompt(caption: str, native_text: str) -> str:
    return f"""Convert this document figure into structured data.

Return JSON only with exactly these keys:
- title: string
- figure_type: one of chart, diagram, infographic, photograph, other
- summary: string
- legend: array of strings
- series: array of objects with name and points; each point has label and value strings
- notes: array of strings
- literal_text: array containing visible text strings

Preserve every visible numeric value and its relationship to labels. Do not infer values.
Caption supplied by the PDF parser: {caption!r}
Native PDF text inside/near the visual: {native_text!r}
"""


def _parse_json_object(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    result = json.loads(cleaned)
    if not isinstance(result, dict):
        raise ValueError("Vision model did not return a JSON object")
    return result


def _provenance(item: Any) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for provenance in getattr(item, "prov", []) or []:
        if hasattr(provenance, "model_dump"):
            output.append(provenance.model_dump(mode="json", exclude_none=True))
        elif isinstance(provenance, dict):
            output.append(provenance)
    return output


def validate_table_frame(frame: Any) -> list[str]:
    issues: list[str] = []
    rows, columns = frame.shape
    if rows == 0:
        issues.append("table_has_no_rows")
    if columns < 2:
        issues.append("table_has_fewer_than_two_columns")
    if columns and all(not str(column).strip() for column in frame.columns):
        issues.append("table_headers_are_empty")
    if columns and table_headers_are_default(list(frame.columns)):
        issues.append("table_headers_are_default")
    if rows and columns:
        empty_ratio = float(frame.isna().sum().sum()) / float(rows * columns)
        if empty_ratio > 0.5:
            issues.append("table_is_more_than_half_empty")
    return issues


# Preserve the established import path while using the repository-wide rule.
table_headers_are_default = _shared_table_headers_are_default


def validate_figure_spec(spec: dict[str, Any], native_text: str) -> list[str]:
    issues: list[str] = []
    if not spec.get("summary"):
        issues.append("figure_summary_missing")
    if not spec.get("figure_type"):
        issues.append("figure_type_missing")
    native_numbers = set(NUMBER_PATTERN.findall(native_text))
    serialized = json.dumps(spec, ensure_ascii=False)
    missing_numbers = sorted(number for number in native_numbers if number not in serialized)
    if missing_numbers:
        issues.append("native_numeric_tokens_missing:" + ",".join(missing_numbers[:20]))
    return issues


def figure_markdown(spec: dict[str, Any]) -> str:
    title = spec.get("title") or "Untitled figure"
    lines = [f"## {title}", "", str(spec.get("summary") or "").strip()]
    series = spec.get("series") or []
    rows: list[tuple[str, str, str]] = []
    for item in series:
        name = str(item.get("name") or "Series")
        for point in item.get("points") or []:
            rows.append((name, str(point.get("label") or ""), str(point.get("value") or "")))
    if rows:
        lines.extend(["", "| Series | Label | Value |", "|---|---|---|"])
        lines.extend(f"| {name} | {label} | {value} |" for name, label, value in rows)
    notes = spec.get("notes") or []
    if notes:
        lines.extend(["", "### Notes", *[f"- {note}" for note in notes]])
    return "\n".join(lines).strip() + "\n"


def make_bedrock_vision_describer(model_id: str, *, region_name: str | None = None) -> VisionDescriber:
    import boto3

    client = boto3.client("bedrock-runtime", region_name=region_name)

    def describe(image_bytes: bytes, caption: str, native_text: str) -> dict[str, Any]:
        prompt = _figure_prompt(caption, native_text)
        response = client.converse(
            modelId=model_id,
            messages=[{
                "role": "user",
                "content": [
                    {"text": prompt},
                    {"image": {"format": "png", "source": {"bytes": image_bytes}}},
                ],
            }],
            inferenceConfig={"maxTokens": 1800, "temperature": 0},
        )
        text = "".join(
            block.get("text", "")
            for block in response["output"]["message"]["content"]
        ).strip()
        return _parse_json_object(text)

    return describe


def make_nous_deepseek_vision_describer(
    api_key: str,
    *,
    model_id: str = NOUS_DEEPSEEK_VISION_MODEL,
    api_url: str = NOUS_API_URL,
    urlopen: Callable[..., Any] = urllib.request.urlopen,
) -> VisionDescriber:
    """Create a Nous-hosted DeepSeek vision adapter without persisting its key."""
    if not api_key:
        raise ValueError("Nous API key is required")

    def describe(image_bytes: bytes, caption: str, native_text: str) -> dict[str, Any]:
        payload = {
            "model": model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _figure_prompt(caption, native_text)},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/png;base64," + b64encode(image_bytes).decode("ascii")
                            },
                        },
                    ],
                }
            ],
            "temperature": 0,
            "max_tokens": 1800,
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        with urlopen(request, timeout=120) as response:
            data = json.load(response)
        content = data["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(
                item.get("text", "") for item in content if isinstance(item, dict)
            )
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Nous vision model returned empty content")
        return _parse_json_object(content)

    return describe


def make_nous_deepseek_markdown_extractor(
    api_key: str,
    *,
    model_id: str = NOUS_DEEPSEEK_VISION_MODEL,
    api_url: str = NOUS_API_URL,
    urlopen: Callable[..., Any] = urllib.request.urlopen,
) -> PageMarkdownExtractor:
    """Create a page-image-to-Markdown extractor using Nous DeepSeek vision."""
    if not api_key:
        raise ValueError("Nous API key is required")

    def extract(image_bytes: bytes, page_number: int, docling_markdown: str) -> str:
        prompt = f"""Transcribe PDF page {page_number} into faithful Markdown.

Requirements:
- Preserve headings, paragraphs, lists, footnotes, and reading order.
- Reconstruct visible tables as Markdown tables.
- For charts, include the title, legend, labels, and every visible numeric value.
- Do not summarize, omit, or invent content.
- Return Markdown only, without a fenced code block.

The following parser output is a fallible draft. Use the page image as the source
of truth and correct the draft where necessary:

{docling_markdown}
"""
        payload = {
            "model": model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/png;base64," + b64encode(image_bytes).decode("ascii")
                            },
                        },
                    ],
                }
            ],
            "temperature": 0,
            "max_tokens": 5000,
        }
        request = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        with urlopen(request, timeout=180) as response:
            data = json.load(response)
        content = data["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(
                item.get("text", "") for item in content if isinstance(item, dict)
            )
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Nous page extraction returned empty content")
        return re.sub(r"^```(?:markdown|md)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE) + "\n"

    return extract


def extract_split_pdf_markdown(
    pages_dir: Path,
    extract_markdown: PageMarkdownExtractor,
    *,
    output_filename: str = "ocr.md",
    on_error: PageExtractionErrorHandler | None = None,
    include_pages: set[int] | None = None,
) -> dict[int, str]:
    """Extract split pages independently, checkpointing successes and skipping failures."""
    import pymupdf

    output: dict[int, str] = {}
    for page_pdf in sorted(pages_dir.glob("page-[0-9][0-9][0-9]/source.pdf")):
        match = re.fullmatch(r"page-(\d{3})", page_pdf.parent.name)
        if match is None:
            continue
        page_number = int(match.group(1))
        if include_pages is not None and page_number not in include_pages:
            continue
        checkpoint = page_pdf.parent / output_filename
        if checkpoint.is_file():
            cached = checkpoint.read_text(encoding="utf-8")
            if cached.strip():
                output[page_number] = cached
                continue
        with pymupdf.open(page_pdf) as document:
            if len(document) != 1:
                raise ValueError(f"Expected one page in {page_pdf}, found {len(document)}")
            page = document[0]
            draft = page.get_text("text").strip()
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
            image_bytes = pixmap.tobytes("png")
        try:
            markdown = extract_markdown(
                image_bytes,
                page_number,
                draft,
            )
            checkpoint.write_text(markdown, encoding="utf-8")
            output[page_number] = markdown
        except Exception as error:
            if on_error is not None:
                on_error(page_number, error)
            continue
    if not output and not any(pages_dir.glob("page-[0-9][0-9][0-9]/source.pdf")):
        raise ValueError(f"No split page PDFs found under {pages_dir}")
    return output


def extract_page_artifacts(
    document: Any,
    output_dir: Path,
    *,
    extract_markdown: PageMarkdownExtractor | None = None,
    markdown_engine: str = "deepseek",
    page_markdown_overrides: dict[int, str] | None = None,
) -> dict[str, Any]:
    """Persist page images and side-by-side Docling/OCR Markdown artifacts."""
    if markdown_engine not in {"deepseek", "llamaparse"}:
        raise ValueError(f"Unsupported Markdown engine: {markdown_engine}")
    page_markdown_overrides = page_markdown_overrides or {}
    output_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for page_number, page in sorted((getattr(document, "pages", {}) or {}).items()):
        page_dir = output_dir / f"page-{page_number:03d}"
        page_dir.mkdir(parents=True, exist_ok=True)
        docling_markdown = document.export_to_markdown(page_no=page_number).strip() + "\n"
        (page_dir / "docling.md").write_text(docling_markdown, encoding="utf-8")
        issues: list[str] = []
        source_image: str | None = None
        ocr_markdown = page_markdown_overrides.get(page_number)
        extraction_failed = False
        image_ref = getattr(page, "image", None)
        image = image_ref.pil_image if image_ref is not None else None
        if image is None:
            issues.append("page_image_unavailable")
        else:
            image_path = page_dir / "source.png"
            image.save(image_path, format="PNG")
            source_image = str(image_path.relative_to(output_dir))
            if ocr_markdown is None and extract_markdown is not None:
                buffer = BytesIO()
                image.save(buffer, format="PNG")
                try:
                    ocr_markdown = extract_markdown(
                        buffer.getvalue(), page_number, docling_markdown
                    )
                except Exception as error:
                    extraction_failed = True
                    issues.append(
                        f"{markdown_engine}_page_extraction_failed:{type(error).__name__}"
                    )
        if ocr_markdown is not None:
            ocr_markdown = ocr_markdown.strip() + "\n"
            (page_dir / f"{markdown_engine}.md").write_text(
                ocr_markdown,
                encoding="utf-8",
            )
        elif not extraction_failed:
            issues.append(f"{markdown_engine}_page_extraction_unavailable")
        engine_path = (
            str((page_dir / f"{markdown_engine}.md").relative_to(output_dir))
            if ocr_markdown is not None
            else None
        )
        record = {
            "page": page_number,
            "source_image": source_image,
            "docling_markdown": str((page_dir / "docling.md").relative_to(output_dir)),
            "ocr_engine": markdown_engine,
            "ocr_markdown": engine_path,
            "deepseek_markdown": engine_path if markdown_engine == "deepseek" else None,
            "llamaparse_markdown": engine_path if markdown_engine == "llamaparse" else None,
            "markdown_source": markdown_engine if ocr_markdown is not None else "docling",
            "issues": issues,
        }
        (page_dir / "metadata.json").write_text(
            json.dumps(record, indent=2) + "\n",
            encoding="utf-8",
        )
        records.append(record)
    manifest = {
        "schema_version": "1.0",
        "pages": records,
        "summary": {
            "page_count": len(records),
            "ocr_engine": markdown_engine,
            "ocr_pages": sum(record["ocr_markdown"] is not None for record in records),
            "deepseek_pages": sum(record["deepseek_markdown"] is not None for record in records),
            "llamaparse_pages": sum(record["llamaparse_markdown"] is not None for record in records),
            "issue_count": sum(len(record["issues"]) for record in records),
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def extract_visual_artifacts(
    document: Any,
    output_dir: Path,
    *,
    describe_figure: VisionDescriber | None = None,
) -> dict[str, Any]:
    """Save structured tables, figure crops, evidence, and a validation manifest."""
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir = output_dir / "tables"
    figures_dir = output_dir / "figures"
    table_records: list[dict[str, Any]] = []
    figure_records: list[dict[str, Any]] = []

    for index, table in enumerate(getattr(document, "tables", []) or [], start=1):
        artifact_dir = tables_dir / f"table-{index:03d}"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        frame = table.export_to_dataframe(document)
        caption = table.caption_text(document).strip()
        issues = validate_table_frame(frame)
        frame.to_csv(artifact_dir / "table.csv", index=False)
        (artifact_dir / "table.json").write_text(
            frame.to_json(orient="records", force_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        html = table.export_to_html(document, add_caption=True)
        (artifact_dir / "table.html").write_text(
            "<!doctype html><meta charset='utf-8'><title>Extracted table</title>" + html,
            encoding="utf-8",
        )
        image = table.get_image(document)
        if image is not None:
            image.save(artifact_dir / "crop.png")
        else:
            issues.append("table_crop_unavailable")
        record = {
            "id": f"table-{index:03d}",
            "kind": "table",
            "caption": caption,
            "rows": int(frame.shape[0]),
            "columns": int(frame.shape[1]),
            "provenance": _provenance(table),
            "artifacts": {
                "csv": str((artifact_dir / "table.csv").relative_to(output_dir)),
                "json": str((artifact_dir / "table.json").relative_to(output_dir)),
                "html": str((artifact_dir / "table.html").relative_to(output_dir)),
                "crop": str((artifact_dir / "crop.png").relative_to(output_dir)) if image is not None else None,
            },
            "review_status": "passed" if not issues else "review_required",
            "issues": issues,
        }
        (artifact_dir / "metadata.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        table_records.append(record)

    for index, picture in enumerate(getattr(document, "pictures", []) or [], start=1):
        artifact_dir = figures_dir / f"figure-{index:03d}"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        caption = picture.caption_text(document).strip()
        image = picture.get_image(document)
        issues: list[str] = []
        native_text = caption
        crop_path: str | None = None
        if image is not None:
            crop = artifact_dir / "crop.png"
            image.save(crop)
            crop_path = str(crop.relative_to(output_dir))
        else:
            issues.append("figure_crop_unavailable")
        spec: dict[str, Any] | None = None
        if image is not None and describe_figure is not None:
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            try:
                spec = describe_figure(buffer.getvalue(), caption, native_text)
                issues.extend(validate_figure_spec(spec, native_text))
                (artifact_dir / "figure.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
                (artifact_dir / "figure.md").write_text(figure_markdown(spec), encoding="utf-8")
            except Exception as error:
                issues.append(f"vision_description_failed:{type(error).__name__}")
        elif image is not None:
            issues.append("vision_description_unavailable")
        (artifact_dir / "native-text.txt").write_text(native_text + "\n", encoding="utf-8")
        record = {
            "id": f"figure-{index:03d}",
            "kind": "figure",
            "caption": caption,
            "provenance": _provenance(picture),
            "artifacts": {
                "crop": crop_path,
                "native_text": str((artifact_dir / "native-text.txt").relative_to(output_dir)),
                "spec": str((artifact_dir / "figure.json").relative_to(output_dir)) if spec else None,
                "markdown": str((artifact_dir / "figure.md").relative_to(output_dir)) if spec else None,
            },
            "review_status": "passed" if not issues else "review_required",
            "issues": issues,
        }
        (artifact_dir / "metadata.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        figure_records.append(record)

    all_records = [*table_records, *figure_records]
    issue_count = sum(len(record["issues"]) for record in all_records)
    manifest = {
        "schema_version": "1.0",
        "tables": table_records,
        "figures": figure_records,
        "summary": {
            "table_count": len(table_records),
            "figure_count": len(figure_records),
            "passed": sum(record["review_status"] == "passed" for record in all_records),
            "review_required": sum(record["review_status"] == "review_required" for record in all_records),
            "issue_count": issue_count,
        },
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
