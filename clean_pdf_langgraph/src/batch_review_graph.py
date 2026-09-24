"""Batch LangGraph: PDF -> two raw Markdown extracts -> two HTML pages -> vision QC.

Each PDF gets an isolated output directory. The graph never repairs extraction
artifacts or overwrites an earlier run. Vision failures are reported as
unverified, never as successful comparisons.
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
from typing import Any, TypedDict
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


class BatchReviewState(CleaningState, total=False):
    pdfplumber_html: str
    pdfplumber_corrected_html: str
    docling_html: str
    extractor_reviews: dict[str, dict[str, Any]]
    error_reports: dict[str, str]
    vision_approved: bool
    table_slideshow_html: str
    corrected_docling_html: str


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
    interval_seconds = max(0.1, float(os.getenv("GEHA_SLIDESHOW_SECONDS", "3")))
    slideshow_path = output_dir / f"{source.stem}_table_review.html"
    html_source_path = output_dir / f"{source.stem}_docling_tables.html"
    cards: list[str] = []
    for extractor in EXTRACTORS:
        for table in state[f"{extractor}_tables"]:
            markup = raw_table_markup(table["columns"], table["rows"])
            cards.append(
                f'<section class="table-card">'
                f'<h2>{html.escape(extractor)} table {int(table["number"])} '
                f'· PDF page {int(table["page"])}</h2>'
                f'<p class="table-source">Nearest heading: '
                f'<strong>{html.escape(table.get("nearest_heading") or "none")}</strong></p>'
                f'<p class="table-source">HTML source: '
                f'<code>{html.escape(str(html_source_path.resolve()))}</code><br>'
                f'PDF source: <code>{html.escape(str(source.resolve()))}</code> · '
                f'PDF page: {int(table["page"])}</p>'
                f'<div class="table-wrap">{markup}</div></section>'
            )

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
.status {{ color:#5f6f7f; margin-bottom:18px; }} .empty {{ color:#9f1d20; }}
</style></head><body><main>
<h1>Human review: extracted tables</h1>
<p class="status" id="status">Starting table review…</p>
{cards_html}
</main><script>
const cards = [...document.querySelectorAll('.table-card')];
const status = document.getElementById('status');
let index = 0;
function show() {{
  cards.forEach((card, i) => card.classList.toggle('active', i === index));
  status.textContent = cards.length
  ? `Table ${{index + 1}} of ${{cards.length}} · {interval_seconds:g} seconds per table`
    : 'No extracted tables were found.';
}}
show();
if (cards.length > 1) {{
  const timer = setInterval(() => {{
    index += 1;
    if (index >= cards.length) {{
      clearInterval(timer);
      status.textContent = `Review complete · ${{cards.length}} tables displayed`;
      return;
    }}
    show();
  }}, {interval_seconds * 1000:g});
}}
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


def vision_node(state: BatchReviewState) -> BatchReviewState:
    reviews: dict[str, dict[str, Any]] = {}
    service_failure: str | None = None
    corrected_markup: list[tuple[TableArtifact, str]] = []
    for extractor in EXTRACTORS:
        tables: list[TableArtifact] = state[f"{extractor}_tables"]
        verdicts: list[dict[str, Any]] = []
        issues: list[ReviewIssue] = []
        initial_results: list[dict[str, Any]] = []
        if not tables:
            issues.append(_unverified_issue(
                f"{extractor} extraction", "No tables were extracted; human review required."
            ))
        for table in tables:
            artifact = f"{extractor} table {table['number']}"
            markup = raw_table_markup(table["columns"], table["rows"])
            if not state["use_vision"] or service_failure:
                verdict, found = "uncertain", []
            elif len(markup) > 20_000:
                verdict, found = "uncertain", [_unverified_issue(
                    artifact, "HTML table exceeds the 20,000-character review limit.",
                    table["page"],
                )]
            else:
                try:
                    current_markup = markup
                    found: list[ReviewIssue] = []
                    verdict = "uncertain"
                    correction_attempts = 0
                    page_images = images_for_pages(state["page_images"], [table["page"]])
                    for iteration in range(2):
                        screenshot = None
                        if state.get("output_dir"):
                            screenshot = Path(state["output_dir"]) / (
                                f"{Path(state['pdf_path']).stem}_{extractor}_table_"
                                f"{table['number']}_html_{iteration}.png"
                            )
                            try:
                                render_html_table_screenshot(current_markup, screenshot)
                            except (ImportError, ModuleNotFoundError):
                                screenshot = None
                        verdict, found = compare_html_table(
                            artifact=artifact, table_html=current_markup,
                            pdf_images=page_images, html_screenshot=screenshot,
                            model=state["vision_model"],
                        )
                        if iteration == 0:
                            initial_results.append({
                                "table": table["number"], "page": table["page"],
                                "verdict": verdict, "issue_count": len(found),
                            })
                        if verdict != "mismatch" or iteration == 1:
                            break
                        current_markup = correct_html_table(
                            artifact=artifact, table_html=current_markup,
                            pdf_images=page_images, issues=found,
                            model=state["vision_model"],
                        )
                        correction_attempts += 1
                    if initial_results and initial_results[-1]["table"] == table["number"]:
                        initial_results[-1]["correction_attempts"] = correction_attempts
                    corrected_markup.append((table, current_markup))
                except Exception as error:
                    # API bodies can contain credentials or submitted content.
                    # Persist only the exception class and stop further calls.
                    service_failure = type(error).__name__
                    verdict, found = "uncertain", []
            verdicts.append({
                "table": table["number"], "page": table["page"], "verdict": verdict,
            })
            issues.extend(found)

        if extractor == "docling" and corrected_markup and state.get("output_dir"):
            source = Path(state["pdf_path"])
            corrected_path = Path(state["output_dir"]) / (
                f"{source.stem}_docling_tables_corrected.html"
            )
            sections = "\n".join(
                f'<section><h2>Docling table {table["number"]} · PDF page {table["page"]}</h2>'
                f'<p class="table-source">Nearest heading: '
                f'<strong>{html.escape(table.get("nearest_heading") or "none")}</strong></p>'
                f'{markup}</section>'
                for table, markup in corrected_markup
            )
            write_new(corrected_path, (
                f"<!doctype html><html><head><meta charset='utf-8'><title>Corrected Docling tables</title>"
                f"<style>{RAW_TABLE_CSS} section{{margin:24px 0}}</style></head><body><main>"
                f"<h1>Corrected Docling tables - {html.escape(source.name)}</h1>{sections}"
                f"</main></body></html>"
            ))

        if not state["use_vision"]:
            issues.append(_unverified_issue(
                f"{extractor} visual review",
                "Reviewer declined the vision data transfer."
                if state.get("vision_approved") is False else "Vision review was disabled.",
            ))
        elif service_failure:
            issues.append(_unverified_issue(
                f"{extractor} visual review",
                f"Vision service unavailable ({service_failure}); comparisons are unverified.",
            ))
        counts = {
            verdict: sum(item["verdict"] == verdict for item in verdicts)
            for verdict in ("match", "mismatch", "uncertain")
        }
        reviews[extractor] = {
            "table_count": len(tables), "verdicts": verdicts,
            "initial_results": initial_results,
            "counts": counts, "issues": issues,
            "status": "passed" if tables and not issues and counts["match"] == len(tables)
            else "needs_human_review",
        }
    result: BatchReviewState = {"extractor_reviews": reviews}
    if state.get("output_dir") and Path(state["output_dir"], f"{Path(state['pdf_path']).stem}_docling_tables_corrected.html").is_file():
        result["corrected_docling_html"] = str(Path(state["output_dir"]) / f"{Path(state['pdf_path']).stem}_docling_tables_corrected.html")
    return result


def decline_node(state: BatchReviewState) -> BatchReviewState:
    """Produce unverified reports without making a model request."""
    return {"use_vision": False, **vision_node({**state, "use_vision": False})}


def corrected_slideshow_node(state: BatchReviewState) -> BatchReviewState:
    """Open the corrected Docling HTML after the comparison loop."""
    corrected = state.get("corrected_docling_html")
    interval_seconds = max(0.1, float(os.getenv("GEHA_SLIDESHOW_SECONDS", "3")))
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
    graph.add_node("vision_compare", vision_node)
    graph.add_node("corrected_slideshow", corrected_slideshow_node)
    graph.add_node("vision_declined", decline_node)
    graph.add_node("write_extractor_reports", report_node)
    graph.add_edge(START, "docling_extract")
    graph.add_edge("docling_extract", "build_combined_html")
    graph.add_edge("build_combined_html", "render_pdf_pages")
    graph.add_edge("render_pdf_pages", "cycle_html_tables")
    graph.add_edge("cycle_html_tables", "vision_compare")
    graph.add_edge("vision_compare", "corrected_slideshow")
    graph.add_edge("corrected_slideshow", "write_extractor_reports")
    graph.add_edge("vision_declined", "write_extractor_reports")
    graph.add_edge("write_extractor_reports", END)
    return graph.compile(checkpointer=checkpointer)


def run_pdf(
    pdf_path: Path, output_dir: Path, *, vision_model: str = "gpt-4o",
    use_vision: bool = True,
) -> BatchReviewState:
    if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    initial: BatchReviewState = {
        "pdf_path": str(pdf_path.resolve()), "output_dir": str(output_dir.resolve()),
        "vision_model": vision_model, "use_vision": use_vision,
        "iteration": 1, "max_iterations": 1,
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
    limit: int | None = None,
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
        limit=args.limit,
    )
    print(json.dumps({"summary": str(run_dir / "batch_summary.json"),
                      "pdf_count": summary["pdf_count"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
