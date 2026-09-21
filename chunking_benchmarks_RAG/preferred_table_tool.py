"""LangChain tool for exact Preferred-row lookup in stored GEHA policy tables."""

from __future__ import annotations

import os
from typing import Any

from langchain_core.tools import tool

try:  # Support package import and direct execution from this directory.
    from .medical_claims_advisor import (
        is_revision_table,
        preferred_products,
        retrieve_tables_for_named_condition,
    )
    from .table_rag import DEFAULT_DATABASE_URL
except ImportError:  # pragma: no cover - direct-script execution
    from medical_claims_advisor import (
        is_revision_table,
        preferred_products,
        retrieve_tables_for_named_condition,
    )
    from table_rag import DEFAULT_DATABASE_URL


def find_preferred_policy_tables(
    query: str, database_url: str
) -> dict[str, Any]:
    """Retrieve complete matching tables, retaining only explicit Preferred rows."""
    query = query.strip()
    if not query:
        raise ValueError("query must name a policy, drug, or documented condition")

    candidates = retrieve_tables_for_named_condition(query, database_url)
    matches = []
    for table in candidates:
        if is_revision_table(table["title"]):
            continue
        preferred = preferred_products(table["rows_json"])
        if not preferred:
            continue
        matches.append(
            {
                "source_pdf": table["source"],
                "table_number": table["table_number"],
                "table_title": table["title"],
                "explicit_conditions": list(table.get("conditions_json") or []),
                "preferred_products": preferred,
                "full_table_html": table["full_html"],
                "rows": table["rows_json"],
            }
        )

    return {
        "query": query,
        "match_count": len(matches),
        "tables": matches,
        "note": (
            "Only rows explicitly marked Preferred in the extracted GEHA table are reported. "
            "No match does not establish that a treatment is excluded or not covered."
        ),
    }


@tool("search_preferred_policy_tables")
def search_preferred_policy_tables(query: str) -> dict[str, Any]:
    """Find GEHA policy tables with explicit Preferred drugs for a policy, drug, or condition.

    Uses exact policy-name, drug-name, and documented-condition matching against
    PostgreSQL, not an LLM or a medical inference. Returns complete source tables
    and source PDF names as evidence. Do not treat a missing Preferred row as a
    coverage determination.
    """
    database_url = os.getenv("GEHA_RAG_DATABASE_URL", DEFAULT_DATABASE_URL)
    return find_preferred_policy_tables(query, database_url)
