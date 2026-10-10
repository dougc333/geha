"""SSE backend for the public-document ingestion demo."""

from __future__ import annotations

import asyncio
import json
import os
import threading
import traceback
import uuid
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiohttp import web

from crawl_dir.src.ingestion_mcp import ROOT, download_public_pdf
from crawl_dir.src.pipeline.scanned_ingestion import (
    image_only_pages,
    detect_visual_figure_pages,
    pdf_page_count,
    process_scanned_document,
    render_pdf_page_with_pymupdf,
    render_pdf_viewer_with_playwright_chromium,
    review_chart_html_with_claude,
)
from crawl_dir.src.pipeline.claude_client import CLAUDE_MODEL, claude_credentials_available
from crawl_dir.src.pipeline.figure_specs import (
    TOOL_ID as FIGURE_SPEC_TOOL_ID,
    make_spec_generator,
    make_spec_segmenter,
    spec_pages,
    spec_reviewer,
)
from crawl_dir.src.pipeline.figure_segmentation import (
    generate_page_html_with_corrected_figures,
    segment_charts_and_figures,
)
from crawl_dir.demo.bill_of_lading_workflow import (
    GRAPH_PROGRAM as BILL_OF_LADING_GRAPH_PROGRAM,
    correct_bill_of_lading_cells,
    generate_bill_of_lading_html_from_schema,
    review_bill_of_lading,
    segment_bill_of_lading_with_schema,
)

DEFAULT_DOCUMENT = "coverage-policies/geha-coverage-policy-datroway.pdf"
# Only the bill-of-lading cell extraction/correction graph still calls OpenAI.
OPENAI_MODEL = "gpt-4.1-mini"
DEMO_DOCUMENTS = {
    DEFAULT_DOCUMENT: {
        "title": "Datroway",
        "family": "coverage-policies",
        "filename": "geha-coverage-policy-datroway.pdf",
        "document_version": "demo-2026-10-09",
        "layout_kind": "mixed_policy",
    },
    "coverage-policies/geha-coverage-policy-elrexfio.pdf": {
        "title": "Elrexfio",
        "family": "coverage-policies",
        "filename": "geha-coverage-policy-elrexfio.pdf",
        "document_version": "demo-2026-10-09",
        "layout_kind": "mixed_policy",
    },
    "coverage-policies/geha-coverage-policy-bendamustine.pdf": {
        "title": "Bendamustine",
        "family": "coverage-policies",
        "filename": "geha-coverage-policy-bendamustine.pdf",
        "document_version": "demo-2026-10-09",
        "layout_kind": "native_text_report",
    },
    "forms/bill-of-lading.pdf": {
        "title": "Bill of lading",
        "family": "forms",
        "filename": "bill-of-lading.pdf",
        "document_version": "synthetic-demo-2026-09-27",
        "layout_kind": "dense_form",
        "workflow": "bill_of_lading_schema_graph",
        "local_fixture": True,
        "layout_hint": (
            "Bill of lading with header, shipper/consignee fields, routing fields, "
            "container/cargo grid, freight charges, totals, terms, and signature areas."
        ),
    },
    "research/ey-limra-workforce-benefits-study-final-2025.pdf": {
        "title": "EY workforce benefits",
        "family": "research",
        "filename": "ey-limra-workforce-benefits-study-final-2025.pdf",
        "document_version": "2025",
        "layout_kind": "hybrid_figure_report",
        "local_fixture": True,
        "source_status": "Local public research report",
        "figure_specs": "annotations/research/ey-limra-workforce-benefits-study-final-2025/figure-specs",
    },
}
UI_DIST = Path(__file__).parent / "ui" / "dist"
ALLOWED_ARTIFACT_ROOTS = tuple((ROOT / name).resolve() for name in ("raw", "runs"))
SERVER_INSTANCE_ID = uuid.uuid4().hex


@dataclass
class DemoRun:
    run_id: str
    events: list[dict[str, Any]] = field(default_factory=list)
    complete: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)

    def emit(self, event: dict[str, Any]) -> None:
        with self.lock:
            self.events.append({
                **event,
                "seq": len(self.events) + 1,
                "at": datetime.now(timezone.utc).isoformat(),
            })

    def finish(self) -> None:
        with self.lock:
            self.complete = True

    def snapshot(self, offset: int) -> tuple[list[dict[str, Any]], bool]:
        with self.lock:
            return self.events[offset:], self.complete


