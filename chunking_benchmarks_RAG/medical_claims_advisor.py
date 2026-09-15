"""Grounded medical-claims advisor over the policy table RAG index."""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

try:  # Support module and direct-script execution.
    from .table_rag import (
        DEFAULT_DATABASE_URL,
        DEFAULT_EMBEDDING_MODEL,
        connect,
        load_embedding_model,
        retrieve_tables,
    )
except ImportError:  # pragma: no cover - exercised by direct CLI use
    from table_rag import (
        DEFAULT_DATABASE_URL,
        DEFAULT_EMBEDDING_MODEL,
        connect,
        load_embedding_model,
        retrieve_tables,
    )


ADVISOR_INSTRUCTIONS = """
You are a medical claims policy advisor working only from retrieved G.E.H.A.
coverage-policy evidence.

Your role is to explain policy-table facts that may help a user prepare or
review a claim. You do not adjudicate claims, guarantee coverage or payment,
make medical-necessity determinations, or give medical advice.

Rules:
- Use only the supplied policy evidence.
- Cite every material conclusion with the source filename and table title.
- Treat PREFERENCE and PRIOR AUTHORIZATION values as policy-table facts, not as
  a guarantee that a claim will be approved or paid.
- When CONDITION STATUS is EXPLICIT, you may repeat only the supplied condition
  names and criteria.
- When CONDITION STATUS is NOT_EXPLICITLY_ENUMERATED, say that the extracted
  policy table did not explicitly enumerate conditions. Never infer a condition
  from the drug name, billing description, or outside knowledge.
- Absence of a condition is not evidence that the condition is excluded.
- If the evidence is missing, ambiguous, conflicting, or from a revision-history
  table, explain the limitation and recommend official plan review.
- Do not request or expose names, member IDs, Social Security numbers, dates of
  birth, medical-record numbers, credentials, or payment information.
- Give concise, actionable next steps, such as confirming the HCPCS code,
  checking prior authorization, and contacting the plan or claims administrator.
""".strip()


def condition_status(result: dict[str, Any]) -> str:
    return "EXPLICIT" if result.get("conditions_json") else "NOT_EXPLICITLY_ENUMERATED"


def evidence_records(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return safe, serializable evidence for CLI/UI display."""
    return [
        {
            "source": result["source"],
            "table_number": result["table_number"],
            "table_title": result["title"],
            "similarity": round(float(result["similarity"]), 4),
            "condition_status": condition_status(result),
            "conditions": list(result.get("conditions_json") or []),
            "table_csv": result["full_csv"],
        }
        for result in results
    ]


def build_evidence_context(results: list[dict[str, Any]]) -> str:
    """Group tables by policy so condition criteria are not duplicated."""
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        by_source[result["source"]].append(result)

    policies: list[str] = []
    for source, tables in by_source.items():
        first = tables[0]
        conditions = list(first.get("conditions_json") or [])
        indication_context = (first.get("indication_context") or "").strip()
        lines = [
            f"SOURCE: {source}",
            f"CONDITION STATUS: {condition_status(first)}",
            f"CONDITIONS: {json.dumps(conditions)}",
            "INDICATION CRITERIA:",
            indication_context
            if indication_context
            else "No explicit Indication Specific Criteria section was extracted.",
        ]
        for table in tables:
            lines.extend(
                [
                    "",
                    f"TABLE: {table['title']} (table {table['table_number']})",
                    f"RETRIEVAL SIMILARITY: {float(table['similarity']):.4f}",
                    table["full_csv"].strip(),
                ]
            )
        policies.append("\n".join(lines))
    return "\n\n--- NEXT POLICY ---\n\n".join(policies)


def retrieve_claims_evidence(
    query: str,
    *,
    database_url: str,
    embedding_model: Any,
    top_tables: int = 3,
    candidate_rows: int = 30,
) -> list[dict[str, Any]]:
    """Use the existing parent-child table RAG retriever."""
    with connect(database_url) as connection:
        return retrieve_tables(
            connection,
            embedding_model,
            query,
            top_tables,
            candidate_rows,
        )


def generate_claims_advice(
    question: str,
    results: list[dict[str, Any]],
    model: str,
    *,
    client: Any | None = None,
) -> str:
    if not results:
        return "No policy tables were retrieved. The available evidence is insufficient."
    openai_client = client or OpenAI()
    response = openai_client.responses.create(
        model=model,
        instructions=ADVISOR_INSTRUCTIONS,
        input=(
            f"QUESTION:\n{question}\n\n"
            f"RETRIEVED POLICY EVIDENCE:\n{build_evidence_context(results)}"
        ),
    )
    return response.output_text


def main() -> None:
    load_dotenv(Path(__file__).with_name(".env"), override=True)
    parser = argparse.ArgumentParser(
        description="Grounded medical claims advisor over policy tables."
    )
    parser.add_argument("question")
    parser.add_argument(
        "--database-url",
        default=os.getenv("GEHA_RAG_DATABASE_URL", DEFAULT_DATABASE_URL),
    )
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"))
    parser.add_argument("--top-tables", type=int, default=3)
    parser.add_argument("--candidate-rows", type=int, default=30)
    parser.add_argument(
        "--evidence-only",
        action="store_true",
        help="Print retrieved evidence as JSON without calling an LLM.",
    )
    args = parser.parse_args()

    embedding_model = load_embedding_model(args.embedding_model)
    results = retrieve_claims_evidence(
        args.question,
        database_url=args.database_url,
        embedding_model=embedding_model,
        top_tables=args.top_tables,
        candidate_rows=args.candidate_rows,
    )
    if args.evidence_only:
        print(json.dumps(evidence_records(results), indent=2))
        return
    print(generate_claims_advice(args.question, results, args.model))


if __name__ == "__main__":
    main()

