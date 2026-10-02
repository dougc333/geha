"""Batch LangGraph: PDF -> raw Docling HTML -> bounded visual correction loop.

Each PDF gets an isolated output directory. The graph preserves raw extraction
artifacts and writes corrections separately without overwriting an earlier run.
Vision failures are reported as unverified, never as successful comparisons.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import time
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from .extractors import docling_extract, render_pdf_pages, source_sha256, write_new
from .html_vision_review import (
    compare_html_table, correct_html_table, render_html_table_screenshot,
)
from .raw_table_html import RAW_TABLE_CSS, combined_raw_html, raw_table_markup
from .schema import CleaningState, ReviewIssue, TableArtifact
from .vision_review import images_for_pages
from .paths import BATCH_RUNS_DIR, PDF_DIR


EXTRACTORS = ("docling",)

ReviewVerdict = Literal["match", "mismatch", "uncertain"]


class TableVerdict(TypedDict):
    table: int
    page: int
    verdict: ReviewVerdict


class InitialTableResult(TypedDict):
    table: int
    page: int
    verdict: ReviewVerdict
    issue_count: int
    correction_attempts: int


class CorrectedTable(TypedDict):
    table: TableArtifact
    markup: str


class BatchReviewState(CleaningState, total=False):
    pdfplumber_html: str
    pdfplumber_corrected_html: str
    docling_html: str
    extractor_reviews: dict[str, dict[str, Any]]
    error_reports: dict[str, str]
    vision_approved: bool
    table_slideshow_html: str
    corrected_docling_html: str
    review_table_index: int
    review_current_markup: str
    review_current_verdict: ReviewVerdict
    review_current_issues: list[ReviewIssue]
    review_html_screenshot: str
    review_correction_attempts: int
    review_service_failure: str
    review_verdicts: list[TableVerdict]
    review_initial_results: list[InitialTableResult]
    review_issues: list[ReviewIssue]
    review_corrected_tables: list[CorrectedTable]
    review_validation_failures: list[list[dict[str, Any]]]


def docling_node(state: BatchReviewState) -> BatchReviewState:
    source = Path(state["pdf_path"])
    result = docling_extract(source, Path(state["output_dir"]))
    if "page_count" not in result:
        import pymupdf
        with pymupdf.open(source) as document:
            result["page_count"] = document.page_count
    return {**result, "source_sha256": source_sha256(source)}


def html_node(state: BatchReviewState) -> BatchReviewState:
    source = Path(state["pdf_path"])
    output_dir = Path(state["output_dir"])
    paths: dict[str, str] = {}
    for extractor in EXTRACTORS:
        path = output_dir / f"{source.stem}_{extractor}_tables.html"
        tables: list[TableArtifact] = state[f"{extractor}_tables"]
        write_new(path, combined_raw_html(
            source.name, extractor, tables,
            html_path=str(path.resolve()), pdf_path=str(source.resolve()),
        ))
        paths[f"{extractor}_html"] = str(path)
    return paths


def render_pages_node(state: BatchReviewState) -> BatchReviewState:
    return {"page_images": render_pdf_pages(
        Path(state["pdf_path"]), Path(state["output_dir"]), state["page_count"]
    )}


def cycle_html_tables_node(state: BatchReviewState) -> BatchReviewState:
    """Show every extracted table for three seconds before human approval.

    The slideshow is a self-contained local HTML file so it remains available
    after this graph pauses at ``interrupt`` and the CLI process exits.
    """
    source = Path(state["pdf_path"])
    output_dir = Path(state["output_dir"])
    interval_seconds = max(0.1, float(os.getenv("GEHA_SLIDESHOW_SECONDS", "5")))
    slideshow_path = output_dir / f"{source.stem}_table_review.html"
    html_source_path = output_dir / f"{source.stem}_docling_tables.html"
    cards: list[str] = []
    validation_failures = state.get("review_validation_failures", [])
    table_position = 0
    for extractor in EXTRACTORS:
        for table in state[f"{extractor}_tables"]:
            has_content = any(
                isinstance(column, str) and column.strip()
                for column in table.get("columns", [])
            ) or any(
                isinstance(cell, str) and cell.strip()
                for row in table.get("rows", []) if isinstance(row, list)
                for cell in row
            )
            if not has_content:
                table_position += 1
                continue
            markup = raw_table_markup(table["columns"], table["rows"])
            failures = (
                validation_failures[table_position]
                if table_position < len(validation_failures) else []
            )
            has_error = any(failure.get("severity") == "error" for failure in failures)
            card_state = " validation-error" if has_error else (
                " validation-warning" if failures else ""
            )
            alerts = "".join(
                f'<li><strong>{html.escape(str(failure.get("code", "CONTENT_WARNING")))}</strong>: '
                f'{html.escape(str(failure.get("explanation", "Extracted text requires review.")))}</li>'
                for failure in failures
            )
            alert_html = (
                f'<div class="validation-alert" role="alert"><strong>Extraction warning</strong>'
                f'<ul>{alerts}</ul></div>' if alerts else ""
            )
            cards.append(
                f'<section class="table-card{card_state}">'
                f'<h2>{html.escape(extractor)} table {int(table["number"])} '
                f'· PDF page {int(table["page"])}</h2>'
                f'<p class="table-source">Nearest heading: '
                f'<strong>{html.escape(table.get("nearest_heading") or "none")}</strong></p>'
                f'<p class="table-source">HTML source: '
                f'<code>{html.escape(str(html_source_path.resolve()))}</code><br>'
                f'PDF source: <code>{html.escape(str(source.resolve()))}</code> · '
                f'PDF page: {int(table["page"])}</p>'
                f'{alert_html}'
                f'<div class="table-wrap">{markup}</div></section>'
            )
            table_position += 1

    cards_html = "\n".join(cards) or '<p class="empty">No tables were extracted.</p>'
    slideshow = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Table review · {html.escape(source.name)}</title>
<style>
{RAW_TABLE_CSS}
main {{ width:min(1440px,calc(100% - 32px)); margin:24px auto; padding:24px; background:#fff; border-radius:12px; }}
.table-source {{ margin:0 0 12px; color:#5f6f7f; font-size:0.78rem; line-height:1.35; }}
.table-source code {{ overflow-wrap:anywhere; }}
.table-card {{ display:none; }} .table-card.active {{ display:block; }}
.table-card.validation-error {{ border:4px solid #c62828; border-radius:10px; padding:16px; background:#fff7f7; }}
.table-card.validation-warning {{ border:4px solid #b26a00; border-radius:10px; padding:16px; background:#fffaf0; }}
.validation-alert {{ margin:12px 0; padding:12px 14px; border-left:5px solid #b26a00; background:#fff; color:#7a4800; }}
.validation-error .validation-alert {{ border-left-color:#c62828; color:#9f1d20; }}
.validation-alert ul {{ margin:7px 0 0; padding-left:22px; }}
.review-controls {{ display:flex; align-items:center; gap:12px; margin-bottom:18px; }}
.status {{ color:#5f6f7f; margin:0; }} .empty {{ color:#9f1d20; }}
.pause-button {{ border:1px solid #163a63; border-radius:7px; padding:7px 14px; background:#163a63; color:#fff; font:inherit; font-weight:700; cursor:pointer; }}
.pause-button:hover {{ background:#0b2946; }} .pause-button:focus-visible {{ outline:3px solid #f2a900; outline-offset:2px; }}
.pause-button:disabled {{ cursor:not-allowed; opacity:.55; }}
</style></head><body><main>
<h1>Human review: extracted tables</h1>
<div class="review-controls">
<button class="pause-button" id="pause" type="button" aria-pressed="false">Pause</button>
<p class="status" id="status" aria-live="polite">Starting table review…</p>
</div>
{cards_html}
</main><script>
const cards = [...document.querySelectorAll('.table-card')];
const status = document.getElementById('status');
const pauseButton = document.getElementById('pause');
let index = 0;
let timer = null;
let paused = false;
let complete = false;
function updateStatus() {{
  if (!cards.length) {{
    status.textContent = 'No extracted tables were found.';
  }} else if (complete) {{
    status.textContent = `Review complete · ${{cards.length}} tables displayed`;
  }} else {{
    status.textContent = `Table ${{index + 1}} of ${{cards.length}} · {interval_seconds:g} seconds per table${{paused ? ' · paused' : ''}}`;
  }}
}}
function show() {{
  cards.forEach((card, i) => card.classList.toggle('active', i === index));
  updateStatus();
}}
function schedule() {{
  clearTimeout(timer);
  if (paused || complete || cards.length <= 1) return;
  timer = setTimeout(() => {{
    if (paused || complete) return;
    index += 1;
    if (index >= cards.length) {{
      index = cards.length - 1;
      complete = true;
      pauseButton.disabled = true;
      updateStatus();
      return;
    }}
    show();
    schedule();
  }}, {interval_seconds * 1000:g});
}}
pauseButton.addEventListener('click', () => {{
  paused = !paused;
  pauseButton.textContent = paused ? 'Resume' : 'Pause';
  pauseButton.setAttribute('aria-pressed', String(paused));
  updateStatus();
  schedule();
}});
if (cards.length <= 1) pauseButton.disabled = true;
show();
schedule();
</script></body></html>"""
    write_new(slideshow_path, slideshow)
    if cards and os.getenv("GEHA_NO_BROWSER") != "1":
        webbrowser.open(slideshow_path.resolve().as_uri())
        time.sleep(interval_seconds * len(cards))
    return {"table_slideshow_html": str(slideshow_path)}


