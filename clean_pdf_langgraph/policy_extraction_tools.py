"""LangChain tools for staging Docling text, HTML tables, and PDF page images.

These tools only read a PDF in the coverage-policy directory and write new
review artifacts. They do not ingest data into PostgreSQL or approve a policy.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

try:  # Package import and direct execution from this directory.
    from .extract_pdf_tables_html import (
        extract_pdf, native_text_converter, ocr_table_converter, require_embedded_text,
    )
except ImportError:  # pragma: no cover - direct-script execution
    from extract_pdf_tables_html import (
        extract_pdf, native_text_converter, ocr_table_converter, require_embedded_text,
    )


POLICY_DIR = Path(__file__).resolve().parents[1] / "downloads" / "coverage-policies"
REVIEW_DIR = Path(__file__).resolve().parent / "extraction_review"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _is_png(path: Path) -> bool:
    if not path.is_file():
        return False
    with path.open("rb") as stream:
        return stream.read(8) == PNG_SIGNATURE


def _policy_pdf(pdf_filename: str) -> Path:
    """Keep an agent-supplied filename inside the approved policy directory."""
    if not pdf_filename or Path(pdf_filename).name != pdf_filename:
        raise ValueError("pdf_filename must be a PDF filename, not a path")
    if not pdf_filename.lower().endswith(".pdf"):
        raise ValueError("pdf_filename must end in .pdf")
    pdf_path = POLICY_DIR / pdf_filename
    if not pdf_path.is_file():
        raise FileNotFoundError(f"Policy PDF not found: {pdf_filename}")
    if pdf_path.resolve().parent != POLICY_DIR.resolve():
        raise ValueError("pdf_filename must resolve inside the coverage-policy directory")
    return pdf_path


def _page_count(pdf_path: Path) -> int:
    """Read the PDF's page count using Poppler without rendering a page."""
    result = subprocess.run(
        ["pdfinfo", str(pdf_path)],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    match = re.search(r"^Pages:\s*(\d+)\s*$", result.stdout, re.MULTILINE)
    if not match:
        raise ValueError(f"Could not determine page count for {pdf_path.name}")
    return int(match.group(1))


def render_policy_pdf_pages(
    pdf_filename: str,
    first_page: int = 1,
    last_page: int | None = None,
    dpi: int = 180,
) -> dict[str, Any]:
    """Render selected source-PDF pages to separate, review-only PNG files."""
    pdf_path = _policy_pdf(pdf_filename)
    if not 100 <= dpi <= 300:
        raise ValueError("dpi must be between 100 and 300")
    page_count = _page_count(pdf_path)
    end = page_count if last_page is None else last_page
    if first_page < 1 or end < first_page or end > page_count:
        raise ValueError(f"page range must be within 1..{page_count}")
    if end - first_page + 1 > 50:
        raise ValueError("Render at most 50 pages per call; specify a smaller range")

    source_sha256 = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    output_dir = REVIEW_DIR / pdf_path.stem / f"pdf_pages_{source_sha256[:12]}_{dpi}dpi"
    output_dir.mkdir(parents=True, exist_ok=True)
    pages: list[dict[str, Any]] = []
    for number in range(first_page, end + 1):
        output_path = output_dir / f"page-{number:04d}.png"
        if output_path.exists():
            if not _is_png(output_path):
                raise ValueError(f"Existing page image is not a valid PNG: {output_path}")
            status = "already_staged"
        else:
            with tempfile.TemporaryDirectory(prefix="render-", dir=output_dir) as temporary:
                prefix = Path(temporary) / "page"
                subprocess.run(
                    [
                        "pdftoppm", "-f", str(number), "-l", str(number),
                        "-singlefile", "-r", str(dpi), "-png",
                        str(pdf_path), str(prefix),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                rendered = prefix.with_suffix(".png")
                if not _is_png(rendered):
                    raise ValueError(f"Poppler did not produce a valid PNG for page {number}")
                rendered.replace(output_path)
            status = "staged"
        pages.append({"page": number, "png": str(output_path), "status": status})

    return {
        "source_pdf": pdf_path.name,
        "source_sha256": source_sha256,
        "page_count": page_count,
        "dpi": dpi,
        "output_dir": str(output_dir),
        "pages": pages,
        "note": "Source-page images for review; no comparison or approval has been performed.",
    }


def extract_docling_policy(pdf_filename: str) -> dict[str, Any]:
    """Stage Docling Markdown plus contextualized chunks for human review."""
    pdf_path = _policy_pdf(pdf_filename)
    output_dir = REVIEW_DIR / pdf_path.stem
    markdown_path = output_dir / f"{pdf_path.stem}.docling.md"
    chunks_path = output_dir / f"{pdf_path.stem}.docling_chunks.md"
    if markdown_path.exists() and chunks_path.exists():
        return {
            "source_pdf": pdf_path.name,
            "status": "already_staged",
            "markdown_path": str(markdown_path),
            "chunks_path": str(chunks_path),
        }
    if markdown_path.exists() or chunks_path.exists():
        raise FileExistsError(
            f"Incomplete review artifacts for {pdf_path.name}; inspect {output_dir}"
        )

    # Keep the tokenizer aligned with the existing Docling conversion script.
    from docling.chunking import HybridChunker
    from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer

    document = native_text_converter().convert(pdf_path).document
    require_embedded_text(document, pdf_path.name)
    tokenizer = HuggingFaceTokenizer.from_pretrained(
        model_name="BAAI/bge-small-en-v1.5", max_tokens=700
    )
    chunker = HybridChunker(tokenizer=tokenizer, merge_peers=True)
    chunks = [chunker.contextualize(chunk) for chunk in chunker.chunk(document)]
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(document.export_to_markdown(), encoding="utf-8")
    chunks_path.write_text(
        "".join(f"## Chunk {number}\n\n{content}\n\n\n\n" for number, content in enumerate(chunks, 1)),
        encoding="utf-8",
    )
    return {
        "source_pdf": pdf_path.name,
        "status": "staged",
        "markdown_path": str(markdown_path),
        "chunks_path": str(chunks_path),
        "chunk_count": len(chunks),
        "table_count": len(document.tables),
    }


def stage_docling_chunks_for_review(pdf_path: Path, output_dir: Path) -> dict[str, Any]:
    """Stage chunk text plus Docling heading/page provenance for visual QC.

    Unlike the reusable LangChain tool, this writes into a unique graph run
    directory, so every review has an immutable input manifest.
    """
    from docling.chunking import HybridChunker
    from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer

    document = native_text_converter().convert(pdf_path).document
    require_embedded_text(document, pdf_path.name)
    tokenizer = HuggingFaceTokenizer.from_pretrained(
        model_name="BAAI/bge-small-en-v1.5", max_tokens=700
    )
    chunker = HybridChunker(tokenizer=tokenizer, merge_peers=True)
    chunks: list[dict[str, Any]] = []
    for number, chunk in enumerate(chunker.chunk(document), 1):
        pages = sorted({
            prov.page_no
            for item in (getattr(chunk.meta, "doc_items", None) or [])
            for prov in (getattr(item, "prov", None) or [])
        })
        chunks.append({
            "chunk_number": number,
            "headings": list(getattr(chunk.meta, "headings", None) or []),
            "pages": pages,
            "text": chunker.contextualize(chunk),
        })
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / f"{pdf_path.stem}.docling.md"
    chunks_path = output_dir / f"{pdf_path.stem}.docling_chunks.md"
    manifest_path = output_dir / "chunk_manifest.json"
    markdown_path.write_text(document.export_to_markdown(), encoding="utf-8")
    chunks_path.write_text(
        "".join(
            f"## Chunk {chunk['chunk_number']}\n\n{chunk['text']}\n\n\n\n"
            for chunk in chunks
        ),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps({"source_pdf": pdf_path.name, "chunks": chunks}, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "source_pdf": pdf_path.name,
        "markdown_path": str(markdown_path),
        "chunks_path": str(chunks_path),
        "manifest_path": str(manifest_path),
        "chunk_count": len(chunks),
        "chunks": chunks,
    }


def extract_html_policy_tables(pdf_filename: str) -> dict[str, Any]:
    """Stage standalone HTML for each non-revision table in a policy PDF."""
    pdf_path = _policy_pdf(pdf_filename)
    output_dir = REVIEW_DIR / pdf_path.stem / "html_tables"
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(
            f"Review HTML already exists for {pdf_path.name}; inspect {output_dir}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    result = extract_pdf(
        pdf_path,
        output_dir,
        native_text_converter(),
        ocr_table_converter(),
    )
    return {**result, "output_dir": str(output_dir)}


@tool("docling_extract")
def docling_extract(pdf_filename: str) -> dict[str, Any]:
    """Extract one GEHA PDF to review-only Docling Markdown and numbered chunks."""
    return extract_docling_policy(pdf_filename)


@tool("html_table_extract")
def html_table_extract(pdf_filename: str) -> dict[str, Any]:
    """Extract one GEHA PDF's non-revision tables to review-only HTML pages."""
    return extract_html_policy_tables(pdf_filename)


@tool("pdf_page_screenshots")
def pdf_page_screenshots(
    pdf_filename: str,
    first_page: int = 1,
    last_page: int | None = None,
    dpi: int = 180,
) -> dict[str, Any]:
    """Render one GEHA PDF page by page to numbered PNGs for visual extraction review."""
    return render_policy_pdf_pages(pdf_filename, first_page, last_page, dpi)
