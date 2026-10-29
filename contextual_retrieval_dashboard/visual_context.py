"""Contextual retrieval over figure artifacts from a saved ingestion run."""

from __future__ import annotations

import base64
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypedDict

from geha_processing.io import atomic_jsonl, read_jsonl, sha256_file

from crawl_dir.src.pipeline.claude_client import (
    CLAUDE_MODEL,
    FALLBACK_BETA,
    ClaudeRefusalError,
    image_block,
)


VISUAL_PROMPT_VERSION = "anthropic-visual-contextual-retrieval-v1"
VISUAL_SYSTEM_PROMPT = (
    "You prepare concise context for retrieval indexing. The PDF is the original "
    "document page and the image is one reconstructed figure chunk from that page. "
    "Use only those artifacts. Do not answer questions, add advice, or introduce "
    "facts absent from the supplied page."
)
VISUAL_USER_PROMPT = (
    "Situate the figure chunk within the original PDF page for retrieval. State the "
    "document topic, figure subject, population or categories, and time period needed "
    "to disambiguate it. Answer only with a short succinct context."
)
FIGURE_DIR = re.compile(r"^(?:fig|figure)-(\d+)$")
ITERATION_FILE = re.compile(r"^iteration-(\d+)\.png$")


class VisualContextResult(TypedDict):
    context: str
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int


VisualContextGenerator = Callable[[Path, Path], str | VisualContextResult]
EventSink = Callable[[dict[str, Any]], None]


def _latest_iteration(figure_dir: Path) -> Path | None:
    candidates: list[tuple[int, Path]] = []
    for path in figure_dir.glob("iteration-*.png"):
        match = ITERATION_FILE.fullmatch(path.name)
        if match:
            candidates.append((int(match.group(1)), path))
    return max(candidates, default=(0, None), key=lambda item: item[0])[1]


def discover_visual_chunks(run_dir: Path) -> list[dict[str, Any]]:
    """Map each figure directory to its page PDF and highest-numbered iteration."""
    run_dir = run_dir.resolve()
    chunks: list[dict[str, Any]] = []
    for page_dir in sorted((run_dir / "pages").glob("page-*")):
        if not page_dir.is_dir():
            continue
        page_match = re.fullmatch(r"page-(\d+)", page_dir.name)
        source_pdf = page_dir / "source.pdf"
        segments = page_dir / "segments"
        if not page_match or not source_pdf.is_file() or not segments.is_dir():
            continue
        page_number = int(page_match.group(1))
        for figure_dir in sorted(path for path in segments.iterdir() if path.is_dir()):
            figure_match = FIGURE_DIR.fullmatch(figure_dir.name)
            if not figure_match:
                continue
            latest = _latest_iteration(figure_dir)
            if latest is None:
                continue
            evidence_path = figure_dir / "native-evidence.json"
            literal_text = ""
            if evidence_path.is_file():
                try:
                    literal_text = str(
                        json.loads(evidence_path.read_text(encoding="utf-8")).get(
                            "literal_text", ""
                        )
                    )
                except (OSError, json.JSONDecodeError):
                    pass
            chunks.append({
                "chunk_id": f"{page_dir.name}:{figure_dir.name}",
                "pages": [page_number],
                "section": f"{page_dir.name} / {figure_dir.name} / {latest.stem}",
                "source_pdf": str(source_pdf.relative_to(run_dir)),
                "chunk_image": str(latest.relative_to(run_dir)),
                "literal_text": literal_text,
            })
    return chunks


def _pdf_block(path: Path) -> dict[str, Any]:
    return {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": "application/pdf",
            "data": base64.standard_b64encode(path.read_bytes()).decode("ascii"),
        },
        "title": path.name,
        "cache_control": {"type": "ephemeral"},
    }