def human_review_node(state: BatchReviewState) -> BatchReviewState:
    """Pause after local artifacts exist, before sending any of them to OpenAI."""
    if not state["use_vision"]:
        return {"vision_approved": False}
    approved = interrupt({
        "question": "Send the PDF page images and extracted HTML tables for vision review?",
        "source_pdf": state["pdf_path"],
        "docling_markdown": state["docling_markdown"],
        "docling_chunks_markdown": state["docling_chunks_markdown"],
        "docling_tables_markdown": state["docling_tables_markdown"],
        "docling_html": state["docling_html"],
        "table_slideshow_html": state.get("table_slideshow_html"),
        "page_images": state["page_images"],
        "vision_model": state["vision_model"],
    })
    if type(approved) is not bool:
        raise ValueError("Human review must resume with a boolean approval")
    return {"vision_approved": approved}


def _unverified_issue(artifact: str, explanation: str, page: int = 0) -> ReviewIssue:
    return {
        "artifact": artifact, "page": page, "kind": "other",
        "pdf_evidence": "", "extracted_evidence": "", "explanation": explanation,
    }


def initialize_review_node(state: BatchReviewState) -> BatchReviewState:
    """Initialize the table-review cursor and bounded correction state."""
    issues: list[ReviewIssue] = []
    if not state["docling_tables"]:
        issues.append(_unverified_issue(
            "docling extraction", "No tables were extracted; human review required."
        ))
    return {
        "review_table_index": 0,
        "review_current_markup": "",
        "review_current_verdict": "uncertain",
        "review_current_issues": [],
        "review_html_screenshot": "",
        "review_correction_attempts": 0,
        "review_service_failure": "",
        "review_verdicts": [],
        "review_initial_results": [],
        "review_issues": issues,
        "review_corrected_tables": [],
    }


