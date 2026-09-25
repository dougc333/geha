#!/usr/bin/env python3
"""Run the clean_pdf_langgraph table-review flow over split, one-page PDFs.

Each ``<policy>-page-NNN.pdf`` is converted by Docling independently.  Results
are then regrouped by the original policy name so the output layout matches a
normal ``clean_pdf_langgraph/review_runs/run-*/<policy>/`` batch run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict
from uuid import uuid4


SCRIPT_DIR = Path(__file__).resolve().parent
AA_DIR = SCRIPT_DIR.parent
GEHA_ROOT = Path(os.getenv("GEHA_ROOT", str(SCRIPT_DIR.parents[3]))).resolve()
CLEAN_GRAPH_ROOT = GEHA_ROOT / "clean_pdf_langgraph"
if not (CLEAN_GRAPH_ROOT / "src" / "batch_review_graph.py").is_file():
    raise RuntimeError(f"clean_pdf_langgraph was not found at {CLEAN_GRAPH_ROOT}")
sys.path.insert(0, str(CLEAN_GRAPH_ROOT))

from langgraph.graph import END, START, StateGraph  # noqa: E402

from src.batch_review_graph import (  # noqa: E402
    BatchReviewState,
    corrected_slideshow_node,
    cycle_html_tables_node,
    html_node,
    report_node,
    run_pdf as run_existing_page_pdf,
    vision_node,
)
from src.extractors import (  # noqa: E402
    _docling_tokenizer,
    correct_table_headers,
    nearest_markdown_table_headings,
    write_new,
)
from src.schema import ChunkArtifact, TableArtifact  # noqa: E402


PAGE_PATTERN = re.compile(r"^(?P<stem>.+)-page-(?P<page>\d+)\.pdf$", re.IGNORECASE)


class SinglePageReviewState(BatchReviewState, total=False):
    page_pdf_paths: list[str]


def discover_page_groups(input_dir: Path) -> dict[str, list[tuple[int, Path]]]:
    """Group and validate split PDFs by their original policy stem."""
    groups: dict[str, list[tuple[int, Path]]] = {}
    for path in sorted(input_dir.glob("*.pdf")):
        match = PAGE_PATTERN.match(path.name)
        if not match:
            continue
        stem = match.group("stem")
        page = int(match.group("page"))
        groups.setdefault(stem, []).append((page, path.resolve()))

    for stem, pages in groups.items():
        pages.sort()
        numbers = [number for number, _ in pages]
        expected = list(range(1, len(numbers) + 1))
        if numbers != expected:
            raise ValueError(
                f"{stem} has non-contiguous page PDFs: expected {expected}, got {numbers}"
            )
    return dict(sorted(groups.items()))


def combined_source_sha256(page_paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in page_paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def docling_single_pages_node(state: SinglePageReviewState) -> SinglePageReviewState:
    """Run Docling on each page PDF and aggregate policy-level artifacts."""
    from docling.chunking import HybridChunker
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    source = Path(state["pdf_path"])
    output_dir = Path(state["output_dir"])
    page_paths = [Path(value) for value in state["page_pdf_paths"]]

    options = PdfPipelineOptions()
    options.do_ocr = False
    options.do_table_structure = True
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )
    chunker = HybridChunker(tokenizer=_docling_tokenizer(), merge_peers=True)

    markdown_sections: list[str] = []
    tables: list[TableArtifact] = []
    chunks: list[ChunkArtifact] = []

    for original_page, page_path in enumerate(page_paths, 1):
        document = converter.convert(page_path).document
        exported_markdown = document.export_to_markdown()
        markdown_sections.append(
            f"<!-- Source page {original_page}: {page_path.name} -->\n\n"
            f"{exported_markdown}"
        )
        headings = nearest_markdown_table_headings(exported_markdown)

        for local_table_index, table in enumerate(document.tables):
            frame = table.export_to_dataframe(doc=document)
            table_number = len(tables) + 1
            tables.append({
                "extractor": "docling",
                "number": table_number,
                "page": original_page,
                "markdown": frame.to_markdown(index=False),
                "columns": [str(column) for column in frame.columns],
                "rows": frame.fillna("").astype(str).values.tolist(),
                "nearest_heading": (
                    headings[local_table_index]
                    if len(headings) > local_table_index
                    else ""
                ),
            })

        for chunk in chunker.chunk(document):
            chunks.append({
                "number": len(chunks) + 1,
                "pages": [original_page],
                "headings": list(getattr(chunk.meta, "headings", None) or []),
                "text": chunker.contextualize(chunk),
            })

    tables = correct_table_headers(tables)
    markdown_path = output_dir / f"{source.stem}.docling.md"
    chunks_path = output_dir / f"{source.stem}.docling_chunks.md"
    tables_path = output_dir / f"{source.stem}_docling_tables.md"
    write_new(markdown_path, "\n\n".join(markdown_sections) + "\n")
    write_new(
        chunks_path,
        "\n\n".join(
            f"## Chunk {chunk['number']}\n\n"
            f"Pages: {', '.join(map(str, chunk['pages']))}\n\n"
            f"Headings: {' > '.join(chunk['headings']) or 'none'}\n\n{chunk['text']}"
            for chunk in chunks
        ) + "\n",
    )
    write_new(
        tables_path,
        "\n\n".join(
            f"## Docling table {table['number']} (page {table['page']})\n\n"
            f"Nearest heading: {table.get('nearest_heading') or 'none'}\n\n"
            f"{table['markdown']}"
            for table in tables
        ) + "\n",
    )
    return {
        "source_sha256": combined_source_sha256(page_paths),
        "page_count": len(page_paths),
        "docling_markdown": str(markdown_path),
        "docling_chunks_markdown": str(chunks_path),
        "docling_tables_markdown": str(tables_path),
        "docling_chunks": chunks,
        "docling_tables": tables,
    }


def render_single_pages_node(state: SinglePageReviewState) -> SinglePageReviewState:
    """Copy the existing page PNG or render each one-page PDF into run artifacts."""
    import pypdfium2 as pdfium

    source = Path(state["pdf_path"])
    output_dir = Path(state["output_dir"])
    outputs: list[str] = []
    for original_page, value in enumerate(state["page_pdf_paths"], 1):
        page_pdf = Path(value)
        target = output_dir / f"{source.stem}_images_{original_page}.png"
        sibling_png = page_pdf.with_suffix(".png")
        if sibling_png.is_file():
            shutil.copyfile(sibling_png, target)
        else:
            pdf = pdfium.PdfDocument(str(page_pdf))
            try:
                if len(pdf) != 1:
                    raise ValueError(f"Expected a one-page PDF: {page_pdf}")
                page = pdf[0]
                try:
                    bitmap = page.render(scale=160 / 72)
                    try:
                        image = bitmap.to_pil()
                        try:
                            image.save(target, format="PNG")
                        finally:
                            image.close()
                    finally:
                        bitmap.close()
                finally:
                    page.close()
            finally:
                pdf.close()
        if target.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
            raise RuntimeError(f"Invalid rendered PNG: {target}")
        outputs.append(str(target))
    return {"page_images": outputs}


def build_graph(checkpointer=None):
    graph = StateGraph(SinglePageReviewState)
    graph.add_node("docling_extract_single_pages", docling_single_pages_node)
    graph.add_node("build_combined_html", html_node)
    graph.add_node("render_pdf_pages", render_single_pages_node)
    graph.add_node("cycle_html_tables", cycle_html_tables_node)
    graph.add_node("vision_compare", vision_node)
    graph.add_node("corrected_slideshow", corrected_slideshow_node)
    graph.add_node("write_extractor_reports", report_node)
    graph.add_edge(START, "docling_extract_single_pages")
    graph.add_edge("docling_extract_single_pages", "build_combined_html")
    graph.add_edge("build_combined_html", "render_pdf_pages")
    graph.add_edge("render_pdf_pages", "cycle_html_tables")
    graph.add_edge("cycle_html_tables", "vision_compare")
    graph.add_edge("vision_compare", "corrected_slideshow")
    graph.add_edge("corrected_slideshow", "write_extractor_reports")
    graph.add_edge("write_extractor_reports", END)
    return graph.compile(checkpointer=checkpointer)


def run_policy(
    *, stem: str, pages: list[tuple[int, Path]], source_pdf: Path,
    output_dir: Path, vision_model: str, approve: bool,
) -> SinglePageReviewState:
    from langgraph.checkpoint.sqlite import SqliteSaver

    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    initial: SinglePageReviewState = {
        "pdf_path": str(source_pdf.resolve()),
        "page_pdf_paths": [str(path) for _, path in pages],
        "output_dir": str(output_dir.resolve()),
        "vision_model": vision_model,
        "use_vision": approve,
        "vision_approved": approve,
        "iteration": 1,
        "max_iterations": 1,
    }
    with SqliteSaver.from_conn_string(str(output_dir / "checkpoint.sqlite")) as saver:
        graph = build_graph(checkpointer=saver)
        return graph.invoke(
            initial,
            config={"configurable": {"thread_id": stem}},
        )


def run_batch(
    *, input_dir: Path, source_dir: Path, run_dir: Path,
    vision_model: str, approve: bool,
) -> dict[str, Any]:
    groups = discover_page_groups(input_dir)
    if not groups:
        raise FileNotFoundError(f"No <policy>-page-NNN.pdf files in {input_dir}")
    run_dir.mkdir(parents=True, exist_ok=False)
    results: list[dict[str, Any]] = []
    page_inputs = [
        (source_stem, original_page, page_pdf)
        for source_stem, pages in groups.items()
        for original_page, page_pdf in pages
    ]
    for source_stem, original_page, page_pdf in page_inputs:
        source_pdf = source_dir / f"{source_stem}.pdf"
        output_dir = run_dir / page_pdf.stem
        try:
            state = run_existing_page_pdf(
                page_pdf, output_dir,
                vision_model=vision_model, use_vision=approve,
            )
            review = state["extractor_reviews"]["docling"]
            status = (
                "vision_declined" if not approve else
                "passed" if review["status"] == "passed" else
                "needs_human_review"
            )
            item = {
                "pdf": page_pdf.name,
                "source_pdf": source_pdf.name,
                "original_page": original_page,
                "status": status,
                "docling_tables": len(state["docling_tables"]),
                "output_dir": str(output_dir),
                "error_reports": state["error_reports"],
            }
        except Exception as error:
            output_dir.mkdir(parents=True, exist_ok=True)
            failure_path = output_dir / f"{page_pdf.stem}_processing_errors.md"
            if not failure_path.exists():
                write_new(
                    failure_path,
                    f"# Processing failed: {page_pdf.name}\n\n"
                    f"Exception type: {type(error).__name__}\n\n"
                    "No visual verification was completed for this PDF.\n",
                )
            item = {
                "pdf": page_pdf.name,
                "source_pdf": source_pdf.name,
                "original_page": original_page,
                "status": "processing_error",
                "output_dir": str(output_dir),
                "error_report": str(failure_path),
            }
        results.append(item)
        print(json.dumps(item, ensure_ascii=False), flush=True)

    summary = {
        "input_dir": str(input_dir.resolve()),
        "source_dir": str(source_dir.resolve()),
        "run_dir": str(run_dir.resolve()),
        "vision_model": vision_model if approve else None,
        "pdf_count": len(page_inputs),
        "source_document_count": len(groups),
        "single_page_pdf_count": len(page_inputs),
        "results": results,
    }
    write_new(run_dir / "batch_summary.json", json.dumps(summary, indent=2) + "\n")
    return summary


def default_run_dir() -> Path:
    return SCRIPT_DIR / "review_runs" / (
        f"run-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=AA_DIR / "singlepage")
    parser.add_argument("--source-dir", type=Path, default=AA_DIR)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--vision-model", default="gpt-4o")
    parser.add_argument(
        "--approve", action="store_true",
        help="Approve sending page images and extracted table HTML to OpenAI",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List discovered policies/pages without creating artifacts",
    )
    args = parser.parse_args()
    groups = discover_page_groups(args.input_dir.expanduser().resolve())
    if args.list:
        print(json.dumps({stem: len(pages) for stem, pages in groups.items()}, indent=2))
        return
    if args.approve and not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required with --approve")
    os.environ.setdefault("GEHA_NO_BROWSER", "1")
    run_dir = args.output_dir.expanduser().resolve() if args.output_dir else default_run_dir()
    summary = run_batch(
        input_dir=args.input_dir.expanduser().resolve(),
        source_dir=args.source_dir.expanduser().resolve(),
        run_dir=run_dir,
        vision_model=args.vision_model,
        approve=args.approve,
    )
    print(json.dumps({
        "summary": str(run_dir / "batch_summary.json"),
        "pdf_count": summary["pdf_count"],
        "single_page_pdf_count": summary["single_page_pdf_count"],
    }, indent=2), flush=True)


if __name__ == "__main__":
    main()
