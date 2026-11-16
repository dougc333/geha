"""Local API and PDF scanner for the four ingestion collections."""

from __future__ import annotations

import asyncio
import html
import hashlib
import json
import re
import sys
import threading
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pymupdf
from aiohttp import web


APP_ROOT = Path(__file__).resolve().parent
CRAWL_ROOT = Path("/Users/dc/geha/crawl_dir")
REPO_ROOT = APP_ROOT.parents[1]
STATE_PATH = APP_ROOT / "data" / "scan_state.json"
UI_DIST = APP_ROOT / "dist"

COLLECTIONS = {
    "population_health": {
        "path": CRAWL_ROOT / "runs" / "population_health",
        "recommendation": "Use the figure-spec workflow on figure pages in all seven PDFs.",
    },
    "policy": {
        "path": CRAWL_ROOT / "runs" / "policy",
        "recommendation": "Use figure specs selectively: AHIP HealthCareDollar page 1 only.",
    },
    "forms_directory": {
        "path": CRAWL_ROOT / "runs" / "forms_directory",
        "recommendation": "Do not use figure specs; preserve form fields, boxes, lists and tables.",
    },
    "medical": {
        "path": CRAWL_ROOT / "runs" / "medical",
        "recommendation": "Use native text and table extraction; marketing visuals are not chart-spec targets.",
    },
}

# Qualitative calibration from the verified visual audit. Numeric page/label/region
# metrics are recomputed on every scan; table totals come from the canonical run QC.
CALIBRATION: dict[str, tuple[str, str, str]] = {
    "2021ProfileOlderAmericans_508.pdf": (
        "Profile statistics, bars and infographic callouts",
        "Yes",
        "Figure specs on quantitative visual pages",
    ),
    "2020Profileolderamericans.final_.pdf": (
        "Profile statistics, bars and infographic callouts",
        "Yes",
        "Figure specs on quantitative visual pages",
    ),
    "AHR_2025HWC_ExecutiveBrief_FINAL-Web.pdf": (
        "Bar charts, comparative metrics and spotlight graphics",
        "Yes",
        "Figure specs on quantitative visual pages",
    ),
    "AHR_2025Senior_ExecutiveBrief_FINAL-Web.pdf": (
        "Bars, line charts, state map and comparative graphics",
        "Yes",
        "Figure specs on quantitative visual pages",
    ),
    "ahr_2025hwc_comprehensivereport_final-web.pdf": (
        "Numerous charts and health-measure graphics",
        "Yes",
        "Figure specs after the shorter pilot documents",
    ),
    "allstatesummaries-ahr24.pdf": (
        "State metric summaries and small trend charts",
        "Yes; separate each chart from its adjacent table",
        "Reusable figure template plus table extraction",
    ),
    "allstatesums-hwc2022.pdf": (
        "Infographic summary pages followed by large tables",
        "Yes for summary graphics only",
        "Figure specs for summaries; table pipeline for companion pages",
    ),
    "AHIP_HealthCareDollar.pdf": (
        "Page 1 is a quantitative healthcare-dollar infographic",
        "Yes; page 1 only",
        "Figure spec for page 1; tables for pages 2–3",
    ),
    "PA%20white%20paper%2012.4.2025%20final.pdf": (
        "No material data figures; appendix chart is a multipage matrix",
        "No",
        "Native text and table extraction",
    ),
    "Tenncare-PDL.pdf": ("Formulary tables", "No", "Native text and table extraction"),
    "10050-s-medicare-and-you.pdf": (
        "No substantial quantitative figures; text and comparison tables",
        "No",
        "Native text and table extraction",
    ),
    "kentucky-medicaid-pa-criteria.pdf": (
        "Clinical criteria and tables",
        "No",
        "Native text and table extraction",
    ),
    "ODM06723fillx.pdf": ("Form fields and boxes", "No", "Form/field extraction"),
    "im-1sslsp.pdf": ("Form sections and tables", "No", "Form and table extraction"),
    "IM-1SSL-Fillable-Secured-6-24-21.pdf": ("Form sections and tables", "No", "Form and table extraction"),
    "IM-1ABDS_Spanish.pdf": ("Form sections and tables", "No", "Form and table extraction"),
    "optical_providers_adult_medicaid.pdf": ("Provider list; no data figures", "No", "Table/list extraction"),
    "Revised_KYState_MedicaidKCHIPQHPAppForFamily.pdf": ("Application form", "No", "Form/field extraction"),
    "Revised_KYState_MedicaidKCHIPQHPAppForOnePerson.pdf": ("Application form", "No", "Form/field extraction"),
}