def review_work_route(state: BatchReviewState) -> Literal["prepare", "finish"]:
    return "prepare" if state["review_table_index"] < len(state["docling_tables"]) else "finish"


def prepare_table_node(state: BatchReviewState) -> BatchReviewState:
    table = state["docling_tables"][state["review_table_index"]]
    return {
        "review_current_markup": raw_table_markup(table["columns"], table["rows"]),
        "review_current_verdict": "uncertain",
        "review_current_issues": [],
        "review_html_screenshot": "",
        "review_correction_attempts": 0,
        "review_service_failure": "",
    }


def render_html_candidate_node(state: BatchReviewState) -> BatchReviewState:
    """Render the current HTML candidate; comparison can continue without Playwright."""
    table = state["docling_tables"][state["review_table_index"]]
    screenshot = Path(state["output_dir"]) / (
        f"{Path(state['pdf_path']).stem}_docling_table_{table['number']}_html_"
        f"{state['review_correction_attempts']}.png"
    )
    try:
        render_html_table_screenshot(state["review_current_markup"], screenshot)
    except (ImportError, ModuleNotFoundError):
        return {"review_html_screenshot": ""}
    except Exception as error:
        return {
            "review_html_screenshot": "",
            "review_service_failure": type(error).__name__,
        }
    return {"review_html_screenshot": str(screenshot)}


