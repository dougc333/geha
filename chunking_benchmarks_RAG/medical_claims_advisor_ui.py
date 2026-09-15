"""Streamlit chat interface for the grounded medical claims advisor."""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAIError
from psycopg import Error as PsycopgError

try:  # Support Streamlit execution from the repository root or this directory.
    from .medical_claims_advisor import (
        evidence_records,
        generate_claims_advice,
        retrieve_claims_evidence,
    )
    from .table_rag import (
        DEFAULT_DATABASE_URL,
        DEFAULT_EMBEDDING_MODEL,
        load_embedding_model,
    )
except ImportError:  # pragma: no cover - Streamlit direct-script execution
    from medical_claims_advisor import (
        evidence_records,
        generate_claims_advice,
        retrieve_claims_evidence,
    )
    from table_rag import (
        DEFAULT_DATABASE_URL,
        DEFAULT_EMBEDDING_MODEL,
        load_embedding_model,
    )


load_dotenv(Path(__file__).with_name(".env"), override=True)
st.set_page_config(page_title="Medical Claims Policy Advisor", page_icon="🩺")


@st.cache_resource
def cached_embedding_model(name: str):
    return load_embedding_model(name)


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
    model_name = st.text_input("OpenAI model", os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"))
    top_tables = st.slider("Parent tables", 1, 8, 3)
    candidate_rows = st.slider("Candidate rows", 5, 100, 30, step=5)

if "claims_messages" not in st.session_state:
    st.session_state.claims_messages = []

for message in st.session_state.claims_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("evidence"):
            with st.expander("Retrieved policy evidence"):
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
if question:
    st.session_state.claims_messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        if not os.getenv("OPENAI_API_KEY"):
            answer = "Set OPENAI_API_KEY in chunking_benchmarks_RAG/.env to generate an explanation."
            st.error(answer)
            evidence = []
        else:
            try:
                with st.spinner("Retrieving policy tables and checking condition metadata..."):
                    results = retrieve_claims_evidence(
                        question,
                        database_url=database_url,
                        embedding_model=cached_embedding_model(embedding_name),
                        top_tables=top_tables,
                        candidate_rows=candidate_rows,
                    )
                    evidence = evidence_records(results)
                    answer = generate_claims_advice(question, results, model_name)
            except (OpenAIError, PsycopgError, RuntimeError, ValueError) as exc:
                answer = f"The advisor could not complete this request: {exc}"
                evidence = []
                st.error(answer)
            else:
                st.markdown(answer)
                with st.expander("Retrieved policy evidence"):
                    for item in evidence:
                        st.markdown(
                            f"**{item['source']} - {item['table_title']}**  \n"
                            f"Similarity: `{item['similarity']}`  \n"
                            f"Condition status: `{item['condition_status']}`  \n"
                            f"Conditions: `{item['conditions']}`"
                        )
                        st.code(item["table_csv"], language="csv")

    st.session_state.claims_messages.append(
        {"role": "assistant", "content": answer, "evidence": evidence}
    )

