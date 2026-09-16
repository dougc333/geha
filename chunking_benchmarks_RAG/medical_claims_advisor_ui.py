"""Streamlit chat interface for the grounded medical claims advisor."""

from __future__ import annotations

import os
import time
from pathlib import Path

import streamlit as st
from psycopg import Error as PsycopgError

try:  # Support Streamlit execution from the repository root or this directory.
    from .billing_code_data import requested_billing_codes
    from .medical_claims_advisor import (
        condition_inventory,
        build_policy_summary,
        evidence_records,
        format_condition_inventory,
        format_billing_code_matches,
        format_retrieval_summary,
        is_condition_inventory_query,
        is_preferred_condition_query,
        retrieve_claims_evidence,
        retrieve_billing_code_matches,
        retrieve_policy_sections,
        retrieve_tables_for_named_condition,
        should_expand_universal,
        table_records,
    )
    from .table_rag import (
        DEFAULT_DATABASE_URL,
        DEFAULT_EMBEDDING_MODEL,
        load_embedding_model,
    )
except ImportError:  # pragma: no cover - Streamlit direct-script execution
    from billing_code_data import requested_billing_codes
    from medical_claims_advisor import (
        condition_inventory,
        build_policy_summary,
        evidence_records,
        format_condition_inventory,
        format_billing_code_matches,
        format_retrieval_summary,
        is_condition_inventory_query,
        is_preferred_condition_query,
        retrieve_claims_evidence,
        retrieve_billing_code_matches,
        retrieve_policy_sections,
        retrieve_tables_for_named_condition,
        should_expand_universal,
        table_records,
    )
    from table_rag import (
        DEFAULT_DATABASE_URL,
        DEFAULT_EMBEDDING_MODEL,
        load_embedding_model,
    )


st.set_page_config(page_title="Medical Claims Policy Advisor", page_icon="🩺")
POLICY_DIR = Path(__file__).resolve().parents[1] / "downloads" / "coverage-policies"
POLICY_CHUNK_SUFFIX = ".docling_chunks.md"


def policy_name_qc_terms() -> list[str]:
    """Derive search terms from the policy chunk files in filename order."""
    prefix = "geha-coverage-policy-"
    return [
        path.name.removeprefix(prefix).removesuffix(POLICY_CHUNK_SUFFIX)
        for path in sorted(POLICY_DIR.glob(f"{prefix}*{POLICY_CHUNK_SUFFIX}"))
        if path.is_file()
    ]


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

    sections = summary.get("sections", [])
    indication_sections = [
        section for section in sections if section["section_type"] == "indication"
    ]
    universal_sections = [
        section for section in sections if section["section_type"] == "universal"
    ]
    if indication_sections:
        st.markdown("#### Indication-specific approval criteria")
        for section in indication_sections:
            st.markdown(
                f"**{section['condition']}** · source chunk {section['chunk_number']}"
            )
            st.markdown(section["content"])
    elif summary["criteria"]:
        st.markdown(f"#### {summary['matched_condition']} criteria")
        st.markdown("\n".join(f"- {criterion}" for criterion in summary["criteria"]))

    if universal_sections:
        with st.expander(
            "Universal approval criteria for this policy",
            expanded=summary.get("expand_universal", False),
        ):
            for section in universal_sections:
                st.caption(f"Source chunk {section['chunk_number']}")
                st.markdown(section["content"])

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
with st.sidebar:
    st.header("Retrieval settings")
    database_url = st.text_input(
        "PostgreSQL URL",
        os.getenv("GEHA_RAG_DATABASE_URL", DEFAULT_DATABASE_URL),
        type="password",
    )
    embedding_name = st.text_input("Embedding model", DEFAULT_EMBEDDING_MODEL)
    top_tables = st.slider("Parent tables", 1, 8, 3)
    candidate_rows = st.slider("Candidate rows", 5, 100, 30, step=5)
    st.divider()
    st.subheader("Policy-name search QC")
    st.caption("Search each policy name from a .docling_chunks.md file; show each result for 3 seconds.")
    if st.button("Start 3-second search cycle"):
        terms = policy_name_qc_terms()
        if terms:
            st.session_state.qc_terms = terms
            st.session_state.qc_index = 0
            st.session_state.qc_active = True
            st.session_state.claims_messages = []
        else:
            st.warning(f"No policy chunk files found in {POLICY_DIR}")
    if st.session_state.get("qc_active"):
        if st.button("Stop search cycle"):
            st.session_state.qc_active = False
        else:
            st.caption(
                f"Search {st.session_state.qc_index + 1} of "
                f"{len(st.session_state.qc_terms)}: "
                f"{st.session_state.qc_terms[st.session_state.qc_index]}"
            )
    elif st.session_state.get("qc_complete"):
        st.caption(f"Completed {st.session_state.qc_complete} policy-name searches.")

if "claims_messages" not in st.session_state:
    st.session_state.claims_messages = []
qc_search = st.session_state.get("qc_active", False)
if qc_search:
    # Clear the previous result before rendering history, so the QC cycle
    # behaves like a slideshow instead of accumulating large policy tables.
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

question = st.chat_input(
    "Ask about a drug, HCPCS code, preference, prior authorization, or documented condition"
)
if qc_search:
    # Use the same search branch as a submitted chat query, showing one result
    # at a time rather than accumulating dozens of large policy tables.
    question = st.session_state.qc_terms[st.session_state.qc_index]
if question:
    st.session_state.claims_messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        expand_evidence = False
        policy_summary = None
        if requested_billing_codes(question):
            try:
                with st.spinner("Checking exact GEHA billing-code rows..."):
                    billing_matches = retrieve_billing_code_matches(question, database_url)
                answer = format_billing_code_matches(question, billing_matches)
                evidence = []
            except PsycopgError:
                answer = "Billing-code lookup is unavailable. Check the GEHA database and retry."
                evidence = []
                st.error(answer)
        elif is_condition_inventory_query(question):
            try:
                inventory = condition_inventory(database_url)
                preferred_only = is_preferred_condition_query(question)
                answer = format_condition_inventory(
                    inventory, preferred_only=preferred_only
                )
                evidence = []
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
                        policy_summary["sections"] = retrieve_policy_sections(
                            database_url, policy_summary["source"], question
                        )
                        policy_summary["expand_universal"] = should_expand_universal(question)
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

    st.session_state.claims_messages.append(
        {
            "role": "assistant",
            "content": answer,
            "policy_summary": policy_summary,
            "evidence": evidence,
            "expand_evidence": expand_evidence,
        }
    )
    if qc_search:
        st.session_state.qc_index += 1
        if st.session_state.qc_index < len(st.session_state.qc_terms):
            time.sleep(3)
            st.rerun()
        else:
            st.session_state.qc_complete = len(st.session_state.qc_terms)
            st.session_state.qc_active = False
