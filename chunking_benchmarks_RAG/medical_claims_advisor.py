"""Grounded medical-claims advisor over the policy table RAG index."""

from __future__ import annotations

import argparse
import json
import os
import re
from functools import lru_cache
from html import escape
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import AuthenticationError, OpenAIError, PermissionDeniedError

try:  # Support module and direct-script execution.
    from .billing_code_data import requested_billing_codes
    from .table_rag import (
        DEFAULT_DATABASE_URL,
        DEFAULT_EMBEDDING_MODEL,
        connect,
        generate_answer,
        load_embedding_model,
        retrieve_tables,
    )
except ImportError:  # pragma: no cover - exercised by direct CLI use
    from billing_code_data import requested_billing_codes
    from table_rag import (
        DEFAULT_DATABASE_URL,
        DEFAULT_EMBEDDING_MODEL,
        connect,
        generate_answer,
        load_embedding_model,
        retrieve_tables,
    )


CONDITION_ALIASES_PATH = Path(__file__).with_name("condition_aliases.json")
CONDITION_CANONICAL_NAMES_PATH = Path(__file__).with_name(
    "condition_canonical_names.json"
)


def condition_status(result: dict[str, Any]) -> str:
    if result.get("matched_condition_alias"):
        return "APPROVED_ALIAS"
    return "EXPLICIT" if result.get("conditions_json") else "NOT_EXPLICITLY_ENUMERATED"


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


@lru_cache(maxsize=1)
def load_condition_canonical_names() -> dict[tuple[str, str], str]:
    """Load reviewed, source-specific display names without changing source data."""
    records = json.loads(CONDITION_CANONICAL_NAMES_PATH.read_text(encoding="utf-8"))
    mappings: dict[tuple[str, str], str] = {}
    for record in records:
        source = record["source"]
        original = record["original_condition"]
        canonical = record["canonical_condition"]
        if not all(
            isinstance(value, str) and value.strip()
            for value in (source, original, canonical)
        ):
            raise ValueError(f"Invalid condition display mapping: {record}")
        key = (source, original)
        if key in mappings:
            raise ValueError(f"Duplicate condition display mapping: {key}")
        mappings[key] = canonical
    return mappings


def canonical_condition(source: str, condition: str) -> str:
    """Return an approved display name, retaining the source label elsewhere."""
    return load_condition_canonical_names().get((source, condition), condition)


def normalized_search_text(value: str) -> str:
    """Normalize punctuation while retaining word boundaries for alias matching."""
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def contains_search_term(question: str, term: str) -> bool:
    normalized_question = f" {normalized_search_text(question)} "
    normalized_term = normalized_search_text(term)
    return bool(normalized_term) and f" {normalized_term} " in normalized_question


@lru_cache(maxsize=1)
def load_condition_aliases() -> tuple[dict[str, Any], ...]:
    """Load human-approved condition aliases and their source-policy links."""
    records = json.loads(CONDITION_ALIASES_PATH.read_text(encoding="utf-8"))
    required = {"canonical_condition", "source", "aliases", "required_concepts"}
    for record in records:
        missing = required - set(record)
        if missing:
            raise ValueError(
                f"Condition alias record is missing {sorted(missing)}: {record}"
            )
    return tuple(records)


def match_approved_condition_alias(question: str) -> dict[str, Any] | None:
    """Return the most-specific approved alias whose concepts match the question."""
    candidates: list[tuple[int, str, dict[str, Any]]] = []
    for record in load_condition_aliases():
        phrases = [record["canonical_condition"], *record["aliases"]]
        phrase_matches = [
            phrase for phrase in phrases if contains_search_term(question, phrase)
        ]
        concept_matches: list[str] = []
        all_concepts_match = True
        for group in record["required_concepts"]:
            matches = [term for term in group if contains_search_term(question, term)]
            if not matches:
                all_concepts_match = False
                break
            concept_matches.append(
                max(matches, key=lambda term: len(normalized_search_text(term)))
            )
        if not phrase_matches and not all_concepts_match:
            continue
        if phrase_matches:
            specificity = 1000 + max(
                len(normalized_search_text(phrase).split()) for phrase in phrase_matches
            )
        else:
            specificity = 500 + sum(
                len(normalized_search_text(term).split()) for term in concept_matches
            )
        candidates.append((specificity, record["canonical_condition"], record))
    if not candidates:
        return None
    return max(candidates, key=lambda candidate: (candidate[0], candidate[1]))[2]


