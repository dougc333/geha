"""Whole-document contextual retrieval and local vector indexing for forms."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, TypedDict

from .page_contextual_retrieval import (
    CLAUDE_MODEL,
    FALLBACK_BETA,
    discover_page_chunks,
)


PROMPT_VERSION = "anthropic-whole-form-context-v1"
SYSTEM_PROMPT = (
    "You prepare concise context for retrieval indexing. Use only the supplied "
    "form or application. Do not fill it in, answer it, add advice, or introduce "
    "facts absent from the document."
)
USER_PROMPT = """Summarize this complete form or application for search retrieval.
Preserve the form name, issuing organization, purpose, intended applicant, major
sections, required information, and submission instructions. Return only one
concise factual retrieval context. The complete source remains authoritative."""


class ClaudeFormResult(TypedDict):
    context: str
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int


FormContextGenerator = Callable[[str], str | ClaudeFormResult]
Embedder = Callable[[str], list[float]]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def _read_single_jsonl(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
    return json.loads(lines[0]) if len(lines) == 1 else None


def make_claude_form_context_generator(
    model: str = CLAUDE_MODEL,
) -> FormContextGenerator:
    """Use the direct Anthropic call and cache block used by page context runs."""
    import anthropic

    client = anthropic.Anthropic(max_retries=2, timeout=180)

    def generate(document: str) -> ClaudeFormResult:
        with client.beta.messages.stream(
            model=model,
            max_tokens=700,
            system=[
                {"type": "text", "text": SYSTEM_PROMPT},
                {
                    "type": "text",
                    "text": f"<document>\n{document}\n</document>",
                    "cache_control": {"type": "ephemeral"},
                },
            ],
            messages=[{
                "role": "user",
                "content": [{"type": "text", "text": USER_PROMPT}],
            }],
            betas=[FALLBACK_BETA],
            fallbacks="default",
        ) as stream:
            message = stream.get_final_message()
        if message.stop_reason == "refusal":
            raise RuntimeError("Claude declined whole-form contextualization")
        context = " ".join(
            "".join(block.text for block in message.content if block.type == "text").split()
        ).strip()
        usage = message.usage
        return {
            "context": context,
            "input_tokens": int(usage.input_tokens),
            "output_tokens": int(usage.output_tokens),
            "cache_creation_input_tokens": int(
                usage.cache_creation_input_tokens or 0
            ),
            "cache_read_input_tokens": int(usage.cache_read_input_tokens or 0),
        }

    return generate


def make_local_embedder(
    model: str = "BAAI/bge-small-en-v1.5",
) -> Embedder:
    """Create an on-device normalized embedder; form text never leaves the host."""
    from sentence_transformers import SentenceTransformer

    encoder = SentenceTransformer(model, local_files_only=True)

    def embed(text: str) -> list[float]:
        vector = encoder.encode(
            [text],
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]
        return [float(value) for value in vector.tolist()]

    return embed


class FormVectorStore:
    """SQLite-backed vector records with explicit links to filesystem sources."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS form_embeddings (
                    document_id TEXT PRIMARY KEY,
                    chunk_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    source_uri TEXT NOT NULL,
                    retrieval_context TEXT NOT NULL,
                    contextual_retrieval_text TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    embedding_model TEXT NOT NULL,
                    embedding_dimensions INTEGER NOT NULL,
                    document_sha256 TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def upsert(self, record: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO form_embeddings (
                    document_id, chunk_id, filename, source_path, source_uri,
                    retrieval_context, contextual_retrieval_text, embedding_json,
                    embedding_model, embedding_dimensions, document_sha256, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    chunk_id=excluded.chunk_id,
                    filename=excluded.filename,
                    source_path=excluded.source_path,
                    source_uri=excluded.source_uri,
                    retrieval_context=excluded.retrieval_context,
                    contextual_retrieval_text=excluded.contextual_retrieval_text,
                    embedding_json=excluded.embedding_json,
                    embedding_model=excluded.embedding_model,
                    embedding_dimensions=excluded.embedding_dimensions,
                    document_sha256=excluded.document_sha256,
                    updated_at=excluded.updated_at
                """,
                (
                    record["document_id"],
                    record["chunk_id"],
                    record["filename"],
                    record["source_path"],
                    record["source_uri"],
                    record["retrieval_context"],
                    record["contextual_retrieval_text"],
                    json.dumps(record["embedding"]),
                    record["embedding_model"],
                    record["embedding_dimensions"],
                    record["document_sha256"],
                    record["contextualized_at"],
                ),
            )

    def list(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT document_id, chunk_id, filename, source_path, source_uri,
                       retrieval_context, embedding_model, embedding_dimensions,
                       document_sha256, updated_at
                FROM form_embeddings ORDER BY filename
                """
            ).fetchall()
        return [dict(row) for row in rows]


def assemble_whole_form(
    pages_dir: Path,
    *,
    preferred_engine: str | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    pages = discover_page_chunks(pages_dir, preferred_engine=preferred_engine)
    if not pages:
        raise ValueError(f"No extracted page Markdown found under {pages_dir}")
    document = "\n\n".join(
        f"<page number=\"{page['page']}\">\n{page['text']}\n</page>"
        for page in pages
    )
    return document, pages


def contextualize_whole_form(
    *,
    document_id: str,
    filename: str,
    document_dir: Path,
    pages_dir: Path,
    output_dir: Path,
    vector_store: FormVectorStore,
    preferred_engine: str | None = None,
    context_model: str = CLAUDE_MODEL,
    embedding_model: str = "BAAI/bge-small-en-v1.5",
    generate_context: FormContextGenerator | None = None,
    embed_text: Embedder | None = None,
) -> dict[str, Any]:
    """Create exactly one context, embedding, and vector row for one form."""
    document, pages = assemble_whole_form(
        pages_dir,
        preferred_engine=preferred_engine,
    )
    document_sha256 = _sha256(document)
    output_path = output_dir / "whole-document-context.jsonl"
    existing = _read_single_jsonl(output_path)
    source_path = document_dir / "source.pdf"
    source_uri = f"/api/documents/{document_id}/source"
    if (
        existing
        and existing.get("document_sha256") == document_sha256
        and existing.get("context_model") == context_model
        and existing.get("embedding_model") == embedding_model
        and existing.get("prompt_version") == PROMPT_VERSION
        and isinstance(existing.get("embedding"), list)
    ):
        record = existing
        reused = True
    else:
        _write_json_atomic(output_dir / "contextual-retrieval.json", {
            "schema_version": "1.0",
            "status": "running",
            "document_id": document_id,
            "filename": filename,
            "model": context_model,
            "prompt_version": PROMPT_VERSION,
            "storage_strategy": "whole_document",
            "source_page_count": len(pages),
            "retrieval_units": 1,
            "total_pages": 1,
            "completed_pages": 0,
            "current_page": 1,
            "error": None,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "source_path": str(source_path),
            "source_uri": source_uri,
            "vector_database": str(vector_store.path),
            "pages": [{
                "page": 1,
                "chunk_id": f"{document_id}:whole-document",
                "source_markdown": "whole-document",
                "status": "processing",
                "contextualized_at": None,
                "prompt_cache": {},
            }],
            "updated_at": utc_now(),
        })
        generator = generate_context or make_claude_form_context_generator(context_model)
        embedder = embed_text or make_local_embedder(embedding_model)
        generated = generator(document)
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
            raise RuntimeError("Claude returned empty whole-form context")
        contextual_text = f"{context}\n\n{document}"
        # The complete form remains in contextual_retrieval_text and the vector
        # database row. The concise context is the semantic routing vector;
        # embedding a long blank form would truncate useful retrieval terms.
        embedding = embedder(context)
        if not embedding:
            raise RuntimeError("Embedding model returned an empty vector")
        timestamp = utc_now()
        record = {
            "schema_version": "1.0",
            "document_id": document_id,
            "chunk_id": f"{document_id}:whole-document",
            "chunk_index": 0,
            "filename": filename,
            "source_name": filename,
            "source_path": str(source_path),
            "source_uri": source_uri,
            "source_page_count": len(pages),
            "text": document,
            "retrieval_context": context,
            "contextual_retrieval_text": contextual_text,
            "embedding": embedding,
            "embedding_dimensions": len(embedding),
            "context_model": context_model,
            "embedding_model": embedding_model,
            "embedding_input": "retrieval_context",
            "prompt_version": PROMPT_VERSION,
            "prompt_cache": usage,
            "document_sha256": document_sha256,
            "contextualized_at": timestamp,
            "metadata": {
                "document_type": "form_application",
                "route": "whole_document_context",
                "storage_strategy": "whole_document",
                "retrieval_units": 1,
                "source_pdf": str(source_path),
                "source_uri": source_uri,
            },
            "review_status": "pending",
        }
        _write_jsonl_atomic(output_path, [record])
        reused = False
    vector_store.upsert(record)
    status = {
        "schema_version": "1.0",
        "status": "complete",
        "document_id": document_id,
        "filename": filename,
        "model": context_model,
        "prompt_version": PROMPT_VERSION,
        "storage_strategy": "whole_document",
        "source_page_count": len(pages),
        "retrieval_units": 1,
        "total_pages": 1,
        "completed_pages": 1,
        "current_page": None,
        "error": None,
        "cache_creation_input_tokens": record.get("prompt_cache", {}).get(
            "cache_creation_input_tokens", 0
        ),
        "cache_read_input_tokens": record.get("prompt_cache", {}).get(
            "cache_read_input_tokens", 0
        ),
        "source_path": str(source_path),
        "source_uri": source_uri,
        "context_artifact": str(output_path),
        "vector_database": str(vector_store.path),
        "embedding_model": embedding_model,
        "embedding_dimensions": record["embedding_dimensions"],
        "pages": [{
            "page": 1,
            "chunk_id": record["chunk_id"],
            "source_markdown": "whole-document",
            "status": "complete",
            "contextualized_at": record["contextualized_at"],
            "prompt_cache": record.get("prompt_cache", {}),
        }],
        "last_page_status": "reused" if reused else "generated",
        "updated_at": utc_now(),
    }
    _write_json_atomic(output_dir / "contextual-retrieval.json", status)
    return status
