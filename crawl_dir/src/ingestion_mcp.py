"""Local MCP server for public scanned-PDF ingestion."""

from __future__ import annotations

import asyncio
import functools
import json
import uuid
from dataclasses import asdict
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .download_geha_docs import download_one, load_documents, normalized_relative_path
from .pipeline.artifact_io import resolve_raw_document
from .pipeline.scanned_ingestion import (
    detect_visual_figure_pages,
    image_only_pages,
    pdf_page_count,
    process_scanned_document,
)
from .pipeline.claude_client import CLAUDE_MODEL
from .pipeline.figure_specs import process_document_with_figure_specs, spec_pages
from .pipeline.page_segmentation import segment_page_with_claude
from .pipeline.artifact_io import run_id

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "src" / "documents.json"
server = FastMCP(
    name="geha-corpus-ingestion",
    instructions=("DEMO ONLY; not production or HIPAA-ready. List or download curated public "
                  "GEHA PDFs, then ingest PDFs under crawl_dir/raw. Preview first; confirm=true "
                  "is required before writing files or calling Claude."),
)



async def _off_loop(function, /, **kwargs):
    """Run a blocking pipeline call in a worker thread.

    MCP tools execute inside an asyncio loop, and the pipeline renders HTML with
    Playwright's sync API, which refuses to run while a loop is active.
    """
    return await asyncio.to_thread(functools.partial(function, **kwargs))

def _manifest_entry(selector: str) -> dict:
    """Resolve an exact canonical path or a unique PDF filename from the manifest."""
    selector = selector.strip()
    if not selector:
        raise ValueError("document must be a manifest relative path or unique PDF filename")
    matches = [item for item in load_documents(MANIFEST)
               if selector in {normalized_relative_path(item),
                               Path(normalized_relative_path(item)).name}]
    if not matches:
        raise ValueError(f"No curated public PDF matches {selector!r}; call list_public_pdfs first")
    if len(matches) > 1:
        raise ValueError(f"PDF filename is ambiguous; use one of: " + ", ".join(
            normalized_relative_path(item) for item in matches))
    return matches[0]


@server.tool(
    name="list_public_pdfs",
    description=("List curated public GEHA PDFs available to the demo downloader. Optionally "
                 "filter by words in the title, filename, description, or tags and by family: "
                 "coverage-policies, medical, or dental."),
    annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False,
                                idempotent_hint=True, open_world_hint=False),
)
def list_public_pdfs(query: str = "", family: str = "") -> dict:
    allowed = {"coverage-policies", "medical", "dental"}
    if family and family not in allowed:
        raise ValueError(f"family must be blank or one of {sorted(allowed)}")
    terms = query.casefold().split()
    results = []
    for item in load_documents(MANIFEST):
        relative = normalized_relative_path(item)
        if family and relative.split("/", 1)[0] != family:
            continue
        searchable = " ".join(str(item.get(key, "")) for key in
                              ("title", "description", "relative_path", "tags")).casefold()
        if terms and not all(term in searchable for term in terms):
            continue
        results.append({"title": item["title"], "document": relative,
                        "last_updated": item.get("last_updated"), "bytes": item.get("bytes")})
    return {"count": len(results), "query": query, "family": family or None,
            "documents": results}


@server.tool(
    name="download_public_pdf",
    description=("Demo-only: preview or download one curated public GEHA PDF selected by its "
                 "manifest relative path or unique filename. The confirmed call writes under "
                 "crawl_dir/raw and validates HTTPS host, PDF signature, and manifest SHA-256."),
    annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False,
                                idempotent_hint=True, open_world_hint=True),
)
def download_public_pdf(document: str, confirm: bool = False) -> dict:
    entry = _manifest_entry(document)
    relative = normalized_relative_path(entry)
    destination = ROOT / "raw" / relative
    plan = {
        "demo_only": True,
        "title": entry["title"],
        "document": relative,
        "url": entry["url"],
        "destination": str(destination),
        "expected_sha256": entry["sha256"],
        "expected_bytes": entry["bytes"],
    }
    if not confirm:
        return {"status": "approval_required", **plan,
                "next_step": "Review the GEHA URL and destination, then call again with confirm=true."}
    result = download_one(entry, ROOT / "raw", timeout=60, retries=3, strict_hash=True)
    return {**asdict(result), "demo_only": True, "destination": str(destination)}