STATE_LOCK = threading.RLock()
SCAN_THREAD: threading.Thread | None = None
EXTRACTION_THREAD: threading.Thread | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_id(family: str, path: Path) -> str:
    return hashlib.sha1(f"{family}:{path}".encode()).hexdigest()[:16]


def medical_classification(name: str) -> tuple[str, str, str]:
    if "summary-of-benefits-and-coverage" in name:
        return ("SBC tables; no quantitative charts", "No", "Native text and table extraction")
    if "medical-benefits-guide" in name:
        return (
            "Marketing photos, icons and callout panels; no quantitative charts",
            "Not for chart specs",
            "Native text and table extraction",
        )
    if "medicare-benefits-guide" in name:
        return (
            "Marketing panels and comparison layouts; no quantitative charts",
            "Not for chart specs",
            "Native text and table extraction",
        )
    return ("Plan tables; no quantitative charts", "No", "Native text and table extraction")


def classification(family: str, name: str) -> tuple[str, str, str]:
    if name in CALIBRATION:
        return CALIBRATION[name]
    if family == "medical":
        return medical_classification(name)
    return ("Not yet classified", "Review", "Native text extraction")


def discover_pdfs() -> list[dict[str, Any]]:
    discovered: list[dict[str, Any]] = []
    for family, config in COLLECTIONS.items():
        run_root: Path = config["path"]
        by_source: dict[str, tuple[Path, dict[str, Any]]] = {}
        for manifest_path in sorted(run_root.glob("*/*/run-manifest.json")):
            try:
                manifest = json.loads(manifest_path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            source = manifest.get("source")
            if source and source not in by_source:
                by_source[source] = (manifest_path, manifest)
        for source, (manifest_path, _) in sorted(by_source.items()):
            pdf_path = (CRAWL_ROOT / source).resolve()
            description, recommendation, workflow = classification(family, pdf_path.name)
            qc_path = manifest_path.parent / "qc-report.json"
            canonical_tables = None
            if qc_path.exists():
                try:
                    canonical_tables = int(json.loads(qc_path.read_text()).get("table_count", 0))
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    pass
            discovered.append({
                "id": record_id(family, pdf_path),
                "family": family,
                "name": pdf_path.name,
                "path": str(pdf_path),
                "manifestPath": str(manifest_path),
                "canonicalTableCount": canonical_tables,
                "figureDescription": description,
                "recommendation": recommendation,
                "recommendedWorkflow": workflow,
            })
    return discovered


def empty_pdf(record: dict[str, Any]) -> dict[str, Any]:
    return {
        **record,
        "status": "not_scanned",
        "scannedAt": None,
        "error": None,
        "pageCount": None,
        "nativeTextPages": None,
        "blankTextPages": [],
        "nativeLabels": None,
        "nativeLabelCount": None,
        "figureCount": None,
        "figurePages": [],
        "chartCount": None,
        "chartPages": [],
        "tableCount": None,
        "tablePages": [],
        "formCount": None,
        "formPages": [],
        "formFieldCount": None,
        "scanSeconds": None,
        "extractionStatus": "not_started",
        "extractionStartedAt": None,
        "extractionCompletedAt": None,
        "extractionError": None,
        "extractionRunPath": None,
        "markdownPath": None,
        "chunksPath": None,
        "pageHtmlCount": 0,
        "figureSpecCount": 0,
        "logicalTableCount": 0,
    }


def load_state() -> dict[str, Any]:
    prior: dict[str, Any] = {}
    if STATE_PATH.exists():
        try:
            prior_state = json.loads(STATE_PATH.read_text())
            prior = {
                pdf["id"]: pdf
                for collection in prior_state.get("collections", [])
                for pdf in collection.get("pdfs", [])
            }
        except (OSError, json.JSONDecodeError, KeyError):
            prior = {}
    groups: dict[str, list[dict[str, Any]]] = {key: [] for key in COLLECTIONS}
    for record in discover_pdfs():
        current = empty_pdf(record)
        if record["id"] in prior:
            saved = prior[record["id"]]
            current.update({key: value for key, value in saved.items() if key in current})
            current.update({
                "path": record["path"],
                "manifestPath": record["manifestPath"],
                "canonicalTableCount": record["canonicalTableCount"],
                "figureDescription": record["figureDescription"],
                "recommendation": record["recommendation"],
                "recommendedWorkflow": record["recommendedWorkflow"],
            })
            if current["extractionStatus"] == "extracting":
                current["extractionStatus"] = "error"
                current["extractionError"] = "Extraction was interrupted by an API restart."
        groups[record["family"]].append(current)
    return {
        "version": 2,
        "running": False,
        "startedAt": None,
        "completedAt": None,
        "activePdf": None,
        "activeExtraction": None,
        "collections": [
            {
                "key": family,
                "path": str(config["path"]),
                "status": "not_scanned",
                "total": len(groups[family]),
                "completed": 0,
                "errors": 0,
                "recommendation": config["recommendation"],
                "pdfs": groups[family],
            }
            for family, config in COLLECTIONS.items()
        ],
    }


STATE = load_state()


def refresh_collection_statuses() -> None:
    for collection in STATE["collections"]:
        statuses = [pdf["status"] for pdf in collection["pdfs"]]
        collection["completed"] = sum(status == "completed" for status in statuses)
        collection["errors"] = sum(status == "error" for status in statuses)
        if any(status == "scanning" for status in statuses):
            collection["status"] = "scanning"
        elif any(status == "queued" for status in statuses):
            collection["status"] = "queued"
        elif statuses and all(status == "completed" for status in statuses):
            collection["status"] = "completed"
        elif any(status == "error" for status in statuses):
            collection["status"] = "error"
        else:
            collection["status"] = "not_scanned"


def persist_state() -> None:
    with STATE_LOCK:
        refresh_collection_statuses()
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temp = STATE_PATH.with_suffix(".tmp")
        temp.write_text(json.dumps(STATE, indent=2))
        temp.replace(STATE_PATH)


def significant_images(page: pymupdf.Page) -> list[pymupdf.Rect]:
    page_area = page.rect.get_area()
    rectangles: list[pymupdf.Rect] = []
    seen: set[int] = set()
    for image in page.get_images(full=True):
        xref = image[0]
        if xref in seen:
            continue
        seen.add(xref)
        for rect in page.get_image_rects(xref):
            if rect.width >= 100 and rect.height >= 70 and rect.get_area() >= page_area * 0.015:
                rectangles.append(rect)
    return rectangles


def markdown_table_pages(manifest_path: Path) -> list[int]:
    pages_root = manifest_path.parent / "pages"
    result: list[int] = []
    separator = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|){1,}", re.MULTILINE)
    for page_md in sorted(pages_root.glob("page-*/page.md")):
        try:
            if separator.search(page_md.read_text(errors="ignore")):
                result.append(int(page_md.parent.name.split("-")[-1]))
        except (OSError, ValueError):
            continue
    return result


