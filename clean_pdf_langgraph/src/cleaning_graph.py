"""Run one PDF extraction/QC iteration, then stop for human review.

All artifacts are created next to their source PDF, and existing artifacts are
never overwritten. No repair, approval, or database-ingestion node is present.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from .extractors import (
    docling_extract, naive_pdf_extract, render_pdf_pages, source_sha256, write_new,
)
from .schema import CleaningState, ReviewIssue
from .vision_review import compare_unit, images_for_pages


PDF_DIR = Path(__file__).resolve().parents[1]


def resolve_source(pdf_name: str) -> Path:
    """Restrict CLI selection to an existing top-level source PDF."""
    if Path(pdf_name).name != pdf_name or not pdf_name.lower().endswith(".pdf"):
        raise ValueError("Pass a PDF filename only, not a path")
    source = PDF_DIR / pdf_name
    if not source.is_file() or source.resolve().parent != PDF_DIR.resolve():
        raise FileNotFoundError(f"No source PDF in {PDF_DIR}: {pdf_name}")
    return source


def preflight_outputs(pdf_path: Path) -> None:
    """Fail before writing anything if any extraction artifact already exists."""
    stem = pdf_path.stem
    expected = [
        f"{stem}_pdfplumber.md", f"{stem}.docling.md",
        f"{stem}.docling_chunks.md", f"{stem}_docling_tables.md",
        f"{stem}_errors.md",
    ]
    existing = [name for name in expected if (pdf_path.parent / name).exists()]
    existing += [path.name for path in pdf_path.parent.glob(f"{stem}_images_*.png")]
    if existing:
        raise FileExistsError(f"Existing artifacts; no files changed: {', '.join(existing)}")


def extract_pdfplumber_node(state: CleaningState) -> CleaningState:
    if state["iteration"] != 1 or state["max_iterations"] != 1:
        raise ValueError("This graph permits exactly one extraction iteration")
    pdf_path = Path(state["pdf_path"])
    return {
        **naive_pdf_extract(pdf_path, Path(state["output_dir"])),
        "source_sha256": source_sha256(pdf_path),
    }


def extract_docling_node(state: CleaningState) -> CleaningState:
    return docling_extract(Path(state["pdf_path"]), Path(state["output_dir"]))


def render_pages_node(state: CleaningState) -> CleaningState:
    return {"page_images": render_pdf_pages(
        Path(state["pdf_path"]), Path(state["output_dir"]), state["page_count"]
    )}


def compare_node(state: CleaningState) -> CleaningState:
    """Compare every raw table and every Docling chunk against source pages."""
    units: list[tuple[str, str, str, list[int]]] = []
    for table in state["pdfplumber_tables"] + state["docling_tables"]:
        units.append((
            f"{table['extractor']} table {table['number']}", "table",
            table["markdown"], [table["page"]],
        ))
    for chunk in state["docling_chunks"]:
        unit_text = f"Headings: {' > '.join(chunk['headings']) or 'none'}\n{chunk['text']}"
        units.append((f"Docling chunk {chunk['number']}", "chunk", unit_text, chunk["pages"]))

    issues: list[ReviewIssue] = []
    if not units:
        issues.append({
            "artifact": "whole document", "page": 0, "kind": "other",
            "pdf_evidence": "", "extracted_evidence": "",
            "explanation": "No tables or chunks were extracted; human review required.",
        })
    matched = uncertain = 0
    vision_failure: str | None = None
    for artifact, kind, text, pages in units:
        if vision_failure:
            verdict, found = "uncertain", []
        elif not state["use_vision"]:
            verdict, found = "uncertain", [{
                "artifact": artifact, "page": pages[0] if pages else 0,
                "kind": "other", "pdf_evidence": "", "extracted_evidence": "",
                "explanation": "Vision review was disabled; human comparison required.",
            }]
        elif len(text) > 20000:
            verdict, found = "uncertain", [{
                "artifact": artifact, "page": pages[0] if pages else 0,
                "kind": "other", "pdf_evidence": "", "extracted_evidence": "",
                "explanation": "Extraction unit exceeds the 20,000-character vision limit.",
            }]
        else:
            try:
                verdict, found = compare_unit(
                    artifact=artifact, kind=kind, extracted_text=text,
                    images=images_for_pages(state["page_images"], pages),
                    model=state["vision_model"],
                )
            except Exception as error:
                # Fail closed, but do not make repeated API calls or copy an API
                # error body (which may contain a credential) into the report.
                vision_failure = type(error).__name__
                verdict, found = "uncertain", []
        matched += verdict == "match"
        uncertain += verdict == "uncertain"
        issues.extend(found)

    if vision_failure:
        issues.append({
            "artifact": "visual verification", "page": 0, "kind": "other",
            "pdf_evidence": "", "extracted_evidence": "",
            "explanation": f"Vision service unavailable ({vision_failure}); all remaining units are unverified.",
        })

    return {
        "issues": issues,
        "reviewed_units": len(units),
        "matched_units": matched,
        "uncertain_units": uncertain,
        "status": "needs_human_review" if issues else "visually_matched",
    }


def write_errors_node(state: CleaningState) -> CleaningState:
    pdf_path = Path(state["pdf_path"])
    report_path = Path(state["output_dir"]) / f"{pdf_path.stem}_errors.md"
    lines = [
        f"# First-pass extraction review: {pdf_path.name}", "",
        f"- Source SHA-256: `{state['source_sha256']}`",
        f"- Iterations: {state['iteration']} of {state['max_iterations']}",
        f"- Review status: {state['status']}",
        f"- Units compared: {state['reviewed_units']}",
        f"- Matched: {state['matched_units']}",
        f"- Uncertain: {state['uncertain_units']}",
        f"- Issues: {len(state['issues'])}", "",
        "No extracted content has been repaired or approved. Review the PDF images",
        "and the raw Markdown before deciding on a cleaning rule.", "",
    ]
    for index, issue in enumerate(state["issues"], 1):
        lines.extend([
            f"## {index}. {issue['artifact']} — {issue['kind']}", "",
            f"- Page: {issue['page'] or 'unknown'}",
            f"- Source PDF evidence: {issue['pdf_evidence'] or 'not available'}",
            f"- Extracted evidence: {issue['extracted_evidence'] or 'not available'}",
            f"- Explanation: {issue['explanation']}", "",
        ])
    write_new(report_path, "\n".join(lines))
    return {"error_report": str(report_path)}


def build_graph():
    graph = StateGraph(CleaningState)
    graph.add_node("pdfplumber_extract", extract_pdfplumber_node)
    graph.add_node("docling_extract", extract_docling_node)
    graph.add_node("render_pdf_pages", render_pages_node)
    graph.add_node("vision_compare", compare_node)
    graph.add_node("write_errors", write_errors_node)
    graph.add_edge(START, "pdfplumber_extract")
    graph.add_edge("pdfplumber_extract", "docling_extract")
    graph.add_edge("docling_extract", "render_pdf_pages")
    graph.add_edge("render_pdf_pages", "vision_compare")
    graph.add_conditional_edges(
        "vision_compare",
        lambda state: "review" if state["status"] == "needs_human_review" else "done",
        {"review": "write_errors", "done": END},
    )
    graph.add_edge("write_errors", END)
    return graph.compile()


def run_one(pdf_name: str, *, vision_model: str = "gpt-4o", use_vision: bool = True) -> CleaningState:
    pdf_path = resolve_source(pdf_name)
    preflight_outputs(pdf_path)
    initial: CleaningState = {
        "pdf_path": str(pdf_path), "output_dir": str(pdf_path.parent),
        "vision_model": vision_model, "use_vision": use_vision,
        "iteration": 1, "max_iterations": 1, "status": "pending",
    }
    return build_graph().invoke(initial)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--pdf", help="One PDF filename from the source directory")
    source.add_argument("--all", action="store_true", help="Process all top-level PDFs")
    parser.add_argument("--vision-model", default="gpt-4o")
    parser.add_argument(
        "--no-vision", action="store_true",
        help="Offline extraction smoke test; reports all units as unverified",
    )
    args = parser.parse_args()
    names = [path.name for path in sorted(PDF_DIR.glob("*.pdf"))] if args.all else [args.pdf]
    for name in names:
        result = run_one(name, vision_model=args.vision_model, use_vision=not args.no_vision)
        print(json.dumps({
            "pdf": name,
            "status": result["status"],
            "iteration": result["iteration"],
            "pages": result["page_count"],
            "pdfplumber_tables": len(result["pdfplumber_tables"]),
            "docling_tables": len(result["docling_tables"]),
            "docling_chunks": len(result["docling_chunks"]),
            "issues": len(result["issues"]),
            "error_report": result.get("error_report"),
        }, indent=2), flush=True)


if __name__ == "__main__":
    main()
