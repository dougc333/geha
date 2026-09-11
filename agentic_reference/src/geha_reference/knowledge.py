from __future__ import annotations

import json
from pathlib import Path

from .models import Citation, KnowledgeChunk


def load_knowledge(path: Path) -> list[KnowledgeChunk]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    chunks = []
    for item in payload:
        source = item["source"]
        chunks.append(
            KnowledgeChunk(
                chunk_id=item["chunk_id"],
                text=item["text"],
                citation=Citation(
                    title=source["title"],
                    url=source["url"],
                    page=source.get("page"),
                    section=source.get("section"),
                ),
                metadata=item.get("metadata", {}),
            )
        )
    return chunks