def is_form_page(family: str, name: str, text: str, widget_count: int, drawings: int) -> bool:
    if family != "forms_directory" or name == "optical_providers_adult_medicaid.pdf":
        return False
    if widget_count:
        return True
    cues = len(re.findall(r"\b(?:application|applicant|signature|date signed|address|case number|social security|check one|yes|no)\b", text, re.I))
    return cues >= 2 and drawings >= 8


def candidate_chart_page(family: str, name: str, page_number: int, text: str, drawings: int, image_count: int) -> bool:
    if family == "forms_directory" or family == "medical":
        return False
    if family == "policy":
        return name == "AHIP_HealthCareDollar.pdf" and page_number == 1
    if family != "population_health":
        return False
    if name == "allstatesummaries-ahr24.pdf":
        return True
    if name == "allstatesums-hwc2022.pdf":
        return page_number % 2 == 1
    percent_tokens = len(re.findall(r"(?<!\w)[+-]?\d+(?:\.\d+)?\s*%", text))
    numeric_tokens = len(re.findall(r"(?<!\w)\d+(?:\.\d+)?(?:%|x|\b)", text))
    figure_words = bool(re.search(r"\b(?:profile highlights|spotlight|key findings|by state|by age|trend|rate|prevalence)\b", text, re.I))
    return (percent_tokens >= 3 and drawings >= 8) or (figure_words and numeric_tokens >= 4 and (drawings >= 5 or image_count))


