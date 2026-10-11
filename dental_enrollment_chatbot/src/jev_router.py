"""Optional TypeSafe Jev classifier for ambiguous natural-language answers.

The state machine always owns eligibility and recommendation decisions. Jev is
only an input normalizer and is called only when deterministic parsing fails.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import tracing

try:
    from typesafe_sdk import Choice, TypeSafeClient
except ImportError:  # The deterministic flow remains usable without the SDK.
    Choice = TypeSafeClient = None


CHOICES: dict[str, dict[str, str]] = {
    "member_type": {
        "active_employee": "Active civilian federal employee.",
        "federal_retiree": "Federal retiree or annuitant.",
        "retired_uniformed": "Retired uniformed service member.",
        "eligible_family": "Eligible family member of an eligible enrollee.",
        "unclear": "None is explicit or the answer is ambiguous.",
    },
    "opportunity": {
        "open_season": "Enrolling during the stated Open Season.",
        "newly_eligible_or_qle": "Newly eligible or has a qualifying life event.",
        "unsure": "Does not know whether there is a valid enrollment opportunity.",
    },
    "opportunity_detail": {
        "newly_eligible": "New hire or newly eligible for FEDVIP dental coverage.",
        "qle": "Qualifying life event or QLE outside Open Season.",
        "unsure": "The answer does not distinguish newly eligible from QLE.",
    },
    "qle_event": {
        "marriage": "Marriage.",
        "acquire_family_member": "Acquiring an eligible non-spouse family member.",
        "lose_family_member": "Losing a covered family member.",
        "lose_other_coverage": "Losing other dental or vision coverage.",
        "move_service_area": "Moving out of a regional plan service area.",
        "active_military_nonpay": "Going on active military duty in non-pay status.",
        "return_active_military": "Returning to pay status from active military duty.",
        "return_lwop": "Returning to pay status from Leave Without Pay or LWOP.",
        "annuity_restored": "Annuity or compensation restored.",
        "transfer_eligible_position": "Transferring to an eligible position.",
        "unsure": "No single listed qualifying life event is explicit.",
    },
    "need": {
        "routine": "Primarily preventive or routine dental care and lowest premium.",
        "major": "Upcoming major work such as root canal, crown, bridge, dentures, or surgery.",
        "orthodontia": "Child or adult orthodontic treatment.",
        "maximum": "Wants maximum coverage, unlimited annual maximum, or a third adult cleaning.",
        "unsure": "No clear preference or treatment need.",
    },
}


@lru_cache(maxsize=1)
def _client():
    if TypeSafeClient is None:
        raise RuntimeError("typesafe-sdk is not installed")
    return TypeSafeClient(api_key=os.environ["TYPESAFE_API_KEY"])


def classify(message: str, field: str) -> dict[str, Any] | None:
    """Return a confident normalized label, or ``None`` to ask again safely."""
    if field not in CHOICES or not os.environ.get("TYPESAFE_API_KEY") or Choice is None:
        return None
    try:
        question = Choice(
            instructions="Classify only what the member explicitly states. Do not infer eligibility.",
            criteria=CHOICES[field],
        )
        response = _client().system_one(
            state={"member_answer": message}, questions={field: question}
        )
        answer = response.choices[field]
        if float(answer.confidence) < 0.70 or answer.choice in {"unclear", "unsure"}:
            return None
        return {
            "value": answer.choice,
            "confidence": float(answer.confidence),
            "model": response.model,
            "probabilities": dict(answer.probabilities),
        }
    except Exception:
        return None


class JevExtractor:
    """Map a free-text answer onto a stage's options with Jev's Choice probabilities.

    Drop-in replacement for llm_extract.BedrockExtractor. Two close top options
    become a clarifying question; low confidence or "unsure" becomes "none".
    Raises when Jev is unavailable, so the graph falls back to the keyword parser.
    """
    name = "jev"

    def __init__(self, min_confidence: float = 0.5, ask_margin: float = 0.25):
        self.min_confidence = min_confidence  # tune on a dev set, not the test set
        self.ask_margin = ask_margin

    def __call__(self, question: str, options: dict[str, str], message: str) -> dict:
        if Choice is None or not os.environ.get("TYPESAFE_API_KEY"):
            raise RuntimeError("Jev unavailable: typesafe-sdk or TYPESAFE_API_KEY missing")
        criteria = {**options, "unsure": "None of the options is explicit in the reply."}
        choice = Choice(
            instructions=f"{question} Classify only what the member explicitly states. "
                         "Do not infer eligibility.",
            criteria=criteria,
        )
        with tracing.generation("extract-answer", "jev", message) as generation:
            response = _client().system_one(state={"member_answer": message}, questions={"q": choice})
            ranked = sorted(((k, float(v)) for k, v in response.choices["q"].probabilities.items()),
                            key=lambda kv: -kv[1])
            (top, p1), (second, p2) = ranked[0], ranked[1]
            if top == "unsure" or p1 < self.min_confidence:
                result = {"decision": "none", "label": None, "candidates": []}
            elif p1 - p2 < self.ask_margin and second != "unsure":
                result = {"decision": "ambiguous", "label": None, "candidates": [top, second]}
            else:
                result = {"decision": "one", "label": top, "candidates": []}
            result["reason"] = f"top {top}={p1:.2f}, next {second}={p2:.2f}"
            if generation is not None:
                generation.update(model=response.model, output={**result, "probabilities": dict(ranked)})
        return result
