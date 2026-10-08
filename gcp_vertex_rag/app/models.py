"""API and domain models."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class RetrievedContext:
    text: str
    source_uri: str
    score: float | None = None


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class Citation(BaseModel):
    id: int
    source_uri: str
    score: float | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    grounded: bool

