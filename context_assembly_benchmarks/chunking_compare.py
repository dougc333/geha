"""Pure comparison helpers for the chunking chatbot."""

from __future__ import annotations

import math
import re
from typing import Any


# Curated aliases are intentionally narrow. They correct verified extraction/name variants without
# applying stemming or fuzzy matching to exact drug names and HCPCS codes.
DRUG_NAME_ALIASES = {
    "berahyaluronidas e alfa-pmph": "berahyaluronidase alfa-pmph",
}


def canonicalize_drug_names(text: str) -> str:
    canonical = text.casefold()
    for alias, drug_name in sorted(DRUG_NAME_ALIASES.items(), key=lambda item: -len(item[0])):
        canonical = canonical.replace(alias, drug_name)
    return canonical


def normalized(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", canonicalize_drug_names(text)))


def expected_values(case: dict[str, Any] | None) -> list[str]:
    if not case:
        return []
    expected = case.get("expected", [])
    if case.get("kind") == "Qualifier":
        return [str(fact["match"][0]) for fact in case["facts"]]
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


# --- fact-level scoring (used by the context and answer completeness evaluations) -----------

def required_facts(case: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Every fact a complete answer needs, as {text, type: value|qualifier, match: [phrases]}.

    Preference and relation cases contribute table values; qualifier cases carry labelled facts,
    including qualifiers stored beside the table (footnotes, exceptions, authorization periods).
    """
    if not case:
        return []
    if case.get("kind") == "Qualifier":
        return [dict(fact) for fact in case["facts"]]
    return [{"text": value, "type": "value", "match": [value]} for value in expected_values(case)]


def fact_present(fact: dict[str, Any], text: str) -> bool:
    haystack = normalized(text)
    return any(normalized(phrase) and normalized(phrase) in haystack for phrase in fact["match"])


def fact_presence(case: dict[str, Any] | None, text: str) -> list[bool]:
    return [fact_present(fact, text) for fact in required_facts(case)]


def sibling_rows(rows_text: list[str], case: dict[str, Any] | None) -> dict[str, int]:
    """Rows sent to the model vs rows that carry a required table value (the rest is noise)."""
    values = [fact for fact in required_facts(case) if fact["type"] == "value"]
    needed = sum(any(fact_present(fact, row) for fact in values) for row in rows_text)
    return {"rows_sent": len(rows_text), "rows_needed": needed, "sibling_rows": len(rows_text) - needed}
