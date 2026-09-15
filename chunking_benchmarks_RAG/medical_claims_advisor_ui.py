"""Streamlit chat interface for the grounded medical claims advisor."""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from openai import AuthenticationError, OpenAIError, PermissionDeniedError
from psycopg import Error as PsycopgError

try:  # Support Streamlit execution from the repository root or this directory.
    from .medical_claims_advisor import (
        condition_inventory,
        build_policy_summary,
        evidence_records,
        format_condition_inventory,
        format_retrieval_summary,
        generate_openai_section,
        inventory_evidence,
        is_condition_inventory_query,
        is_preferred_condition_query,
        retrieve_claims_evidence,
        retrieve_tables_for_named_condition,
        table_records,
    )
    from .table_rag import (
        DEFAULT_DATABASE_URL,
        DEFAULT_EMBEDDING_MODEL,
        load_embedding_model,
    )
except ImportError:  # pragma: no cover - Streamlit direct-script execution
    from medical_claims_advisor import (
        condition_inventory,
        build_policy_summary,
        evidence_records,
        format_condition_inventory,
        format_retrieval_summary,
        generate_openai_section,
        inventory_evidence,
        is_condition_inventory_query,
        is_preferred_condition_query,
        retrieve_claims_evidence,
        retrieve_tables_for_named_condition,
        table_records,
    )
    from table_rag import (
        DEFAULT_DATABASE_URL,
        DEFAULT_EMBEDDING_MODEL,
        load_embedding_model,
    )


st.set_page_config(page_title="Medical Claims Policy Advisor", page_icon="🩺")
POLICY_DIR = Path(__file__).resolve().parents[1] / "downloads" / "coverage-policies"


@st.cache_resource
def cached_embedding_model(name: str):
    return load_embedding_model(name)


def render_policy_summary(summary: dict, key_prefix: str) -> None:
    st.markdown("#### Answer")
    st.info(summary["answer"])

    st.markdown("#### Source documents")
    source = summary["source"]
    stem = source.removesuffix(".pdf")
    assets = [
        ("📕 GEHA policy PDF", POLICY_DIR / source, "application/pdf"),
        ("📄 Extracted policy text", POLICY_DIR / f"{stem}.docling.md", "text/markdown"),
        ("📊 Extracted tables", POLICY_DIR / f"{stem}_table_openai.csv", "text/csv"),
    ]
    columns = st.columns(3)
    for index, (label, path, mime) in enumerate(assets):
        with columns[index]:
            if path.exists():
                st.download_button(
                    label,
                    data=path.read_bytes(),
                    file_name=path.name,
                    mime=mime,
                    key=f"{key_prefix}-source-{index}",
                    use_container_width=True,
                )
            else:
                st.caption(f"{label}: unavailable")

    st.markdown("#### The policy lists")
    preferred = summary["preferred"]
    non_preferred = summary["non_preferred"]
    prior_auth = summary["prior_auth"]
    st.markdown(
        f"- **Preferred:** {', '.join(preferred) if preferred else 'Not listed'}\n"
        f"- **Non-preferred:** {', '.join(non_preferred) if non_preferred else 'Not listed'}"
    )
    if prior_auth:
        distinct_values = set(prior_auth.values())
        if len(distinct_values) == 1:
            value = next(iter(distinct_values))
            st.markdown(f"- **Prior authorization:** {value} for all {len(prior_auth)} listed drugs")
        else:
            values = "; ".join(f"{name}: {value}" for name, value in prior_auth.items())
            st.markdown(f"- **Prior authorization:** {values}")
    else:
        st.markdown("- **Prior authorization:** Not present in the extracted table")

    if summary["criteria"]:
        st.markdown(f"#### {summary['matched_condition']} criteria")
        st.markdown("\n".join(f"- {criterion}" for criterion in summary["criteria"]))

    st.markdown("#### Extracted GEHA policy tables")
    for table_index, table in enumerate(summary.get("tables", [])):
        st.markdown(
            f"**Table {table['table_number']}: {table['title']}**"
        )
        records = table_records(table["full_csv"])
        if records:
            st.dataframe(
                records,
                hide_index=True,
                use_container_width=True,
                key=f"{key_prefix}-table-{table_index}",
            )
        else:
            # Keep unusual extraction output visible even when it cannot be
            # normalized into records.
            st.code(table["full_csv"], language="csv")


st.title("Medical Claims Policy Advisor")
st.caption(
    "Grounded in extracted G.E.H.A. policy tables. This tool explains policy "
    "evidence; it does not adjudicate claims or guarantee coverage or payment."
)
st.warning(
    "Do not enter names, member IDs, Social Security numbers, dates of birth, "
    "medical-record numbers, credentials, or payment information."
)
st.caption(
    "GEHA evidence is shown first. A separately labeled OpenAI typo/OCR-correction pass is "
    "shown last and is never written to the GEHA database."
)