@server.tool(
    name="ingest_scanned_pdf",
    description=("Demo-only: inspect or ingest one public multipage PDF under crawl_dir/raw. Image-only "
                 "pages are split, reconstructed as HTML, corrected by Claude vision in a "
                 "bounded loop, converted to Markdown, and saved as an unpromoted candidate."),
    annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False,
                                idempotent_hint=False, open_world_hint=True),
)
async def ingest_scanned_pdf(
    family: str,
    document: str,
    document_version: str,
    data_classification: str,
    plan_year: int | None = None,
    model: str = CLAUDE_MODEL,
    max_corrections: int = 6,
    confirm: bool = False,
) -> dict:
    if data_classification != "public":
        raise ValueError("This tool accepts only data_classification='public'")
    source = resolve_raw_document(ROOT, family, document)
    scanned = image_only_pages(source)
    plan = {"demo_only": True, "family": family, "document": document, "source": str(source),
            "data_classification": "public", "page_count": pdf_page_count(source),
            "image_only_pages": scanned, "model": model,
            "max_corrections": max_corrections}
    if not scanned:
        return {"status": "not_needed", **plan}
    if not confirm:
        return {"status": "approval_required", **plan,
                "external_processing": "Claude receives source-page PNGs and candidate HTML.",
                "next_step": "Review this plan, then call again with confirm=true."}
    output = await _off_loop(
        process_scanned_document,
        root=ROOT, family=family, document=document,
        document_version=document_version, plan_year=plan_year,
        model=model, max_corrections=max_corrections,
    )
    qc = json.loads((output / "qc-report.json").read_text())
    return {"status": "candidate_created", **plan, "run": str(output), "qc": qc}


@server.tool(
    name="ingest_native_pdf_with_semantic_html_charts",
    description=("Demo-only: ingest one public native-text PDF under crawl_dir/raw with "
                 "local structured extraction on ordinary pages and bounded Claude semantic "
                 "HTML generation plus strict chart correction on numbered-figure pages. Produces "
                 "page-aware Markdown, semantic HTML, tables, RAG chunks, and a QC report."),
    annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False,
                                idempotent_hint=False, open_world_hint=True),
)
async def ingest_native_pdf_with_visual_figures(
    family: str,
    document: str,
    document_version: str,
    data_classification: str,
    plan_year: int | None = None,
    model: str = CLAUDE_MODEL,
    max_corrections: int = 6,
    confirm: bool = False,
) -> dict:
    """Route native text locally and numbered figure pages through visual verification."""
    if data_classification != "public":
        raise ValueError("This demo tool accepts only data_classification='public'")
    source = resolve_raw_document(ROOT, family, document)
    scanned = image_only_pages(source)
    if scanned:
        raise ValueError(
            f"Pages {scanned} are image-only; use ingest_scanned_pdf for this document"
        )
    figure_pages = detect_visual_figure_pages(source)
    plan = {
        "demo_only": True,
        "family": family,
        "document": document,
        "source": str(source),
        "data_classification": "public",
        "page_count": pdf_page_count(source),
        "native_text_pages": list(range(1, pdf_page_count(source) + 1)),
        "visual_figure_pages": figure_pages,
        "model": model,
        "max_corrections": max_corrections,
        "routing": "Docling native structure + whole-page visual figure verification",
    }
    if not confirm:
        return {
            "status": "approval_required",
            **plan,
            "external_processing": (
                "Only rendered pages containing embedded 'Figure N' labels are sent to Claude."
            ),
            "next_step": "Review the detected figure pages, then call again with confirm=true.",
        }
    output = await _off_loop(
        process_scanned_document,
        root=ROOT,
        family=family,
        document=document,
        document_version=document_version,
        plan_year=plan_year,
        model=model,
        max_corrections=max_corrections,
        additional_visual_pages=figure_pages,
    )
    qc = json.loads((output / "qc-report.json").read_text(encoding="utf-8"))
    return {"status": "candidate_created", **plan, "run": str(output), "qc": qc}


def _figure_spec_dir(family: str, document: str) -> Path:
    return ROOT / "annotations" / family / Path(document).stem / "figure-specs"


