"""Deterministically classify PDF pages for extraction and visual-review routing."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import pymupdf


FIGURE_LABEL = re.compile(
    r"(?im)^\s*(?:figure|fig\.?|chart|exhibit|diagram|infographic)\s*"
    r"(?:\d+[a-z]?|[ivxlcdm]+|[a-z])\b"
)
PERCENT = re.compile(r"(?<!\w)\d+(?:\.\d+)?%")
MIN_FIGURE_IMAGE_AREA = 0.08
MAX_FIGURE_IMAGE_AREA = 0.85
SCANNED_IMAGE_AREA = 0.85
MIN_VECTOR_DRAWINGS = 20
MIN_VECTOR_NUMERIC_LABELS = 3
PAGE_TYPE_CRITERIA = {
    "narrative": "Primarily prose or headings without a substantive table or figure.",
    "table": "Contains one or more substantive data tables but no substantive figure.",
    "figure": "Contains a chart, graph, diagram, infographic, or substantive image but no table.",
    "mixed": "Contains both a substantive table and a substantive figure.",
    "scanned": "A full-page raster or scan with too little embedded text to classify safely.",
}
JEV_INSTRUCTIONS = (
    "Classify one PDF page from non-content layout features. Structured table counts are "
    "strong table evidence. Explicit figure-label counts, substantial image counts, and dense "
    "vector graphics with numeric labels are figure evidence. A near-full-page image with very "
    "little embedded text is scanned rather than a figure. Choose mixed when both table and "
    "figure evidence exist. No document text or table values are provided."
)


def jev_available() -> bool:
    if not os.getenv("TYPESAFE_API_KEY"):
        return False
    try:
        import typesafe_sdk  # noqa: F401
    except ImportError:
        return False
    return True


class JevPageClassifier:
    """Classify non-content page features with batched TypeSafe JEV choices."""

    def __init__(self, client: Any | None = None, batch_size: int = 10) -> None:
        self._client = client
        self.batch_size = max(1, min(25, batch_size))

    def _get_client(self) -> Any:
        if self._client is None:
            from typesafe_sdk import TypeSafeClient

            self._client = TypeSafeClient(api_key=os.environ["TYPESAFE_API_KEY"])
        return self._client

    def classify_many(self, features: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
        from typesafe_sdk import Choice

        results: dict[int, dict[str, Any]] = {}
        for offset in range(0, len(features), self.batch_size):
            batch = features[offset:offset + self.batch_size]
            questions = {
                f"page_{item['page']:04d}": Choice(
                    instructions=(
                        f"{JEV_INSTRUCTIONS} Classify page {item['page']} using only its "
                        "matching feature record."
                    ),
                    criteria=PAGE_TYPE_CRITERIA,
                )
                for item in batch
            }
            response = self._get_client().system_one(
                state={"page_features": json.dumps(batch, sort_keys=True)},
                questions=questions,
            )
            for item in batch:
                answer = response.choices[f"page_{item['page']:04d}"]
                results[int(item["page"])] = {
                    "choice": str(answer.choice),
                    "confidence": round(float(answer.confidence), 4),
                    "probabilities": {
                        str(key): round(float(value), 4)
                        for key, value in answer.probabilities.items()
                    },
                    "model": str(response.model),
                }
        return results


def _normalized_box(rect: pymupdf.Rect, page_rect: pymupdf.Rect) -> list[int]:
    """Return a stable 0..1000 bounding box for later crop/review stages."""
    return [
        round((rect.x0 - page_rect.x0) / page_rect.width * 1000),
        round((rect.y0 - page_rect.y0) / page_rect.height * 1000),
        round((rect.x1 - page_rect.x0) / page_rect.width * 1000),
        round((rect.y1 - page_rect.y0) / page_rect.height * 1000),
    ]


def _image_regions(page: pymupdf.Page) -> list[dict[str, Any]]:
    page_area = max(1.0, page.rect.width * page.rect.height)
    seen: set[tuple[float, float, float, float]] = set()
    regions: list[dict[str, Any]] = []
    for image in page.get_images(full=True):
        xref = int(image[0])
        try:
            rects = page.get_image_rects(xref)
        except (RuntimeError, ValueError):
            continue
        for rect in rects:
            key = tuple(round(value, 2) for value in (rect.x0, rect.y0, rect.x1, rect.y1))
            if key in seen or rect.is_empty or rect.is_infinite:
                continue
            seen.add(key)
            regions.append({
                "box": _normalized_box(rect, page.rect),
                "area_ratio": round(rect.width * rect.height / page_area, 4),
            })
    return sorted(regions, key=lambda item: item["area_ratio"], reverse=True)


def classify_pdf_pages(
    source: Path,
    table_records: list[dict[str, Any]],
    *,
    classifier: Any | None = None,
    require_jev: bool = False,
) -> dict[str, Any]:
    """Classify pages as narrative, table, figure, mixed, or scanned.

    Table evidence comes from the canonical structured-table extractor. Figure
    evidence is intentionally conservative: explicit figure labels, substantial
    embedded images, or dense vector graphics accompanied by numeric labels.
    Full-page raster images with little embedded text are classified as scanned
    pages rather than figures.
    """
    tables_by_page: dict[int, list[str]] = {}
    for table in table_records:
        for page_number in table.get("source_pages", []):
            tables_by_page.setdefault(int(page_number), []).append(str(table["table_id"]))

    evidence_pages: list[dict[str, Any]] = []
    with pymupdf.open(source) as document:
        for index, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            labels = [match.group(0).strip() for match in FIGURE_LABEL.finditer(text)]
            images = _image_regions(page)
            max_image_area = images[0]["area_ratio"] if images else 0.0
            scanned = len(text) < 20 and max_image_area >= SCANNED_IMAGE_AREA
            figure_images = [
                region for region in images
                if MIN_FIGURE_IMAGE_AREA <= region["area_ratio"] < MAX_FIGURE_IMAGE_AREA
            ]
            drawing_count = len(page.get_drawings())
            numeric_label_count = len(PERCENT.findall(text))
            vector_chart = (
                drawing_count >= MIN_VECTOR_DRAWINGS
                and numeric_label_count >= MIN_VECTOR_NUMERIC_LABELS
                and index not in tables_by_page
            )
            figure = bool(labels or figure_images or vector_chart) and not scanned
            table_ids = sorted(tables_by_page.get(index, []))
            table = bool(table_ids)
            if figure and table:
                page_type = "mixed"
            elif figure:
                page_type = "figure"
            elif table:
                page_type = "table"
            elif scanned:
                page_type = "scanned"
            else:
                page_type = "narrative"
            evidence_pages.append({
                "page": index,
                "table_ids": table_ids,
                "deterministic_page_type": page_type,
                "signals": {
                    "figure_labels": labels,
                    "substantial_image_regions": figure_images,
                    "maximum_image_area_ratio": max_image_area,
                    "drawing_count": drawing_count,
                    "percent_token_count": numeric_label_count,
                    "dense_vector_chart": vector_chart,
                    "embedded_text_characters": len(text),
                },
            })

    # Only aggregate, non-content features leave the machine. Literal page text,
    # labels, table values, bounding boxes, and source files remain local.
    jev_features = [{
        "page": item["page"],
        "structured_table_count": len(item["table_ids"]),
        "explicit_figure_label_count": len(item["signals"]["figure_labels"]),
        "substantial_image_count": len(item["signals"]["substantial_image_regions"]),
        "maximum_image_area_ratio": item["signals"]["maximum_image_area_ratio"],
        "drawing_count": item["signals"]["drawing_count"],
        "percent_token_count": item["signals"]["percent_token_count"],
        "dense_vector_chart": item["signals"]["dense_vector_chart"],
        "embedded_text_characters": item["signals"]["embedded_text_characters"],
        "scanned_page_signal": item["deterministic_page_type"] == "scanned",
        "deterministic_suggestion": item["deterministic_page_type"],
    } for item in evidence_pages]

    provider = classifier
    fallback_reason = None
    if provider is None and jev_available():
        provider = JevPageClassifier(
            batch_size=int(os.getenv("JEV_PAGE_BATCH_SIZE", "10")),
        )
    elif provider is None:
        fallback_reason = "typesafe-sdk or TYPESAFE_API_KEY is unavailable"
        if require_jev:
            raise RuntimeError(f"JEV page classification required: {fallback_reason}")

    jev_results: dict[int, dict[str, Any]] = {}
    if provider is not None:
        try:
            jev_results = provider.classify_many(jev_features)
        except Exception as error:
            fallback_reason = f"JEV classification failed: {type(error).__name__}: {error}"
            if require_jev:
                raise RuntimeError(fallback_reason) from error

    pages: list[dict[str, Any]] = []
    for item in evidence_pages:
        classification = jev_results.get(int(item["page"]))
        page_type = (
            classification["choice"] if classification is not None
            else item["deterministic_page_type"]
        )
        if page_type not in PAGE_TYPE_CRITERIA:
            page_type = item["deterministic_page_type"]
        scanned = item["deterministic_page_type"] == "scanned"
        if scanned:
            page_type = "scanned"
        table = bool(item["table_ids"]) or page_type in {"table", "mixed"}
        figure = page_type in {"figure", "mixed"}
        # Preserve hard local facts even if the external classifier is uncertain.
        if scanned:
            table = figure = False
        elif item["table_ids"] and figure:
            page_type = "mixed"
        elif item["table_ids"]:
            page_type = "table"
        content_types = [kind for kind, present in (
            ("text", item["signals"]["embedded_text_characters"] > 0),
            ("table", table), ("figure", figure), ("scanned", scanned),
        ) if present]
        pages.append({
            "page": item["page"],
            "page_type": page_type,
            "content_types": content_types,
            "table_detected": table,
            "figure_detected": figure,
            "scanned_page": scanned,
            "visual_review_recommended": figure or scanned,
            "table_ids": item["table_ids"],
            "classification": {
                "method": "jev" if classification is not None else "deterministic_fallback",
                **(classification or {}),
                **({"fallback_reason": fallback_reason} if fallback_reason else {}),
            },
            "signals": item["signals"],
        })

    def selected(kind: str) -> list[int]:
        return [item["page"] for item in pages if item["page_type"] == kind]

    figure_pages = [item["page"] for item in pages if item["figure_detected"]]
    table_pages = [item["page"] for item in pages if item["table_detected"]]
    visual_review_pages = [
        item["page"] for item in pages if item["visual_review_recommended"]
    ]
    return {
        "schema_version": "1.0",
        "method": "jev_over_non_content_layout_features",
        "classifier": {
            "provider": "TypeSafe Jev",
            "mode": "jev" if jev_results else "deterministic_fallback",
            "external_fields": sorted(
                key for key in jev_features[0] if key != "page"
            ) if jev_features else [],
            **({"fallback_reason": fallback_reason} if fallback_reason else {}),
        },
        "pages": pages,
        "summary": {
            "page_count": len(pages),
            "figure_pages": figure_pages,
            "table_pages": table_pages,
            "mixed_pages": selected("mixed"),
            "scanned_pages": selected("scanned"),
            "narrative_pages": selected("narrative"),
            "visual_review_pages": visual_review_pages,
        },
    }
