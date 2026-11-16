"""Convert a local document into structure-aware Docling chunks.

An AWS worker should first download an S3 object to local ephemeral storage, call
``chunk_document``, and then upload the JSONL result. Keeping S3 access outside this
module makes conversion deterministic and straightforward to test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from geha_processing.io import sha256_file, write_jsonl as _write_jsonl


DEFAULT_TOKENIZER = "BAAI/bge-small-en-v1.5"
DEFAULT_MAX_TOKENS = 380


def _document_id(source: Path) -> str:
    """Return a stable identifier based on the source bytes."""
    return sha256_file(source)


def _metadata(chunk: Any) -> dict[str, Any]:
    """Convert Docling's chunk metadata model to JSON-compatible data."""
    meta = getattr(chunk, "meta", None)
    if meta is None:
        return {}
    if hasattr(meta, "model_dump"):
        return meta.model_dump(mode="json", exclude_none=True)
    if hasattr(meta, "export_json_dict"):
        return meta.export_json_dict()
    if isinstance(meta, dict):
        return meta
    return {"value": str(meta)}


def build_records(
    chunks: Iterable[Any],
    *,
    chunker: Any,
    source: Path,
    document_id: str,
) -> list[dict[str, Any]]:
    """Build stable JSONL records from Docling chunks."""
    records: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks):
        text = chunker.contextualize(chunk).strip()
        if not text:
            continue
        chunk_id = hashlib.sha256(
            f"{document_id}:{index}:{text}".encode("utf-8")
        ).hexdigest()
        records.append(
            {
                "schema_version": "1.0",
                "document_id": document_id,
                "chunk_id": chunk_id,
                "chunk_index": index,
                "source_name": source.name,
                "text": text,
                "metadata": _metadata(chunk),
                "review_status": "pending",
            }
        )
    return records


def build_whole_document_record(
    *,
    source: Path,
    document_id: str,
    text: str,
    classification: dict[str, Any],
) -> list[dict[str, Any]]:
    """Represent a form/application as one retrievable document, not fragments."""
    normalized = text.strip()
    if not normalized:
        return []
    chunk_id = hashlib.sha256(
        f"{document_id}:whole-document:{normalized}".encode("utf-8")
    ).hexdigest()
    return [{
        "schema_version": "1.0",
        "document_id": document_id,
        "chunk_id": chunk_id,
        "chunk_index": 0,
        "source_name": source.name,
        "text": normalized,
        "metadata": {
            "document_type": classification["document_type"],
            "route": classification["route"],
            "storage_strategy": "whole_document",
        },
        "review_status": "pending",
    }]


def write_jsonl(records: Iterable[dict[str, Any]], output: Path) -> int:
    """Write one UTF-8 JSON object per line and return the record count."""
    return _write_jsonl(output, records, sort_keys=True)


def chunk_document(
    source: Path,
    output: Path,
    *,
    tokenizer_model: str = DEFAULT_TOKENIZER,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    describe_figure: Any | None = None,
    extract_page_markdown: Any | None = None,
    page_markdown_engine: str = "deepseek",
    page_markdown_overrides: dict[int, str] | None = None,
) -> dict[str, Any]:
    """Parse a document, apply Docling HybridChunker, and write JSONL."""
    if not source.is_file():
        raise FileNotFoundError(source)
    if max_tokens < 1:
        raise ValueError("max_tokens must be positive")

    # Imports are local so record-writing utilities remain lightweight to test.
    from docling.chunking import HybridChunker
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling_core.transforms.chunker.tokenizer.huggingface import (
        HuggingFaceTokenizer,
    )

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_table_structure = True
    pipeline_options.generate_page_images = True
    pipeline_options.generate_picture_images = True
    pipeline_options.generate_table_images = True
    pipeline_options.images_scale = 2.0
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        }
    )
    document = converter.convert(source).document
    document_path = output.parent / "document.md"
    document_path.parent.mkdir(parents=True, exist_ok=True)
    document_path.write_text(document.export_to_markdown(), encoding="utf-8")
    document_id = _document_id(source)
    from .visual_processing import extract_page_artifacts, extract_visual_artifacts

    visual_manifest = extract_visual_artifacts(
        document,
        output.parent / "visuals",
        describe_figure=describe_figure,
    )
    page_manifest = extract_page_artifacts(
        document,
        output.parent / "pages",
        extract_markdown=extract_page_markdown,
        markdown_engine=page_markdown_engine,
        page_markdown_overrides=page_markdown_overrides,
    )
    selected_pages: list[str] = []
    for page_record in page_manifest["pages"]:
        selected_relative = (
            page_record.get("ocr_markdown")
            or page_record["docling_markdown"]
        )
        selected_path = output.parent / "pages" / selected_relative
        selected_pages.append(selected_path.read_text(encoding="utf-8").strip())
    if selected_pages:
        document_path.write_text("\n\n".join(selected_pages) + "\n", encoding="utf-8")
    final_document_text = document_path.read_text(encoding="utf-8")
    from .document_router import classify_document

    classification = classify_document(source.name, final_document_text)
    if classification["route"] == "whole_document_context":
        records = build_whole_document_record(
            source=source,
            document_id=document_id,
            text=final_document_text,
            classification=classification,
        )
        storage_strategy = "whole_document"
    else:
        tokenizer = HuggingFaceTokenizer.from_pretrained(
            model_name=tokenizer_model,
            max_tokens=max_tokens,
        )
        chunker = HybridChunker(tokenizer=tokenizer, merge_peers=True)
        records = build_records(
            chunker.chunk(document),
            chunker=chunker,
            source=source,
            document_id=document_id,
        )
        storage_strategy = "structure_aware_chunks"
    count = write_jsonl(records, output)
    return {
        "document_id": document_id,
        "source": str(source),
        "output": str(output),
        "document_markdown": str(document_path),
        "chunks": count,
        "storage_strategy": storage_strategy,
        "classification": classification,
        "tokenizer": tokenizer_model,
        "max_tokens": max_tokens,
        "visuals": visual_manifest["summary"],
        "visual_manifest": str(output.parent / "visuals" / "manifest.json"),
        "pages": page_manifest["summary"],
        "page_manifest": str(output.parent / "pages" / "manifest.json"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Local input document")
    parser.add_argument("--output", type=Path, required=True, help="Output JSONL path")
    parser.add_argument("--tokenizer", default=DEFAULT_TOKENIZER)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    args = parser.parse_args()

    result = chunk_document(
        args.source.expanduser().resolve(),
        args.output.expanduser().resolve(),
        tokenizer_model=args.tokenizer,
        max_tokens=args.max_tokens,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