@server.tool(
    name="ingest_pdf_with_figure_specs",
    description=("Demo-only: ingest one public PDF under crawl_dir/raw using authored figure "
                 "specs (annotations/<family>/<document>/figure-specs/page-NNN.json) for its "
                 "charts. Every printed value and label in each spec is checked against the "
                 "native PDF text inside the figure box, and semantic HTML is rendered without "
                 "a model; pages without specs use local native-text extraction. No model or "
                 "network call. Fails if the document has no specs."),
    annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False,
                                idempotent_hint=False, open_world_hint=False),
)
async def ingest_pdf_with_figure_specs(
    family: str,
    document: str,
    document_version: str,
    data_classification: str,
    plan_year: int | None = None,
    confirm: bool = False,
) -> dict:
    """Run the no-model figure-spec pipeline and report per-figure verification."""
    if data_classification != "public":
        raise ValueError("This demo tool accepts only data_classification='public'")
    source = resolve_raw_document(ROOT, family, document)
    specs_dir = _figure_spec_dir(family, document)
    pages = spec_pages(specs_dir) if specs_dir.is_dir() else []
    if not pages:
        raise ValueError(
            f"No figure specs found at {specs_dir}. Write page-NNN.json specs for this "
            "document's charts, or use ingest_native_pdf_with_semantic_html_charts."
        )
    figure_pages = detect_visual_figure_pages(source)
    plan = {
        "demo_only": True,
        "family": family,
        "document": document,
        "source": str(source),
        "data_classification": "public",
        "page_count": pdf_page_count(source),
        "specs_dir": str(specs_dir),
        "spec_pages": pages,
        # Pages that print "Figure N" but have no spec fall back to native text only.
        "figure_pages_without_specs": sorted(set(figure_pages) - set(pages)),
        "model": None,
        "routing": "Authored figure specs verified against native PDF text + Docling native pages",
    }
    if not confirm:
        return {
            "status": "approval_required",
            **plan,
            "external_processing": "None; everything runs locally.",
            "next_step": "Review the spec pages, then call again with confirm=true.",
        }
    output = await _off_loop(
        process_document_with_figure_specs,
        root=ROOT, family=family, document=document,
        document_version=document_version, specs_dir=specs_dir, plan_year=plan_year,
    )
    qc = json.loads((output / "qc-report.json").read_text(encoding="utf-8"))
    figures = []
    for batch_path in sorted((output / "pages").glob("page-*/segments/batch.json")):
        batch = json.loads(batch_path.read_text(encoding="utf-8"))
        page = int(batch_path.parts[-3].split("-")[1])
        figures.extend({
            "page": page, "id": figure["id"], "status": figure["status"],
            "verifier_errors": figure["selected_error_count"],
            "value_evidence": figure.get("value_evidence"),
            "html": str(batch_path.parent / figure["final_html"]),
        } for figure in batch["figures"])
    return {
        "status": "candidate_created", **plan, "run": str(output), "qc": qc,
        "figures": figures,
        "verifier_errors": sum(figure["verifier_errors"] for figure in figures),
    }


@server.tool(
    name="segment_document_page",
    description=("Demo-only: detect semantic regions on one public or synthetic-demo PDF page. "
                 "Returns normalized bounding boxes and saves regions.json, ordered crop PNGs, "
                 "and a red-box audit overlay. Use for dense forms, ruled tables, multi-column "
                 "pages, bills of lading, or when whole-page extraction loses reading order."),
    annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False,
                                idempotent_hint=False, open_world_hint=True),
)
def segment_document_page(
    family: str,
    document: str,
    page: int,
    data_classification: str,
    layout_hint: str = "",
    model: str = CLAUDE_MODEL,
    confirm: bool = False,
) -> dict:
    if data_classification != "public":
        raise ValueError("This demo tool accepts only data_classification='public'")
    source = resolve_raw_document(ROOT, family, document)
    page_count = pdf_page_count(source)
    if page < 1 or page > page_count:
        raise ValueError(f"page must be between 1 and {page_count}")
    plan = {
        "demo_only": True,
        "family": family,
        "document": document,
        "page": page,
        "page_count": page_count,
        "model": model,
        "output": "normalized boxes, crops, regions-overlay.png, and regions.json",
    }
    if not confirm:
        return {
            "status": "approval_required",
            **plan,
            "external_processing": "Claude receives one rasterized public-document page.",
            "next_step": "Review the plan, then call again with confirm=true.",
        }

    document_id = "--".join(Path(document).with_suffix("").parts)
    identifier = f"{run_id()}-segment-{uuid.uuid4().hex[:6]}"
    output_dir = ROOT / "runs" / family / document_id / identifier / f"page-{page:03d}"
    output_dir.mkdir(parents=True)
    source_png = output_dir / "source.png"
    import pymupdf
    with pymupdf.open(source) as pdf:
        pdf[page - 1].get_pixmap(matrix=pymupdf.Matrix(2.5, 2.5), alpha=False).save(source_png)
    result = segment_page_with_claude(source_png, output_dir / "segments", model, layout_hint)
    return {
        "status": "segmented",
        **plan,
        "run": str(output_dir.parent),
        "source_png": str(source_png),
        "regions_json": str(output_dir / "segments" / "regions.json"),
        "overlay": str(output_dir / "segments" / "regions-overlay.png"),
        "page_type": result["page_type"],
        "reason": result["reason"],
        "regions": result["regions"],
    }


if __name__ == "__main__":
    server.run("stdio")
