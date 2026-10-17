"""Reference answers and deterministic generation checks for labeled queries."""

from __future__ import annotations

import re
from typing import Any

try:
    from .chunking_compare import evidence_coverage, expected_values
except ImportError:
    from chunking_compare import evidence_coverage, expected_values


CODE_RE = re.compile(r"\b[A-Z]\d{4}\b", re.IGNORECASE)


def reference_answer(case: dict[str, Any] | None) -> str | None:
    """Render the verified structured expectation as a judge-readable answer."""
    if not case:
        return None
    if case["kind"] == "Qualifier":
        return "A complete answer states all of: " + " ".join(
            f"({index}) {fact['text']}" for index, fact in enumerate(case["facts"], 1)
        )
    if case["kind"] == "Preference lookup":
        preference = case.get("preference", "requested")
        products = "; ".join(str(value) for value in case.get("expected", []))
        return f"The {preference} products are: {products}."

    rows = case.get("expected", [])
    where = case.get("where", {})
    constraint = "; ".join(f"{key}={value}" for key, value in where.items())
    rendered_rows = [
        "; ".join(f"{key}={value}" for key, value in row.items()) for row in rows
    ]
    prefix = f"For {constraint}, " if constraint else ""
    return prefix + "the expected rows are: " + " | ".join(rendered_rows) + "."


def allowed_codes(case: dict[str, Any]) -> set[str]:
    """Return HCPCS-like codes explicitly allowed by the labeled answer."""
    values: list[str] = []
    values.extend(str(value) for value in case.get("where", {}).values())
    for row in case.get("expected", []):
        if isinstance(row, dict):
            values.extend(str(value) for value in row.values())
    return {match.upper() for value in values for match in CODE_RE.findall(value)}


def deterministic_generation_metrics(
    answer: str, case: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Score labeled-value completeness and exact-code contamination."""
    if not case:
        return None
    found, total, coverage = evidence_coverage(expected_values(case), answer)
    expected_codes = allowed_codes(case)
    mentioned_codes = {code.upper() for code in CODE_RE.findall(answer)}
    unexpected_codes = (
        sorted(mentioned_codes - expected_codes) if expected_codes else []
    )
    exact_code_compliant = not unexpected_codes
    return {
        "expected_values_found": found,
        "expected_values_total": total,
        "expected_value_coverage": coverage,
        "reference_complete": coverage == 1.0,
        "allowed_codes": sorted(expected_codes),
        "mentioned_codes": sorted(mentioned_codes),
        "unexpected_codes": unexpected_codes,
        "exact_code_compliant": exact_code_compliant,
        "deterministic_pass": coverage == 1.0 and exact_code_compliant,
    }
