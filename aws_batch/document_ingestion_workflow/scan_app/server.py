"""Local API and PDF scanner for the five ingestion collections."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import threading
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pymupdf
from aiohttp import web


APP_ROOT = Path(__file__).resolve().parent
CRAWL_ROOT = APP_ROOT.parents[1] / "crawl_dir"
STATE_PATH = APP_ROOT / "scan_state.json"
LEGACY_STATE_PATH = APP_ROOT / "data" / "scan_state.json"
SCAN_REGISTRY_PATH = APP_ROOT / "scan_registry.json"
UI_DIST = APP_ROOT / "dist"

RECOMMENDATIONS = {
    "research": "Use figure specs for native-text research reports with charts; reuse existing reviewed runs where available.",
    "population_health": "Use the figure-spec workflow on figure pages in all seven PDFs.",
    "policy": "Use figure specs selectively: AHIP HealthCareDollar page 1 only.",
    "forms_directory": "Preserve form fields, boxes, lists and tables.",
    "medical": "Use native text and table extraction; review marketing visuals separately.",
}
COLLECTIONS = {
    path.name: {
        "path": path,
        "recommendation": RECOMMENDATIONS.get(
            path.name, "Scan source PDFs for native text, figures, and tables before ingestion."
        ),
    }
    for path in sorted((CRAWL_ROOT / "raw").iterdir()) if path.is_dir()
}

# Qualitative calibration from the verified visual audit. Numeric page/label/region
# metrics are recomputed on every scan; table totals come from the canonical run QC.
CALIBRATION: dict[str, tuple[str, str, str]] = {
    "ey-limra-workforce-benefits-study-final-2025.pdf": (
        "Native text with quantitative charts, figures and tables",
        "Yes; existing figure-spec runs are available",
        "Reuse the reviewed figure-spec run and preserve document-level hybrid chunks",
    ),
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


def run_timestamp(path: Path) -> str:
    """Return a sortable timestamp token embedded in a run directory name."""
    match = re.search(r"(\d{4})-?(\d{2})-?(\d{2})(?:T(\d{6})Z?)?", path.parent.name)
    if not match:
        return ""
    return "".join(part or "" for part in match.groups())


def load_scan_registry() -> dict[str, Any]:
    if not SCAN_REGISTRY_PATH.exists():
        return {"version": 1, "collections": {}}
    try:
        registry = json.loads(SCAN_REGISTRY_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "collections": {}}
    if not isinstance(registry.get("collections"), dict):
        registry["collections"] = {}
    return registry


def inventory_fingerprint(records: list[dict[str, Any]]) -> str:
    inventory: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda item: item["path"]):
        path = Path(record["path"])
        try:
            stat = path.stat()
            inventory.append({
                "path": record["path"],
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            })
        except OSError:
            inventory.append({"path": record["path"], "missing": True})
    payload = json.dumps(inventory, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


SCAN_REGISTRY = load_scan_registry()


def discover_pdfs() -> list[dict[str, Any]]:
    discovered: list[dict[str, Any]] = []
    for family, config in COLLECTIONS.items():
        run_root = CRAWL_ROOT / "runs" / family
        by_source: dict[str, list[tuple[Path, dict[str, Any]]]] = {}
        for manifest_path in sorted(run_root.glob("*/*/run-manifest.json")):
            try:
                manifest = json.loads(manifest_path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            source = manifest.get("source")
            if source:
                by_source.setdefault(source, []).append((manifest_path, manifest))
        for source, runs in sorted(by_source.items()):
            processed_runs: list[tuple[Path, dict[str, Any]]] = []
            for candidate_path, _ in runs:
                qc_path = candidate_path.parent / "qc-report.json"
                if not qc_path.exists():
                    continue
                try:
                    processed_runs.append((candidate_path, json.loads(qc_path.read_text())))
                except (OSError, json.JSONDecodeError):
                    continue
            if processed_runs:
                manifest_path, qc = max(
                    processed_runs,
                    key=lambda item: (run_timestamp(item[0]), item[0].parent.name),
                )
            else:
                manifest_path, _ = max(
                    runs,
                    key=lambda item: (run_timestamp(item[0]), item[0].parent.name),
                )
                qc = {}
            pdf_path = (CRAWL_ROOT / source).resolve()
            try:
                source_stat = pdf_path.stat()
                source_fingerprint = hashlib.sha256(
                    f"{source_stat.st_size}:{source_stat.st_mtime_ns}".encode()
                ).hexdigest()
            except OSError:
                source_fingerprint = "missing"
            description, recommendation, workflow = classification(family, pdf_path.name)
            canonical_tables = None
            try:
                canonical_tables = int(qc.get("table_count", 0)) if qc else None
            except (ValueError, TypeError):
                pass
            discovered.append({
                "id": record_id(family, pdf_path),
                "family": family,
                "name": pdf_path.name,
                "path": str(pdf_path),
                "sourceFingerprint": source_fingerprint,
                "manifestPath": str(manifest_path),
                "canonicalTableCount": canonical_tables,
                "processedRunCount": len(processed_runs),
                "ingestionStatus": qc.get("status") if qc else None,
                "ingestionRunName": manifest_path.parent.name if processed_runs else None,
                "figureDescription": description,
                "recommendation": recommendation,
                "recommendedWorkflow": workflow,
            })
        known = {record["path"] for record in discovered if record["family"] == family}
        for pdf_path in sorted(config["path"].rglob("*.pdf")):
            pdf_path = pdf_path.resolve()
            if str(pdf_path) in known:
                continue
            stat = pdf_path.stat()
            fingerprint = hashlib.sha256(
                f"{stat.st_size}:{stat.st_mtime_ns}".encode()
            ).hexdigest()
            description, recommendation, workflow = classification(family, pdf_path.name)
            discovered.append({
                "id": record_id(family, pdf_path),
                "family": family,
                "name": pdf_path.name,
                "path": str(pdf_path),
                "sourceFingerprint": fingerprint,
                "manifestPath": None,
                "canonicalTableCount": None,
                "processedRunCount": 0,
                "ingestionStatus": None,
                "ingestionRunName": None,
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
    }


def load_state() -> dict[str, Any]:
    prior: dict[str, Any] = {}
    state_source = STATE_PATH if STATE_PATH.exists() else LEGACY_STATE_PATH
    if state_source.exists():
        try:
            prior_state = json.loads(state_source.read_text())
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
            saved_fingerprint = saved.get("sourceFingerprint")
            if saved_fingerprint is None or saved_fingerprint == record["sourceFingerprint"]:
                current.update({key: value for key, value in saved.items() if key in current})
                current.update({
                    "path": record["path"],
                    "sourceFingerprint": record["sourceFingerprint"],
                    "manifestPath": record["manifestPath"],
                    "canonicalTableCount": record["canonicalTableCount"],
                    "processedRunCount": record["processedRunCount"],
                    "ingestionStatus": record["ingestionStatus"],
                    "ingestionRunName": record["ingestionRunName"],
                    "figureDescription": record["figureDescription"],
                    "recommendation": record["recommendation"],
                    "recommendedWorkflow": record["recommendedWorkflow"],
                })
        groups[record["family"]].append(current)
    collections: list[dict[str, Any]] = []
    for family, config in COLLECTIONS.items():
        fingerprint = inventory_fingerprint(groups[family])
        registry_entry = SCAN_REGISTRY["collections"].get(family, {})
        completed_times = [
            pdf["scannedAt"]
            for pdf in groups[family]
            if pdf.get("status") == "completed" and pdf.get("scannedAt")
        ]
        if (
            not registry_entry
            and groups[family]
            and len(completed_times) == len(groups[family])
        ):
            registry_entry = {
                "path": str(config["path"]),
                "scannedAt": max(completed_times),
                "inventoryFingerprint": fingerprint,
                "pdfCount": len(groups[family]),
            }
            SCAN_REGISTRY["collections"][family] = registry_entry
        collections.append({
            "key": family,
            "path": str(config["path"]),
            "status": "not_scanned",
            "total": len(groups[family]),
            "completed": 0,
            "errors": 0,
            "recommendation": config["recommendation"],
            "lastScannedAt": registry_entry.get("scannedAt"),
            "inventoryFingerprint": fingerprint,
            "hasChanges": registry_entry.get("inventoryFingerprint") != fingerprint,
            "pdfs": groups[family],
        })
    return {
        "version": 1,
        "running": False,
        "startedAt": None,
        "completedAt": None,
        "activePdf": None,
        "collections": collections,
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


def persist_scan_registry() -> None:
    SCAN_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = SCAN_REGISTRY_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(SCAN_REGISTRY, indent=2))
    temp.replace(SCAN_REGISTRY_PATH)


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
    if family in {"forms", "forms_directory", "claims", "appeals", "medical"}:
        return False
    if family == "policy":
        return name == "AHIP_HealthCareDollar.pdf" and page_number == 1
    if family == "research":
        if name != "ey-limra-workforce-benefits-study-final-2025.pdf":
            return False
        percent_tokens = len(re.findall(r"(?<!\w)[+-]?\d+(?:\.\d+)?\s*%", text))
        numeric_tokens = len(re.findall(r"(?<!\w)\d+(?:\.\d+)?(?:%|x|\b)", text))
        return (percent_tokens >= 3 and drawings >= 8) or (numeric_tokens >= 4 and (drawings >= 5 or image_count))
    if family == "benefits_research":
        if re.search(r"(?im)^\s*Figure\s+\d+\s*:", text):
            return True
        if re.search(r"(?im)^\s*Table\s+\d+(?:\s*\([^)]*\))?\s*:", text):
            return False
    if family == "population_health" and name == "allstatesummaries-ahr24.pdf":
        return True
    if family == "population_health" and name == "allstatesums-hwc2022.pdf":
        return page_number % 2 == 1
    percent_tokens = len(re.findall(r"(?<!\w)[+-]?\d+(?:\.\d+)?\s*%", text))
    numeric_tokens = len(re.findall(r"(?<!\w)\d+(?:\.\d+)?(?:%|x|\b)", text))
    figure_words = bool(re.search(r"\b(?:figure|chart|survey|profile highlights|spotlight|key findings|by state|by age|trend|rate|prevalence)\b", text, re.I))
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
    manifest_path = Path(pdf["manifestPath"]) if pdf.get("manifestPath") else None
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
    source_table_pages: list[int] = []
    source_table_count = 0

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
        table_on_page = False
        if manifest_path is None:
            found_tables = page.find_tables().tables
            table_titles = re.findall(
                r"(?im)^\s*Table\s+\d+(?:\s*\([^)]*\))?\s*:", text
            )
            numeric_prefix = re.findall(r"\b\d+\.\d{2}\b", text[:1200])
            continuation = (
                page_number - 1 in source_table_pages
                and not table_titles
                and len(numeric_prefix) >= 8
            )
            table_on_page = bool(found_tables or table_titles or continuation)
            if table_on_page:
                source_table_pages.append(page_number)
                source_table_count += max(len(found_tables), len(table_titles), int(continuation))
        figure_caption = bool(re.search(r"(?im)^\s*Figure\s+\d+\s*:", text))
        if (not (table_on_page and not figure_caption)
                and candidate_chart_page(pdf["family"], pdf["name"], page_number,
                                         text, drawings, len(images))):
            chart_pages.append(page_number)
            figure_pages.append(page_number)
            native_label_count += len(words)
            regions = vector_chart_regions(page, text)
            chart_count += regions
            figure_count += max(1, regions)
    page_count = len(doc)
    doc.close()

    table_pages = markdown_table_pages(manifest_path) if manifest_path else source_table_pages
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
        "tableCount": canonical_tables if canonical_tables is not None else source_table_count if manifest_path is None else len(table_pages),
        "tablePages": table_pages,
        "formCount": len(form_pages),
        "formPages": form_pages,
        "formFieldCount": form_field_count,
        "scanSeconds": round(time.monotonic() - started, 3),
    }


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
                if collection["pdfs"] and all(pdf["status"] == "completed" for pdf in collection["pdfs"]):
                    scanned_at = utc_now()
                    collection["lastScannedAt"] = scanned_at
                    collection["hasChanges"] = False
                    SCAN_REGISTRY["collections"][collection["key"]] = {
                        "path": collection["path"],
                        "scannedAt": scanned_at,
                        "inventoryFingerprint": collection["inventoryFingerprint"],
                        "pdfCount": collection["total"],
                    }
                    persist_scan_registry()
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
    global SCAN_THREAD, STATE
    force = request.query.get("force") == "1"
    with STATE_LOCK:
        if STATE["running"]:
            return web.json_response({"error": "A scan is already running."}, status=409)
        # Re-discover the directories at click time so newly added PDFs appear
        # without restarting the server. Existing per-PDF results are restored
        # from scan_state.json by their stable record IDs.
        STATE = load_state()
        pending = [
            pdf
            for collection in STATE["collections"]
            for pdf in collection["pdfs"]
            if force or pdf["status"] != "completed"
        ]
        if not pending:
            persist_state()
            return web.json_response({"started": False, "upToDate": True, "force": False})
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
    return web.json_response({"started": True, "force": force, "queued": len(pending)}, status=202)


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
    if UI_DIST.exists():
        app.router.add_static("/assets", UI_DIST / "assets")
    app.router.add_get("/{tail:.*}", index)
    return app


if __name__ == "__main__":
    persist_scan_registry()
    persist_state()
    web.run_app(make_app(), host="127.0.0.1", port=8788)
