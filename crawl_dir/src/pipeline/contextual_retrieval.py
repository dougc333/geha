"""Anthropic-style contextual retrieval over canonical Docling chunks.

The canonical ``chunks.jsonl`` artifact is immutable input. This module writes
``contextual-chunks.jsonl`` beside it so reviewers can compare the original
Docling chunk, deterministic provenance prefix, and Claude's document-aware
retrieval context without silently changing an approved candidate.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypedDict

from .claude_client import CLAUDE_MODEL, FALLBACK_BETA, ClaudeRefusalError


PROMPT_VERSION = "anthropic-contextual-retrieval-v1"
SYSTEM_PROMPT = (
    "You prepare concise context for retrieval indexing. Use only the supplied "
    "document. Do not answer questions, add advice, or introduce facts absent "
    "from the document."
)
USER_TEMPLATE = """Here is the chunk we want to situate within the whole document.
<chunk>
{chunk}
</chunk>
Please give a short succinct context to situate this chunk within the overall
document for the purposes of improving search retrieval of the chunk. Include
the document subject and any policy code, entity, section, or time period needed
to disambiguate it. Answer only with the succinct context and nothing else."""

EventSink = Callable[[dict[str, Any]], None]


class ClaudeContextResult(TypedDict):
    context: str
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int


ContextGenerator = Callable[[str, str], str | ClaudeContextResult]


def contextual_retrieval_prompt(document: str, chunk: str) -> dict[str, Any]:
    """Return the prompt with the entire document separate from the target chunk."""
    return {
        "system": [
            {"type": "text", "text": SYSTEM_PROMPT},
            {
                "type": "text",
                "text": f"<document>\n{document}\n</document>",
                "cache_control": {"type": "ephemeral"},
            },
        ],
        "message": USER_TEMPLATE.format(chunk=chunk),
    }


def make_claude_context_generator(model: str = CLAUDE_MODEL) -> ContextGenerator:
    """Create one reusable Claude client; the document block is prompt-cacheable."""
    import anthropic

    client = anthropic.Anthropic(max_retries=2, timeout=180)

    def generate(document: str, chunk: str) -> ClaudeContextResult:
        prompt = contextual_retrieval_prompt(document, chunk)
        with client.beta.messages.stream(
            model=model,
            max_tokens=256,
            system=prompt["system"],
            messages=[{
                "role": "user",
                "content": [{"type": "text", "text": prompt["message"]}],
            }],
            betas=[FALLBACK_BETA],
            fallbacks="default",
        ) as stream:
            message = stream.get_final_message()
        if message.stop_reason == "refusal":
            category = (
                getattr(message.stop_details, "category", None)
                if message.stop_details else None
            )
            raise ClaudeRefusalError(
                f"Claude declined contextualization (category: {category})"
            )
        text = "".join(block.text for block in message.content if block.type == "text")
        usage = message.usage
        return {
            "context": " ".join(text.split()).strip(),
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cache_creation_input_tokens": usage.cache_creation_input_tokens or 0,
            "cache_read_input_tokens": usage.cache_read_input_tokens or 0,
        }

    return generate


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _write_jsonl_atomic(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    temporary.replace(path)


def contextualize_candidate(
    run_dir: Path,
    *,
    model: str = CLAUDE_MODEL,
    generate_context: ContextGenerator | None = None,
    event_sink: EventSink | None = None,
) -> Path:
    """Contextualize every canonical chunk, checkpointing after every Claude call."""
    run_dir = run_dir.resolve()
    candidate = run_dir / "candidate"
    document_path = candidate / "document.md"
    chunks_path = candidate / "chunks.jsonl"
    output_path = candidate / "contextual-chunks.jsonl"
    metadata_path = candidate / "contextual-retrieval.json"
    if not document_path.is_file() or not chunks_path.is_file():
        raise FileNotFoundError(f"Canonical candidate is incomplete: {run_dir}")

    document = document_path.read_text(encoding="utf-8")
    if not document.strip():
        raise ValueError(f"Canonical candidate document.md is empty: {run_dir}")
    chunks = _read_jsonl(chunks_path)
    completed = {record["chunk_id"]: record for record in _read_jsonl(output_path)}
    generate = generate_context or make_claude_context_generator(model)
    records: list[dict[str, Any]] = []

    for index, chunk in enumerate(chunks, 1):
        chunk_id = chunk["chunk_id"]
        existing = completed.get(chunk_id)
        if (
            existing
            and existing.get("source_sha256") == chunk.get("source_sha256")
            and existing.get("text") == chunk.get("text")
            and existing.get("contextual_retrieval_prompt_version") == PROMPT_VERSION
            and existing.get("contextual_retrieval_model") == model
            and isinstance(existing.get("prompt_cache"), dict)
        ):
            record = existing
            status = "reused"
        else:
            generated = generate(document, chunk["text"])
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
                usage = {key: generated[key] for key in (
                    "input_tokens",
                    "output_tokens",
                    "cache_creation_input_tokens",
                    "cache_read_input_tokens",
                )}
            if not context:
                raise RuntimeError(f"Claude returned empty context for {chunk_id}")
            record = {
                **chunk,
                "retrieval_context": context,
                "contextual_retrieval_text": f"{context}\n\n{chunk['text']}",
                "contextual_retrieval_model": model,
                "contextual_retrieval_prompt_version": PROMPT_VERSION,
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
                "document_id": chunk["document_id"],
                "chunk_id": chunk_id,
                "index": index,
                "total": len(chunks),
                "status": status,
                "prompt_cache": record.get("prompt_cache", {}),
            })

    metadata = {
        "schema_version": 1,
        "prompt_version": PROMPT_VERSION,
        "model": model,
        "whole_document_chars": len(document),
        "chunk_count": len(chunks),
        "completed_count": len(records),
        "cache_creation_input_tokens": sum(
            record.get("prompt_cache", {}).get("cache_creation_input_tokens", 0)
            for record in records
        ),
        "cache_read_input_tokens": sum(
            record.get("prompt_cache", {}).get("cache_read_input_tokens", 0)
            for record in records
        ),
        "output": output_path.name,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "indexing_note": (
            "Use contextual_retrieval_text for contextual embeddings and contextual BM25; "
            "retain text for display and evidence verification."
        ),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return output_path
