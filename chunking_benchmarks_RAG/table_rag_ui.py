"""Streamlit UI for deterministic-versus-LLM table-RAG comparisons."""

from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAIError
from psycopg import Error as PsycopgError

try:  # Support `streamlit run` from either the repository or this directory.
    from .table_rag import (
        DEFAULT_DATABASE_URL,
        DEFAULT_EMBEDDING_MODEL,
        load_embedding_model,
    )
    from .table_rag_comparison import (
        DEFAULT_EVAL_PATH,
        ComparisonSettings,
        compare_case,
        langfuse_client,
        optional_price,
        summarize,
    )
except ImportError:  # pragma: no cover - Streamlit direct-script execution
    from table_rag import (
        DEFAULT_DATABASE_URL,
        DEFAULT_EMBEDDING_MODEL,
        load_embedding_model,
    )
    from table_rag_comparison import (
        DEFAULT_EVAL_PATH,
        ComparisonSettings,
        compare_case,
        langfuse_client,
        optional_price,
        summarize,
    )


load_dotenv(Path(__file__).with_name(".env"), override=True)
st.set_page_config(page_title="Table-RAG A/B Evaluation", layout="wide")


@st.cache_resource
def cached_embedding_model(name: str):
    return load_embedding_model(name)


def price_default(name: str) -> float:
    return optional_price(name) or 0.0


def result_rows(results: list[dict]) -> list[dict]:
    return [
        {
            "case": item["case_id"],
            "expected table": item["expected_table_retrieved"],
            "deterministic correct": item["deterministic"]["correct"],
            "LLM correct": item["llm"]["correct"],
            "LLM tokens": item["llm"]["usage"]["total"],
            "LLM cost (USD)": item["llm"]["cost_usd"],
            "LLM latency (ms)": round(item["llm"]["latency_ms"], 1),
            "error": item["llm"]["error"],
            "Langfuse trace": item["langfuse_trace_url"],
        }
        for item in results
    ]


st.title("Table-RAG: deterministic vs. LLM")
st.caption(
    "Both methods receive the same top retrieved table. Objective product-list "
    "accuracy is compared with token usage, configured cost, latency, and traces."
)

with st.sidebar:
    st.header("Configuration")
    database_url = st.text_input(
        "PostgreSQL URL",
        os.getenv("GEHA_RAG_DATABASE_URL", DEFAULT_DATABASE_URL),
        type="password",
    )
    embedding_name = st.text_input("Embedding model", DEFAULT_EMBEDDING_MODEL)
    llm_model = st.text_input("LLM model", os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"))
    candidate_rows = st.number_input("Candidate rows", 1, 200, 20)
    input_price = st.number_input(
        "Input price / 1M tokens (USD)",
        min_value=0.0,
        value=price_default("OPENAI_INPUT_COST_PER_1M_USD"),
        format="%.6f",
    )
    output_price = st.number_input(
        "Output price / 1M tokens (USD)",
        min_value=0.0,
        value=price_default("OPENAI_OUTPUT_COST_PER_1M_USD"),
        format="%.6f",
    )
    langfuse_base = os.getenv("LANGFUSE_BASE_URL", "http://localhost:3000")
    tracing_configured = bool(
        os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")
    )
    st.write("Langfuse tracing:", "configured" if tracing_configured else "disabled")
    st.link_button("Open Langfuse", langfuse_base)

cases = json.loads(DEFAULT_EVAL_PATH.read_text(encoding="utf-8"))
settings = ComparisonSettings(
    database_url=database_url,
    model=llm_model,
    candidate_rows=int(candidate_rows),
    input_price_per_million=input_price if input_price else None,
    output_price_per_million=output_price if output_price else None,
)

single_tab, batch_tab = st.tabs(["Single case", "Batch error-rate comparison"])

with single_tab:
    selected_id = st.selectbox("Evaluation case", [case["id"] for case in cases])
    selected = next(case for case in cases if case["id"] == selected_id)
    st.write(selected["query"])
    if st.button("Run single comparison", type="primary"):
        if not os.getenv("OPENAI_API_KEY"):
            st.error("Set OPENAI_API_KEY in chunking_benchmarks_RAG/.env first.")
        else:
            with st.spinner("Retrieving one table and running both methods..."):
                try:
                    result = compare_case(
                        selected,
                        cached_embedding_model(embedding_name),
                        settings,
                        langfuse=langfuse_client(),
                    )
                    client = langfuse_client()
                    if client:
                        client.flush()
                except (OpenAIError, PsycopgError, RuntimeError, ValueError) as exc:
                    st.exception(exc)
                else:
                    left, right = st.columns(2)
                    with left:
                        st.subheader("Deterministic")
                        st.metric(
                            "Correct",
                            "Yes" if result["deterministic"]["correct"] else "No",
                        )
                        st.metric("LLM tokens", 0)
                        st.metric("Cost", "$0.000000")
                        st.json(result["deterministic"]["products"])
                    with right:
                        st.subheader("LLM")
                        st.metric(
                            "Correct", "Yes" if result["llm"]["correct"] else "No"
                        )
                        st.metric("Tokens", result["llm"]["usage"]["total"])
                        cost = result["llm"]["cost_usd"]
                        st.metric(
                            "Configured cost",
                            f"${cost:.6f}" if cost is not None else "See Langfuse",
                        )
                        st.json(result["llm"]["products"])
                    if result["langfuse_trace_url"]:
                        st.link_button(
                            "Open this trace in Langfuse", result["langfuse_trace_url"]
                        )
                    if result["llm"]["error"]:
                        st.error(result["llm"]["error"])

with batch_tab:
    limit = st.slider("Number of cases", 1, len(cases), min(5, len(cases)))
    st.warning(
        f"This will make {limit} paid LLM calls. The deterministic method makes none."
    )
    confirmed = st.checkbox("I understand this batch makes paid API calls")
    if st.button("Run batch comparison", disabled=not confirmed):
        if not os.getenv("OPENAI_API_KEY"):
            st.error("Set OPENAI_API_KEY in chunking_benchmarks_RAG/.env first.")
        else:
            results = []
            progress = st.progress(0)
            status = st.empty()
            model = cached_embedding_model(embedding_name)
            lf_client = langfuse_client()
            for index, case in enumerate(cases[:limit], 1):
                status.write(f"Running {index}/{limit}: `{case['id']}`")
                results.append(compare_case(case, model, settings, langfuse=lf_client))
                progress.progress(index / limit)
            if lf_client:
                lf_client.flush()
            summary = summarize(results)
            deterministic = summary["deterministic"]
            llm = summary["llm"]
            columns = st.columns(4)
            columns[0].metric(
                "Deterministic error", f"{deterministic['error_rate']:.1%}"
            )
            columns[1].metric("LLM error", f"{llm['error_rate']:.1%}")
            columns[2].metric("LLM tokens", f"{llm['tokens']:,}")
            columns[3].metric(
                "LLM configured cost",
                f"${llm['cost_usd']:.6f}"
                if llm["cost_usd"] is not None
                else "See Langfuse",
            )
            st.dataframe(
                result_rows(results),
                use_container_width=True,
                column_config={"Langfuse trace": st.column_config.LinkColumn()},
            )
            st.download_button(
                "Download comparison JSON",
                json.dumps({"summary": summary, "results": results}, indent=2),
                file_name="table_rag_ab_comparison.json",
                mime="application/json",
            )

st.caption(
    "Local cost is calculated only when current per-million-token prices are supplied. "
    "Langfuse can infer cost from its model definition when usage is recorded."
)