def vector_chart_regions(page: pymupdf.Page, text: str) -> int:
    page_area = page.rect.get_area()
    count = 0
    try:
        clusters = page.cluster_drawings()
    except Exception:
        clusters = []
    for rect in clusters:
        ratio = rect.get_area() / page_area if page_area else 0
        if ratio < 0.025 or ratio > 0.9 or rect.width < 100 or rect.height < 55:
            continue
        clipped = page.get_text("text", clip=rect) or ""
        numbers = len(re.findall(r"(?<!\w)[+-]?\d+(?:\.\d+)?\s*(?:%|x)?", clipped))
        labels = len(re.findall(r"[A-Za-z]{3,}", clipped))
        if numbers >= 3 and labels >= 2:
            count += 1
    if count == 0 and text.strip():
        count = 1
    return count


def scan_pdf(pdf: dict[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    path = Path(pdf["path"])
    manifest_path = Path(pdf["manifestPath"])
    doc = pymupdf.open(path)
    blank_pages: list[int] = []
    figure_pages: list[int] = []
    chart_pages: list[int] = []
    form_pages: list[int] = []
    native_text_pages = 0
    native_label_count = 0
    form_field_count = 0
    figure_count = 0
    chart_count = 0

    for index, page in enumerate(doc):
        page_number = index + 1
        text = page.get_text("text") or ""
        words = page.get_text("words") or []
        compact = re.sub(r"\s+", "", text)
        if compact:
            native_text_pages += 1
        else:
            blank_pages.append(page_number)
        drawings = len(page.get_drawings())
        images = significant_images(page)
        widgets = list(page.widgets() or [])
        form_field_count += len(widgets)
        if is_form_page(pdf["family"], pdf["name"], text, len(widgets), drawings):
            form_pages.append(page_number)
        if candidate_chart_page(pdf["family"], pdf["name"], page_number, text, drawings, len(images)):
            chart_pages.append(page_number)
            figure_pages.append(page_number)
            native_label_count += len(words)
            regions = vector_chart_regions(page, text)
            chart_count += regions
            figure_count += max(1, regions)
    page_count = len(doc)
    doc.close()

    table_pages = markdown_table_pages(manifest_path)
    canonical_tables = pdf.get("canonicalTableCount")
    return {
        "status": "completed",
        "scannedAt": utc_now(),
        "error": None,
        "pageCount": page_count,
        "nativeTextPages": native_text_pages,
        "blankTextPages": blank_pages,
        "nativeLabels": bool(figure_pages) and native_label_count > 0,
        "nativeLabelCount": native_label_count,
        "figureCount": figure_count,
        "figurePages": figure_pages,
        "chartCount": chart_count,
        "chartPages": chart_pages,
        "tableCount": canonical_tables if canonical_tables is not None else len(table_pages),
        "tablePages": table_pages,
        "formCount": len(form_pages),
        "formPages": form_pages,
        "formFieldCount": form_field_count,
        "scanSeconds": round(time.monotonic() - started, 3),
    }


def find_pdf(pdf_id: str) -> dict[str, Any] | None:
    for collection in STATE["collections"]:
        for pdf in collection["pdfs"]:
            if pdf["id"] == pdf_id:
                return pdf
    return None


def relative_document_path(pdf: dict[str, Any]) -> str:
    family_root = (CRAWL_ROOT / "raw" / pdf["family"]).resolve()
    return str(Path(pdf["path"]).resolve().relative_to(family_root))


def detected_figure_regions(page: pymupdf.Page) -> list[dict[str, Any]]:
    """Return native PDF evidence for likely chart/figure regions on one page."""
    page_area = page.rect.get_area()
    candidates: list[tuple[pymupdf.Rect, str]] = []
    try:
        clusters = page.cluster_drawings()
    except Exception:
        clusters = []
    for rect in clusters:
        ratio = rect.get_area() / page_area if page_area else 0
        if 0.025 <= ratio <= 0.9 and rect.width >= 100 and rect.height >= 55:
            clipped = page.get_text("text", clip=rect) or ""
            numbers = len(re.findall(r"(?<!\w)[+-]?\d+(?:\.\d+)?\s*(?:%|x)?", clipped))
            labels = len(re.findall(r"[A-Za-z]{3,}", clipped))
            if numbers >= 3 and labels >= 2:
                candidates.append((rect, "vector_geometry"))
    for rect in significant_images(page):
        candidates.append((rect, "embedded_image"))

    regions: list[dict[str, Any]] = []
    for rect, detection in candidates:
        if any(rect.intersects(existing["rect"]) and
               rect.get_area() <= existing["rect"].get_area() * 1.15
               for existing in regions):
            continue
        native_text = re.sub(r"\s+", " ", page.get_text("text", clip=rect) or "").strip()
        regions.append({"rect": rect, "detection": detection, "native_text": native_text})
    if not regions:
        regions.append({
            "rect": page.rect,
            "detection": "whole_page_fallback",
            "native_text": re.sub(r"\s+", " ", page.get_text("text") or "").strip(),
        })
    return regions


def page_html_document(
    *,
    pdf_name: str,
    page_number: int,
    markdown: str,
    table_ids: list[str],
    figure_spec: dict[str, Any] | None,
) -> str:
    figure_html = ""
    if figure_spec:
        cards = []
        for region in figure_spec["regions"]:
            values = ", ".join(region["numeric_tokens"]) or "No numeric labels detected"
            cards.append(
                "<figure>"
                f"<figcaption>{html.escape(region['id'])} · {html.escape(region['detection'])}</figcaption>"
                f"<p>{html.escape(region['native_text'])}</p>"
                f"<small>Values: {html.escape(values)}</small>"
                "</figure>"
            )
        figure_html = "<section><h2>Figure evidence</h2>" + "".join(cards) + "</section>"
    table_html = ""
    if table_ids:
        links = "".join(
            f'<li><a href="../../candidate/tables/{html.escape(table_id)}.html">'
            f"{html.escape(table_id)}</a></li>" for table_id in table_ids
        )
        table_html = f"<section><h2>Logical tables on this page</h2><ul>{links}</ul></section>"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(pdf_name)} · page {page_number}</title>
  <style>
    body {{ max-width: 960px; margin: 40px auto; padding: 0 24px; color: #172c3a; font: 16px/1.55 system-ui, sans-serif; }}
    pre {{ white-space: pre-wrap; background: #f3f6f5; padding: 20px; border: 1px solid #d8e1df; }}
    figure {{ margin: 16px 0; padding: 16px; border-left: 4px solid #2f8b78; background: #f5f9f8; }}
    figcaption {{ font-weight: 700; }} small {{ color: #587078; }}
  </style>
</head>
<body>
  <header><h1>{html.escape(pdf_name)}</h1><p>Page {page_number}</p></header>
  <main>
    <section><h2>Extracted page Markdown</h2><pre>{html.escape(markdown)}</pre></section>
    {figure_html}
    {table_html}
  </main>
</body>
</html>
"""


def markdown_cell(value: Any) -> str:
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", str(value))
    return cleaned.replace("|", r"\|").replace("\n", "<br>").strip()


def write_named_document_markdown(candidate_dir: Path, source_stem: str) -> Path:
    """Write one full-document Markdown file with consolidated logical tables."""
    base = (candidate_dir / "document.md").read_text(encoding="utf-8").rstrip()
    table_paths = sorted((candidate_dir / "tables").glob("table-*.json"))
    sections = [base]
    if table_paths:
        sections.append(
            "# Canonical logical tables\n\n"
            "These tables supersede any page-fragment table renderings above. "
            "Continuation fragments were consolidated before this section was written."
        )
    for table_path in table_paths:
        record = json.loads(table_path.read_text(encoding="utf-8"))
        headers = [str(value) for value in record.get("headers", [])]
        rows = record.get("rows", [])
        pages = ", ".join(str(value) for value in record.get("source_pages", [])) or "unknown"
        section = markdown_cell(record.get("section") or record["table_id"])
        lines = [
            f"## {section}",
            "",
            f"Source pages: {pages} · Table ID: `{record['table_id']}`",
            "",
        ]
        if headers:
            lines.extend([
                "| " + " | ".join(markdown_cell(header) for header in headers) + " |",
                "| " + " | ".join("---" for _ in headers) + " |",
            ])
            for row in rows:
                lines.append(
                    "| " + " | ".join(markdown_cell(row.get(header, "")) for header in headers) + " |"
                )
        else:
            lines.append("_No table columns were extracted._")
        sections.append("\n".join(lines))
    destination = candidate_dir / f"{source_stem}.md"
    destination.write_text("\n\n---\n\n".join(sections).rstrip() + "\n", encoding="utf-8")
    return destination


def write_page_artifacts(run_dir: Path, pdf: dict[str, Any]) -> tuple[int, int, int]:
    """Add page HTML and draft native-evidence specs to a canonical run."""
    from crawl_dir.src.pipeline.artifact_io import atomic_json

    figure_pages = set(pdf.get("figurePages") or []) | set(pdf.get("chartPages") or [])
    page_html_count = 0
    figure_spec_count = 0
    logical_table_ids: set[str] = set()
    with pymupdf.open(pdf["path"]) as document:
        for page_number in range(1, document.page_count + 1):
            page_dir = run_dir / "pages" / f"page-{page_number:03d}"
            manifest_path = page_dir / "page-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            table_ids = [str(value) for value in manifest.get("table_ids", [])]
            logical_table_ids.update(table_ids)
            figure_spec: dict[str, Any] | None = None
            if page_number in figure_pages:
                page = document[page_number - 1]
                regions = detected_figure_regions(page)
                page_native_text = re.sub(
                    r"\s+", " ", page.get_text("text") or ""
                ).strip()
                figure_spec = {
                    "schema_version": 1,
                    "artifact_type": "draft_native_figure_evidence",
                    "status": "needs_review",
                    "source_pdf": pdf["name"],
                    "page": page_number,
                    "page_size_pt": [round(page.rect.width, 3), round(page.rect.height, 3)],
                    "page_native_text": page_native_text,
                    "page_numeric_tokens": re.findall(
                        r"[+-]?\d+(?:\.\d+)?\s*(?:%|x)?", page_native_text
                    ),
                    "regions": [
                        {
                            "id": f"figure-{index:02d}",
                            "box_pt": [round(value, 3) for value in region["rect"]],
                            "detection": region["detection"],
                            "native_text": region["native_text"],
                            "numeric_tokens": re.findall(
                                r"[+-]?\d+(?:\.\d+)?\s*(?:%|x)?", region["native_text"]
                            ),
                        }
                        for index, region in enumerate(regions, 1)
                    ],
                }
                atomic_json(page_dir / "page.spec.json", figure_spec)
                manifest["figure_spec"] = "page.spec.json"
                figure_spec_count += 1
            else:
                manifest["figure_spec"] = None

            if figure_spec or table_ids:
                markdown_path = page_dir / "page.md"
                markdown = markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else ""
                (page_dir / "page.html").write_text(
                    page_html_document(
                        pdf_name=pdf["name"],
                        page_number=page_number,
                        markdown=markdown,
                        table_ids=table_ids,
                        figure_spec=figure_spec,
                    ),
                    encoding="utf-8",
                )
                manifest["html"] = "page.html"
                page_html_count += 1
            atomic_json(manifest_path, manifest)
    return page_html_count, figure_spec_count, len(logical_table_ids)


def run_extraction(pdf_id: str) -> None:
    global EXTRACTION_THREAD
    try:
        with STATE_LOCK:
            pdf = find_pdf(pdf_id)
            if pdf is None:
                return
        if pdf.get("status") != "completed":
            scan_result = scan_pdf(pdf)
            with STATE_LOCK:
                pdf.update(scan_result)
                persist_state()

        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        from crawl_dir.src.pipeline.artifact_io import sha256_file
        from crawl_dir.src.pipeline.runner import process_document

        source = Path(pdf["path"])
        source_hash = sha256_file(source)
        identifier = (
            f"scan-app-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-"
            f"{source_hash[:6]}"
        )
        run_dir = process_document(
            root=CRAWL_ROOT,
            family=pdf["family"],
            document=relative_document_path(pdf),
            document_version=source_hash[:12],
            requested_run_id=identifier,
        )
        candidate_dir = run_dir / "candidate"
        named_markdown = write_named_document_markdown(candidate_dir, source.stem)
        page_html_count, figure_spec_count, logical_table_count = write_page_artifacts(
            run_dir, pdf
        )
        with STATE_LOCK:
            pdf.update({
                "extractionStatus": "completed",
                "extractionCompletedAt": utc_now(),
                "extractionError": None,
                "extractionRunPath": str(run_dir),
                "markdownPath": str(named_markdown),
                "chunksPath": str(candidate_dir / "chunks.jsonl"),
                "pageHtmlCount": page_html_count,
                "figureSpecCount": figure_spec_count,
                "logicalTableCount": logical_table_count,
            })
    except Exception as exc:
        with STATE_LOCK:
            pdf = find_pdf(pdf_id)
            if pdf is not None:
                pdf.update({
                    "extractionStatus": "error",
                    "extractionCompletedAt": utc_now(),
                    "extractionError": f"{type(exc).__name__}: {exc}",
                })
    finally:
        with STATE_LOCK:
            STATE["activeExtraction"] = None
            EXTRACTION_THREAD = None
            persist_state()


def run_scan(force: bool) -> None:
    global SCAN_THREAD
    try:
        for collection in STATE["collections"]:
            for pdf in collection["pdfs"]:
                with STATE_LOCK:
                    if not force and pdf["status"] == "completed":
                        continue
                    pdf["status"] = "scanning"
                    pdf["error"] = None
                    STATE["activePdf"] = pdf["path"]
                    persist_state()
                try:
                    result = scan_pdf(pdf)
                except Exception as exc:
                    result = {"status": "error", "error": f"{type(exc).__name__}: {exc}", "scannedAt": utc_now()}
                with STATE_LOCK:
                    pdf.update(result)
                    persist_state()
        with STATE_LOCK:
            STATE["completedAt"] = utc_now()
    finally:
        with STATE_LOCK:
            STATE["running"] = False
            STATE["activePdf"] = None
            persist_state()
            SCAN_THREAD = None


async def get_state(_: web.Request) -> web.Response:
    with STATE_LOCK:
        refresh_collection_statuses()
        return web.json_response(deepcopy(STATE))


async def start_scan(request: web.Request) -> web.Response:
    global SCAN_THREAD
    force = request.query.get("force") == "1"
    with STATE_LOCK:
        if STATE["running"]:
            return web.json_response({"error": "A scan is already running."}, status=409)
        if EXTRACTION_THREAD is not None:
            return web.json_response({
                "error": "A Docling extraction is running; wait for it to finish before scanning."
            }, status=409)
        STATE["running"] = True
        STATE["startedAt"] = utc_now()
        STATE["completedAt"] = None
        for collection in STATE["collections"]:
            for pdf in collection["pdfs"]:
                if force or pdf["status"] != "completed":
                    pdf["status"] = "queued"
        persist_state()
        SCAN_THREAD = threading.Thread(target=run_scan, args=(force,), daemon=True, name="pdf-collection-scan")
        SCAN_THREAD.start()
    return web.json_response({"started": True, "force": force}, status=202)


async def start_extraction(request: web.Request) -> web.Response:
    global EXTRACTION_THREAD
    pdf_id = request.match_info["pdf_id"]
    with STATE_LOCK:
        pdf = find_pdf(pdf_id)
        if pdf is None:
            return web.json_response({"error": "Unknown PDF."}, status=404)
        if STATE["running"]:
            return web.json_response({
                "error": "The collection scan is running; wait for it to finish before extracting."
            }, status=409)
        if EXTRACTION_THREAD is not None:
            return web.json_response({
                "error": "Another Docling extraction is already running.",
                "activeExtraction": STATE.get("activeExtraction"),
            }, status=409)
        pdf.update({
            "extractionStatus": "extracting",
            "extractionStartedAt": utc_now(),
            "extractionCompletedAt": None,
            "extractionError": None,
        })
        STATE["activeExtraction"] = pdf["path"]
        persist_state()
        EXTRACTION_THREAD = threading.Thread(
            target=run_extraction,
            args=(pdf_id,),
            daemon=True,
            name=f"docling-extract-{pdf_id}",
        )
        EXTRACTION_THREAD.start()
    return web.json_response({"started": True, "pdfId": pdf_id}, status=202)


async def index(_: web.Request) -> web.StreamResponse:
    index_path = UI_DIST / "index.html"
    if index_path.exists():
        return web.FileResponse(index_path)
    return web.Response(
        text="UI not built. Run `npm install && npm run build`, or use `npm run dev` on port 5174.",
        content_type="text/plain",
        status=503,
    )


def make_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/api/state", get_state)
    app.router.add_post("/api/scan", start_scan)
    app.router.add_post("/api/extract/{pdf_id}", start_extraction)
    if UI_DIST.exists():
        app.router.add_static("/assets", UI_DIST / "assets")
    app.router.add_get("/{tail:.*}", index)
    return app


if __name__ == "__main__":
    persist_state()
    web.run_app(make_app(), host="127.0.0.1", port=8788)
