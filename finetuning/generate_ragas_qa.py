"""Generate a provenance-rich RAGAS test set from canonical chunk JSONL.

The program treats each input chunk as a LangChain document, asks RAGAS to
generate synthetic questions and reference answers, and writes both the native
RAGAS records and a compact question/answer view. It does not ingest data into
a vector store and it does not generate hard negatives.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from geha_processing.io import write_jsonl as _write_jsonl


DEFAULT_INPUT = Path(
    "/Users/dc/geha/crawl_dir/runs/dental/"
    "fedvip--2026-geha-dental-plan-brochure/"
    "batch-20261009-token-safe/candidate/chunks.jsonl"
)

TOC_TITLES = {
    "contents",
    "table of contents",
    "what's inside",
    "whats inside",
    "in this guide",
}
DOT_LEADER_RE = re.compile(r"\.{4,}")
TRAILING_PAGE_RE = re.compile(
    r"(?:\.{2,}|\s{3,})\s*(?:\d{1,3}|[ivxlcdm]+)\s*$", re.IGNORECASE
)
LEADING_PAGE_RE = re.compile(r"^\s*(?:[-\u2022]\s*)?\d{1,3}\s+\D+")


@dataclass(frozen=True)
class SourceChunk:
    chunk_id: str
    text: str
    pages: tuple[int, ...]
    section: str
    content_type: str


def _clean_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _normalize_heading(value: str) -> str:
    value = re.sub(r"[^a-z0-9' ]+", " ", value.casefold()).strip()
    return re.sub(r"\s+", " ", value)


def table_of_contents_reason(row: dict[str, Any]) -> str | None:
    """Identify navigation-only chunks that should not produce QA pairs."""
    text = _clean_text(row.get("text"))
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None

    section = _normalize_heading(_clean_text(row.get("section")))
    first_line = _normalize_heading(lines[0])
    if section in TOC_TITLES or first_line in TOC_TITLES:
        return "toc_heading"

    candidate_lines = lines
    leader_count = sum(bool(DOT_LEADER_RE.search(line)) for line in candidate_lines)
    page_entry_count = sum(
        bool(TRAILING_PAGE_RE.search(line)) or bool(LEADING_PAGE_RE.search(line))
        for line in candidate_lines
    )
    if len(candidate_lines) >= 4 and (
        leader_count >= 2 or page_entry_count / len(candidate_lines) >= 0.60
    ):
        return "toc_layout"
    return None


def load_chunks(
    path: Path,
    *,
    text_field: str = "contextualized_text",
    min_characters: int = 100,
) -> list[SourceChunk]:
    """Load useful chunks while preserving retrieval provenance."""
    chunks: list[SourceChunk] = []
    seen_ids: set[str] = set()

    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on {path}:{line_number}: {exc}") from exc

            chunk_id = _clean_text(row.get("chunk_id"))
            if not chunk_id:
                raise ValueError(f"Missing chunk_id on {path}:{line_number}")
            if chunk_id in seen_ids:
                raise ValueError(f"Duplicate chunk_id {chunk_id!r} on line {line_number}")
            seen_ids.add(chunk_id)

            if table_of_contents_reason(row):
                continue

            text = _clean_text(row.get(text_field)) or _clean_text(row.get("text"))
            if len(text) < min_characters:
                continue

            pages = tuple(
                int(page) for page in row.get("pages", []) if isinstance(page, int)
            )
            chunks.append(
                SourceChunk(
                    chunk_id=chunk_id,
                    text=text,
                    pages=pages,
                    section=_clean_text(row.get("section")),
                    content_type=_clean_text(row.get("content_type")) or "text",
                )
            )

    if not chunks:
        raise ValueError(
            f"No chunks in {path} passed min_characters={min_characters}"
        )
    return chunks


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def _word_set(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.casefold()))


def match_context_to_chunk(
    context: str,
    chunks: Sequence[SourceChunk],
) -> SourceChunk | None:
    """Best-effort provenance recovery for a RAGAS reference context."""
    normalized_context = _normalize(context)
    if not normalized_context:
        return None

    for chunk in chunks:
        normalized_chunk = _normalize(chunk.text)
        if normalized_context == normalized_chunk:
            return chunk
        if normalized_context in normalized_chunk or normalized_chunk in normalized_context:
            return chunk

    context_words = _word_set(context)
    if not context_words:
        return None

    best_chunk: SourceChunk | None = None
    best_score = 0.0
    for chunk in chunks:
        chunk_words = _word_set(chunk.text)
        denominator = min(len(context_words), len(chunk_words))
        if denominator == 0:
            continue
        containment = len(context_words & chunk_words) / denominator
        if containment > best_score:
            best_score = containment
            best_chunk = chunk

    return best_chunk if best_score >= 0.75 else None


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return None if math.isnan(value) else value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        return _json_safe(value.item())
    return str(value)


def enrich_record(
    record: dict[str, Any],
    chunks: Sequence[SourceChunk],
    sample_number: int,
) -> dict[str, Any]:
    contexts = record.get("reference_contexts") or []
    if isinstance(contexts, str):
        contexts = [contexts]

    matched: list[SourceChunk] = []
    for context in contexts:
        if not isinstance(context, str):
            continue
        chunk = match_context_to_chunk(context, chunks)
        if chunk and chunk.chunk_id not in {item.chunk_id for item in matched}:
            matched.append(chunk)

    enriched = dict(record)
    enriched.update(
        {
            "id": f"ragas-{sample_number:04d}",
            "source_chunk_ids": [chunk.chunk_id for chunk in matched],
            "source_pages": sorted({page for chunk in matched for page in chunk.pages}),
            "source_sections": list(
                dict.fromkeys(chunk.section for chunk in matched if chunk.section)
            ),
        }
    )
    return _json_safe(enriched)


def compact_qa_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record["id"],
        "question": record.get("user_input"),
        "answer": record.get("reference"),
        "reference_contexts": record.get("reference_contexts", []),
        "source_chunk_ids": record.get("source_chunk_ids", []),
        "source_pages": record.get("source_pages", []),
        "source_sections": record.get("source_sections", []),
        "synthesizer_name": record.get("synthesizer_name"),
    }


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    _write_jsonl(path, (_json_safe(record) for record in records))


def generate(args: argparse.Namespace) -> tuple[Path, Path]:
    try:
        from langchain_core.documents import Document
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        from ragas.run_config import RunConfig
        from ragas.testset import TestsetGenerator
    except ImportError as exc:
        raise SystemExit(
            "Missing generation dependencies. Activate /Users/dc/geha/"
            "finetuning/.venv and install finetuning/requirements.txt."
        ) from exc

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is required for RAGAS generation")

    chunks = load_chunks(
        args.input,
        text_field=args.text_field,
        min_characters=args.min_characters,
    )
    documents = [
        Document(
            page_content=chunk.text,
            metadata={
                "chunk_id": chunk.chunk_id,
                "pages": list(chunk.pages),
                "section": chunk.section,
                "content_type": chunk.content_type,
                "source": str(args.input),
            },
        )
        for chunk in chunks
    ]

    llm = ChatOpenAI(
        model=args.model,
        temperature=args.temperature,
        timeout=args.timeout,
        max_retries=args.max_retries,
    )
    embeddings = OpenAIEmbeddings(model=args.embedding_model)
    run_config = RunConfig(
        timeout=args.timeout,
        max_retries=args.max_retries,
        max_wait=args.max_retry_wait,
        max_workers=args.max_workers,
        log_tenacity=True,
        seed=args.seed,
    )
    generator = TestsetGenerator.from_langchain(
        llm,
        embeddings,
        llm_context=(
            "Generate answerable questions about the 2026 GEHA FEDVIP dental plan. "
            "Answers must be supported only by the supplied document context. "
            "Preserve exact benefit limits, percentages, dollar amounts, waiting "
            "periods, exclusions, plan options, and eligibility distinctions."
        ),
    )
    testset = generator.generate_with_langchain_docs(
        documents,
        testset_size=args.testset_size,
        run_config=run_config,
        with_debugging_logs=args.debug,
        raise_exceptions=True,
    )

    raw_records = testset.to_pandas().to_dict(orient="records")
    enriched = [
        enrich_record(record, chunks, index)
        for index, record in enumerate(raw_records, start=1)
    ]

    output_dir = args.output_dir or args.input.parent / "ragas"
    native_path = output_dir / "ragas_testset.jsonl"
    qa_path = output_dir / "qa_pairs.jsonl"
    write_jsonl(native_path, enriched)
    write_jsonl(qa_path, (compact_qa_record(record) for record in enriched))
    return native_path, qa_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate RAGAS question/reference-answer pairs from chunk JSONL."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--testset-size", type=int, default=50)
    parser.add_argument(
        "--text-field",
        choices=("text", "contextualized_text"),
        default="contextualized_text",
    )
    parser.add_argument("--min-characters", type=int, default=100)
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--embedding-model", default="text-embedding-3-small")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Maximum concurrent RAGAS tasks; lower this after connection errors.",
    )
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--max-retries", type=int, default=10)
    parser.add_argument("--max-retry-wait", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and count chunks without making API calls.",
    )
    return parser


def main() -> None:
    os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")
    args = build_parser().parse_args()
    if args.testset_size < 1:
        raise SystemExit("--testset-size must be at least 1")
    if args.max_workers < 1:
        raise SystemExit("--max-workers must be at least 1")
    if not args.input.is_file():
        raise SystemExit(f"Chunk file does not exist: {args.input}")

    chunks = load_chunks(
        args.input,
        text_field=args.text_field,
        min_characters=args.min_characters,
    )
    print(f"Loaded {len(chunks)} eligible chunks from {args.input}")
    if args.dry_run:
        print("Dry run complete; no model or embedding calls were made.")
        return

    native_path, qa_path = generate(args)
    print(f"Wrote native RAGAS records to {native_path}")
    print(f"Wrote compact question/answer pairs to {qa_path}")
    print("Review generated pairs before using them for evaluation or training.")


if __name__ == "__main__":
    main()
