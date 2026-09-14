from __future__ import annotations

from pathlib import Path

from .agent import ReferenceAgent
from .audit import AuditLogger
from .knowledge import load_knowledge
from .repository import ClaimRepository
from .retrieval import (
    HashingEmbeddingProvider,
    InMemoryVectorIndex,
    SentenceTransformerEmbeddingProvider,
)
from .tools import ReferenceTools


def build_agent(
    *,
    semantic_model: str | None = None,
    audit_path: Path | None = None,
) -> ReferenceAgent:
    agentic_root = Path(__file__).resolve().parents[2]
    geha_root = agentic_root.parent
    chunks = load_knowledge(agentic_root / "data" / "public_reference.json")
    embedder = (
        SentenceTransformerEmbeddingProvider(semantic_model)
        if semantic_model
        else HashingEmbeddingProvider()
    )
    index = InMemoryVectorIndex(chunks, embedder)
    claims = ClaimRepository(geha_root / "claims" / "claims.json")
    tools = ReferenceTools(claims, index, AuditLogger(audit_path))
    return ReferenceAgent(tools)
