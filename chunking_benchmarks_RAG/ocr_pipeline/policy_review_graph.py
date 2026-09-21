"""Review-only LangGraph for GEHA PDF table and Docling chunk QC.

The default path is local-only. Passing --vision-model explicitly sends source
page PNGs, chunk text, and rendered HTML table PNGs to the OpenAI API for QC.
Neither path updates published extracts or PostgreSQL.
"""

from __future__ import annotations

import argparse
import json
import re
import tempfile
from io import StringIO
from pathlib import Path
from typing import Any, Callable, TypedDict

import pandas as pd
from langgraph.graph import END, START, StateGraph

from .policy_visual_compare import compare_with_openai, render_html_table_png

TABLE_RE = re.compile(r"<table\b[^>]*>.*?</table>", re.IGNORECASE | re.DOTALL)
REVIEW_DIR = Path(__file__).resolve().parents[2] / "downloads" / "coverage-policies" / "extraction_review"


def _promote_header(frame: Any) -> tuple[Any, bool]:
    try:
        from ..extract_pdf_tables_html import promote_embedded_header
    except ImportError:  # pragma: no cover - direct script execution
        from chunking_benchmarks_RAG.extract_pdf_tables_html import promote_embedded_header
    return promote_embedded_header(frame)


def _render_pages(pdf_filename: str, *, first_page: int, last_page: int) -> dict[str, Any]:
    try:
        from ..policy_extraction_tools import render_policy_pdf_pages
    except ImportError:  # pragma: no cover - direct script execution
        from chunking_benchmarks_RAG.policy_extraction_tools import render_policy_pdf_pages
    return render_policy_pdf_pages(pdf_filename, first_page, last_page)


def _extract(pdf_path: Path, run_dir: Path) -> dict[str, Any]:
    try:
        from ..extract_pdf_tables_html import extract_pdf, ocr_table_converter
        from ..pdf_conversion import native_text_converter
    except ImportError:  # pragma: no cover - direct script execution
        from chunking_benchmarks_RAG.extract_pdf_tables_html import extract_pdf, ocr_table_converter
        from chunking_benchmarks_RAG.pdf_conversion import native_text_converter
    return extract_pdf(pdf_path, run_dir, native_text_converter(), ocr_table_converter())


def _extract_chunks(pdf_path: Path, run_dir: Path) -> dict[str, Any]:
    try:
        from ..policy_extraction_tools import stage_docling_chunks_for_review
    except ImportError:  # pragma: no cover - direct script execution
        from chunking_benchmarks_RAG.policy_extraction_tools import stage_docling_chunks_for_review
    return stage_docling_chunks_for_review(pdf_path, run_dir)


def _validate_pdf_name(pdf_filename: str) -> Path:
    try:
        from ..policy_extraction_tools import _policy_pdf
    except ImportError:  # pragma: no cover - direct script execution
        from chunking_benchmarks_RAG.policy_extraction_tools import _policy_pdf
    return _policy_pdf(pdf_filename)


class ReviewState(TypedDict, total=False):
    pdf_filename: str
    vision_model: str
    run_dir: str
    extraction: dict[str, Any]
    chunk_artifacts: dict[str, Any]
    chunks: list[dict[str, Any]]
    page_images: dict[int, str]
    html_images: dict[int, str]
    findings: list[dict[str, Any]]
    visual_findings: list[dict[str, Any]]
    iterations: list[dict[str, Any]]
    repair_attempts: int
    repaired_tables: list[int]
    status: str
    report_path: str


def inspect_staged_table(html_path: Path, table: dict[str, Any]) -> dict[str, Any]:
    """Check machine-detectable extraction artifacts without judging PDF fidelity."""
    source = html_path.read_text(encoding="utf-8")
    match = TABLE_RE.search(source)
    if not match:
        return {"issue": "missing_html_table", "detail": "No table element found"}
    frames = pd.read_html(StringIO(match.group(0)))
    if len(frames) != 1 or frames[0].empty:
        return {"issue": "empty_or_split_table", "detail": "No usable table rows"}
    _repaired, promotable = _promote_header(frames[0])
    if promotable:
        return {"issue": "numeric_header_row", "detail": "First row contains column labels"}
    if table.get("page") is None:
        return {"issue": "missing_page", "detail": "No source page was recorded"}
    return {"issue": None, "detail": "Structural checks passed; visual check still required"}


