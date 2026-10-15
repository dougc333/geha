"""Streamlit UI for inspecting GEHA parent-child table retrieval."""

from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path
from typing import Any

import psycopg
import streamlit as st
from dotenv import load_dotenv

try:
    from .eval_queries import load_eval_queries
    from .table_rag import (
        DEFAULT_DATABASE_URL,
        DEFAULT_EMBEDDING_MODEL,
        connect,
        load_embedding_model,
        retrieve_child_rows,
        retrieve_tables,
    )
except ImportError:  # Streamlit runs this file with its directory on sys.path.
    from eval_queries import load_eval_queries
    from table_rag import (
        DEFAULT_DATABASE_URL,
        DEFAULT_EMBEDDING_MODEL,
        connect,
        load_embedding_model,
        retrieve_child_rows,
        retrieve_tables,
    )


APP_DIRECTORY = Path(__file__).resolve().parent
load_dotenv(APP_DIRECTORY / ".env", override=True)

st.set_page_config(
    page_title="GEHA Parent–Child Table Retrieval",
    page_icon="🔎",
    layout="wide",
)

st.markdown(
    """
    <style>
      .block-container {max-width: 1220px; padding-top: 2rem;}
      .hero {
        padding: 1.35rem 1.55rem; border: 1px solid #d9e2f2; border-radius: 18px;
        background: linear-gradient(135deg, #f2f7ff 0%, #f2fff7 100%);
        margin-bottom: 1rem;
      }
      .hero h1 {margin: 0 0 .3rem 0; color: #17243a; font-size: 2rem;}
      .hero p {margin: 0; color: #526076;}
      .flow {
        padding: .8rem 1rem; border-left: 4px solid #4f7fdb; border-radius: 8px;
        background: #f7f9fc; color: #26364d; margin: .5rem 0 1rem;
      }
      .match {color: #137a45; font-weight: 700;}
      .miss {color: #b5473c; font-weight: 700;}
      div[data-testid="stMetric"] {border: 1px solid #e2e7ef; padding: .7rem; border-radius: 12px;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner="Loading the 384-dimensional embedding model…")
def cached_embedding_model(model_name: str):
    return load_embedding_model(model_name)


def database_counts(database_url: str) -> tuple[int, int]:
    with connect(database_url) as connection:
        row = connection.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM policy_tables) AS parent_count,
                (SELECT COUNT(*) FROM policy_table_vectors) AS child_count
            """
        ).fetchone()
    return int(row["parent_count"]), int(row["child_count"])


def expected_summary(case: dict[str, Any]) -> str:
    expected = case["expected"]
    if case["kind"] == "Preference lookup":
        return ", ".join(expected)
    return "; ".join(
        ", ".join(f"{key}={value}" for key, value in row.items())
        for row in expected
    )


def display_results(
    results: list[dict[str, Any]],
    child_rows: list[dict[str, Any]],
    selected_case: dict[str, Any] | None,
) -> None:
    rows_by_table: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in child_rows:
        rows_by_table[int(row["table_id"])].append(row)

    for rank, result in enumerate(results, 1):
        expected_match = bool(
            selected_case
            and result["source"] == selected_case["source"]
            and int(result["table_number"]) == int(selected_case["table_number"])
        )
        badge = " · expected eval table" if expected_match else ""
        st.subheader(f"{rank}. {result['title']}{badge}")

        source_col, table_col, score_col = st.columns([2.5, 1, 1])
        source_col.metric("Parent source", result["source"])
        table_col.metric("Table", result["table_number"])
        score_col.metric("Best child cosine similarity", f"{result['similarity']:.3f}")

        st.markdown("**Matching child rows** — these row embeddings caused the parent table to rank.")
        matches = rows_by_table[int(result["id"])]
        for child in matches:
            with st.expander(
                f"Child row {child['row_number']} · similarity {child['similarity']:.3f}",
                expanded=child["match_rank"] == 1,
            ):
                st.code(child["search_text"], language=None)

        st.markdown("**Complete parent table returned**")
        records = result["rows_json"]
        if isinstance(records, list):
            st.dataframe(records, use_container_width=True, hide_index=True)
        else:
            st.code(result["full_csv"], language="text")
        st.download_button(
            "Download parent table as CSV",
            data=result["full_csv"],
            file_name=f"{Path(result['source']).stem}-table-{result['table_number']}.csv",
            mime="text/csv",
            key=f"download-{result['id']}",
        )
        st.divider()


