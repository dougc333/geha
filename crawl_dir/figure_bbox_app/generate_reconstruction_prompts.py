from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pymupdf

from crawl_dir.src.pipeline.artifact_io import atomic_json

from .backend import ANNOTATION_DIR, DOCUMENT_ID, SOURCE_PDF, load_annotations


PROMPTS_PATH = ANNOTATION_DIR / "figure-reconstruction-prompts.json"
PROMPTS_DIR = ANNOTATION_DIR / "reconstruction-prompts"
APPROVED_PROMPTS_DIR = ANNOTATION_DIR / "approved-reconstruction-prompts"
APPROVED_PAGE_4_PROMPT = (
    ANNOTATION_DIR.parents[2]
    / "runs/research"
    / DOCUMENT_ID
    / "manual-figure-page004-checkpoint/pages/page-004/segments/figure-01-tailwind-svg/reconstruction-prompt.md"
)
PAGE_5_FIGURE_2_REGION_ID = "page-005-region-4c8ed247"
PAGE_5_FIGURE_3_REGION_ID = "page-005-region-5b62c880"
APPROVED_REGION_PROMPTS = {
    PAGE_5_FIGURE_2_REGION_ID: APPROVED_PROMPTS_DIR / f"{PAGE_5_FIGURE_2_REGION_ID}.md",
    PAGE_5_FIGURE_3_REGION_ID: APPROVED_PROMPTS_DIR / f"{PAGE_5_FIGURE_3_REGION_ID}.md",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalized_clip(page: pymupdf.Page, box: dict[str, Any]) -> pymupdf.Rect:
    return pymupdf.Rect(
        float(box["x1"]) * page.rect.width / 1000,
        float(box["y1"]) * page.rect.height / 1000,
        float(box["x2"]) * page.rect.width / 1000,
        float(box["y2"]) * page.rect.height / 1000,
    )


def compact_lines(value: str) -> list[str]:
    return [re.sub(r"\s+", " ", line).strip() for line in value.splitlines() if line.strip()]


def ordered_unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def color_hex(color: tuple[float, ...] | None) -> str | None:
    if not color or len(color) < 3:
        return None
    channels = [max(0, min(255, round(channel * 255))) for channel in color[:3]]
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def positioned_percentage_evidence(
    page: pymupdf.Page,
    box: dict[str, Any],
) -> dict[str, Any]:
    """Recover chart percentages without discarding their visual relationships.

    A flat PDF text stream cannot say which percentage belongs to which bar. This
    routine keeps coordinates, matches tokens to filled vector marks, clusters
    repeated x positions into bars, and fails closed when that geometry is weak.
    """
    clip = normalized_clip(page, box)
    percent_pattern = re.compile(r"^[+\-]?\d+(?:\.\d+)?%$")
    words = page.get_text("words", clip=clip, sort=False)
    word_records = [
        {
            "x0": float(word[0]),
            "y0": float(word[1]),
            "x1": float(word[2]),
            "y1": float(word[3]),
            "text": str(word[4]),
        }
        for word in words
    ]
    filled_shapes: list[dict[str, Any]] = []
    for drawing in page.get_drawings():
        rect = drawing.get("rect")
        fill = drawing.get("fill")
        if rect is None or fill is None or not rect.intersects(clip):
            continue
        area = float(rect.width * rect.height)
        if rect.width < 3 or rect.height < 3 or area >= float(clip.width * clip.height) * 0.35:
            continue
        fill_hex = color_hex(fill)
        if fill_hex in {None, "#ffffff", "#fefefe"}:
            continue
        filled_shapes.append({"rect": rect, "area": area, "color": fill_hex})

    tokens: list[dict[str, Any]] = []
    for word in word_records:
        cleaned = word["text"].strip("()[]{}.,;:")
        if not percent_pattern.match(cleaned):
            continue
        cx = (word["x0"] + word["x1"]) / 2
        cy = (word["y0"] + word["y1"]) / 2
        containing = [shape for shape in filled_shapes if shape["rect"].contains((cx, cy))]
        shape = min(containing, key=lambda item: item["area"]) if containing else None
        tokens.append({
            "text": cleaned,
            "value": float(cleaned.rstrip("%")),
            "bbox": [round(word[name], 3) for name in ("x0", "y0", "x1", "y1")],
            "center": [round(cx, 3), round(cy, 3)],
            "fill_color": shape["color"] if shape else None,
            "inside_filled_mark": bool(shape),
        })

    mark_tokens = [token for token in tokens if token["inside_filled_mark"]]
    seed_clusters: list[list[dict[str, Any]]] = []
    x_tolerance = max(7.0, float(clip.width) * 0.025)
    for token in sorted(mark_tokens, key=lambda item: item["center"][0]):
        for cluster in seed_clusters:
            center = sum(item["center"][0] for item in cluster) / len(cluster)
            if abs(token["center"][0] - center) <= x_tolerance:
                cluster.append(token)
                break
        else:
            seed_clusters.append([token])
    dominant = [cluster for cluster in seed_clusters if len(cluster) >= 2]
    dominant_centers = [sum(item["center"][0] for item in cluster) / len(cluster) for cluster in dominant]

    groups: list[dict[str, Any]] = []
    if len(dominant_centers) >= 2:
        assignments: list[list[dict[str, Any]]] = [[] for _ in dominant_centers]
        for token in mark_tokens:
            index = min(range(len(dominant_centers)), key=lambda i: abs(token["center"][0] - dominant_centers[i]))
            assignments[index].append(token)
        for token in (item for item in tokens if not item["inside_filled_mark"]):
            index = min(range(len(dominant_centers)), key=lambda i: abs(token["center"][0] - dominant_centers[i]))
            if abs(token["center"][0] - dominant_centers[index]) > x_tolerance * 2.0:
                continue
            existing = assignments[index]
            if not existing:
                continue
            y_values = [item["center"][1] for item in existing]
            if min(y_values) - 30 <= token["center"][1] <= max(y_values) + 30:
                assignments[index].append(token)
        sorted_assignments = sorted(
            zip(dominant_centers, assignments), key=lambda item: item[0]
        )
        for center, assigned in sorted_assignments:
            segments = sorted(assigned, key=lambda item: item["center"][1])
            total = sum(item["value"] for item in segments)
            bottom = max(item["bbox"][3] for item in segments)
            neighbor_distances = [abs(center - other) for other in dominant_centers if other != center]
            label_radius = max(18.0, (min(neighbor_distances) / 2 - 3) if neighbor_distances else 35.0)
            label_words = [
                word for word in word_records
                if bottom + 1 <= word["y0"] <= bottom + 45
                and abs(((word["x0"] + word["x1"]) / 2) - center) <= label_radius
                and not percent_pattern.match(word["text"].strip("()[]{}.,;:"))
            ]
            if label_words:
                first_label_y = min(word["y0"] for word in label_words)
                label_words = [word for word in label_words if abs(word["y0"] - first_label_y) <= 2.5]
            label = " ".join(word["text"] for word in sorted(label_words, key=lambda item: (item["y0"], item["x0"])))
            groups.append({
                "label": label.strip() or f"bar_at_x_{round(center, 1)}",
                "x_center": round(center, 3),
                "segments_top_to_bottom": [
                    {
                        "value": item["text"],
                        "fill_color": item["fill_color"],
                        "bbox": item["bbox"],
                    }
                    for item in segments
                ],
                "displayed_sum": round(total, 3),
            })

    reliable = (
        len(groups) >= 2
        and all(len(group["segments_top_to_bottom"]) >= 2 for group in groups)
        and all(90 <= group["displayed_sum"] <= 110 for group in groups)
    )
    orientation = "vertical" if reliable else None

    if not reliable and tokens:
        row_source_tokens = mark_tokens if len(mark_tokens) >= 3 else tokens
        row_seed_clusters: list[list[dict[str, Any]]] = []
        y_tolerance = max(6.0, float(clip.height) * 0.012)
        for token in sorted(row_source_tokens, key=lambda item: item["center"][1]):
            for cluster in row_seed_clusters:
                center = sum(item["center"][1] for item in cluster) / len(cluster)
                if abs(token["center"][1] - center) <= y_tolerance:
                    cluster.append(token)
                    break
            else:
                row_seed_clusters.append([token])

        row_centers = [sum(item["center"][1] for item in cluster) / len(cluster) for cluster in row_seed_clusters]
        row_assignments = [list(cluster) for cluster in row_seed_clusters]
        seeded_boxes = {tuple(item["bbox"]) for item in row_source_tokens}
        for token in (item for item in tokens if tuple(item["bbox"]) not in seeded_boxes):
            if not row_centers:
                continue
            index = min(range(len(row_centers)), key=lambda i: abs(token["center"][1] - row_centers[i]))
            if abs(token["center"][1] - row_centers[index]) <= y_tolerance * 2:
                row_assignments[index].append(token)

        horizontal_groups: list[dict[str, Any]] = []
        for center, assigned in sorted(zip(row_centers, row_assignments), key=lambda item: item[0]):
            segments = sorted(assigned, key=lambda item: item["center"][0])
            if not segments:
                continue
            left_edge = min(item["bbox"][0] for item in segments)
            label_words = [
                word for word in word_records
                if word["x1"] < left_edge - 2
                and abs(((word["y0"] + word["y1"]) / 2) - center) <= y_tolerance * 1.7
                and not percent_pattern.match(word["text"].strip("()[]{}.,;:"))
            ]
            label = " ".join(word["text"] for word in sorted(label_words, key=lambda item: item["x0"]))
            horizontal_groups.append({
                "label": label.strip() or f"row_at_y_{round(center, 1)}",
                "y_center": round(center, 3),
                "segments_left_to_right": [
                    {
                        "value": item["text"],
                        "fill_color": item["fill_color"],
                        "bbox": item["bbox"],
                    }
                    for item in segments
                ],
                "displayed_sum": round(sum(item["value"] for item in segments), 3),
            })
        merged_groups: list[dict[str, Any]] = []
        for group in horizontal_groups:
            if (
                merged_groups
                and not group["label"].startswith("row_at_y_")
                and group["label"] == merged_groups[-1]["label"]
            ):
                previous = merged_groups[-1]
                combined = sorted(
                    previous["segments_left_to_right"] + group["segments_left_to_right"],
                    key=lambda item: item["bbox"][0],
                )
                previous["segments_left_to_right"] = combined
                previous["displayed_sum"] = round(
                    sum(float(item["value"].rstrip("%")) for item in combined), 3
                )
                previous["y_center"] = round((previous["y_center"] + group["y_center"]) / 2, 3)
            else:
                merged_groups.append(group)
        horizontal_groups = merged_groups
        labeled_rows = sum(not group["label"].startswith("row_at_y_") for group in horizontal_groups)
        horizontal_reliable = len(horizontal_groups) >= 3 and labeled_rows >= max(2, len(horizontal_groups) // 2)
        if horizontal_reliable:
            groups = horizontal_groups
            reliable = True
            orientation = "horizontal"

    mapped_boxes = {
        tuple(segment["bbox"])
        for group in groups
        for segment in group.get("segments_top_to_bottom", group.get("segments_left_to_right", []))
    } if reliable else set()
    unmapped = [token for token in tokens if tuple(token["bbox"]) not in mapped_boxes]
    return {
        "status": "mapped" if reliable else "ambiguous",
        "orientation": orientation,
        "bars": groups if reliable else [],
        "unmapped_percentage_tokens": unmapped,
        "percentage_tokens": tokens,
    }


def evidence_for_region(page: pymupdf.Page, box: dict[str, Any]) -> dict[str, Any]:
    text = page.get_text("text", clip=normalized_clip(page, box), sort=True)
    lines = compact_lines(text)
    fonts = ordered_unique(
        span["font"]
        for block in page.get_text("dict", clip=normalized_clip(page, box))["blocks"]
        if "lines" in block
        for line in block["lines"]
        for span in line["spans"]
        if span.get("font")
    )
    percentages = ordered_unique(re.findall(r"(?<!\w)[+\-]?\d+(?:\.\d+)?%", text))
    years = ordered_unique(re.findall(r"\b(?:19|20)\d{2}\b", text))
    numeric_tokens = ordered_unique(
        re.findall(r"(?<![\w.])[+\-]?\d+(?:\.\d+)?(?:x|k|m|bn)?(?![\w.])", text, re.I)
    )
    return {
        "text": "\n".join(lines),
        "lines": lines,
        "fonts": fonts,
        "percentages": percentages,
        "years": years,
        "numeric_tokens": numeric_tokens[:80],
        "chart_structure": positioned_percentage_evidence(page, box),
    }


def strategy_for(box: dict[str, Any], evidence: dict[str, Any]) -> list[str]:
    text = evidence["text"].lower()
    has_percentages = bool(evidence["percentages"])
    has_axes = any(word in text for word in ("question:", "figure", "year", "employees", "employers"))
    if box.get("kind") == "image" and not has_percentages:
        return [
            "Identify the image boundary, caption, credit, and any overlaid text before authoring.",
            "Preserve the authoritative crop as an image rather than inventing visual detail; add accurate alt text from native evidence.",
            "Recreate only the surrounding caption and callout structure with semantic HTML and Tailwind.",
            "Render at the crop's exact pixel dimensions and compare boundary, caption, and reading order once.",
        ]
    steps = [
        "Start with the lowest shared structural anchor: baseline, axis, table edge, or aligned row beneath the data marks.",
        "Place the category labels and sublabels into aligned groups before drawing any bars, points, or shapes.",
        "Load the PDF's embedded font families and lock the observed text hierarchy before chart construction; do not run a font-guessing loop.",
    ]
    if has_percentages:
        steps.extend([
            "Construct one complete category or series at a time. Treat every displayed percentage as locked evidence.",
            "For stacked marks, calculate segment dimensions from the displayed percentages using one common total size; preserve stacking order and color relationships.",
            "Add change annotations, years, leader lines, legends, and footnotes only after the primary series is aligned.",
            "Repeat the same measured construction for the remaining categories or series.",
        ])
    elif has_axes:
        steps.extend([
            "Construct one complete category, row, or series at a time using the extracted labels and numeric tokens as locked evidence.",
            "Repeat the same measured structure for the remaining groups, then add legend, callouts, footnotes, and source text.",
        ])
    else:
        steps.extend([
            "Partition the region into its largest visual groups and reconstruct them in reading order with semantic HTML and inline SVG where geometry matters.",
            "Add captions, annotations, and secondary details only after the main geometry is stable.",
        ])
    steps.extend([
        "Include an accessible semantic table or structured description without changing the visible layout.",
        "Render at the authoritative crop's exact pixel dimensions and perform a side-by-side check for clipping, overlap, scale, spacing, text, and data relationships.",
    ])
    return steps


def prompt_markdown(page_number: int, box: dict[str, Any], evidence: dict[str, Any]) -> str:
    lines = evidence["lines"]
    likely_title = next((line for line in lines if len(line) > 12), box.get("label") or "Figure")
    locked = evidence["percentages"] + evidence["years"]
    font_text = ", ".join(evidence["fonts"]) or "Use the embedded PDF fonts detected on this page"
    steps = strategy_for(box, evidence)
    if box["id"] == PAGE_5_FIGURE_2_REGION_ID:
        steps = [
            "Start with the shared horizontal baseline and place the 2023 and 2025 labels beneath their respective bars.",
            "Load the PDF's embedded font families and lock the observed title, question, percentages, years, and legend text before chart construction.",
            "Construct the 2023 vertical bar from exactly two stacked segments using one common total height: 66% gray above 34% yellow.",
            "Construct the 2025 vertical bar at the same total height: 77% gray above 23% yellow.",
            "Place 66% and 77% centered in their gray segments, and 34% and 23% centered in their yellow segments.",
            "Preserve the thin connector between the two yellow/gray boundaries, the baseline, bar widths, spacing, background, and legend color mapping.",
            "Include an accessible semantic table containing the two years and their gray/yellow values without changing the visible layout.",
            "Render at the authoritative crop's exact pixel dimensions and perform a side-by-side check for clipping, overlap, scale, spacing, text, and data relationships.",
        ]
    elif box["id"] == PAGE_5_FIGURE_3_REGION_ID:
        steps = [
            "Start with the shared horizontal baseline and place the Today and In five years labels beneath equal-width stacked bars.",
            "Build the legend in this exact top-to-bottom category and color order: orange = 50% or more; coral = 25% to 49%; blue = 10% to 24%; teal = Less than 10%; green = None.",
            "Construct the Today bar from top to bottom as 4% orange, 8% coral, 16% blue, 37% teal, and 35% green.",
            "Construct the In five years bar from top to bottom as 6% orange, 11% coral, 23% blue, 39% teal, and 23% green.",
            "Place every percentage inside its corresponding colored segment, preserving the source's white text and relative segment heights.",
            "Add the left 65% and right 77% bracket annotations exactly as displayed; treat them as independent source annotations and do not recompute them from rounded segment labels.",
            "Preserve the title, question, bar spacing, baseline, background, bracket geometry, and legend placement.",
            "Include an accessible semantic table with category, Today, and In five years values without changing the visible layout.",
            "Render at the authoritative crop's exact pixel dimensions and perform a side-by-side check for clipping, overlap, scale, spacing, text, and data relationships.",
        ]
    if box["id"] == PAGE_5_FIGURE_3_REGION_ID:
        locked_summary = "\n".join([
            "- Legend thresholds and colors: orange = 50% or more; coral = 25% to 49%; blue = 10% to 24%; teal = Less than 10%; green = None.",
            "- Today, top to bottom: 4%, 8%, 16%, 37%, 35%; displayed bracket annotation: 65%.",
            "- In five years, top to bottom: 6%, 11%, 23%, 39%, 23%; displayed bracket annotation: 77%.",
            "- Preserve displayed rounded values exactly; do not normalize or replace them with derived totals.",
        ])
    else:
        chart_structure = evidence.get("chart_structure", {})
        if chart_structure.get("status") == "mapped":
            orientation = chart_structure.get("orientation") or "unknown"
            mapping_lines = [f"- Geometry-derived {orientation} bar mapping (not PDF text order):"]
            for group in chart_structure["bars"]:
                segment_key = "segments_top_to_bottom" if orientation == "vertical" else "segments_left_to_right"
                direction = "top to bottom" if orientation == "vertical" else "left to right"
                segments = ", ".join(
                    f"{segment['value']} {segment['fill_color']}"
                    for segment in group[segment_key]
                )
                mapping_lines.append(
                    f"  - {group['label']}: {direction} = {segments}; displayed sum = {group['displayed_sum']}%."
                )
            unmapped = chart_structure.get("unmapped_percentage_tokens", [])
            if unmapped:
                positioned = ", ".join(
                    f"{token['text']} at ({token['center'][0]}, {token['center'][1]})"
                    for token in unmapped
                )
                mapping_lines.append(
                    "- Unmapped percentage tokens (legend thresholds, bracket annotations, or other callouts; do not assign them to a bar without visual confirmation): "
                    + positioned
                )
            locked_summary = "\n".join(mapping_lines)
        elif evidence["percentages"]:
            positioned = ", ".join(
                f"{token['text']} at ({token['center'][0]}, {token['center'][1]})"
                for token in chart_structure.get("percentage_tokens", [])
            )
            locked_summary = (
                "- Bar mapping status: ambiguous. Do not treat the extracted percentages as a sequence or assign them to bars.\n"
                f"- Positioned percentage tokens for visual verification only: {positioned or ', '.join(locked)}"
            )
        else:
            locked_summary = "- No percentage tokens were extracted; preserve all visible numeric labels from the crop."
    prompt_lines = [
        f"# Page {page_number} · {box.get('label') or box['id']}",
        "",
        "Create an HTML equivalent of the supplied authoritative crop using semantic HTML, Tailwind CSS, supplemental inline CSS, and inline SVG where useful.",
        "",
        f"Likely figure heading: **{likely_title}**",
        f"Region ID: `{box['id']}`",
        f"Region type: `{box.get('kind', 'figure')}`",
        f"Embedded font evidence: {font_text}",
        "",
        "## Ordered reconstruction strategy",
        "",
    ]
    prompt_lines.extend(f"{index}. {step}" for index, step in enumerate(steps, start=1))
    prompt_lines.extend([
        "",
        "## Locked evidence",
        "",
        f"- Normalized box: x1={box['x1']}, y1={box['y1']}, x2={box['x2']}, y2={box['y2']}",
        locked_summary,
        "- Native text:",
        "",
        "```text",
        evidence["text"] or "No native text was extracted. Treat the crop as authoritative visual evidence.",
        "```",
        "",
        "Do not infer missing values or silently change labels. Record the source crop, source HTML, compiled CSS, browser HTML, rendered PNG, and review findings together.",
        "",
    ])
    return "\n".join(prompt_lines)


def generate_prompts() -> dict[str, Any]:
    annotations = load_annotations()
    pages: dict[str, list[dict[str, Any]]] = {}
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(SOURCE_PDF) as document:
        for page_key, boxes in sorted(annotations["pages"].items(), key=lambda item: int(item[0])):
            page_number = int(page_key)
            page = document.load_page(page_number - 1)
            records: list[dict[str, Any]] = []
            page_dir = PROMPTS_DIR / f"page-{page_number:03d}"
            page_dir.mkdir(parents=True, exist_ok=True)
            for box in boxes:
                evidence = evidence_for_region(page, box)
                figure_match = re.search(r"\bFigure\s+\d+\b", evidence["text"], re.I)
                display_label = figure_match.group(0).title() if figure_match else (box.get("label") or "Figure")
                prompt_box = {**box, "label": display_label}
                if page_number == 4 and APPROVED_PAGE_4_PROMPT.is_file():
                    prompt = APPROVED_PAGE_4_PROMPT.read_text(encoding="utf-8")
                    method = "user_approved"
                elif box["id"] in APPROVED_REGION_PROMPTS and APPROVED_REGION_PROMPTS[box["id"]].is_file():
                    prompt = APPROVED_REGION_PROMPTS[box["id"]].read_text(encoding="utf-8")
                    method = "user_approved"
                else:
                    prompt = prompt_markdown(page_number, prompt_box, evidence)
                    method = "deterministic_from_native_evidence"
                prompt_file = page_dir / f"{box['id']}.md"
                prompt_file.write_text(prompt, encoding="utf-8")
                records.append({
                    "region_id": box["id"],
                    "label": display_label,
                    "kind": box.get("kind", "figure"),
                    "box": {name: box[name] for name in ("x1", "y1", "x2", "y2")},
                    "method": method,
                    "prompt_file": str(prompt_file),
                    "prompt": prompt,
                    "evidence": evidence,
                })
            pages[page_key] = records
    payload = {
        "schema_version": 1,
        "document_id": DOCUMENT_ID,
        "source_pdf": str(SOURCE_PDF),
        "annotation_file": str(ANNOTATION_DIR / "figure-bounding-boxes.json"),
        "generated_at": utc_now(),
        "region_count": sum(len(records) for records in pages.values()),
        "pages": pages,
    }
    atomic_json(PROMPTS_PATH, payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Create per-region reconstruction prompts")
    parser.parse_args()
    result = generate_prompts()
    print(f"{result['region_count']} prompts -> {PROMPTS_PATH}")


if __name__ == "__main__":
    main()