def repair_numeric_header(html_path: Path) -> bool:
    """Promote a recognizable first row in staged HTML, never in published HTML."""
    source = html_path.read_text(encoding="utf-8")
    match = TABLE_RE.search(source)
    if not match:
        return False
    frames = pd.read_html(StringIO(match.group(0)))
    if len(frames) != 1:
        return False
    repaired, promoted = _promote_header(frames[0])
    if not promoted:
        return False
    replacement = repaired.fillna("").to_html(
        index=False, border=0, classes=["policy-table"], justify="left", escape=True
    )
    html_path.write_text(
        source[: match.start()] + replacement + source[match.end() :], encoding="utf-8"
    )
    return True


def build_review_graph(
    *,
    extractor: Callable[[Path, Path], dict[str, Any]] | None = None,
    renderer: Callable[..., dict[str, Any]] = _render_pages,
    inspector: Callable[[Path, dict[str, Any]], dict[str, Any]] = inspect_staged_table,
    repairer: Callable[[Path], bool] = repair_numeric_header,
    chunk_extractor: Callable[[Path, Path], dict[str, Any]] = _extract_chunks,
    table_renderer: Callable[..., Path] = render_html_table_png,
    comparator: Callable[..., dict[str, Any]] = compare_with_openai,
):
    """Stage, compare, conditionally repair once, then require human review."""

    def stage(state: ReviewState) -> ReviewState:
        # Pre-staged artifacts are useful in offline tests; CLI always extracts anew.
        if state.get("extraction") and state.get("run_dir"):
            return {"repair_attempts": state.get("repair_attempts", 0)}
        pdf_path = _validate_pdf_name(state["pdf_filename"])
        base = REVIEW_DIR / pdf_path.stem
        base.mkdir(parents=True, exist_ok=True)
        run_dir = Path(tempfile.mkdtemp(prefix="qc-", dir=base))
        result = (extractor or _extract)(pdf_path, run_dir)
        update: ReviewState = {
            "run_dir": str(run_dir), "extraction": result, "repair_attempts": 0,
        }
        if state.get("vision_model"):
            chunks = chunk_extractor(pdf_path, run_dir)
            update["chunk_artifacts"] = {
                key: value for key, value in chunks.items() if key != "chunks"
            }
            update["chunks"] = chunks["chunks"]
        return update

    def render(state: ReviewState) -> ReviewState:
        images: dict[int, str] = {}
        pages = {
            item["page"] for item in state["extraction"]["outputs"]
            if isinstance(item.get("page"), int)
        }
        if state.get("vision_model"):
            pages.update(
                page for chunk in state.get("chunks", []) for page in chunk.get("pages", [])
                if isinstance(page, int)
            )
        for page in sorted(pages):
            try:
                result = renderer(state["pdf_filename"], first_page=page, last_page=page)
                images[page] = result["pages"][0]["png"]
            except Exception:
                # A missing image must force review, not silently pass QC.
                continue
        html_images: dict[int, str] = {}
        if state.get("vision_model"):
            image_dir = Path(state["run_dir"]) / "html_screenshots"
            for table in state["extraction"]["outputs"]:
                html_path = Path(state["run_dir"]) / table["html"]
                png_path = image_dir / (
                    f"iteration-{state.get('repair_attempts', 0) + 1}-"
                    f"table-{table['table_number']:04d}.png"
                )
                try:
                    table_renderer(html_path, png_path, rows=table["rows"])
                    html_images[table["table_number"]] = str(png_path)
                except Exception:
                    # The visual pass records an uncertain table, never a match.
                    continue
        return {"page_images": images, "html_images": html_images}

    def inspect(state: ReviewState) -> ReviewState:
        findings: list[dict[str, Any]] = []
        for table in state["extraction"]["outputs"]:
            html_path = Path(state["run_dir"]) / table["html"]
            identity = {
                "table_number": table["table_number"], "heading": table["heading"],
                "page": table.get("page"), "html": table["html"],
                "source_png": state.get("page_images", {}).get(table.get("page")),
            }
            try:
                finding = inspector(html_path, table)
            except Exception as exc:
                finding = {"issue": "inspection_error", "detail": f"{type(exc).__name__}: {exc}"}
            if not identity["source_png"] and finding["issue"] is None:
                finding = {"issue": "missing_page_image", "detail": "No source PNG available"}
            findings.append({**identity, **finding})
        return {"findings": findings}

    def route(state: ReviewState) -> str:
        findings = state.get("findings", [])
        if (
            findings
            and state.get("repair_attempts", 0) == 0
            and any(item["issue"] == "numeric_header_row" for item in findings)
        ):
            return "repair"
        return "review"

    def after_inspect(state: ReviewState) -> str:
        return "visual_compare" if state.get("vision_model") else route(state)

    def visual_compare(state: ReviewState) -> ReviewState:
        """One model pass over each table and each chunk; count issues by type."""
        results: list[dict[str, Any]] = []
        model = state["vision_model"]
        page_images = state.get("page_images", {})
        html_images = state.get("html_images", {})
        api_failure: str | None = None

        def check(identity: dict[str, Any], *, image_pages: list[int],
                  extracted_image: Path | None = None, text: str = "") -> None:
            nonlocal api_failure
            paths = [Path(page_images[p]) for p in image_pages if p in page_images]
            if api_failure or len(paths) != len(image_pages) or not paths or len(paths) > 3:
                results.append({**identity, "verdict": "uncertain", "issues": [],
                                "reason": api_failure or "source images unavailable or >3 pages"})
                return
            if identity["kind"] == "table" and extracted_image is None:
                results.append({**identity, "verdict": "uncertain", "issues": [],
                                "reason": "rendered HTML image unavailable"})
                return
            try:
                answer = comparator(
                    kind=identity["kind"], pdf_images=paths,
                    extracted_image=extracted_image, extracted_text=text,
                    heading=identity["heading"], identifier=identity["id"], model=model,
                )
                if answer.get("verdict") not in {"match", "mismatch", "uncertain"}:
                    raise ValueError("invalid comparator verdict")
                if answer["verdict"] == "mismatch" and not answer.get("issues"):
                    raise ValueError("mismatch without issues")
                if answer["verdict"] == "match" and answer.get("issues"):
                    raise ValueError("match verdict with issues")
                results.append({**identity, **answer})
            except Exception as exc:
                # Do not persist API error bodies, which may contain submitted text.
                if type(exc).__name__ in {"AuthenticationError", "PermissionDeniedError"}:
                    api_failure = type(exc).__name__
                results.append({**identity, "verdict": "uncertain", "issues": [],
                                "reason": type(exc).__name__})

        for table in state["extraction"]["outputs"]:
            number = table["table_number"]
            page = table.get("page")
            check({"kind": "table", "id": f"table-{number}", "heading": table["heading"],
                   "table_number": number, "page": page},
                  image_pages=[page] if isinstance(page, int) else [],
                  extracted_image=Path(html_images[number]) if number in html_images else None)
        for chunk in state.get("chunks", []):
            number = chunk["chunk_number"]
            check({"kind": "chunk", "id": f"chunk-{number}",
                   "heading": " > ".join(chunk.get("headings", [])),
                   "chunk_number": number, "pages": chunk.get("pages", [])},
                  image_pages=chunk.get("pages", []), text=chunk["text"])

        def errors(kind: str) -> int:
            return sum(
                len(item["issues"]) for item in results
                if item["kind"] == kind and item["verdict"] == "mismatch"
            )

        iteration = {
            "number": len(state.get("iterations", [])) + 1,
            "table_error_count": errors("table"),
            "chunk_heading_error_count": sum(
                issue.get("type") == "heading_mismatch"
                for item in results if item["kind"] == "chunk" and item["verdict"] == "mismatch"
                for issue in item["issues"]
            ),
            "chunk_other_error_count": sum(
                issue.get("type") != "heading_mismatch"
                for item in results if item["kind"] == "chunk" and item["verdict"] == "mismatch"
                for issue in item["issues"]
            ),
            "total_error_count": errors("table") + errors("chunk"),
            "uncertain_count": sum(item["verdict"] == "uncertain" for item in results),
            "structural_error_count": sum(bool(item["issue"]) for item in state["findings"]),
            "table_unit_count": sum(item["kind"] == "table" for item in results),
            "chunk_unit_count": sum(item["kind"] == "chunk" for item in results),
            "matched_count": sum(item["verdict"] == "match" for item in results),
            "mismatched_count": sum(item["verdict"] == "mismatch" for item in results),
            "model": model,
        }
        print(json.dumps({"visual_qc_iteration": iteration}), flush=True)
        return {"visual_findings": results,
                "iterations": [*state.get("iterations", []), iteration]}

    def after_visual_compare(state: ReviewState) -> str:
        if state.get("repair_attempts", 0) > 0:
            return "review"
        local_headers = any(item["issue"] == "numeric_header_row" for item in state["findings"])
        model_headers = any(
            item["kind"] == "table" and item["verdict"] == "mismatch" and
            any(issue.get("type") == "numeric_header_row" for issue in item["issues"])
            for item in state.get("visual_findings", [])
        )
        return "repair" if local_headers or model_headers else "review"

    def repair(state: ReviewState) -> ReviewState:
        repaired: list[int] = []
        model_header_tables = {
            item["table_number"] for item in state.get("visual_findings", [])
            if item["kind"] == "table" and item["verdict"] == "mismatch" and
            any(issue.get("type") == "numeric_header_row" for issue in item["issues"])
        }
        for item in state["findings"]:
            if item["issue"] == "numeric_header_row" or item["table_number"] in model_header_tables:
                if repairer(Path(state["run_dir"]) / item["html"]):
                    repaired.append(item["table_number"])
        return {"repair_attempts": 1, "repaired_tables": repaired}

    def after_repair(state: ReviewState) -> str:
        return "render" if state.get("vision_model") and state.get("repaired_tables") else (
            "inspect" if not state.get("vision_model") else "review"
        )

    def decide_review(state: ReviewState) -> ReviewState:
        issues = [item for item in state.get("findings", []) if item["issue"]]
        if state.get("vision_model"):
            latest = state.get("iterations", [])[-1] if state.get("iterations") else None
            passed = bool(latest) and not issues and not latest["total_error_count"] \
                and not latest["uncertain_count"] and bool(state["extraction"]["outputs"]) \
                and bool(state.get("chunks"))
            return {"status": (
                "visual_qc_passed_pending_human_review" if passed else "needs_human_review"
            )}
        return {
            "status": "needs_human_review" if issues or not state["extraction"]["outputs"]
            else "awaiting_visual_review"
        }

    def report(state: ReviewState) -> ReviewState:
        path = Path(state["run_dir"]) / "qc_report.json"
        path.write_text(json.dumps({
            "source_pdf": state["pdf_filename"],
            "status": state["status"],
            "extraction": state["extraction"],
            "chunk_artifacts": state.get("chunk_artifacts"),
            "page_images": state.get("page_images", {}),
            "html_images": state.get("html_images", {}),
            "findings": state.get("findings", []),
            "visual_findings": state.get("visual_findings", []),
            "iterations": state.get("iterations", []),
            "repair_attempts": state.get("repair_attempts", 0),
            "repaired_tables": state.get("repaired_tables", []),
            "data_transfer": (
                {"endpoint": "https://api.openai.com/v1/responses", "store": False,
                 "scope": "relevant PDF-page PNGs, chunk text, rendered HTML-table PNGs"}
                if state.get("vision_model") else None
            ),
            "note": (
                "Model-generated QC suggestions, not GEHA policy facts. "
                "No database writes. Human review remains required."
                if state.get("vision_model") else
                "Local structural QC only. Compare each PNG and HTML table manually."
            ),
        }, indent=2) + "\n", encoding="utf-8")
        return {"report_path": str(path)}

    graph = StateGraph(ReviewState)
    for name, node in (
        ("stage", stage), ("render", render), ("inspect", inspect),
        ("visual_compare", visual_compare), ("repair", repair),
        ("review", decide_review), ("report", report),
    ):
        graph.add_node(name, node)
    graph.add_edge(START, "stage")
    graph.add_edge("stage", "render")
    graph.add_edge("render", "inspect")
    graph.add_conditional_edges(
        "inspect", after_inspect,
        {"visual_compare": "visual_compare", "repair": "repair", "review": "review"},
    )
    graph.add_conditional_edges(
        "visual_compare", after_visual_compare, {"repair": "repair", "review": "review"}
    )
    graph.add_conditional_edges(
        "repair", after_repair, {"render": "render", "inspect": "inspect", "review": "review"}
    )
    graph.add_edge("review", "report")
    graph.add_edge("report", END)
    return graph.compile()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_filename", help="PDF basename in downloads/coverage-policies")
    parser.add_argument("--vision-model", help="Opt in to OpenAI image comparisons with this model")
    args = parser.parse_args()
    result = build_review_graph().invoke(
        {"pdf_filename": args.pdf_filename, "vision_model": args.vision_model or ""},
        {"recursion_limit": 20},
    )
    print(json.dumps({
        "status": result["status"], "report_path": result["report_path"],
        "tables": len(result["extraction"]["outputs"]),
        "chunks": len(result.get("chunks", [])),
        "iterations": result.get("iterations", []),
    }, indent=2))


if __name__ == "__main__":
    main()