def make_visual_context_generator(
    model: str = CLAUDE_MODEL,
) -> VisualContextGenerator:
    """Create a Claude generator that receives a page PDF and figure image."""
    import anthropic

    client = anthropic.Anthropic(max_retries=2, timeout=180)

    def generate(source_pdf: Path, chunk_image: Path) -> VisualContextResult:
        with client.beta.messages.stream(
            model=model,
            max_tokens=256,
            system=VISUAL_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": [
                    _pdf_block(source_pdf),
                    {
                        "type": "text",
                        "text": "The following image is the target figure chunk.",
                    },
                    image_block(chunk_image),
                    {"type": "text", "text": VISUAL_USER_PROMPT},
                ],
            }],
            betas=[FALLBACK_BETA],
            fallbacks="default",
        ) as stream:
            message = stream.get_final_message()
        if message.stop_reason == "refusal":
            category = (
                getattr(message.stop_details, "category", None)
                if message.stop_details
                else None
            )
            raise ClaudeRefusalError(
                f"Claude declined visual contextualization (category: {category})"
            )
        text = "".join(
            block.text for block in message.content if block.type == "text"
        )
        usage = message.usage
        return {
            "context": " ".join(text.split()).strip(),
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cache_creation_input_tokens": (
                getattr(usage, "cache_creation_input_tokens", 0) or 0
            ),
            "cache_read_input_tokens": (
                getattr(usage, "cache_read_input_tokens", 0) or 0
            ),
        }

    return generate


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return read_jsonl(path)


def _write_jsonl_atomic(path: Path, records: list[dict[str, Any]]) -> None:
    atomic_jsonl(path, records)


def contextualize_visual_run(
    run_dir: Path,
    *,
    model: str = CLAUDE_MODEL,
    generate_context: VisualContextGenerator | None = None,
    event_sink: EventSink | None = None,
) -> Path:
    """Contextualize the latest rendered iteration for every saved figure segment."""
    run_dir = run_dir.resolve()
    output_path = run_dir / "visual-contextual-chunks.jsonl"
    metadata_path = run_dir / "visual-contextual-retrieval.json"
    chunks = discover_visual_chunks(run_dir)
    if not chunks:
        raise FileNotFoundError(f"No page figure iterations found under {run_dir}")
    completed = {
        record["chunk_id"]: record for record in _read_jsonl(output_path)
    }
    generate = generate_context or make_visual_context_generator(model)
    records: list[dict[str, Any]] = []

    for index, chunk in enumerate(chunks, 1):
        source_pdf = run_dir / chunk["source_pdf"]
        chunk_image = run_dir / chunk["chunk_image"]
        document_sha256 = sha256_file(source_pdf)
        chunk_sha256 = sha256_file(chunk_image)
        existing = completed.get(chunk["chunk_id"])
        if (
            existing
            and existing.get("document_sha256") == document_sha256
            and existing.get("chunk_sha256") == chunk_sha256
            and existing.get("contextual_retrieval_prompt_version")
            == VISUAL_PROMPT_VERSION
            and existing.get("contextual_retrieval_model") == model
        ):
            record = existing
            status = "reused"
        else:
            generated = generate(source_pdf, chunk_image)
            if isinstance(generated, str):
                context = generated
                usage = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                }
            else:
                context = generated["context"]
                usage = {
                    key: generated[key]
                    for key in (
                        "input_tokens",
                        "output_tokens",
                        "cache_creation_input_tokens",
                        "cache_read_input_tokens",
                    )
                }
            if not context:
                raise RuntimeError(
                    f"Claude returned empty context for {chunk['chunk_id']}"
                )
            index_text = "\n\n".join(
                part for part in (context, chunk.get("literal_text", "")) if part
            )
            record = {
                **chunk,
                "document_sha256": document_sha256,
                "chunk_sha256": chunk_sha256,
                "retrieval_context": context,
                "contextual_retrieval_text": index_text,
                "contextual_retrieval_model": model,
                "contextual_retrieval_prompt_version": VISUAL_PROMPT_VERSION,
                "contextualized_at": datetime.now(timezone.utc).isoformat(),
                "prompt_cache": usage,
            }
            status = "generated"
        records.append(record)
        _write_jsonl_atomic(output_path, records)
        if event_sink:
            event_sink({
                "type": "contextual_chunk_ready",
                "run": str(run_dir),
                "document_id": run_dir.parent.name,
                "chunk_id": chunk["chunk_id"],
                "index": index,
                "total": len(chunks),
                "status": status,
                "prompt_cache": record.get("prompt_cache", {}),
            })

    metadata = {
        "schema_version": 1,
        "artifact_mode": "page_pdf_and_latest_figure_iteration",
        "prompt_version": VISUAL_PROMPT_VERSION,
        "model": model,
        "chunk_count": len(chunks),
        "completed_count": len(records),
        "cache_creation_input_tokens": sum(
            record.get("prompt_cache", {}).get(
                "cache_creation_input_tokens", 0
            )
            for record in records
        ),
        "cache_read_input_tokens": sum(
            record.get("prompt_cache", {}).get("cache_read_input_tokens", 0)
            for record in records
        ),
        "output": output_path.name,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    return output_path
