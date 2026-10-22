"""Page-granular Claude contextual retrieval with resumable checkpoints.

The complete extracted document is kept in Claude's cacheable system prefix.
Only the current page changes between requests.  Each successful page is
written immediately so an interrupted run resumes at the first stale page.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, TypedDict


CLAUDE_MODEL = "claude-sonnet-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
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


class ClaudeContextResult(TypedDict):
    context: str
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int


ContextGenerator = Callable[[str, str], str | ClaudeContextResult]
ProgressSink = Callable[[dict[str, Any]], None]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def contextual_retrieval_prompt(document: str, chunk: str) -> dict[str, Any]:
    """Return the same cacheable prompt contract used by the crawler pipeline."""
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
    """Create one reusable Anthropic client for all pages in one document."""
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
            raise RuntimeError(
                f"Claude declined contextualization (category: {category})"
            )
        text = "".join(block.text for block in message.content if block.type == "text")
        usage = message.usage
        return {
            "context": " ".join(text.split()).strip(),
            "input_tokens": int(usage.input_tokens),
            "output_tokens": int(usage.output_tokens),
            "cache_creation_input_tokens": int(
                usage.cache_creation_input_tokens or 0
            ),
            "cache_read_input_tokens": int(usage.cache_read_input_tokens or 0),
        }

    return generate


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _write_jsonl_atomic(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    temporary.replace(path)


def discover_page_chunks(
    pages_dir: Path,
    *,
    preferred_engine: str | None = None,
) -> list[dict[str, Any]]:
    """Load one retrieval chunk per page using the best available Markdown."""
    preferred = f"{preferred_engine}.md" if preferred_engine else None
    candidates = [
        "docling.normalized.md",
        preferred,
        "llamaparse.md",
        "deepseek.md",
        "docling.md",
    ]
    ordered_names = [name for index, name in enumerate(candidates) if name and name not in candidates[:index]]
    chunks: list[dict[str, Any]] = []
    for page_dir in sorted(pages_dir.glob("page-[0-9][0-9][0-9]")):
        page_number = int(page_dir.name.removeprefix("page-"))
        markdown_path = next(
            (page_dir / name for name in ordered_names if (page_dir / name).is_file()),
            None,
        )
        if markdown_path is None:
            continue
        text = markdown_path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        chunks.append({
            "page": page_number,
            "chunk_id": page_dir.name,
            "text": text,
            "source_markdown": str(markdown_path.relative_to(pages_dir.parent)),
            "source_sha256": _sha256(text),
        })
    return chunks


def _summary(
    *,
    status: str,
    document_id: str,
    filename: str,
    model: str,
    document_sha256: str,
    chunks: list[dict[str, Any]],
    records: list[dict[str, Any]],
    current_page: int | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    completed = {record["page"]: record for record in records}
    pages = []
    for chunk in chunks:
        record = completed.get(chunk["page"])
        pages.append({
            "page": chunk["page"],
            "chunk_id": chunk["chunk_id"],
            "source_markdown": chunk["source_markdown"],
            "status": "complete" if record else (
                "processing" if chunk["page"] == current_page else "pending"
            ),
            "contextualized_at": record.get("contextualized_at") if record else None,
            "prompt_cache": record.get("prompt_cache", {}) if record else {},
        })
    return {
        "schema_version": "1.0",
        "status": status,
        "document_id": document_id,
        "filename": filename,
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "document_sha256": document_sha256,
        "total_pages": len(chunks),
        "completed_pages": len(records),
        "current_page": current_page,
        "error": error,
        "cache_creation_input_tokens": sum(
            item.get("prompt_cache", {}).get("cache_creation_input_tokens", 0)
            for item in records
        ),
        "cache_read_input_tokens": sum(
            item.get("prompt_cache", {}).get("cache_read_input_tokens", 0)
            for item in records
        ),
        "pages": pages,
        "updated_at": utc_now(),
    }


def contextualize_pages(
    *,
    document_id: str,
    filename: str,
    pages_dir: Path,
    output_dir: Path,
    preferred_engine: str | None = None,
    model: str = CLAUDE_MODEL,
    generate_context: ContextGenerator | None = None,
    progress_sink: ProgressSink | None = None,
) -> dict[str, Any]:
    """Contextualize extracted pages sequentially and checkpoint every page."""
    chunks = discover_page_chunks(pages_dir, preferred_engine=preferred_engine)
    if not chunks:
        raise ValueError(f"No extracted page Markdown found under {pages_dir}")
    document = "\n\n".join(
        f"<page number=\"{chunk['page']}\">\n{chunk['text']}\n</page>"
        for chunk in chunks
    )
    document_sha256 = _sha256(document)
    output_path = output_dir / "contextual-pages.jsonl"
    metadata_path = output_dir / "contextual-retrieval.json"
    previous = {record["page"]: record for record in _read_jsonl(output_path)}
    records: list[dict[str, Any]] = []
    generate = generate_context or make_claude_context_generator(model)

    for chunk in chunks:
        prior = previous.get(chunk["page"])
        if (
            prior
            and prior.get("source_sha256") == chunk["source_sha256"]
            and prior.get("document_sha256") == document_sha256
            and prior.get("contextual_retrieval_prompt_version") == PROMPT_VERSION
            and prior.get("contextual_retrieval_model") == model
        ):
            records.append(prior)
            page_status = "reused"
        else:
            running = _summary(
                status="running",
                document_id=document_id,
                filename=filename,
                model=model,
                document_sha256=document_sha256,
                chunks=chunks,
                records=records,
                current_page=chunk["page"],
            )
            _write_json_atomic(metadata_path, running)
            if progress_sink:
                progress_sink(running)
            generated = generate(document, chunk["text"])
            if isinstance(generated, str):
                context = " ".join(generated.split()).strip()
                usage = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                }
            else:
                context = generated["context"]
                usage = {
                    key: int(generated.get(key, 0))
                    for key in (
                        "input_tokens",
                        "output_tokens",
                        "cache_creation_input_tokens",
                        "cache_read_input_tokens",
                    )
                }
            if not context:
                raise RuntimeError(f"Claude returned empty context for {chunk['chunk_id']}")
            records.append({
                **chunk,
                "retrieval_context": context,
                "contextual_retrieval_text": f"{context}\n\n{chunk['text']}",
                "document_sha256": document_sha256,
                "contextual_retrieval_model": model,
                "contextual_retrieval_prompt_version": PROMPT_VERSION,
                "contextualized_at": utc_now(),
                "prompt_cache": usage,
            })
            page_status = "generated"
        _write_jsonl_atomic(output_path, records)
        checkpoint = _summary(
            status="running",
            document_id=document_id,
            filename=filename,
            model=model,
            document_sha256=document_sha256,
            chunks=chunks,
            records=records,
        )
        checkpoint["last_page_status"] = page_status
        _write_json_atomic(metadata_path, checkpoint)
        if progress_sink:
            progress_sink(checkpoint)

    complete = _summary(
        status="complete",
        document_id=document_id,
        filename=filename,
        model=model,
        document_sha256=document_sha256,
        chunks=chunks,
        records=records,
    )
    complete["output"] = output_path.name
    _write_json_atomic(metadata_path, complete)
    if progress_sink:
        progress_sink(complete)
    return complete


def read_contextual_status(output_dir: Path) -> dict[str, Any] | None:
    path = output_dir / "contextual-retrieval.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def read_contextual_page(output_dir: Path, page_number: int) -> dict[str, Any] | None:
    for record in _read_jsonl(output_dir / "contextual-pages.jsonl"):
        if record.get("page") == page_number:
            return record
    return None