st.markdown(
    """
    <div class="hero">
      <h1>Parent–Child Coverage Policy Retrieval</h1>
      <p>Search small row embeddings, then return the complete table that owns the best matching rows.</p>
    </div>
    <div class="flow">
      Question → 384-D query embedding → cosine search over child rows → group by <code>table_id</code> → complete parent tables
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Retrieval controls")
    database_url = st.text_input(
        "PostgreSQL URL",
        value=os.getenv("GEHA_RAG_DATABASE_URL", DEFAULT_DATABASE_URL),
        type="password",
    )
    embedding_model_name = st.text_input(
        "Embedding checkpoint", value=DEFAULT_EMBEDDING_MODEL
    )
    top_tables = st.slider("Parent tables to return", 1, 5, 3)
    candidate_rows = st.slider("Candidate child rows", 5, 100, 30, step=5)
    matches_per_table = st.slider("Child matches shown per parent", 1, 8, 3)
    st.caption("The database schema requires a 384-dimensional embedding model.")

eval_cases = load_eval_queries()
case_by_id = {case["id"]: case for case in eval_cases}
selection = st.selectbox(
    "Suggested queries from the evaluation suites",
    options=["custom"] + [case["id"] for case in eval_cases],
    format_func=lambda case_id: (
        "Write a custom query"
        if case_id == "custom"
        else f"{case_by_id[case_id]['kind']} · {case_by_id[case_id]['query']}"
    ),
)
selected_case = case_by_id.get(selection)
query_default = selected_case["query"] if selected_case else ""

if selected_case:
    st.caption(
        f"Expected parent: `{selected_case['source']}` table {selected_case['table_number']}  •  "
        f"Expected values: {expected_summary(selected_case)}"
    )

with st.form("retrieval-form"):
    query = st.text_area(
        "Question",
        value=query_default,
        height=90,
        placeholder="For bendamustine HCPCS J9036, what drug and prior authorization are listed?",
        key=f"query-{selection}",
    )
    submitted = st.form_submit_button("Retrieve parent tables", type="primary")

if submitted:
    if not query.strip():
        st.warning("Enter a question or choose an evaluation query.")
        st.stop()

    try:
        with st.spinner("Encoding the question and searching child rows…"):
            model = cached_embedding_model(embedding_model_name)
            parent_count, child_count = database_counts(database_url)
            with connect(database_url) as connection:
                results = retrieve_tables(
                    connection,
                    model,
                    query.strip(),
                    top_tables,
                    candidate_rows,
                )
                child_rows = retrieve_child_rows(
                    connection,
                    model,
                    query.strip(),
                    [int(result["id"]) for result in results],
                    matches_per_table,
                )
    except (psycopg.Error, OSError, ValueError) as error:
        st.error(f"Retrieval could not run: {error}")
        st.info(
            "Start pgvector, run `table_rag.py init-db`, and ingest the coverage-policy CSV files."
        )
        st.stop()

    if not results:
        st.warning("No parent tables were returned. Confirm that the database was ingested.")
        st.stop()

    metric1, metric2, metric3, metric4 = st.columns(4)
    metric1.metric("Indexed parent tables", parent_count)
    metric2.metric("Indexed child rows", child_count)
    metric3.metric("Parents returned", len(results))
    metric4.metric("Embedding dimensions", model.get_embedding_dimension())

    if selected_case:
        hit_rank = next(
            (
                rank
                for rank, result in enumerate(results, 1)
                if result["source"] == selected_case["source"]
                and int(result["table_number"]) == int(selected_case["table_number"])
            ),
            None,
        )
        if hit_rank:
            st.success(f"Evaluation target retrieved at parent-table rank {hit_rank}.")
        else:
            st.warning("The expected evaluation table was not in the returned parent set.")

    display_results(results, child_rows, selected_case)

with st.expander("What this demo proves"):
    st.markdown(
        """
        - A child is one row plus its headers, source filename, and inferred table title.
        - Each child row carries a `table_id` foreign key to its complete parent table.
        - Similarity ranks rows; the best row score ranks its parent.
        - The application returns the complete table so neighboring rows and headers remain available.
        - Retrieval is semantic-only; exact-code search and reranking are not included.
        """
    )
