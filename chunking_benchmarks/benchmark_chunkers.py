"""Compare Docling's structure-aware chunker with a LangChain baseline."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker.tokenizer.huggingface import (
    HuggingFaceTokenizer,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter


def percentile(values: list[int], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def summarize(
    name: str,
    chunks: list[str],
    tokenizer: HuggingFaceTokenizer,
    max_tokens: int,
    elapsed_seconds: float,
    source_tokens: int,
) -> dict[str, object]:
    token_counts = [tokenizer.count_tokens(text=chunk) for chunk in chunks]
    total_tokens = sum(token_counts)
    return {
        "chunker": name,
        "elapsed_seconds": round(elapsed_seconds, 6),
        "chunks": len(chunks),
        "source_tokens": source_tokens,
        "total_chunk_tokens": total_tokens,
        "token_duplication_ratio": round(total_tokens / source_tokens, 4)
        if source_tokens
        else None,
        "tokens_min": min(token_counts, default=0),
        "tokens_mean": round(statistics.mean(token_counts), 2)
        if token_counts
        else 0,
        "tokens_p50": round(percentile(token_counts, 0.50), 2),
        "tokens_p95": round(percentile(token_counts, 0.95), 2),
        "tokens_max": max(token_counts, default=0),
        "over_budget_chunks": sum(count > max_tokens for count in token_counts),
        "under_25_pct_budget_chunks": sum(
            count < max_tokens * 0.25 for count in token_counts
        ),
        "empty_chunks": sum(not chunk.strip() for chunk in chunks),
    }


def write_chunks(path: Path, chunks: list[str]) -> None:
    with path.open("w", encoding="utf-8") as output:
        for index, chunk in enumerate(chunks, 1):
            output.write(f"## Chunk {index}\n\n{chunk}\n\n\n\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--max-tokens", type=int, default=700)
    parser.add_argument("--chunk-overlap", type=int, default=0)
    parser.add_argument(
        "--tokenizer", default="BAAI/bge-small-en-v1.5"
    )
    parser.add_argument("--output-dir", type=Path, default=Path("chunking_results"))
    args = parser.parse_args()

    pdf = args.pdf.expanduser().resolve()
    if not pdf.is_file():
        raise FileNotFoundError(pdf)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    parse_started = time.perf_counter()
    document = DocumentConverter().convert(pdf).document
    parse_seconds = time.perf_counter() - parse_started
    markdown = document.export_to_markdown()

    tokenizer = HuggingFaceTokenizer.from_pretrained(
        model_name=args.tokenizer,
        max_tokens=args.max_tokens,
    )
    source_tokens = tokenizer.count_tokens(text=markdown)

    docling_chunker = HybridChunker(tokenizer=tokenizer, merge_peers=True)
    started = time.perf_counter()
    docling_chunks = [
        docling_chunker.contextualize(chunk)
        for chunk in docling_chunker.chunk(document)
    ]
    docling_seconds = time.perf_counter() - started

    langchain_chunker = RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
        tokenizer.tokenizer,
        chunk_size=args.max_tokens,
        chunk_overlap=args.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    started = time.perf_counter()
    langchain_chunks = langchain_chunker.split_text(markdown)
    langchain_seconds = time.perf_counter() - started

    results = {
        "pdf": str(pdf),
        "max_tokens": args.max_tokens,
        "chunk_overlap": args.chunk_overlap,
        "tokenizer": args.tokenizer,
        "parse_seconds_excluded_from_chunker_timings": round(parse_seconds, 6),
        "results": [
            summarize(
                "docling_hybrid",
                docling_chunks,
                tokenizer,
                args.max_tokens,
                docling_seconds,
                source_tokens,
            ),
            summarize(
                "langchain_recursive",
                langchain_chunks,
                tokenizer,
                args.max_tokens,
                langchain_seconds,
                source_tokens,
            ),
        ],
    }

    stem = pdf.stem
    write_chunks(args.output_dir / f"{stem}_docling_chunks.md", docling_chunks)
    write_chunks(args.output_dir / f"{stem}_langchain_chunks.md", langchain_chunks)
    result_path = args.output_dir / f"{stem}_benchmark.json"
    result_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    print(f"Results saved to {result_path}")


if __name__ == "__main__":
    main()
