"""Build reviewable, provenance-rich retrieval chunks."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Iterable

from ..models import ChunkRecord


SPACE_RE = re.compile(r"[ \t]+")


def clean_text(value: str) -> str:
    lines = [SPACE_RE.sub(" ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def build_chunk_records(
    raw_chunks: Iterable[dict[str, Any]],
    *,
    document_id: str,
    document_version: str,
    plan_year: int | None,
    source_sha256: str,
) -> list[ChunkRecord]:
    records: list[ChunkRecord] = []
    for ordinal, raw in enumerate(raw_chunks, 1):
        text = clean_text(str(raw.get("text") or ""))
        pages = sorted({int(page) for page in raw.get("pages") or [] if int(page) > 0})
        headings = [clean_text(str(value)) for value in raw.get("headings") or []]
        headings = [value for value in headings if value]
        section = headings[-1] if headings else "Unsectioned"
        context = " | ".join(
            part for part in (document_id, f"pages {','.join(map(str, pages))}" if pages else "", section)
            if part
        )
        records.append({
            "chunk_id": f"{document_id}-chunk-{ordinal:04d}",
            "document_id": document_id,
            "document_version": document_version,
            "plan_year": plan_year,
            "pages": pages,
            "section": section,
            "content_type": "text",
            "text": text,
            "contextualized_text": f"{context}\n\n{text}" if text else context,
            "table_ids": list(raw.get("table_ids") or []),
            "source_sha256": source_sha256,
            "review_status": "pending",
        })
    return records


def validate_chunks(records: Iterable[ChunkRecord]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    errors: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    seen: set[str] = set()
    for record in records:
        chunk_id = record["chunk_id"]
        if chunk_id in seen:
            errors.append({"chunk_id": chunk_id, "issue": "duplicate_chunk_id"})
        seen.add(chunk_id)
        if not record["text"]:
            errors.append({"chunk_id": chunk_id, "issue": "empty_text"})
        if not record["pages"]:
            errors.append({"chunk_id": chunk_id, "issue": "missing_page_provenance"})
        if record["section"] == "Unsectioned":
            warnings.append({"chunk_id": chunk_id, "issue": "missing_section_heading"})
        if len(record["text"].split()) < 8:
            warnings.append({"chunk_id": chunk_id, "issue": "context_too_short"})
    return errors, warnings


def validate_embedding_token_lengths(
    records: Iterable[ChunkRecord],
    *,
    encode: Callable[[str], list[int]],
    max_tokens: int,
) -> list[dict[str, object]]:
    """Reject candidate chunks that cannot be embedded without truncation."""
    errors: list[dict[str, object]] = []
    for record in records:
        token_count = len(encode(record["contextualized_text"]))
        if token_count > max_tokens:
            errors.append({
                "chunk_id": record["chunk_id"],
                "issue": "embedding_token_limit_exceeded",
                "token_count": token_count,
                "max_tokens": max_tokens,
            })
    return errors


def write_jsonl(path: Path, records: Iterable[ChunkRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
