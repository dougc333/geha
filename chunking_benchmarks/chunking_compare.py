"""Pure comparison helpers for the chunking chatbot."""

from __future__ import annotations

import math
import re
from typing import Any


def normalized(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))


def expected_values(case: dict[str, Any] | None) -> list[str]:
    if not case:
        return []
    expected = case.get("expected", [])
    if case.get("kind") == "Preference lookup":
        return [str(value) for value in expected]
    return [str(value) for row in expected for value in row.values()]


def evidence_coverage(values: list[str], context: str) -> tuple[int, int, float]:
    if not values:
        return 0, 0, 0.0
    haystack = normalized(context)
    found = sum(normalized(value) in haystack for value in values)
    return found, len(values), found / len(values)


def context_metrics(
    texts: list[str], sources: list[str], values: list[str] | None = None
) -> dict[str, Any]:
    context = "\n\n".join(texts)
    found, total, coverage = evidence_coverage(values or [], context)
    characters = len(context)
    return {
        "context_units": len(texts),
        "distinct_sources": len(set(sources)),
        "characters": characters,
        "estimated_tokens": math.ceil(characters / 4),
        "expected_values_found": found,
        "expected_values_total": total,
        "expected_evidence_coverage": coverage,
    }


def compare_contexts(
    flat_chunks: list[dict[str, Any]],
    parent_tables: list[dict[str, Any]],
    case: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    values = expected_values(case)
    return {
        "flat": context_metrics(
            [str(chunk["search_text"]) for chunk in flat_chunks],
            [str(chunk["source"]) for chunk in flat_chunks],
            values,
        ),
        "hierarchical": context_metrics(
            [str(table["full_csv"]) for table in parent_tables],
            [str(table["source"]) for table in parent_tables],
            values,
        ),
    }
