"""Count full-document Docling hybrid chunks without making LLM calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path
from typing import Any, Iterable


DEFAULT_TOKENIZER = "BAAI/bge-small-en-v1.5"
DEFAULT_MAX_TOKENS = (380, 512, 800)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def page_numbers(chunk: Any) -> list[int]:
    """Return sorted one-based page numbers from Docling provenance."""
    pages: set[int] = set()
    meta = getattr(chunk, "meta", None)
    for item in getattr(meta, "doc_items", []) or []:
        for provenance in getattr(item, "prov", []) or []:
            page_number = getattr(provenance, "page_no", None)
            if page_number is not None:
                pages.add(int(page_number))
    return sorted(pages)


def write_jsonl(records: Iterable[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def chunk_for_budget(
    *,
    document: Any,
    document_id: str,
    source_name: str,
    tokenizer_model: str,
    max_tokens: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from docling.chunking import HybridChunker
    from docling_core.transforms.chunker.tokenizer.huggingface import (
        HuggingFaceTokenizer,
    )

    tokenizer = HuggingFaceTokenizer.from_pretrained(
        model_name=tokenizer_model,
        max_tokens=max_tokens,
    )
    chunker = HybridChunker(tokenizer=tokenizer, merge_peers=True)
    records: list[dict[str, Any]] = []

    for chunk_index, chunk in enumerate(chunker.chunk(dl_doc=document)):
        raw_text = chunk.text.strip()
        retrieval_text = chunker.contextualize(chunk).strip()
        if not retrieval_text:
            continue
        pages = page_numbers(chunk)
        token_count = tokenizer.count_tokens(retrieval_text)
        chunk_id = hashlib.sha256(
            f"{document_id}:{max_tokens}:{chunk_index}:{retrieval_text}".encode()
        ).hexdigest()
        meta = chunk.meta
        records.append(
            {
                "schema_version": "1.0",
                "document_id": document_id,
                "source_name": source_name,
                "chunk_id": chunk_id,
                "chunk_index": chunk_index,
                "raw_text": raw_text,
                "retrieval_text": retrieval_text,
                "token_count": token_count,
                "page_numbers": pages,
                "headings": list(getattr(meta, "headings", []) or []),
                "captions": list(getattr(meta, "captions", []) or []),
                "max_tokens": max_tokens,
                "tokenizer": tokenizer_model,
                "llm_context_status": "not_started",
            }
        )

    token_counts = [record["token_count"] for record in records]
    multi_page = sum(len(record["page_numbers"]) > 1 for record in records)
    summary = {
        "max_tokens": max_tokens,
        "chunks": len(records),
        "chunks_spanning_pages": multi_page,
        "tokens": {
            "minimum": min(token_counts, default=0),
            "maximum": max(token_counts, default=0),
            "mean": round(statistics.fmean(token_counts), 2) if token_counts else 0,
            "median": statistics.median(token_counts) if token_counts else 0,
            "total": sum(token_counts),
        },
    }
    return records, summary


def count_document(
    source: Path,
    output_dir: Path,
    *,
    tokenizer_model: str,
    token_budgets: list[int],
) -> dict[str, Any]:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    if not source.is_file():
        raise FileNotFoundError(source)
    if not token_budgets or any(value < 1 for value in token_budgets):
        raise ValueError("Every --max-tokens value must be positive")

    output_dir.mkdir(parents=True, exist_ok=True)
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False
    pipeline_options.do_table_structure = True
    pipeline_options.generate_page_images = False
    pipeline_options.generate_picture_images = False
    pipeline_options.generate_table_images = False

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        }
    )
    result = converter.convert(source)
    document = result.document
    document.save_as_json(output_dir / "document.json")
    (output_dir / "document.md").write_text(
        document.export_to_markdown(), encoding="utf-8"
    )

    document_id = sha256_file(source)
    budgets: list[dict[str, Any]] = []
    for max_tokens in sorted(set(token_budgets)):
        records, budget_summary = chunk_for_budget(
            document=document,
            document_id=document_id,
            source_name=source.name,
            tokenizer_model=tokenizer_model,
            max_tokens=max_tokens,
        )
        chunks_path = output_dir / f"chunks-{max_tokens}.jsonl"
        write_jsonl(records, chunks_path)
        budgets.append({**budget_summary, "output": str(chunks_path)})
        print(
            f"max_tokens={max_tokens}: {len(records)} chunks "
            f"({budget_summary['chunks_spanning_pages']} span pages)",
            flush=True,
        )

    summary = {
        "schema_version": "1.0",
        "source": str(source),
        "document_id": document_id,
        "document_markdown": str(output_dir / "document.md"),
        "document_json": str(output_dir / "document.json"),
        "tokenizer": tokenizer_model,
        "llm_calls_made": 0,
        "budgets": budgets,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--tokenizer", default=DEFAULT_TOKENIZER)
    parser.add_argument(
        "--max-tokens",
        type=int,
        nargs="+",
        default=list(DEFAULT_MAX_TOKENS),
        help="One or more chunk token budgets; the PDF is converted only once.",
    )
    args = parser.parse_args()
    summary = count_document(
        args.source.expanduser().resolve(),
        args.output_dir.expanduser().resolve(),
        tokenizer_model=args.tokenizer,
        token_budgets=args.max_tokens,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

