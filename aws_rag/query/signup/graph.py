"""Deterministic signup state transitions; RAG never decides enrollment state."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


BENEFIT_TERMS = re.compile(
    r"\b(benefit|cover(?:age|ed|s)?|copay|coinsurance|deductible|cleaning|exam|"
    r"orthodont|braces|root canal|crown|vision|hearing|discount|maximum|implant|"
    r"high plan|standard plan|compare plans?)\b",
    re.I,
)
QUESTION_START = re.compile(r"^\s*(what|which|how|does|do|is|are|will|can|compare|tell me)\b", re.I)
EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
ZIP = re.compile(r"(?<!\d)\d{5}(?:-\d{4})?(?!\d)")


@dataclass(frozen=True)
class Transition:
    stage: str
    status: str
    slots: dict[str, Any]
    reply: str
    event: str
    benefit_question: bool = False


def is_benefit_question(message: str) -> bool:
    return bool(BENEFIT_TERMS.search(message) and ("?" in message or QUESTION_START.search(message)))


def _normalize_updates(message: str, supplied: dict[str, Any]) -> dict[str, Any]:
    updates = dict(supplied)
    lower = message.lower().strip()
    if "eligible" not in updates:
        if re.search(r"\b(no|not eligible|ineligible)\b", lower):
            updates["eligible"] = False
        elif re.search(r"\b(yes|eligible|i am|i'm)\b", lower):
            updates["eligible"] = True
    if "coverage_type" not in updates:
        if "self plus one" in lower or "self + one" in lower:
            updates["coverage_type"] = "self_plus_one"
        elif "family" in lower:
            updates["coverage_type"] = "self_and_family"
        elif re.search(r"\bself only\b", lower):
            updates["coverage_type"] = "self_only"
    if "selected_plan" not in updates:
        if re.search(r"\bhigh(?: plan)?\b", lower):
            updates["selected_plan"] = "high"
        elif re.search(r"\bstandard(?: plan)?\b", lower):
            updates["selected_plan"] = "standard"
    if "email" not in updates and (match := EMAIL.search(message)):
        updates["email"] = match.group(0).lower()
    if "postal_code" not in updates and (match := ZIP.search(message)):
        updates["postal_code"] = match.group(0)
    return updates


def _validate_updates(updates: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    if "eligible" in updates and isinstance(updates["eligible"], bool):
        clean["eligible"] = updates["eligible"]
    if updates.get("coverage_type") in {"self_only", "self_plus_one", "self_and_family"}:
        clean["coverage_type"] = updates["coverage_type"]
    if updates.get("selected_plan") in {"high", "standard"}:
        clean["selected_plan"] = updates["selected_plan"]
    if isinstance(updates.get("email"), str) and EMAIL.fullmatch(updates["email"].strip()):
        clean["email"] = updates["email"].strip().lower()
    if isinstance(updates.get("postal_code"), str) and ZIP.fullmatch(updates["postal_code"].strip()):
        clean["postal_code"] = updates["postal_code"].strip()
    return clean


def prompt_for(stage: str, slots: dict[str, Any]) -> str:
    if stage == "eligibility":
        return "Are you eligible to enroll in a FEDVIP dental plan?"
    if stage == "household":
        return "Which enrollment type do you need: Self Only, Self Plus One, or Self and Family?"
    if stage == "plan_selection":
        return "Which dental plan do you prefer: High or Standard? You can ask me to compare them first."
    if stage == "contact":
        missing = []
        if not slots.get("postal_code"):
            missing.append("ZIP code")
        if not slots.get("email"):
            missing.append("email address")
        return "Please provide your " + " and ".join(missing) + "."
    if stage == "review":
        plan = str(slots.get("selected_plan", "")).title()
        coverage = str(slots.get("coverage_type", "")).replace("_", " ").title()
        email = str(slots.get("email", ""))
        masked = (email[:2] + "***@" + email.split("@", 1)[1]) if "@" in email else "provided"
        return (
            f"Review: {plan} dental, {coverage}, ZIP {slots.get('postal_code')}, "
            f"email {masked}. Reply confirm to finish, or tell me what to change."
        )
    if stage == "completed":
        return "Your guided signup is complete. This does not submit an enrollment to the carrier."
    return "I’ll connect you with a benefits specialist to continue."


def _next_stage(slots: dict[str, Any]) -> tuple[str, str]:
    if slots.get("eligible") is False:
        return "handoff", "handoff"
    if slots.get("eligible") is not True:
        return "eligibility", "active"
    if not slots.get("coverage_type"):
        return "household", "active"
    if not slots.get("selected_plan"):
        return "plan_selection", "active"
    if not slots.get("postal_code") or not slots.get("email"):
        return "contact", "active"
    return "review", "active"


def transition(
    stage: str,
    status: str,
    slots: dict[str, Any],
    message: str,
    supplied_updates: dict[str, Any] | None = None,
) -> Transition:
    if status != "active":
        return Transition(stage, status, dict(slots), prompt_for(stage, slots), "terminal")
    if is_benefit_question(message):
        return Transition(stage, status, dict(slots), "", "benefit_question", True)

    updated = {**slots, **_validate_updates(_normalize_updates(message, supplied_updates or {}))}
    if stage == "review" and re.search(r"\b(confirm|submit|looks good|correct|yes)\b", message, re.I):
        return Transition("completed", "completed", updated, prompt_for("completed", updated), "completed")

    next_stage, next_status = _next_stage(updated)
    event = "handoff" if next_status == "handoff" else "state_advanced" if next_stage != stage else "state_reprompted"
    return Transition(next_stage, next_status, updated, prompt_for(next_stage, updated), event)