def compare_html_candidate_node(state: BatchReviewState) -> BatchReviewState:
    table = state["docling_tables"][state["review_table_index"]]
    artifact = f"docling table {table['number']}"
    markup = state["review_current_markup"]
    service_failure = state.get("review_service_failure", "")
    verdict: ReviewVerdict = "uncertain"
    found: list[ReviewIssue] = []
    if len(markup) > 20_000:
        found = [_unverified_issue(
            artifact, "HTML table exceeds the 20,000-character review limit.", table["page"]
        )]
    elif not service_failure:
        try:
            screenshot = state.get("review_html_screenshot")
            verdict, found = compare_html_table(
                artifact=artifact,
                table_html=markup,
                pdf_images=images_for_pages(state["page_images"], [table["page"]]),
                html_screenshot=Path(screenshot) if screenshot else None,
                model=state["vision_model"],
            )
        except Exception as error:
            service_failure = type(error).__name__

    initial_results = list(state["review_initial_results"])
    if state["review_correction_attempts"] == 0:
        initial_results.append({
            "table": table["number"],
            "page": table["page"],
            "verdict": verdict,
            "issue_count": len(found),
            "correction_attempts": 0,
        })
    return {
        "review_current_verdict": verdict,
        "review_current_issues": found,
        "review_service_failure": service_failure,
        "review_initial_results": initial_results,
    }


def comparison_route(state: BatchReviewState) -> Literal["correct", "finalize"]:
    if (
        state["review_current_verdict"] == "mismatch"
        and state["review_correction_attempts"] < state["max_correction_attempts"]
    ):
        return "correct"
    return "finalize"


def correct_html_candidate_node(state: BatchReviewState) -> BatchReviewState:
    table = state["docling_tables"][state["review_table_index"]]
    attempts = state["review_correction_attempts"] + 1
    try:
        markup = correct_html_table(
            artifact=f"docling table {table['number']}",
            table_html=state["review_current_markup"],
            pdf_images=images_for_pages(state["page_images"], [table["page"]]),
            issues=state["review_current_issues"],
            model=state["vision_model"],
        )
    except Exception as error:
        return {
            "review_correction_attempts": attempts,
            "review_current_verdict": "uncertain",
            "review_current_issues": [],
            "review_service_failure": type(error).__name__,
        }
    return {
        "review_current_markup": markup,
        "review_correction_attempts": attempts,
        "review_html_screenshot": "",
    }


def correction_route(state: BatchReviewState) -> Literal["render", "finalize"]:
    return "finalize" if state.get("review_service_failure") else "render"


def finalize_table_node(state: BatchReviewState) -> BatchReviewState:
    table = state["docling_tables"][state["review_table_index"]]
    initial_results = list(state["review_initial_results"])
    if initial_results and initial_results[-1]["table"] == table["number"]:
        initial_results[-1] = {
            **initial_results[-1],
            "correction_attempts": state["review_correction_attempts"],
        }
    return {
        "review_table_index": state["review_table_index"] + 1,
        "review_verdicts": [
            *state["review_verdicts"],
            {
                "table": table["number"],
                "page": table["page"],
                "verdict": state["review_current_verdict"],
            },
        ],
        "review_initial_results": initial_results,
        "review_issues": [*state["review_issues"], *state["review_current_issues"]],
        "review_corrected_tables": [
            *state["review_corrected_tables"],
            {"table": table, "markup": state["review_current_markup"]},
        ],
    }


