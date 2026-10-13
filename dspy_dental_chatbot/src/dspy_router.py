"""DSPy semantic classifier implementing the enrollment graph extractor protocol."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import dspy


class ClassifyMemberAnswer(dspy.Signature):
    """Map only explicitly stated facts to the supplied choice keys.

    Do not decide benefit eligibility or invent missing facts. If no choice is
    supported, return ``unsure``. If two choices are genuinely supported,
    return the best key in ``label``, the other in ``second_label``, and set
    ``ambiguous`` to true.
    """

    question: str = dspy.InputField(desc="The current enrollment question.")
    options_json: str = dspy.InputField(desc="JSON object mapping allowed keys to their meanings.")
    member_answer: str = dspy.InputField(desc="The member's exact free-text answer.")
    label: str = dspy.OutputField(desc="Exactly one supplied option key, or unsure.")
    second_label: str = dspy.OutputField(desc="A second supplied key only when ambiguous; otherwise none.")
    ambiguous: bool = dspy.OutputField(desc="True only when two supplied choices are explicitly supported.")


def configure_lm() -> dspy.LM:
    """Configure DSPy from provider-neutral environment variables."""
    model = os.getenv("DSPY_MODEL", "").strip()
    if not model:
        raise RuntimeError("DSPY_MODEL is required (for example, openai/gpt-4o-mini)")

    api_key = (
        os.getenv("DSPY_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("OPENROUTER_API_KEY")
        or os.getenv("NOUS_KEY")
    )
    kwargs: dict[str, Any] = {}
    if api_key:
        kwargs["api_key"] = api_key
    if api_base := os.getenv("DSPY_API_BASE", "").strip():
        kwargs["api_base"] = api_base

    cache = os.getenv("DSPY_CACHE", "1").strip().lower() not in {"0", "false", "no"}
    lm = dspy.LM(model, cache=cache, **kwargs)
    dspy.configure(lm=lm)
    return lm


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


class DspyExtractor:
    """Return ``one``, ``ambiguous``, or ``none`` for DentalEnrollmentGraph."""

    name = "dspy"

    def __init__(self, program=None, program_path: str | None = None):
        self.lm = None
        if program is None:
            self.lm = configure_lm()
            program = dspy.Predict(ClassifyMemberAnswer)
            saved = program_path or os.getenv("DSPY_PROGRAM_PATH", "").strip()
            if saved:
                program.load(str(Path(saved).expanduser()))
        self.program = program

    def __call__(self, question: str, options: dict[str, str], message: str) -> dict[str, Any]:
        prediction = self.program(
            question=question,
            options_json=json.dumps(options, sort_keys=True),
            member_answer=message,
        )
        valid = set(options)
        label = str(getattr(prediction, "label", "")).strip()
        second = str(getattr(prediction, "second_label", "")).strip()

        if label not in valid:
            return {
                "decision": "none", "label": None, "candidates": [],
                "reason": f"DSPy returned unsupported label {label!r}",
            }
        if _bool(getattr(prediction, "ambiguous", False)) and second in valid and second != label:
            return {
                "decision": "ambiguous", "label": None,
                "candidates": [label, second], "reason": "DSPy found two explicit choices",
            }
        return {
            "decision": "one", "label": label, "candidates": [],
            "reason": "DSPy semantic classification",
        }


def build_program():
    """Factory shared by the app and offline optimizer."""
    configure_lm()
    return dspy.Predict(ClassifyMemberAnswer)
