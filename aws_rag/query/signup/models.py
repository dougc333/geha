"""API and domain models for guided member signup."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


Product = Literal["dental"]
Stage = Literal[
    "eligibility",
    "household",
    "plan_selection",
    "contact",
    "review",
    "completed",
    "handoff",
]
Status = Literal["active", "completed", "handoff"]

ALLOWED_SLOT_UPDATES = {
    "eligible",
    "coverage_type",
    "selected_plan",
    "postal_code",
    "email",
}


class CreateSignupRequest(BaseModel):
    product: Product = "dental"
    coverage_year: int = Field(default=2026, ge=2026, le=2030)


class SignupMessageRequest(BaseModel):
    client_message_id: UUID
    message: str = Field(min_length=1, max_length=4000)
    expected_version: int = Field(ge=0)
    slot_updates: dict[str, Any] = Field(default_factory=dict)

    @field_validator("slot_updates")
    @classmethod
    def validate_slot_names(cls, value: dict[str, Any]) -> dict[str, Any]:
        unknown = set(value) - ALLOWED_SLOT_UPDATES
        if unknown:
            raise ValueError(f"Unsupported signup fields: {', '.join(sorted(unknown))}")
        return value


class SignupApplication(BaseModel):
    id: UUID
    member_ref: str
    product: Product
    coverage_year: int
    stage: Stage
    status: Status
    slots: dict[str, Any]
    version: int


class SignupTurnResponse(BaseModel):
    application: SignupApplication
    reply: str
    event: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    trace_id: str | None = None
    idempotent_replay: bool = False