def _write_corrected_html(state: BatchReviewState) -> str | None:
    corrected = state["review_corrected_tables"]
    if not corrected or not state.get("output_dir"):
        return None
    source = Path(state["pdf_path"])
    corrected_path = Path(state["output_dir"]) / f"{source.stem}_docling_tables_corrected.html"
    sections = "\n".join(
        f'<section><h2>Docling table {item["table"]["number"]} · '
        f'PDF page {item["table"]["page"]}</h2>'
        f'<p class="table-source">Nearest heading: <strong>'
        f'{html.escape(item["table"].get("nearest_heading") or "none")}</strong></p>'
        f'{item["markup"]}</section>'
        for item in corrected
    )
    write_new(corrected_path, (
        "<!doctype html><html><head><meta charset='utf-8'><title>Corrected Docling tables</title>"
        f"<style>{RAW_TABLE_CSS} section{{margin:24px 0}}</style></head><body><main>"
        f"<h1>Corrected Docling tables - {html.escape(source.name)}</h1>{sections}"
        "</main></body></html>"
    ))
    return str(corrected_path)


def finish_review_node(state: BatchReviewState) -> BatchReviewState:
    issues = list(state["review_issues"])
    service_failure = state.get("review_service_failure")
    if service_failure:
        issues.append(_unverified_issue(
            "docling visual review",
            f"Vision service unavailable ({service_failure}); comparisons are unverified.",
        ))
    counts = {
        verdict: sum(item["verdict"] == verdict for item in state["review_verdicts"])
        for verdict in ("match", "mismatch", "uncertain")
    }
    tables = state["docling_tables"]
    review = {
        "table_count": len(tables),
        "verdicts": state["review_verdicts"],
        "initial_results": state["review_initial_results"],
        "counts": counts,
        "issues": issues,
        "status": "passed"
        if tables and not issues and counts["match"] == len(tables)
        else "needs_human_review",
    }
    result: BatchReviewState = {"extractor_reviews": {"docling": review}}
    corrected_path = _write_corrected_html(state)
    if corrected_path:
        result["corrected_docling_html"] = corrected_path
    return result


def decline_node(state: BatchReviewState) -> BatchReviewState:
    """Produce unverified reports without making a model request."""
    tables = state["docling_tables"]
    verdicts: list[TableVerdict] = [
        {"table": table["number"], "page": table["page"], "verdict": "uncertain"}
        for table in tables
    ]
    issues = [_unverified_issue(
        "docling visual review", "Reviewer declined the vision data transfer."
    )]
    if not tables:
        issues.insert(0, _unverified_issue(
            "docling extraction", "No tables were extracted; human review required."
        ))
    return {
        "use_vision": False,
        "extractor_reviews": {"docling": {
            "table_count": len(tables),
            "verdicts": verdicts,
            "initial_results": [],
            "counts": {"match": 0, "mismatch": 0, "uncertain": len(tables)},
            "issues": issues,
            "status": "needs_human_review",
        }},
    }


def corrected_slideshow_node(state: BatchReviewState) -> BatchReviewState:
    """Open the corrected Docling HTML after the comparison loop."""
    corrected = state.get("corrected_docling_html")
    interval_seconds = max(0.1, float(os.getenv("GEHA_SLIDESHOW_SECONDS", "5")))
    if corrected and os.getenv("GEHA_NO_BROWSER") != "1":
        source = Path(corrected)
        document = source.read_text(encoding="utf-8")
        sections = re.findall(r"<section.*?</section>", document, flags=re.IGNORECASE | re.DOTALL)
        cards = "\n".join(f'<section class="card">{section}</section>' for section in sections)
        viewer = f"""<!doctype html><html><head><meta charset="utf-8"><title>Corrected Docling slideshow</title>
<style>body{{font-family:system-ui;margin:0;background:#edf2f6}}header{{padding:12px 18px;background:#06233d;color:#fff;display:flex;justify-content:space-between;gap:12px}}button{{padding:7px 12px;margin-left:6px}}main{{max-width:1400px;margin:20px auto;background:#fff;padding:24px}}.card{{display:none}}.card.active{{display:block}}#status{{margin:0 0 14px;color:#5f6f7f;font-size:.85rem}}</style></head>
<body><header><strong>Corrected Docling tables</strong><span><button id="prev">◀ Previous</button><button id="next">Next ▶</button></span></header>
<main><p id="status"></p>{cards}</main><script>
const cards=[...document.querySelectorAll('.card')], status=document.getElementById('status'); let i=0, timer;
function show(){{cards.forEach((c,n)=>c.classList.toggle('active',n===i));status.textContent=cards.length?`Table ${{i+1}} of ${{cards.length}} · {interval_seconds:g} seconds per table`:'No corrected tables';}}
function move(d){{i=Math.max(0,Math.min(cards.length-1,i+d));show();schedule();}}
function schedule(){{clearTimeout(timer);if(i<cards.length-1)timer=setTimeout(()=>move(1),{interval_seconds * 1000:g});else status.textContent=`Review complete · ${{cards.length}} tables displayed`;}}
document.getElementById('prev').onclick=()=>move(-1);document.getElementById('next').onclick=()=>move(1);show();schedule();
</script></body></html>"""
        viewer_path = source.with_name(source.stem + "_review.html")
        write_new(viewer_path, viewer)
        webbrowser.open(viewer_path.resolve().as_uri())
    return {}