def table_records(rows_json: Any) -> list[dict[str, str]]:
    """Normalize JSONB table rows into string-valued records."""
    if isinstance(rows_json, str):
        rows_json = json.loads(rows_json)
    if not isinstance(rows_json, list):
        return []
    return [
        {str(key): str(value or "").strip() for key, value in row.items()}
        for row in rows_json
        if isinstance(row, dict)
    ]


def records_as_html(records: list[dict[str, str]]) -> str:
    """Render deterministic records as a compact HTML table."""
    headers = list(records[0]) if records else []
    head = "".join(f"<th>{escape(header)}</th>" for header in headers)
    body = "".join(
        "<tr>"
        + "".join(f"<td>{escape(str(record.get(header, '')))}</td>" for header in headers)
        + "</tr>"
        for record in records
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def preferred_products(rows_json: Any) -> list[str]:
    """Extract rows whose preference value is exactly Preferred after normalization."""
    products: list[str] = []
    for record in table_records(rows_json):
        row = {normalized(key): value for key, value in record.items()}
        if normalized(row.get("preference", "")) != "preferred":
            continue
        product = row.get("drugname") or row.get("name") or ""
        if product and product not in products:
            products.append(product)
    return products


def is_condition_inventory_query(question: str) -> bool:
    words = set(re.findall(r"[a-z]+", question.casefold()))
    asks_about_conditions = bool({"condition", "conditions"} & words)
    asks_for_inventory = bool(
        {"all", "covered", "preferred", "list", "show"} & words
    ) or bool("conditions" in words and {"policy", "policies"} & words)
    return asks_about_conditions and asks_for_inventory


def is_preferred_condition_query(question: str) -> bool:
    """Treat covered-condition searches as the supported preferred-policy inventory."""
    words = set(re.findall(r"[a-z]+", question.casefold()))
    return bool({"condition", "conditions"} & words) and bool(
        {"covered", "preferred"} & words
    )


def query_mentions_condition(question: str, condition: str) -> bool:
    """Match a full condition name or an explicit parenthetical abbreviation."""
    question_words = set(re.findall(r"[a-z0-9]+", question.casefold()))
    condition_without_parentheses = re.sub(r"\([^)]*\)", "", condition).strip()
    if normalized(condition_without_parentheses) in normalized(question):
        return True
    for abbreviation in re.findall(r"\(([^)]+)\)", condition):
        abbreviation_key = normalized(abbreviation)
        if len(abbreviation_key) >= 2 and abbreviation_key in question_words:
            return True
    return False


def query_mentions_policy_source(question: str, source: str) -> bool:
    """Match the policy's filename identifier, such as Talvey or Nplate."""
    stem = re.sub(r"\.pdf$", "", source, flags=re.IGNORECASE)
    stem = re.sub(r"^geha-coverage-policy-", "", stem, flags=re.IGNORECASE)
    identifier = stem.split("-", 1)[0]
    return len(identifier) >= 4 and contains_search_term(question, identifier)


def matching_policy_sources(question: str, terms: list[dict[str, str]]) -> list[str]:
    """Prefer a policy's own name over a drug merely listed by another policy."""
    priorities = {
        "filename": 3,
        "policy_title": 3,
        "generic_name": 2,
        "billing_drug_name": 1,
    }
    matches = [item for item in terms if contains_search_term(question, item["term"])]
    if not matches:
        return []
    score = lambda item: (priorities.get(item["term_type"], 0), len(item["term"].split()))
    best = max(score(item) for item in matches)
    return sorted({item["source_pdf"] for item in matches if score(item) == best})


def condition_table_priority(table: dict[str, Any]) -> tuple[int, str, int]:
    title = table["title"].casefold()
    if "preference" in title or "prior auth" in title:
        rank = 0
    elif "billing" in title:
        rank = 1
    elif "revision" in title or "update" in title or "date" in title:
        rank = 3
    else:
        rank = 2
    return rank, table["source"], int(table["table_number"])


def retrieve_tables_for_named_condition(
    question: str, database_url: str
) -> list[dict[str, Any]]:
    """Return parent tables selected by a policy term, alias, or condition."""
    alias_match = match_approved_condition_alias(question)
    with connect(database_url) as connection:
        source_terms = connection.execute(
            "SELECT source_pdf, term, term_type FROM policy_source_terms"
        ).fetchall()
        named_sources = matching_policy_sources(question, source_terms)
        if named_sources:
            tables = connection.execute(
                """
                SELECT source, table_number, title, full_html, rows_json,
                       conditions_json, indication_context
                FROM policy_tables
                WHERE source = ANY(%s)
                ORDER BY source, table_number
                """,
                (named_sources,),
            ).fetchall()
        elif alias_match:
            tables = connection.execute(
                """
                SELECT source, table_number, title, full_html, rows_json,
                       conditions_json, indication_context
                FROM policy_tables
                WHERE source = %s
                ORDER BY source, table_number
                """,
                (alias_match["source"],),
            ).fetchall()
        else:
            tables = connection.execute(
                """
                SELECT source, table_number, title, full_html, rows_json,
                       conditions_json, indication_context
                FROM policy_tables
                WHERE jsonb_array_length(conditions_json) > 0
                ORDER BY source, table_number
                """
            ).fetchall()

    results: list[dict[str, Any]] = []
    for table in tables:
        if not named_sources and not alias_match and not any(
            query_mentions_condition(question, condition)
            for condition in table["conditions_json"]
        ):
            continue
        item = dict(table)
        item["similarity"] = 1.0
        if alias_match and item["source"] == alias_match["source"]:
            item["matched_condition_alias"] = alias_match["canonical_condition"]
            item["condition_match_basis"] = "approved_alias"
        results.append(item)
    named_sources = {
        result["source"]
        for result in results
        if query_mentions_policy_source(question, result["source"])
    }
    if named_sources:
        results = [
            result for result in results if result["source"] in named_sources
        ]
    return sorted(results, key=condition_table_priority)


def retrieve_policy_sections(
    database_url: str, source: str, question: str
) -> list[dict[str, Any]]:
    """Fetch source-linked approval criteria without semantic or LLM inference."""
    with connect(database_url) as connection:
        sections = connection.execute(
            """
            SELECT chunk_number, section_type, condition, content
            FROM policy_chunks
            WHERE source_pdf = %s AND section_type IN ('indication', 'universal')
            ORDER BY chunk_number
            """,
            (source,),
        ).fetchall()

    conditions = list(dict.fromkeys(
        section["condition"] for section in sections if section["condition"]
    ))
    matched = [
        condition for condition in conditions if query_mentions_condition(question, condition)
    ]
    alias = match_approved_condition_alias(question)
    if alias and alias["source"] == source and alias["canonical_condition"] in conditions:
        matched = [alias["canonical_condition"]]
    return [
        dict(section)
        for section in sections
        if section["section_type"] == "universal"
        or not matched
        or section["condition"] in matched
    ]


def should_expand_universal(question: str) -> bool:
    """Open the universal-criteria panel when the user asks for general rules."""
    wording = question.casefold()
    return "universal" in wording or "general approval" in wording


def condition_inventory(database_url: str) -> list[dict[str, Any]]:
    """List extracted and approved-alias conditions with their linked policies."""
    with connect(database_url) as connection:
        tables = connection.execute(
            """
            SELECT source, table_number, title, full_html, rows_json, conditions_json
            FROM policy_tables
            ORDER BY source, table_number
            """
        ).fetchall()

    policies: dict[str, dict[str, Any]] = {}
    for table in tables:
        policy = policies.setdefault(
            table["source"],
            {
                "source": table["source"],
                "conditions": list(table["conditions_json"]),
                "preferred_treatments": [],
                "preference_tables": [],
            },
        )
        products = preferred_products(table["rows_json"])
        if products:
            policy["preference_tables"].append(table["title"])
        for product in products:
            if product not in policy["preferred_treatments"]:
                policy["preferred_treatments"].append(product)

    inventory: list[dict[str, Any]] = []
    for policy in policies.values():
        for condition in policy["conditions"]:
            inventory.append(
                {
                    "condition": condition,
                    "preferred_treatments": list(policy["preferred_treatments"]),
                    "source": policy["source"],
                    "preference_tables": list(dict.fromkeys(policy["preference_tables"])),
                    "condition_basis": "extracted_condition",
                }
            )

    known = {
        (normalized(item["condition"]), item["source"]) for item in inventory
    }
    for alias in load_condition_aliases():
        key = (normalized(alias["canonical_condition"]), alias["source"])
        if key in known:
            continue
        policy = policies.get(
            alias["source"],
            {"preferred_treatments": [], "preference_tables": []},
        )
        inventory.append(
            {
                "condition": alias["canonical_condition"],
                "preferred_treatments": list(policy["preferred_treatments"]),
                "source": alias["source"],
                "preference_tables": list(
                    dict.fromkeys(policy["preference_tables"])
                ),
                "condition_basis": "approved_alias",
            }
        )
    return sorted(inventory, key=lambda item: normalized(item["condition"]))


def format_condition_inventory(
    inventory: list[dict[str, Any]], *, preferred_only: bool
) -> str:
    selected = [
        item for item in inventory if item["preferred_treatments"] or not preferred_only
    ]
    if not selected:
        return "No explicit conditions with preferred treatments were found."

    heading = (
        "Conditions with preferred treatments in the same policy"
        if preferred_only
        else "Policy conditions"
    )
    groups: dict[str, dict[str, dict[str, Any]]] = {}
    for item in selected:
        condition = canonical_condition(item["source"], item["condition"])
        sources = groups.setdefault(condition, {})
        current = sources.get(item["source"])
        if current is None or (
            current.get("condition_basis") == "approved_alias"
            and item.get("condition_basis") == "extracted_condition"
        ):
            sources[item["source"]] = item

    lines = [f"### {heading}", ""]
    for condition in sorted(groups, key=lambda value: (normalized(value), value)):
        lines.append(f"- **{condition}**")
        for source, item in sorted(groups[condition].items()):
            products = ", ".join(item["preferred_treatments"])
            treatment_text = (
                products or "No Preferred row was found in this policy's tables"
            )
            basis = item.get("condition_basis", "extracted_condition")
            basis_label = (
                "approved condition alias"
                if basis == "approved_alias"
                else "extracted condition metadata"
            )
            source_wording = (
                f"; source wording: `{item['condition']}`"
                if item["condition"] != condition
                else ""
            )
            lines.append(
                f"  - `{source}` — {treatment_text} "
                f"(Basis: {basis_label}{source_wording})"
            )
    lines.extend(
        [
            "",
            (
                "These are policy-level associations from extracted condition metadata or the "
                "versioned, human-approved condition aliases. Preferred rows occur in the same policy. "
                "The tables do not establish that every listed product applies to every condition, "
                "and they do not guarantee claim approval or payment."
            ),
        ]
    )
    return "\n".join(lines)


def inventory_evidence(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert the verified inventory into table-RAG evidence for the optional ask step."""
    selected = [item for item in inventory if item["preferred_treatments"]]
    records = [
        {
            "Condition": item["condition"],
            "Preferred Treatments": "; ".join(item["preferred_treatments"]),
            "GEHA Source": item["source"],
        }
        for item in selected
    ]
    return [
        {
            "source": "GEHA condition inventory; see GEHA Source column",
            "title": "Conditions with preferred treatments in the same policy",
            "full_html": records_as_html(records),
            "rows_json": records,
            "conditions_json": [item["condition"] for item in selected],
        }
    ]


def format_openai_section(text: str) -> str:
    return (
        "### OPENAI ASK — TYPO-CORRECTED, MODEL-GENERATED RESULT\n\n"
        "**Not GEHA source data or an official coverage determination.** This section is "
        "a display-only spelling/OCR correction pass and is not written to pgvector.\n\n"
        f"{text}"
    )


def generate_openai_section(
    question: str,
    results: list[dict[str, Any]],
    model: str,
    *,
    client: Any | None = None,
) -> str:
    return format_openai_section(
        generate_answer(question, results, model, client=client)
    )


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
            "table_html": result["full_html"],
        }
        for result in results
    ]


def is_revision_table(title: str) -> bool:
    normalized_title = normalized(title)
    return "revisionhistory" in normalized_title or (
        "date" in normalized_title and "update" in normalized_title
    )


def policy_display_name(source: str) -> str:
    stem = re.sub(r"\.pdf$", "", source, flags=re.IGNORECASE)
    stem = re.sub(r"^geha-coverage-policy-", "", stem, flags=re.IGNORECASE)
    return stem.replace("-", " ").title()


def best_condition_match(question: str, conditions: list[str]) -> str | None:
    """Choose the documented condition that best matches the user's wording."""
    if not conditions:
        return None
    for condition in conditions:
        if query_mentions_condition(question, condition):
            return condition

    query_words = set(re.findall(r"[a-z0-9]+", question.casefold()))
    if {"cancer", "treatment"} <= query_words:
        query_words.update({"chemotherapy", "induced"})
    scored = []
    for condition in conditions:
        condition_words = set(re.findall(r"[a-z0-9]+", condition.casefold()))
        meaningful = condition_words - {"to", "of", "in", "or", "and"}
        scored.append((len(query_words & meaningful), condition))
    score, condition = max(scored, key=lambda item: item[0])
    return condition if score else None


def condition_criteria(indication_context: str, condition: str | None) -> list[str]:
    if not condition or not indication_context:
        return []
    heading = re.compile(
        rf"^##\s+{re.escape(condition)}\s*$", re.IGNORECASE | re.MULTILINE
    )
    match = heading.search(indication_context)
    if not match:
        return []
    remainder = indication_context[match.end() :]
    next_heading = re.search(r"^##\s+", remainder, re.MULTILINE)
    section = remainder[: next_heading.start()] if next_heading else remainder
    return [
        re.sub(r"^-\s*", "", line).strip()
        for line in section.splitlines()
        if line.strip().startswith("-")
    ]


def build_policy_summary(
    question: str, results: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Build a deterministic, user-facing summary from complete parent tables."""
    if not results:
        return None

    by_source: dict[str, list[dict[str, Any]]] = {}
    source_scores: dict[str, float] = {}
    for result in results:
        source = result["source"]
        by_source.setdefault(source, []).append(result)
        source_scores[source] = max(
            source_scores.get(source, float("-inf")), float(result["similarity"])
        )

    ordered_sources = sorted(by_source, key=lambda source: source_scores[source], reverse=True)
    source = next(
        (
            candidate
            for candidate in ordered_sources
            if any(not is_revision_table(table["title"]) for table in by_source[candidate])
        ),
        ordered_sources[0],
    )
    source_tables = [
        table for table in by_source[source] if not is_revision_table(table["title"])
    ]
    first = source_tables[0] if source_tables else by_source[source][0]
    conditions = list(first.get("conditions_json") or [])
    approved_condition = next(
        (
            table.get("matched_condition_alias")
            for table in source_tables
            if table.get("matched_condition_alias")
        ),
        None,
    )
    matched_condition = approved_condition or best_condition_match(question, conditions)
    if approved_condition and approved_condition not in conditions:
        conditions.append(approved_condition)

    preferred: list[str] = []
    non_preferred: list[str] = []
    prior_auth: dict[str, str] = {}
    for table in source_tables:
        for record in table_records(table["rows_json"]):
            row = {normalized(key): value.strip() for key, value in record.items()}
            name = row.get("drugname") or row.get("name")
            preference = normalized(row.get("preference", ""))
            if name and preference == "preferred" and name not in preferred:
                preferred.append(name)
            elif name and preference == "nonpreferred" and name not in non_preferred:
                non_preferred.append(name)
            auth = row.get("requirespriorauth") or row.get("priorauthorization")
            if name and auth:
                prior_auth[name] = auth

    display_name = policy_display_name(source)
    if matched_condition:
        answer = (
            f"The policy most directly matching this question is **{display_name}**, "
            f"specifically its **{matched_condition}** section."
        )
    else:
        answer = f"The highest-ranked substantive policy is **{display_name}**."

    return {
        "answer": answer,
        "source": source,
        "policy_name": display_name,
        "matched_condition": matched_condition,
        "condition_match_basis": (
            "approved_alias" if approved_condition else "extracted_condition"
        ),
        "conditions": conditions,
        "preferred": preferred,
        "non_preferred": non_preferred,
        "prior_auth": prior_auth,
        "criteria": condition_criteria(
            str(first.get("indication_context") or ""), matched_condition
        ),
        # Preserve the complete parent tables selected by TableRAG so UI/API
        # consumers can render the evidence, not only the parsed summary.
        "tables": [
            {
                "table_number": table["table_number"],
                "title": table["title"],
                "full_html": table["full_html"],
                "rows_json": table["rows_json"],
            }
            for table in source_tables
        ],
    }


def format_retrieval_summary(question: str, results: list[dict[str, Any]]) -> str:
    """Render retrieved GEHA facts without an LLM or outside medical inference."""
    if not results:
        return "No policy tables were retrieved. The available GEHA evidence is insufficient."

    query = question.casefold()
    asks_preferred = "preferred" in query or "preference" in query
    asks_prior_auth = "prior auth" in query or "authorization" in query
    lines = ["### Retrieved GEHA policy evidence", ""]

    for result in results:
        source = result["source"]
        title = result["title"]
        conditions = list(result.get("conditions_json") or [])
        records = table_records(result["rows_json"])
        lines.append(f"- **{title}** — `{source}`")
        if conditions:
            lines.append(f"  - Explicit policy conditions: {', '.join(conditions)}")
        else:
            lines.append(
                "  - Conditions were not explicitly enumerated in this policy extraction; "
                "no condition is inferred."
            )

        if asks_preferred:
            products = preferred_products(result["rows_json"])
            if products:
                lines.append(f"  - Rows marked Preferred: {', '.join(products)}")
            else:
                lines.append("  - No row marked exactly Preferred was found in this table.")

        if asks_prior_auth:
            auth_facts: list[str] = []
            for record in records:
                normalized_record = {normalized(key): value for key, value in record.items()}
                auth_value = normalized_record.get("requirespriorauth") or normalized_record.get(
                    "priorauthorization"
                )
                if not auth_value:
                    continue
                name = normalized_record.get("drugname") or normalized_record.get("name")
                auth_facts.append(f"{name}: {auth_value}" if name else auth_value)
            if auth_facts:
                lines.append(f"  - Prior-authorization rows: {'; '.join(auth_facts)}")
            else:
                lines.append("  - No prior-authorization column/value was found in this table.")

    lines.extend(
        [
            "",
            (
                "This section is a deterministic rendering of retrieved GEHA records. It makes no "
                "medical inference and does not guarantee coverage or payment. Review the exact "
                "extracted tables below and confirm against the official policy."
            ),
        ]
    )
    return "\n".join(lines)


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


def retrieve_billing_code_matches(query: str, database_url: str) -> list[dict[str, Any]]:
    """Match codes in billing/applicable-code rows, never by vector similarity."""
    requested = set(requested_billing_codes(query))
    if not requested:
        return []
    with connect(database_url) as connection:
        rows = connection.execute(
            """
            SELECT source_pdf, table_name, code, item_name, source_line
            FROM policy_billing_codes
            WHERE code = ANY(%s)
            ORDER BY code, source_pdf, table_name, source_line
            """,
            (sorted(requested),),
        ).fetchall()
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (row["code"], row["source_pdf"], row["table_name"])
        match = grouped.setdefault(
            key,
            {
                "billing_code": row["code"],
                "source_document": row["source_pdf"],
                "table_name": row["table_name"],
                "items": [],
                "source_lines": [],
            },
        )
        if row["item_name"] and row["item_name"] not in match["items"]:
            match["items"].append(row["item_name"])
        match["source_lines"].append(row["source_line"])
    return sorted(grouped.values(), key=lambda item: (
        item["billing_code"], item["source_document"], item["table_name"]
    ))


def format_billing_code_matches(query: str, matches: list[dict[str, Any]]) -> str:
    """Present exact code matches with their source document and table name."""
    lines: list[str] = []
    for code in requested_billing_codes(query):
        code_matches = [item for item in matches if item["billing_code"] == code]
        if not code_matches:
            lines.append(f"Billing Code: {code}; no exact match in the indexed billing tables.")
        else:
            for item in code_matches:
                lines.append(
                    f"- Billing Code: {code}; Source document: {item['source_document']}; "
                    f"Table: {item['table_name']}"
                )
    return "\n".join(lines)


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
        help="Print retrieved evidence as JSON instead of a deterministic summary.",
    )
    parser.add_argument(
        "--no-openai",
        action="store_true",
        help="Do not append the optional, clearly labeled OpenAI ask interpretation.",
    )
    args = parser.parse_args()

    if is_condition_inventory_query(args.question):
        inventory = condition_inventory(args.database_url)
        deterministic_answer = format_condition_inventory(
            inventory, preferred_only=is_preferred_condition_query(args.question)
        )
        print(deterministic_answer)
        if not args.no_openai and not args.evidence_only:
            _print_openai_addendum(
                args.question, inventory_evidence(inventory), args.model
            )
        return

    results = retrieve_tables_for_named_condition(args.question, args.database_url)
    if not results:
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
    print(format_retrieval_summary(args.question, results))
    if not args.no_openai:
        _print_openai_addendum(args.question, results, args.model)


def _print_openai_addendum(
    question: str, results: list[dict[str, Any]], model: str
) -> None:
    if not os.getenv("OPENAI_API_KEY"):
        print(
            "\n\n### OPENAI ASK — UNAVAILABLE\n\n"
            "No OPENAI_API_KEY is configured. The GEHA result above is unaffected."
        )
        return
    try:
        print("\n\n" + generate_openai_section(question, results, model))
    except AuthenticationError:
        print(
            "\n\n### OPENAI ASK — UNAVAILABLE\n\n"
            "OpenAI authentication failed. The GEHA result above is unaffected."
        )
    except PermissionDeniedError:
        print(
            "\n\n### OPENAI ASK — UNAVAILABLE\n\n"
            "The configured OpenAI project cannot use this model. The GEHA result above "
            "is unaffected."
        )
    except OpenAIError:
        print(
            "\n\n### OPENAI ASK — UNAVAILABLE\n\n"
            "OpenAI could not generate an interpretation. The GEHA result above is unaffected."
        )


if __name__ == "__main__":
    main()
