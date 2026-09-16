"""Read-only MCP adapter over the existing GEHA policy-table retriever.

The indexed documents are reference material, not claim or member records.
No model call, ingestion, or coverage decision happens in this module.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAX_QUERY_LENGTH = 500
MAX_TABLE_CHARS = 100_000
SOURCE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,180}\.pdf\Z")


def _backend():
    """Import the shared RAG implementation only when a policy tool is called."""
    import sys

    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from chunking_benchmarks_RAG import billing_code_data, medical_claims_advisor
    from chunking_benchmarks_RAG import table_rag

    return billing_code_data, medical_claims_advisor, table_rag


@lru_cache(maxsize=1)
def _embedding_model(model_name: str):
    _, _, rag = _backend()
    return rag.load_embedding_model(model_name)


class PolicyService:
    def __init__(self, database_url: str | None = None, embedding_model: str | None = None):
        self.database_url = database_url or os.environ.get(
            "GEHA_RAG_DATABASE_URL",
            "postgresql://geha:geha-local@127.0.0.1:5433/geha_rag",
        )
        self.embedding_model = embedding_model or os.environ.get(
            "GEHA_RAG_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"
        )

    @staticmethod
    def _query(query: str) -> str:
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= MAX_QUERY_LENGTH:
            raise ValueError("Policy question must contain 1 to 500 characters")
        if any(ord(char) < 32 and char not in "\t\n" for char in query):
            raise ValueError("Policy question contains control characters")
        return query.strip()

    def search(self, query: str, top_tables: int = 5, candidate_rows: int = 30) -> dict[str, Any]:
        query = self._query(query)
        if not 1 <= top_tables <= 8 or not 5 <= candidate_rows <= 100:
            raise ValueError("Use top_tables 1..8 and candidate_rows 5..100")

        billing, advisor, _ = _backend()
        codes = billing.requested_billing_codes(query)
        if codes:
            matches = advisor.retrieve_billing_code_matches(query, self.database_url)
            return {
                "route": "exact_billing_code",
                "query": query,
                "codes": codes,
                "matches": matches,
                "match_count": len(matches),
                "note": "Exact indexed code rows only; no match is not a coverage determination.",
            }

        tables = advisor.retrieve_tables_for_named_condition(query, self.database_url)
        route = "policy_or_condition"
        if not tables:
            route = "semantic_fallback"
            tables = advisor.retrieve_claims_evidence(
                query,
                database_url=self.database_url,
                embedding_model=_embedding_model(self.embedding_model),
                top_tables=top_tables,
                candidate_rows=candidate_rows,
            )
        tables = [
            table for table in tables if not advisor.is_revision_table(table["title"])
        ][:top_tables]
        return {
            "route": route,
            "query": query,
            "match_count": len(tables),
            "tables": [
                {
                    "source_pdf": table["source"],
                    "table_number": table["table_number"],
                    "table_title": table["title"],
                    "similarity": round(float(table["similarity"]), 4),
                    "conditions": list(table.get("conditions_json") or []),
                }
                for table in tables
            ],
            "note": (
                "These are retrieval candidates, not coverage or medical-necessity "
                "determinations. Use get_policy_evidence for the complete source table."
            ),
        }

    def evidence(self, source_pdf: str, table_number: int, question: str = "") -> dict[str, Any]:
        if not isinstance(source_pdf, str) or not SOURCE_PATTERN.fullmatch(source_pdf):
            raise ValueError("source_pdf must be a policy PDF filename, not a path")
        if not isinstance(table_number, int) or table_number < 1:
            raise ValueError("table_number must be a positive integer")
        if question:
            question = self._query(question)
        _, advisor, rag = _backend()
        with rag.connect(self.database_url) as connection:
            table = connection.execute(
                """
                SELECT source, table_number, title, full_csv, conditions_json
                FROM policy_tables
                WHERE source = %s AND table_number = %s
                """,
                (source_pdf, table_number),
            ).fetchone()
        if table is None:
            raise ValueError("No indexed table for that source and table number")
        if len(table["full_csv"]) > MAX_TABLE_CHARS:
            raise ValueError("Indexed table exceeds the MCP response limit")
        sections = advisor.retrieve_policy_sections(
            self.database_url, source_pdf, question
        )
        if sum(len(item["content"]) for item in sections) > MAX_TABLE_CHARS:
            raise ValueError("Indexed policy criteria exceed the MCP response limit")
        return {
            "source_pdf": source_pdf,
            "table_number": table_number,
            "table_title": table["title"],
            "table_csv": table["full_csv"],
            "conditions": list(table.get("conditions_json") or []),
            "criteria_sections": sections,
            "note": (
                "Extracted policy evidence only. Verify against the source PDF; "
                "this is not a coverage, payment, or medical-necessity decision."
            ),
        }