def report_node(state: BatchReviewState) -> BatchReviewState:
    source = Path(state["pdf_path"])
    output_dir = Path(state["output_dir"])
    reports: dict[str, str] = {}
    for extractor in EXTRACTORS:
        review = state["extractor_reviews"][extractor]
        path = output_dir / f"{source.stem}_{extractor}_errors.md"
        lines = [
            f"# {extractor} extraction review: {source.name}", "",
            f"- Source SHA-256: `{state['source_sha256']}`",
            f"- Extracted Markdown: `{Path(state[f'{extractor}_markdown']).name}`",
            f"- Combined HTML: `{Path(state[f'{extractor}_html']).name}`",
            *([f"- Corrected HTML: `{Path(state['corrected_docling_html']).name}`"]
              if extractor == "docling" and state.get("corrected_docling_html") else []),
            f"- Review status: {review['status']}",
            f"- Tables: {review['table_count']}",
            f"- Vision matches: {review['counts']['match']}",
            f"- Vision mismatches: {review['counts']['mismatch']}",
            f"- Unverified: {review['counts']['uncertain']}",
            f"- Reported issues: {len(review['issues'])}", "",
            "Initial table results:",
            *[
                f"- Table {item['table']} (PDF page {item['page']}): "
                f"{item['verdict']} ({item['issue_count']} initial issue(s), "
                f"{item.get('correction_attempts', 0)} correction attempt(s))"
                for item in review.get("initial_results", [])
            ],
            "",
            "Raw extraction is preserved. Corrected HTML, when produced, is derived from the PDF source of truth.",
            "",
        ]
        for result in review["verdicts"]:
            lines.append(
                f"- Table {result['table']} (PDF page {result['page']}): {result['verdict']}"
            )
        lines.append("")
        for number, issue in enumerate(review["issues"], 1):
            lines.extend([
                f"## Issue {number}: {issue['artifact']} — {issue['kind']}", "",
                f"- PDF page: {issue['page'] or 'unknown'}",
                f"- PDF evidence: {issue['pdf_evidence'] or 'not available'}",
                f"- HTML evidence: {issue['extracted_evidence'] or 'not available'}",
                f"- Explanation: {issue['explanation']}", "",
            ])
        if not review["issues"]:
            lines.extend(["No differences were reported by the vision comparison.", ""])
        write_new(path, "\n".join(lines))
        reports[extractor] = str(path)
    return {"error_reports": reports}