with st.sidebar:
    st.header("Retrieval settings")
    database_url = st.text_input(
        "PostgreSQL URL",
        os.getenv("GEHA_RAG_DATABASE_URL", DEFAULT_DATABASE_URL),
        type="password",
    )
    embedding_name = st.text_input("Embedding model", DEFAULT_EMBEDDING_MODEL)
    model_name = st.text_input("OpenAI correction model", os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"))
    top_tables = st.slider("Parent tables", 1, 8, 3)
    candidate_rows = st.slider("Candidate rows", 5, 100, 30, step=5)

if "claims_messages" not in st.session_state:
    st.session_state.claims_messages = []

for message_index, message in enumerate(st.session_state.claims_messages):
    with st.chat_message(message["role"]):
        if message.get("policy_summary"):
            render_policy_summary(message["policy_summary"], f"history-{message_index}")
        else:
            st.markdown(message["content"])
        if message.get("evidence"):
            with st.expander(
                "Retrieved policy evidence",
                expanded=message.get("expand_evidence", False),
            ):
                for item in message["evidence"]:
                    st.markdown(
                        f"**{item['source']} - {item['table_title']}**  \n"
                        f"Similarity: `{item['similarity']}`  \n"
                        f"Condition status: `{item['condition_status']}`  \n"
                        f"Conditions: `{item['conditions']}`"
                    )
                    st.code(item["table_csv"], language="csv")
        if message.get("openai_section"):
            st.markdown(message["openai_section"])

question = st.chat_input(
    "Ask about a drug, HCPCS code, preference, prior authorization, or documented condition"
)
if question:
    st.session_state.claims_messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        openai_evidence = []
        expand_evidence = False
        policy_summary = None
        if is_condition_inventory_query(question):
            try:
                inventory = condition_inventory(database_url)
                preferred_only = is_preferred_condition_query(question)
                answer = format_condition_inventory(
                    inventory, preferred_only=preferred_only
                )
                evidence = []
                openai_evidence = inventory_evidence(inventory)
            except PsycopgError:
                answer = (
                    "The condition inventory is unavailable. Confirm that the pgvector "
                    "service and database configuration are running, then retry."
                )
                evidence = []
                st.error(answer)
        else:
            try:
                with st.spinner("Retrieving GEHA policy tables and condition metadata..."):
                    results = retrieve_tables_for_named_condition(question, database_url)
                    if results:
                        expand_evidence = True
                    else:
                        results = retrieve_claims_evidence(
                            question,
                            database_url=database_url,
                            embedding_model=cached_embedding_model(embedding_name),
                            top_tables=top_tables,
                            candidate_rows=candidate_rows,
                        )
                    policy_summary = build_policy_summary(question, results)
                    if policy_summary:
                        results = [
                            result
                            for result in results
                            if result["source"] == policy_summary["source"]
                            and "revision" not in result["title"].casefold()
                            and not (
                                "date" in result["title"].casefold()
                                and "update" in result["title"].casefold()
                            )
                        ]
                    evidence = evidence_records(results)
                    answer = format_retrieval_summary(question, results)
                    openai_evidence = results
            except (PsycopgError, RuntimeError, ValueError):
                answer = (
                    "Policy retrieval is unavailable. Confirm that the pgvector service and "
                    "database configuration are running, then retry."
                )
                evidence = []
                st.error(answer)

        if policy_summary:
            render_policy_summary(policy_summary, "current")
        else:
            st.markdown(answer)
        if evidence:
            with st.expander("Retrieved policy evidence", expanded=expand_evidence):
                for item in evidence:
                    st.markdown(
                        f"**{item['source']} - {item['table_title']}**  \n"
                        f"Similarity: `{item['similarity']}`  \n"
                        f"Condition status: `{item['condition_status']}`  \n"
                        f"Conditions: `{item['conditions']}`"
                    )
                    st.code(item["table_csv"], language="csv")

        openai_section = ""
        if openai_evidence:
            if not os.getenv("OPENAI_API_KEY"):
                openai_section = (
                    "### OPENAI ASK — UNAVAILABLE\n\n"
                    "No OpenAI API key is configured. The GEHA evidence above is unaffected."
                )
            else:
                try:
                    with st.spinner("Running the separate OpenAI typo/OCR-correction pass..."):
                        openai_section = generate_openai_section(
                            question, openai_evidence, model_name
                        )
                except AuthenticationError:
                    openai_section = (
                        "### OPENAI ASK — UNAVAILABLE\n\n"
                        "OpenAI authentication failed. The GEHA evidence above is unaffected."
                    )
                except PermissionDeniedError:
                    openai_section = (
                        "### OPENAI ASK — UNAVAILABLE\n\n"
                        "The configured OpenAI project cannot use this model. The GEHA evidence "
                        "above is unaffected."
                    )
                except OpenAIError:
                    openai_section = (
                        "### OPENAI ASK — UNAVAILABLE\n\n"
                        "OpenAI could not run the correction pass. The GEHA evidence above is "
                        "unaffected."
                    )
            st.markdown(openai_section)

    st.session_state.claims_messages.append(
        {
            "role": "assistant",
            "content": answer,
            "policy_summary": policy_summary,
            "evidence": evidence,
            "expand_evidence": expand_evidence,
            "openai_section": openai_section,
        }
    )