class DemoRunRegistry:
    """Thread-safe owner of in-memory live-run state."""

    def __init__(self) -> None:
        self._runs: dict[str, DemoRun] = {}
        self._lock = threading.Lock()

    def create(self) -> DemoRun:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run = DemoRun(f"agent-demo-{stamp}-{uuid.uuid4().hex[:6]}")
        with self._lock:
            self._runs[run.run_id] = run
        return run

    def get(self, run_id: str) -> DemoRun:
        with self._lock:
            run = self._runs.get(run_id)
        if run is None:
            raise web.HTTPNotFound(text="Unknown demo run")
        return run


RUNS = DemoRunRegistry()


class ScreenshotToolRouter:
    """Choose the safest local PDF renderer for the requested evidence type."""

    PROFILES = [
        {
            "id": "pymupdf",
            "name": "PyMuPDF page rasterizer",
            "estimated_latency_ms": "50–300",
            "cost_usd_per_page": 0.0,
            "strength": "Exact page-only pixels; no browser controls",
        },
        {
            "id": "playwright_chromium",
            "name": "Playwright + Google Chrome",
            "estimated_latency_ms": "1,000–4,000",
            "cost_usd_per_page": 0.0,
            "strength": "Captures Chrome PDF-viewer behavior",
        },
    ]

    def __init__(self, run: DemoRun) -> None:
        self.run = run

    def choose(self) -> tuple[str, Any]:
        chrome_available = bool(shutil.which("Google Chrome") or
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome").exists())
        profiles = [
            {**profile, "available": profile["id"] == "pymupdf" or chrome_available}
            for profile in self.PROFILES
        ]
        self.run.emit({"type": "screenshot_tools_considered", "tools": profiles,
                       "requirement": "authoritative page-only evidence"})
        selected = "pymupdf"
        reason = (
            "Selected PyMuPDF because visual review requires exact page-only pixels; "
            "Chrome can add viewer margins or controls and has higher startup latency."
        )
        self.run.emit({"type": "screenshot_tool_selected", "tool": selected,
                       "reason": reason})
        return selected, render_pdf_page_with_pymupdf


class LayoutToolRouter:
    """Choose among the extraction workflows used by the demo documents."""

    PROFILES = [
        {
            "id": "native_pdf_text_structure",
            "name": "Native PDF text + structure",
            "estimated_latency": "local parsing; no generation call",
            "incremental_cost": "$0 model cost",
            "strength": "Uses embedded PDF text plus deterministic table extraction",
            "runs": "Docling native export (scanned_ingestion._native_page_exports); no model",
        },
        {
            "id": "whole_page_semantic_html",
            "name": "Whole-page semantic HTML",
            "estimated_latency": "HTML generation + bounded visual correction loop",
            "incremental_cost": "vision generation/review/correction calls",
            "strength": "Preserves complete page composition, charts, tables, and reading order",
            "runs": f"scanned_ingestion.py: generate/review/correct with {CLAUDE_MODEL}",
        },
        {
            "id": "chart_figure_crop_html_correction",
            "name": "Chart/figure crop HTML correction (figure_segmentation)",
            "estimated_latency": "bounding boxes + up to 6 correction passes per visual",
            "incremental_cost": "vision segmentation, generation, review, and correction calls",
            "strength": "Auditable crop PNGs and per-figure attempts/errors before page assembly",
            "runs": (f"figure_segmentation.py: {CLAUDE_MODEL} finds figure boxes, writes HTML, "
                     "reviews and corrects it; fallback when a figure report has no specs"),
        },
        {
            "id": "bill_of_lading_named_cell_ocr",
            "name": "Bill of Lading named-cell OCR",
            "estimated_latency": "8 structured OCR calls + deterministic build",
            "incremental_cost": "8 vision OCR calls; no layout-generation call",
            "strength": "Literal named-cell records drive deterministic HTML assembly",
            "program": str(BILL_OF_LADING_GRAPH_PROGRAM),
            "runs": f"bill_of_lading_workflow.py: cell OCR with {OPENAI_MODEL}",
        },
        {
            "id": FIGURE_SPEC_TOOL_ID,
            "name": "Authored figure specs (no model)",
            "estimated_latency": "local render + native-text verification",
            "incremental_cost": "$0 model cost",
            "strength": "Spec values/labels checked against PDF text; deterministic semantic HTML",
            "runs": "figure_specs.py: annotations/<doc>/figure-specs/page-NNN.json; no model",
        },
    ]

    def __init__(self, run: DemoRun, layout_kind: str, workflow: str | None = None,
                 specs_dir: Path | None = None) -> None:
        self.run = run
        self.layout_kind = layout_kind
        self.workflow = workflow
        self.specs_dir = specs_dir
        self.spec_pages = spec_pages(specs_dir) if specs_dir and specs_dir.is_dir() else []
        self.selected: str | None = None

    def choose(self) -> tuple[Any | None, Any | None]:
        self.run.emit({
            "type": "layout_tools_considered",
            "tools": [
                {**profile, "available": (
                    self.layout_kind in {"native_text_report", "hybrid_figure_report"}
                    if profile["id"] == "native_pdf_text_structure"
                    else self.layout_kind in {"hybrid_figure_report", "mixed_policy"}
                    if profile["id"] == "whole_page_semantic_html"
                    else self.layout_kind == "hybrid_figure_report"
                    if profile["id"] == "chart_figure_crop_html_correction"
                    else self.workflow == "bill_of_lading_schema_graph"
                    if profile["id"] == "bill_of_lading_named_cell_ocr"
                    else bool(self.spec_pages)
                    if profile["id"] == FIGURE_SPEC_TOOL_ID
                    else True
                )}
                for profile in self.PROFILES
            ],
            "observed_layout": self.layout_kind,
        })
        if self.layout_kind == "hybrid_figure_report" and self.spec_pages:
            selected = FIGURE_SPEC_TOOL_ID
            reason = (
                f"Authored figure specs exist for {len(self.spec_pages)} pages "
                f"({self.specs_dir.name}). Verify every printed value and label against native "
                "PDF text inside each figure box and render semantic HTML without a model; "
                "pages without specs use native PDF text."
            )
            callbacks = (make_spec_segmenter(self.specs_dir),
                         make_spec_generator(self.specs_dir, event_sink=self.run.emit))
        elif self.layout_kind == "hybrid_figure_report":
            selected = "chart_figure_crop_html_correction"
            reason = (
                "The EY report uses designed layouts, findings grids, infographics, photography, "
                "and charts throughout. Detect each chart/figure, save its labeled crop and overlay, "
                "correct its semantic HTML for at most six passes, record every error, then assemble "
                "and verify the complete page HTML."
            )
            def generate_figures_with_trace(source_png, segmentation, segment_dir, model):
                return generate_page_html_with_corrected_figures(
                    source_png, segmentation, segment_dir, model,
                    max_iterations=6, event_sink=self.run.emit,
                )

            callbacks = segment_charts_and_figures, generate_figures_with_trace
        elif self.layout_kind == "native_text_report":
            selected = "native_pdf_text_structure"
            reason = (
                "The PDF contains embedded text on every page. Use local native-text and "
                "table extraction without a vision-generation call."
            )
            callbacks = None, None
        elif self.workflow == "bill_of_lading_schema_graph":
            selected = "bill_of_lading_named_cell_ocr"
            reason = (
                "The source matches the curated Bill of Lading fixture. Use its versioned "
                "eight-block schema, extract literal named-cell records, and assemble HTML "
                "deterministically instead of asking a model to recreate the layout."
            )
            def generate_with_trace(source_png, segmentation, segment_dir, model):
                return generate_bill_of_lading_html_from_schema(
                    source_png, segmentation, segment_dir, model,
                    event_sink=self.run.emit,
                )

            callbacks = segment_bill_of_lading_with_schema, generate_with_trace
        else:
            selected = "whole_page_semantic_html"
            reason = "The page is primarily policy content; whole-page context is more useful."
            callbacks = None, None
        self.selected = selected
        self.run.emit({"type": "layout_tool_selected", "tool": selected, "reason": reason})
        return callbacks


class IngestionDemoAgent:
    """Runs the real downloader and scanned-page correction workflow."""

    def __init__(self, run: DemoRun, document: str, delay_seconds: float = 5) -> None:
        self.run = run
        self.document = document
        self.config = DEMO_DOCUMENTS[document]
        self.delay_seconds = delay_seconds

    def execute(self) -> None:
        try:
            self.run.emit({"type": "agent_started", "document": self.document,
                           "title": self.config["title"]})
            if self.config.get("local_fixture"):
                source = ROOT / "raw" / self.document
                if not source.is_file():
                    raise FileNotFoundError(source)
                self.run.emit({"type": "source_ready", "status": self.config.get(
                                   "source_status", "Local synthetic fixture"),
                               "destination": str(source)})
            else:
                self.run.emit({"type": "tool_selected", "tool": "download_public_pdf",
                               "reason": "Acquire the manifest-pinned public source document."})
                download = download_public_pdf(self.document, confirm=True)
                self.run.emit({"type": "download_complete", **download})
            native_figure_report = self.config["layout_kind"] == "hybrid_figure_report"
            native_text_report = self.config["layout_kind"] == "native_text_report"
            specs_dir = (ROOT / self.config["figure_specs"]
                         if self.config.get("figure_specs") else None)
            self.run.emit({
                "type": "tool_selected",
                "tool": ("ingest_native_pdf_with_visual_figures"
                         if native_figure_report else "ingest_scanned_pdf"),
                "reason": (
                    "Rebuild the designed report's figure pages as semantic HTML and verify "
                    "them before assembling the candidate."
                    if native_figure_report else
                    "Use embedded PDF text and deterministic Docling table extraction; no "
                    "LLM generation call is required."
                    if native_text_report else
                    "The PDF may contain image-only pages requiring reconstruction."
                ),
            })
            renderer_name, renderer = ScreenshotToolRouter(self.run).choose()
            router = LayoutToolRouter(
                self.run, self.config["layout_kind"], self.config.get("workflow"), specs_dir
            )
            page_segmenter, segmented_generator = router.choose()
            is_bill_of_lading = self.config.get("workflow") == "bill_of_lading_schema_graph"
            authored_specs = router.selected == FIGURE_SPEC_TOOL_ID
            visual_pages: list[int] = []
            if authored_specs:
                visual_pages = router.spec_pages
                self.run.emit({"type": "visual_pages_selected", "pages": visual_pages,
                               "count": len(visual_pages),
                               "method": "pages with authored figure specs"})
            elif self.config["layout_kind"] == "hybrid_figure_report":
                visual_pages = list(range(1, pdf_page_count(source) + 1))
                self.run.emit({"type": "visual_pages_selected", "pages": visual_pages,
                               "count": len(visual_pages),
                               "method": "all pages in designed EY report"})
            output = process_scanned_document(
                root=ROOT,
                family=self.config["family"],
                document=self.config["filename"],
                document_version=self.config["document_version"],
                # Bill-of-lading cell extraction/correction still run on OpenAI.
                model=(OPENAI_MODEL if is_bill_of_lading else
                       FIGURE_SPEC_TOOL_ID if authored_specs else CLAUDE_MODEL),
                max_corrections=(3 if is_bill_of_lading else 0 if authored_specs else 6),
                corrector=(correct_bill_of_lading_cells if is_bill_of_lading else None),
                reviewer=(review_bill_of_lading if is_bill_of_lading else
                          spec_reviewer if authored_specs else
                          review_chart_html_with_claude if native_figure_report else None),
                source_renderer=renderer,
                source_renderer_name=renderer_name,
                source_renderer_cost_usd=0.0,
                page_segmenter=page_segmenter,
                segmented_generator=segmented_generator,
                segmentation_layout_hint=self.config.get("layout_hint", ""),
                additional_visual_pages=visual_pages,
                requested_run_id=self.run.run_id,
                event_sink=self.run.emit,
                demo_delay_seconds=self.delay_seconds,
            )
            qc = json.loads((output / "qc-report.json").read_text(encoding="utf-8"))
            self.run.emit({"type": "agent_finished", "run": str(output), "qc": qc})
        except Exception as exc:  # Keep the UI trace useful when an external call fails.
            self.run.emit({
                "type": "agent_error",
                "message": str(exc),
                "exception": type(exc).__name__,
                "traceback": traceback.format_exc(limit=8),
            })
        finally:
            self.run.finish()


async def health(_: web.Request) -> web.Response:
    return web.json_response({
        "ready": claude_credentials_available(),
        "openai_ready": bool(os.getenv("OPENAI_API_KEY")),
        "server_instance_id": SERVER_INSTANCE_ID,
        "document": DEFAULT_DOCUMENT,
        "delay_seconds": 5,
        "model": CLAUDE_MODEL,
        "bill_of_lading_model": OPENAI_MODEL,
    })


async def documents(_: web.Request) -> web.Response:
    results = []
    for document, config in DEMO_DOCUMENTS.items():
        source = ROOT / "raw" / document
        visual_pages = (list(range(1, pdf_page_count(source) + 1))
                        if config["layout_kind"] == "hybrid_figure_report" else [])
        results.append({
            "document": document,
            "title": config["title"],
            "filename": config["filename"],
            "page_count": pdf_page_count(source),
            "image_only_pages": image_only_pages(source),
            "visual_reconstruction_pages": visual_pages,
        })
    return web.json_response({"documents": results, "default": DEFAULT_DOCUMENT})


def _page_comparisons_for_run(run_dir: Path) -> dict[str, dict[str, Any]]:
    """Return browser-safe artifact metadata for one saved run."""
    comparisons: dict[str, dict[str, Any]] = {}
    pages_dir = run_dir / "pages"
    if not pages_dir.is_dir():
        return comparisons
    for page_dir in sorted(pages_dir.glob("page-[0-9][0-9][0-9]")):
        source_pdf = page_dir / "source.pdf"
        final_html = page_dir / "final.html"
        if not source_pdf.is_file() or not final_html.is_file():
            continue
        page = int(page_dir.name.rsplit("-", 1)[-1])
        initial_html = page_dir / "iteration-00.html"
        mode = "vision" if initial_html.is_file() else "native"
        tool_id = "native_pdf_text_structure"
        manifest_tool_id: str | None = None
        manifest_path = page_dir / "page-manifest.json"
        if manifest_path.is_file():
            try:
                manifest_tool_id = json.loads(
                    manifest_path.read_text(encoding="utf-8")
                ).get("tool_id")
            except (json.JSONDecodeError, OSError):
                pass
        regions_path = page_dir / "segments" / "regions.json"
        if regions_path.is_file():
            try:
                tool_id = json.loads(regions_path.read_text(encoding="utf-8")).get(
                    "tool_id", "bill_of_lading_named_cell_ocr"
                )
            except (json.JSONDecodeError, OSError):
                tool_id = "bill_of_lading_named_cell_ocr"
        elif manifest_tool_id:
            tool_id = manifest_tool_id
        elif mode == "vision":
            family = run_dir.parent.parent.name
            tool_id = (
                "native_pdf_visual_figures"
                if family == "research"
                else "whole_page_semantic_html"
            )
        base = {
            "page": page,
            "mode": mode,
            "tool_id": tool_id,
            "source_pdf": str(source_pdf),
        }
        before = {**base, "html": str(initial_html if mode == "vision" else final_html)}
        after = {**base, "html": str(final_html)}
        comparisons[str(page)] = {"before": before, "after": after}
    return comparisons


async def previous_run(request: web.Request) -> web.Response:
    """Return only the most recent saved run for one curated document."""
    document = request.query.get("document", DEFAULT_DOCUMENT)
    if document not in DEMO_DOCUMENTS:
        raise web.HTTPBadRequest(text="Unknown demo document")
    config = DEMO_DOCUMENTS[document]
    document_id = "--".join(Path(config["filename"]).with_suffix("").parts)
    runs_dir = ROOT / "runs" / config["family"] / document_id
    excluded = request.query.get("exclude")
    candidates = sorted(
        (path for path in runs_dir.iterdir()
         if path.is_dir() and path.name != excluded and (path / "qc-report.json").is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ) if runs_dir.is_dir() else []
    for run_dir in candidates:
        comparisons = _page_comparisons_for_run(run_dir)
        if comparisons:
            return web.json_response({
                "available": True,
                "run_id": run_dir.name,
                "pages": comparisons,
            })
    return web.json_response({"available": False, "pages": {}})


async def start_run(request: web.Request) -> web.Response:
    if not claude_credentials_available():
        raise web.HTTPConflict(
            text=json.dumps({"error": "No Anthropic credentials: set ANTHROPIC_API_KEY or run "
                                      "`ant auth login` in the backend environment."}),
            content_type="application/json",
        )
    body = await request.json() if request.can_read_body else {}
    delay = float(body.get("delay_seconds", 5))
    if delay < 0 or delay > 15:
        raise web.HTTPBadRequest(text="delay_seconds must be between 0 and 15")
    document = str(body.get("document", DEFAULT_DOCUMENT))
    if document not in DEMO_DOCUMENTS:
        raise web.HTTPBadRequest(text=json.dumps({
            "error": "document must be one of the curated demo documents",
            "allowed": sorted(DEMO_DOCUMENTS),
        }), content_type="application/json")
    if (DEMO_DOCUMENTS[document].get("workflow") == "bill_of_lading_schema_graph"
            and not os.getenv("OPENAI_API_KEY")):
        raise web.HTTPConflict(
            text=json.dumps({"error": "OPENAI_API_KEY is not set; the bill-of-lading workflow "
                                      "still uses OpenAI."}),
            content_type="application/json",
        )
    run = RUNS.create()
    thread = threading.Thread(
        target=IngestionDemoAgent(run, document, delay).execute,
        name=run.run_id,
        daemon=True,
    )
    thread.start()
    return web.json_response({"run_id": run.run_id, "events": f"/api/runs/{run.run_id}/events"})


async def stream_events(request: web.Request) -> web.StreamResponse:
    run = RUNS.get(request.match_info["run_id"])
    response = web.StreamResponse(headers={
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })
    await response.prepare(request)
    offset = 0
    try:
        while True:
            events, complete = run.snapshot(offset)
            for event in events:
                await response.write(f"data: {json.dumps(event)}\n\n".encode())
                offset += 1
            if complete and not events:
                await response.write(b"event: end\ndata: {}\n\n")
                break
            await asyncio.sleep(0.2)
    except (ConnectionResetError, asyncio.CancelledError):
        pass
    return response


def _artifact_path(value: str) -> Path:
    candidate = Path(value).expanduser().resolve()
    if not any(candidate == root or root in candidate.parents for root in ALLOWED_ARTIFACT_ROOTS):
        raise web.HTTPForbidden(text="Artifact path is outside crawl_dir/raw and crawl_dir/runs")
    if not candidate.is_file():
        raise web.HTTPNotFound(text="Artifact does not exist")
    return candidate


async def artifact(request: web.Request) -> web.FileResponse:
    path = _artifact_path(request.query.get("path", ""))
    response = web.FileResponse(path)
    response.headers["Cache-Control"] = "no-store"
    if path.suffix.lower() == ".html":
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:"
        )
    return response


async def index(_: web.Request) -> web.FileResponse:
    if not (UI_DIST / "index.html").exists():
        raise web.HTTPServiceUnavailable(text="Build the UI first with: npm run build")
    return web.FileResponse(UI_DIST / "index.html")


def create_app() -> web.Application:
    app = web.Application(client_max_size=1024 * 1024)
    app.router.add_get("/api/health", health)
    app.router.add_get("/api/documents", documents)
    app.router.add_get("/api/previous-run", previous_run)
    app.router.add_post("/api/runs", start_run)
    app.router.add_get("/api/runs/{run_id}/events", stream_events)
    app.router.add_get("/api/artifact", artifact)
    if UI_DIST.exists():
        app.router.add_static("/assets", UI_DIST / "assets", show_index=False)
    app.router.add_get("/{tail:.*}", index)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="127.0.0.1", port=8510)
