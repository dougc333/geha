from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Citation:
    title: str
    url: str
    page: int | None = None
    section: str | None = None


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    text: str
    citation: Citation
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UserContext:
    """Identity attributes supplied by a trusted authentication layer.

    The demo accepts this object directly. A production API must construct it
    from verified identity-provider claims, never from request-body assertions.
    """

    actor_id: str
    role: str
    subject_member_ids: frozenset[str] = frozenset()
    authorized_claim_ids: frozenset[str] = frozenset()


@dataclass
class AgentResponse:
    intent: str
    answer: str
    citations: list[Citation] = field(default_factory=list)
    needs_human_review: bool = False
    review_reason: str | None = None
    audit_id: str | None = None
    structured_data: dict[str, Any] = field(default_factory=dict)

