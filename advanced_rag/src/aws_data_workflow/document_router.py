"""Deterministically classify extracted documents for workflow routing."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


POLICY_THRESHOLD = 4
FORM_THRESHOLD = 4

FILENAME_SIGNALS = {
    "coverage-policy": 5,
    "summary-of-benefits-and-coverage": 5,
    "plan-brochure": 5,
    "policy": 3,
    "benefits": 1,
}

TEXT_SIGNALS = {
    "medical coverage policy": 5,
    "coverage policy": 4,
    "summary of benefits and coverage": 5,
    "official statement of benefits": 4,
    "policy number": 2,
    "prior authorization": 1,
    "medical necessity": 1,
    "limitations and exclusions": 1,
    "effective date": 1,
}

NON_POLICY_SIGNALS = {
    "bill of lading": -6,
    "invoice number": -5,
    "amount due": -3,
    "research paper": -3,
}

FORM_FILENAME_SIGNALS = {
    "appforoneperson": 6,
    "appformorethanoneperson": 6,
    "appforfamily": 6,
    "im-1ssl": 6,
    "im-1abds": 6,
    "odm06723": 6,
    "odm 06723": 6,
    "fillx": 2,
    "fillable": 2,
}

FORM_TEXT_SIGNALS = {
    "application for health coverage": 6,
    "use this application": 4,
    "application for more than one person": 6,
    "application for one person": 6,
    "designation of authorized representative": 6,
    "first name of applicant/recipient": 4,
    "aged, blind, and disabled supplement": 5,
    "anexo personas mayores, invidentes y discapacitadas": 5,
}


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def _document_type(
    filename: str, text: str, is_policy: bool, is_form_application: bool
) -> str:
    if is_form_application:
        return "form_application"
    if not is_policy:
        return "non_policy"
    combined = f"{filename} {text}"
    if "coverage policy" in combined or "coverage-policy" in combined:
        return "coverage_policy"
    if (
        "plan brochure" in combined
        or "plan-brochure" in combined
        or "summary of benefits and coverage" in combined
        or "summary-of-benefits-and-coverage" in combined
    ):
        return "benefit_plan"
    return "policy_document"


def classify_document(source_name: str, text: str) -> dict[str, Any]:
    """Classify using auditable filename and extracted-text signals.

    ``confidence`` is a normalized rule score for routing, not a calibrated
    statistical probability.
    """
    filename = _normalized(source_name.replace("_", " "))
    normalized_text = _normalized(text)
    score = 0
    form_score = 0
    signals: list[dict[str, Any]] = []
    form_signals: list[dict[str, Any]] = []

    compact_filename = re.sub(r"[^a-z0-9]+", "", filename)
    for phrase, weight in FORM_FILENAME_SIGNALS.items():
        target = re.sub(r"[^a-z0-9]+", "", phrase)
        if target in compact_filename:
            form_score += weight
            form_signals.append({
                "source": "filename",
                "phrase": phrase,
                "weight": weight,
            })

    for phrase, weight in FORM_TEXT_SIGNALS.items():
        if phrase in normalized_text:
            form_score += weight
            form_signals.append({"source": "text", "phrase": phrase, "weight": weight})

    for phrase, weight in FILENAME_SIGNALS.items():
        normalized_phrase = phrase.replace("-", " ")
        if phrase in filename or normalized_phrase in filename:
            score += weight
            signals.append({"source": "filename", "phrase": phrase, "weight": weight})

    for phrase, weight in TEXT_SIGNALS.items():
        if phrase in normalized_text:
            score += weight
            signals.append({"source": "text", "phrase": phrase, "weight": weight})

    for phrase, weight in NON_POLICY_SIGNALS.items():
        if phrase in normalized_text or phrase in filename:
            score += weight
            signals.append({"source": "negative", "phrase": phrase, "weight": weight})

    is_policy = score >= POLICY_THRESHOLD
    is_form_application = form_score >= FORM_THRESHOLD
    route = (
        "whole_document_context"
        if is_form_application
        else "policy_rag" if is_policy else "generic_artifacts"
    )
    return {
        "schema_version": "1.0",
        "source_name": source_name,
        "is_policy": is_policy,
        "is_form_application": is_form_application,
        "document_type": _document_type(
            filename, normalized_text, is_policy, is_form_application
        ),
        "route": route,
        "score": score,
        "threshold": POLICY_THRESHOLD,
        "confidence": round(max(0.0, min(1.0, score / 10)), 2),
        "signals": signals,
        "form_score": form_score,
        "form_threshold": FORM_THRESHOLD,
        "form_signals": form_signals,
        "classifier": "deterministic-document-router-v2",
    }


def classify_file(source_name: str, document_path: Path) -> dict[str, Any]:
    if not document_path.is_file():
        raise FileNotFoundError(document_path)
    return classify_document(
        source_name,
        document_path.read_text(encoding="utf-8"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--document", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = classify_file(
        args.source_name,
        args.document.expanduser().resolve(),
    )
    serialized = json.dumps(result, indent=2)
    if args.output:
        output = args.output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    main()