def build_graph(checkpointer=None):
    graph = StateGraph(BatchReviewState)
    graph.add_node("docling_extract", docling_node)
    graph.add_node("build_combined_html", html_node)
    graph.add_node("render_pdf_pages", render_pages_node)
    graph.add_node("cycle_html_tables", cycle_html_tables_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("initialize_review", initialize_review_node)
    graph.add_node("prepare_table", prepare_table_node)
    graph.add_node("render_html_candidate", render_html_candidate_node)
    graph.add_node("compare_html_candidate", compare_html_candidate_node)
    graph.add_node("correct_html_candidate", correct_html_candidate_node)
    graph.add_node("finalize_table", finalize_table_node)
    graph.add_node("finish_review", finish_review_node)
    graph.add_node("corrected_slideshow", corrected_slideshow_node)
    graph.add_node("vision_declined", decline_node)
    graph.add_node("write_extractor_reports", report_node)
    graph.add_edge(START, "docling_extract")
    graph.add_edge("docling_extract", "build_combined_html")
    graph.add_edge("build_combined_html", "render_pdf_pages")
    graph.add_edge("render_pdf_pages", "cycle_html_tables")
    graph.add_edge("cycle_html_tables", "human_review")
    graph.add_conditional_edges(
        "human_review",
        lambda state: "approved" if state["vision_approved"] else "declined",
        {"approved": "initialize_review", "declined": "vision_declined"},
    )
    graph.add_conditional_edges(
        "initialize_review", review_work_route,
        {"prepare": "prepare_table", "finish": "finish_review"},
    )
    graph.add_edge("prepare_table", "render_html_candidate")
    graph.add_edge("render_html_candidate", "compare_html_candidate")
    graph.add_conditional_edges(
        "compare_html_candidate", comparison_route,
        {"correct": "correct_html_candidate", "finalize": "finalize_table"},
    )
    graph.add_conditional_edges(
        "correct_html_candidate", correction_route,
        {"render": "render_html_candidate", "finalize": "finalize_table"},
    )
    graph.add_conditional_edges(
        "finalize_table", review_work_route,
        {"prepare": "prepare_table", "finish": "finish_review"},
    )
    graph.add_edge("finish_review", "corrected_slideshow")
    graph.add_edge("corrected_slideshow", "write_extractor_reports")
    graph.add_edge("vision_declined", "write_extractor_reports")
    graph.add_edge("write_extractor_reports", END)
    return graph.compile(checkpointer=checkpointer)


def run_pdf(
    pdf_path: Path, output_dir: Path, *, vision_model: str = "gpt-4o",
    use_vision: bool = True, max_correction_attempts: int = 1,
) -> BatchReviewState:
    if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output_dir}")
    if max_correction_attempts < 0:
        raise ValueError("max_correction_attempts cannot be negative")
    output_dir.mkdir(parents=True, exist_ok=True)
    initial: BatchReviewState = {
        "pdf_path": str(pdf_path.resolve()), "output_dir": str(output_dir.resolve()),
        "vision_model": vision_model, "use_vision": use_vision,
        "iteration": 1, "max_iterations": 1,
        "max_correction_attempts": max_correction_attempts,
    }
    from langgraph.checkpoint.sqlite import SqliteSaver
    with SqliteSaver.from_conn_string(str(output_dir / "checkpoint.sqlite")) as saver:
        graph = build_graph(checkpointer=saver)
        config = {"configurable": {"thread_id": output_dir.name}}
        return graph.invoke(initial, config=config)


def resume_pdf(output_dir: Path, *, approve: bool) -> BatchReviewState:
    """Resume one saved review; completed extraction nodes are not re-run."""
    output_dir = output_dir.expanduser().resolve()
    checkpoint = output_dir / "checkpoint.sqlite"
    if not checkpoint.is_file():
        raise FileNotFoundError(f"No saved review checkpoint: {checkpoint}")
    from langgraph.checkpoint.sqlite import SqliteSaver
    with SqliteSaver.from_conn_string(str(checkpoint)) as saver:
        graph = build_graph(checkpointer=saver)
        config = {"configurable": {"thread_id": output_dir.name}}
        snapshot = graph.get_state(config)
        if not any(task.interrupts for task in snapshot.tasks):
            raise ValueError(f"No pending human review in {output_dir}")
        return graph.invoke(Command(resume=approve), config=config)


