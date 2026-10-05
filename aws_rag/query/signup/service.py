"""Signup application service: compute outside transactions, persist atomically."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .graph import prompt_for, transition


BenefitAnswerer = Callable[[str, list[str]], tuple[str, list[dict[str, Any]]]]


def initial_reply(application: dict[str, Any]) -> dict[str, Any]:
    return {
        "application": application,
        "reply": (
            "I’ll guide you through dental plan signup and can answer benefit questions along the way. "
            + prompt_for(application["stage"], application["slots"])
        ),
        "event": "created",
        "sources": [],
    }


def process_turn(
    application: dict[str, Any],
    message: str,
    slot_updates: dict[str, Any],
    document_ids: list[str],
    benefit_answerer: BenefitAnswerer,
) -> dict[str, Any]:
    result = transition(
        application["stage"],
        application["status"],
        application["slots"],
        message,
        slot_updates,
    )
    sources: list[dict[str, Any]] = []
    reply = result.reply
    if result.benefit_question:
        if document_ids:
            answer, sources = benefit_answerer(message, document_ids)
            reply = f"{answer}\n\nTo continue signup: {prompt_for(result.stage, result.slots)}"
        else:
            reply = (
                "The benefits brochure has not been mapped to this plan year yet. "
                f"To continue signup: {prompt_for(result.stage, result.slots)}"
            )
    updated = {
        **application,
        "stage": result.stage,
        "status": result.status,
        "slots": result.slots,
    }
    return {
        "application": updated,
        "reply": reply,
        "event": result.event,
        "sources": sources,
    }

