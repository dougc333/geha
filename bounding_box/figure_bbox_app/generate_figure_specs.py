"""Generate evidence-grounded figure specs from reviewed bounding boxes.

Existing page specs are preserved by default. Each missing page is processed
independently so an interrupted run can be resumed without repeating work.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pymupdf

from crawl_dir.src.pipeline.figure_specs import verify_figure
from geha_processing.io import atomic_json as _atomic_json

SUPPORTED_TYPES = ("pie", "hbar", "vbar", "heatmap", "stats", "harvey", "cycle", "quotes", "steps")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def atomic_json(path: Path, payload: Any) -> None:
    _atomic_json(path, payload)


def parse_pages(value: str | None, available: list[int]) -> list[int]:
    if not value:
        return available
    selected: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = map(int, part.split("-", 1))
            selected.update(range(start, end + 1))
        else:
            selected.add(int(part))
    invalid = selected.difference(available)
    if invalid:
        raise ValueError(f"Pages without saved boxes: {sorted(invalid)}")
    return sorted(selected)


def pdf_box(page: pymupdf.Page, box: dict[str, Any]) -> list[float]:
    rect = page.rect
    return [
        round(float(box["x1"]) * rect.width / 1000, 2),
        round(float(box["y1"]) * rect.height / 1000, 2),
        round(float(box["x2"]) * rect.width / 1000, 2),
        round(float(box["y2"]) * rect.height / 1000, 2),
    ]


def find_passed_artifact(crawl_runs: Path, page_number: int) -> tuple[Path, str]:
    candidates: list[tuple[int, Path, str]] = []
    pattern = f"*/pages/page-{page_number:03d}/page-manifest.json"
    for manifest_path in crawl_runs.glob(pattern):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("status") != "passed" or not manifest.get("markdown"):
            continue
        markdown = manifest_path.parent / str(manifest["markdown"])
        if markdown.is_file():
            candidates.append((manifest_path.stat().st_mtime_ns, markdown, str(manifest.get("tool_id", "unknown"))))
    if not candidates:
        raise FileNotFoundError(f"No passed crawl artifact for page {page_number} under {crawl_runs}")
    _, markdown, tool_id = max(candidates, key=lambda item: item[0])
    return markdown, tool_id


def markdown_table(markdown: str) -> tuple[str, list[list[str]]]:
    lines = markdown.splitlines()
    rows: list[list[str]] = []
    first_table = next((index for index, line in enumerate(lines) if line.strip().startswith("|")), None)
    if first_table is None:
        raise ValueError("Passed crawl artifact has no structured table")
    title = ""
    for line in reversed(lines[:first_table]):
        if line.startswith("##"):
            title = html.unescape(line.lstrip("# ").strip())
            break
    for line in lines[first_table:]:
        stripped = line.strip()
        if not stripped.startswith("|"):
            if rows:
                break
            continue
        cells = [html.unescape(cell.strip()) for cell in stripped.strip("|").split("|")]
        if all(re.fullmatch(r"[-: ]+", cell or "-") for cell in cells):
            continue
        rows.append(cells)
    if not rows:
        raise ValueError("Passed crawl artifact table contains no data rows")
    return title, rows


def build_from_crawl(page_number: int, box: dict[str, Any], box_pt: list[float], markdown_path: Path,
                     tool_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    markdown = markdown_path.read_text(encoding="utf-8")
    title, rows = markdown_table(markdown)
    if not all(len(row) >= 3 and row[0].isdigit() for row in rows):
        raise ValueError(f"Page {page_number} table is not a numbered findings structure")
    items = [{"number": row[0].zfill(2), "label": row[1], "bullets": [row[2]]} for row in rows]
    literal = " ".join([title, *(value for row in rows for value in row)])
    evidence = {
        "schema_version": 1,
        "method": "passed_crawl_dir_page_artifact",
        "source_artifact": str(markdown_path),
        "source_tool_id": tool_id,
        "box_pdf_points": box_pt,
        "word_count": len(literal.split()),
        "literal_text": literal,
        "percent_tokens": re.findall(r"\d+(?:\.\d+)?%", literal),
        "authoritative": True,
    }
    figure = {
        "id": box["id"],
        "label": None,
        "title": title,
        "question": "",
        "box_pt": box_pt,
        "source_artifact": str(markdown_path),
        "chart": {"type": "steps", "items": items},
    }
    return figure, evidence


def default_status(document_id: str, annotations: dict[str, Any], specs_dir: Path) -> dict[str, Any]:
    pages: dict[str, Any] = {}
    for page_key, boxes in annotations.get("pages", {}).items():
        spec_path = specs_dir / f"page-{int(page_key):03d}.json"
        state = "saved" if spec_path.is_file() else "boxed"
        pages[page_key] = {
            "page": int(page_key), "state": state, "attempt": 0,
            "region_count": len(boxes), "message": "Reviewed spec exists" if state == "saved" else "Ready",
            "spec_path": str(spec_path) if spec_path.is_file() else None,
        }
    return {"schema_version": 1, "document_id": document_id, "running": False,
            "updated_at": utc_now(), "pages": pages}


def run_generation(pdf: Path, annotation_path: Path, specs_dir: Path, status_path: Path, *,
                   crawl_runs: Path, pages_value: str | None, author: str, overwrite: bool,
                   builder: Callable[[int, dict[str, Any], list[float], Path, str],
                                     tuple[dict[str, Any], dict[str, Any]]] = build_from_crawl) -> dict[str, Any]:
    annotations = json.loads(annotation_path.read_text(encoding="utf-8"))
    available = sorted(map(int, annotations.get("pages", {}).keys()))
    selected = parse_pages(pages_value, available)
    status = default_status(annotations["document_id"], annotations, specs_dir)
    status["running"] = True
    stage_delay = max(0.0, min(2.0, float(os.environ.get("FIGURE_SPEC_STAGE_DELAY", "0"))))

    def update(page: int, state: str, message: str, *, pause: bool = True, **extra: Any) -> None:
        status["pages"][str(page)].update(state=state, message=message, **extra)
        status["updated_at"] = utc_now()
        atomic_json(status_path, status)
        if stage_delay and pause:
            time.sleep(stage_delay)

    atomic_json(status_path, status)
    try:
        with pymupdf.open(pdf) as document:
            for page_number in selected:
                output = specs_dir / f"page-{page_number:03d}.json"
                if output.is_file() and not overwrite:
                    update(page_number, "skipped_existing", "Preserved reviewed spec", pause=False,
                           spec_path=str(output))
                    continue
                figures: list[dict[str, Any]] = []
                page = document[page_number - 1]
                for box in annotations["pages"][str(page_number)]:
                    box_pt = pdf_box(page, box)
                    update(page_number, "extracting", f"Loading passed crawl artifact for {box['label']}")
                    markdown_path, tool_id = find_passed_artifact(crawl_runs, page_number)
                    update(page_number, "evidence_extracted", f"Crawl data loaded · {markdown_path.parent.parent.name}")
                    update(page_number, "generating", "Assembling spec from verified crawl data", attempt=1)
                    candidate, evidence = builder(page_number, box, box_pt, markdown_path, tool_id)
                    update(page_number, "validating", "Validating against verified crawl data", attempt=1)
                    failures, warnings = verify_figure(candidate, evidence)
                    if failures:
                        update(page_number, "failed", "Deterministic validation failed", errors=failures)
                        continue
                    candidate["validation"] = {"errors": [], "warnings": warnings,
                                               "evidence_method": evidence["method"]}
                    figures.append(candidate)
                if len(figures) == len(annotations["pages"][str(page_number)]):
                    spec = {"schema_version": 1, "document_id": annotations["document_id"],
                            "page": page_number, "author": author, "generated_at": utc_now(), "figures": figures}
                    atomic_json(output, spec)
                    update(page_number, "saved", f"Spec saved · {len(figures)} figure(s)", spec_path=str(output))
    except Exception as exc:
        status["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        status["running"] = False
        status["updated_at"] = utc_now()
        atomic_json(status_path, status)
    return status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--specs-dir", type=Path, required=True)
    parser.add_argument("--status", type=Path, required=True)
    parser.add_argument("--crawl-runs", type=Path, required=True,
                        help="document run directory containing passed page artifacts")
    parser.add_argument("--pages", help="comma-separated pages or ranges; default: all annotated pages")
    parser.add_argument("--author", default="crawl_dir_verified_artifact")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    run_generation(args.pdf.resolve(), args.annotations.resolve(), args.specs_dir.resolve(),
                   args.status.resolve(), crawl_runs=args.crawl_runs.resolve(), pages_value=args.pages,
                   author=args.author, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