def run_batch(
    input_dir: Path, run_dir: Path, *, pdf_name: str | None = None,
    vision_model: str = "gpt-4o", use_vision: bool = True,
    limit: int | None = None, max_correction_attempts: int = 1,
) -> dict[str, Any]:
    input_dir = input_dir.expanduser().resolve()
    run_dir = run_dir.expanduser().resolve()
    if not input_dir.is_dir():
        raise NotADirectoryError(input_dir)
    if run_dir.exists() and any(run_dir.iterdir()):
        raise FileExistsError(f"Run directory is not empty: {run_dir}")
    if pdf_name is not None:
        if Path(pdf_name).name != pdf_name or not pdf_name.lower().endswith(".pdf"):
            raise ValueError("--pdf must be a filename in the input directory")
        pdfs = [input_dir / pdf_name]
    else:
        pdfs = sorted(input_dir.glob("*.pdf"))
    if limit is not None:
        if limit < 1:
            raise ValueError("--limit must be positive")
        pdfs = pdfs[:limit]
    if not pdfs or any(not pdf.is_file() for pdf in pdfs):
        raise FileNotFoundError("No matching top-level PDF files were found")
    run_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for pdf_path in pdfs:
        output_dir = run_dir / pdf_path.stem
        try:
            state = run_pdf(
                pdf_path, output_dir, vision_model=vision_model,
                use_vision=use_vision,
                max_correction_attempts=max_correction_attempts,
            )
            if "__interrupt__" in state:
                item = {
                    "pdf": pdf_path.name, "status": "awaiting_human_approval",
                    "output_dir": str(output_dir),
                    "docling_html": state["docling_html"],
                    "page_images": state["page_images"],
                }
            else:
                item = {
                "pdf": pdf_path.name,
                "status": "vision_declined" if state.get("vision_approved") is False
                else "passed" if all(
                    state["extractor_reviews"][name]["status"] == "passed"
                    for name in EXTRACTORS
                ) else "needs_human_review",
                "docling_tables": len(state["docling_tables"]),
                "output_dir": str(output_dir),
                "error_reports": state["error_reports"],
                }
        except Exception as error:
            # Continue the batch, but preserve a clear per-PDF processing error.
            output_dir.mkdir(parents=True, exist_ok=True)
            failure_path = output_dir / f"{pdf_path.stem}_processing_errors.md"
            write_new(failure_path, (
                f"# Processing failed: {pdf_path.name}\n\n"
                f"Exception type: {type(error).__name__}\n\n"
                "No visual verification was completed for this PDF.\n"
            ))
            item = {"pdf": pdf_path.name, "status": "processing_error",
                    "output_dir": str(output_dir), "error_report": str(failure_path)}
        results.append(item)
        print(json.dumps(item, ensure_ascii=False), flush=True)
    summary = {
        "input_dir": str(input_dir), "run_dir": str(run_dir),
        "vision_model": vision_model if use_vision else None,
        "pdf_count": len(pdfs), "results": results,
    }
    write_new(run_dir / "batch_summary.json", json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=PDF_DIR)
    parser.add_argument("--output-dir", type=Path,
                        help="Fresh run directory; defaults to a unique review_runs subdirectory")
    parser.add_argument("--pdf", help="Process only this top-level PDF filename")
    parser.add_argument("--limit", type=int, help="Process only the first N PDFs")
    parser.add_argument("--vision-model", default="gpt-4o")
    parser.add_argument(
        "--max-correction-attempts", type=int, default=1,
        help="Maximum HTML correction passes per table (default: 1)",
    )
    parser.add_argument("--resume", type=Path,
                        help="Resume a paused per-PDF output directory")
    decision = parser.add_mutually_exclusive_group()
    decision.add_argument("--approve", action="store_true",
                          help="Approve sending images and HTML to the vision model")
    decision.add_argument("--reject", action="store_true",
                          help="Decline the vision transfer and write unverified reports")
    args = parser.parse_args()
    if args.resume:
        if not (args.approve or args.reject):
            parser.error("--resume requires --approve or --reject")
        state = resume_pdf(args.resume, approve=args.approve)
        print(json.dumps({
            "pdf": Path(state["pdf_path"]).name,
            "status": "vision_declined" if not state["vision_approved"] else
            "passed" if all(
                state["extractor_reviews"][name]["status"] == "passed"
                for name in EXTRACTORS
            ) else "needs_human_review",
            "error_reports": state["error_reports"],
        }, indent=2), flush=True)
        return
    if args.approve or args.reject:
        parser.error("--approve and --reject require --resume")
    run_dir = args.output_dir or (
        BATCH_RUNS_DIR /
        f"run-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
    )
    summary = run_batch(
        args.input_dir, run_dir, pdf_name=args.pdf,
        vision_model=args.vision_model, use_vision=True,
        limit=args.limit, max_correction_attempts=args.max_correction_attempts,
    )
    print(json.dumps({"summary": str(run_dir / "batch_summary.json"),
                      "pdf_count": summary["pdf_count"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
