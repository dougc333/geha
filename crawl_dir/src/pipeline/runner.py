"""Run the canonical PDF-to-reviewed-candidate pipeline."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .artifact_io import atomic_json, resolve_raw_document, run_id, sha256_file
from .chunks import (
    build_chunk_records,
    validate_chunks,
    validate_embedding_token_lengths,
    write_jsonl,
)
from .tables import extract_logical_tables


def _valid_split_cache(cache_dir: Path, source_hash: str, page_count: int) -> bool:
    manifest_path = cache_dir / "manifest.json"
    if not manifest_path.is_file():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if (manifest.get("source_sha256") != source_hash or
            manifest.get("page_count") != page_count):
        return False
    pages = manifest.get("pages")
    if not isinstance(pages, list) or len(pages) != page_count:
        return False
    return all(isinstance(item, dict) for item in pages) and all(
        (cache_dir / item.get("filename", "")).is_file()
        and sha256_file(cache_dir / item["filename"]) == item.get("sha256")
        for item in pages
    )


def _split_pages(
    source: Path,
    pages_dir: Path,
    *,
    cache_root: Path | None = None,
    source_hash: str | None = None,
) -> list[dict[str, Any]]:
    """Materialize immutable run pages, reusing a content-addressed split cache."""
    import pymupdf

    pages_dir.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(source) as document:
        page_count = document.page_count
    digest = source_hash or sha256_file(source)
    cache_dir = (cache_root / digest) if cache_root is not None else None
    cache_hit = bool(cache_dir and _valid_split_cache(cache_dir, digest, page_count))

    if cache_dir is None:
        cache_dir = pages_dir / ".split-source"
    if not cache_hit:
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
        cache_dir.mkdir(parents=True)
        cached_pages: list[dict[str, Any]] = []
        with pymupdf.open(source) as document:
            for index in range(document.page_count):
                filename = f"page-{index + 1:03d}.pdf"
                output = cache_dir / filename
                single = pymupdf.open()
                single.insert_pdf(document, from_page=index, to_page=index)
                single.save(output)
                single.close()
                output.chmod(0o444)
                cached_pages.append({"filename": filename, "sha256": sha256_file(output)})
        atomic_json(cache_dir / "manifest.json", {
            "source_sha256": digest,
            "page_count": page_count,
            "pages": cached_pages,
        })

    manifest = json.loads((cache_dir / "manifest.json").read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = []
    for page_number, cached in enumerate(manifest["pages"], start=1):
        page_dir = pages_dir / f"page-{page_number:03d}"
        page_dir.mkdir(parents=True)
        output = page_dir / "source.pdf"
        cached_page = cache_dir / cached["filename"]
        try:
            os.link(cached_page, output)
        except OSError:
            shutil.copy2(cached_page, output)
        records.append({
            "page": page_number,
            "source_pdf": str(output.relative_to(pages_dir)),
            "source_sha256": cached["sha256"],
            "split_cache_hit": cache_hit,
            "split_cache_key": digest,
            "status": "pending",
        })
    if cache_root is None:
        shutil.rmtree(cache_dir)
    return records


def _extract_document(source: Path, markdown_path: Path) -> tuple[list[dict[str, Any]], int, Any]:
    from docling.chunking import HybridChunker
    from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer

    from .pdf_conversion import native_text_converter, require_embedded_text

    document = native_text_converter().convert(source).document
    require_embedded_text(document, source.name)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(document.export_to_markdown() + "\n", encoding="utf-8")
    tokenizer = HuggingFaceTokenizer.from_pretrained(
        # Reserve room for the provenance header added after Docling chunks the
        # body. The completed record is checked against the hard 512-token
        # encoder ceiling below, so an overflow can never pass structural QC.
        model_name="BAAI/bge-small-en-v1.5", max_tokens=380
    )
    chunker = HybridChunker(tokenizer=tokenizer, merge_peers=True)
    raw_chunks: list[dict[str, Any]] = []
    for chunk in chunker.chunk(document):
        pages = sorted({
            int(prov.page_no)
            for item in (getattr(chunk.meta, "doc_items", None) or [])
            for prov in (getattr(item, "prov", None) or [])
            if getattr(prov, "page_no", None)
        })
        raw_chunks.append({
            "pages": pages,
            "headings": list(getattr(chunk.meta, "headings", None) or []),
            "text": chunker.contextualize(chunk),
        })
    page_count = len(document.pages)
    return raw_chunks, page_count, tokenizer


def process_document(
    *,
    root: Path,
    family: str,
    document: str,
    document_version: str,
    plan_year: int | None = None,
    requested_run_id: str | None = None,
) -> Path:
    """Create an immutable run and a candidate; never auto-promote it."""
    root = root.resolve()
    source = resolve_raw_document(root, family, document)
    raw_family = (root / "raw" / family).resolve()
    relative_source = source.relative_to(raw_family).with_suffix("")
    document_id = "--".join(relative_source.parts)
    identifier = requested_run_id or run_id()
    run_dir = root / "runs" / family / document_id / identifier
    if run_dir.exists():
        raise FileExistsError(run_dir)

    input_dir = run_dir / "input"
    pages_dir = run_dir / "pages"
    iteration_dir = run_dir / "iterations" / "iteration-001"
    candidate_dir = run_dir / "candidate"
    input_dir.mkdir(parents=True)
    iteration_dir.mkdir(parents=True)
    candidate_dir.mkdir(parents=True)

    snapshot = input_dir / "source.pdf"
    shutil.copy2(source, snapshot)
    source_hash = sha256_file(snapshot)
    atomic_json(input_dir / "source-reference.json", {
        "family": family,
        "document": document,
        "raw_path": str(source),
        "snapshot": "source.pdf",
        "sha256": source_hash,
    })
    (input_dir / "source.sha256").write_text(f"{source_hash}  source.pdf\n")

    page_records = _split_pages(
        snapshot,
        pages_dir,
        cache_root=root / "cache" / "page-splits",
        source_hash=source_hash,
    )
    raw_chunks, extracted_page_count, tokenizer = _extract_document(
        snapshot, iteration_dir / "document.md"
    )
    shutil.copy2(iteration_dir / "document.md", candidate_dir / "document.md")

    table_records, extraction = extract_logical_tables(
        snapshot,
        iteration_dir / "table-fragments",
        candidate_dir / "tables",
        document_id=document_id,
        document_version=document_version,
        plan_year=plan_year,
    )
    chunks = build_chunk_records(
        raw_chunks,
        document_id=document_id,
        document_version=document_version,
        plan_year=plan_year,
        source_sha256=source_hash,
    )
    chunk_errors, chunk_warnings = validate_chunks(chunks)
    chunk_errors.extend(validate_embedding_token_lengths(
        chunks,
        encode=lambda value: tokenizer.get_tokenizer().encode(
            value, add_special_tokens=True, truncation=False
        ),
        max_tokens=512,
    ))
    write_jsonl(candidate_dir / "chunks.jsonl", chunks)

    for page in page_records:
        page_number = page["page"]
        page_dir = pages_dir / f"page-{page_number:03d}"
        page_text = "\n\n".join(
            chunk["text"] for chunk in chunks if page_number in chunk["pages"]
        ).strip()
        (page_dir / "page.md").write_text(
            page_text + ("\n" if page_text else ""), encoding="utf-8"
        )
        page["markdown"] = "page.md"
        page["html"] = None
        page["table_ids"] = [
            table["table_id"] for table in table_records
            if page_number in table["source_pages"]
        ]
        atomic_json(page_dir / "page-manifest.json", page)

    page_count = len(page_records)
    structural_errors = list(chunk_errors)
    if extracted_page_count and extracted_page_count != page_count:
        structural_errors.append({
            "issue": "page_count_mismatch",
            "split_pages": page_count,
            "extracted_pages": extracted_page_count,
        })
    atomic_json(iteration_dir / "findings.json", {
        "table_extraction": extraction,
        "chunk_errors": chunk_errors,
        "chunk_warnings": chunk_warnings,
    })
    qc_status = "failed" if structural_errors else "needs_visual_review"
    atomic_json(run_dir / "qc-report.json", {
        "status": qc_status,
        "source_sha256": source_hash,
        "page_count": page_count,
        "chunk_count": len(chunks),
        "table_count": len(table_records),
        "structural_errors": structural_errors,
        "structural_warnings": chunk_warnings,
        "visual_verification": {
            "status": "pending",
            "required": True,
            "passed_pages": 0,
            "total_pages": page_count,
        },
    })
    atomic_json(run_dir / "run-manifest.json", {
        "schema_version": 1,
        "run_id": identifier,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "family": family,
        "document_id": document_id,
        "document_version": document_version,
        "plan_year": plan_year,
        "source_sha256": source_hash,
        "source": str(source.relative_to(root)),
        "candidate": "candidate",
        "qc_report": "qc-report.json",
        "promotion_status": "not_promoted",
    })
    return run_dir
