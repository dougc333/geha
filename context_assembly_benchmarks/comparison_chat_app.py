"""Chat UI comparing flat semantic chunks with hierarchical parent expansion."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import psycopg
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

try:
    from .chunking_compare import compare_contexts, expected_values
    from .eval_queries import load_eval_queries
    from .generation_eval import reference_answer
    from .llm_judge import (
        evaluate_path,
        flat_context,
        hierarchical_context,
    )
    from .table_rag import (
        DEFAULT_DATABASE_URL,
        DEFAULT_EMBEDDING_MODEL,
        connect,
        expand_hybrid_tables,
        load_embedding_model,
        retrieve_hybrid_rows,
    )
except ImportError:  # Streamlit adds this directory to sys.path.
    from chunking_compare import compare_contexts, expected_values
    from eval_queries import load_eval_queries
    from generation_eval import reference_answer
    from llm_judge import evaluate_path, flat_context, hierarchical_context
    from table_rag import (
        DEFAULT_DATABASE_URL,
        DEFAULT_EMBEDDING_MODEL,
        connect,
        expand_hybrid_tables,
        load_embedding_model,
        retrieve_hybrid_rows,
    )


APP_DIRECTORY = Path(__file__).resolve().parent
# Prefer credentials and model settings exported by the launching shell. The
# project .env file supplies only values that are not already in the environment.
load_dotenv(APP_DIRECTORY / ".env", override=False)

st.set_page_config(page_title="Hierarchical RAG Demo", page_icon="💬", layout="wide")
st.title("Flat row chunks vs. hierarchical table context")
st.caption(
    "Both paths use the same BM25 + pgvector reciprocal-rank-fused child ranking. "
    "The experiment changes only what enters context: matched rows or their parent tables."
)


@st.cache_data(show_spinner=False)
def load_batch_results(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    import json

    return json.loads(path.read_text())


def batch_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for result in report["results"]:
        if result.get("error"):
            rows.append(
                {
                    "query": result["query"],
                    "flat_judge": "ERROR",
                    "hierarchical_judge": "ERROR",
                    "outcome": "failed",
                }
            )
            continue
        flat_yes = result["flat"]["verdict"]["answers_query"] == "yes"
        hierarchical_yes = result["hierarchical"]["verdict"]["answers_query"] == "yes"
        outcome = (
            "both"
            if flat_yes and hierarchical_yes
            else "flat"
            if flat_yes
            else "hierarchical"
            if hierarchical_yes
            else "neither"
        )
        rows.append(
            {
                "query": result["query"],
                "flat_judge": "YES" if flat_yes else "NO",
                "hierarchical_judge": "YES" if hierarchical_yes else "NO",
                "flat_generation": (
                    "PASS"
                    if result["flat"]
                    .get("generation_metrics", {})
                    .get("deterministic_pass")
                    else "FAIL"
                ),
                "hierarchical_generation": (
                    "PASS"
                    if result["hierarchical"]
                    .get("generation_metrics", {})
                    .get("deterministic_pass")
                    else "FAIL"
                ),
                "outcome": outcome,
                "flat_evidence": result["context_metrics"]["flat"][
                    "expected_evidence_coverage"
                ],
                "hierarchical_evidence": result["context_metrics"]["hierarchical"][
                    "expected_evidence_coverage"
                ],
            }
        )
    return rows


def context_summary_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    labels = {
        "overall": "All measured questions",
        "preference": "Multi-row preference lookup",
        "relation": "Row-to-column relationship",
    }
    kind_by_slice = {
        "overall": None,
        "preference": "Preference lookup",
        "relation": "Row-to-column relationship",
    }
    rows = []
    for slice_name, label in labels.items():
        flat = report["summary"]["flat_semantic_chunks"][slice_name]
        hierarchical = report["summary"]["table_aware_rag"][slice_name]
        kind = kind_by_slice[slice_name]
        selected = [
            result
            for result in report["results"]
            if kind is None or result["kind"] == kind
        ]
        improved = sum(
            result["table_aware_rag"]["expected_evidence_coverage"]
            > result["flat_semantic_chunks"]["expected_evidence_coverage"]
            for result in selected
        )
        rows.append(
            {
                "Evaluation type": label,
                "Questions": flat["cases"],
                "Hierarchy added evidence": f"{improved}/{flat['cases']}",
                "Flat complete": f"{flat['complete_evidence_rate']:.1%}",
                "Hierarchical complete": (
                    f"{hierarchical['complete_evidence_rate']:.1%}"
                ),
                "Coverage lift": (
                    f"{hierarchical['average_evidence_coverage'] - flat['average_evidence_coverage']:+.1%}"
                ),
                "Flat tokens": round(flat["average_estimated_tokens"]),
                "Hierarchical tokens": round(hierarchical["average_estimated_tokens"]),
            }
        )
    return rows


def hierarchy_gain_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for result in report["results"]:
        flat = result["flat_semantic_chunks"]
        hierarchical = result["table_aware_rag"]
        coverage_gain = (
            hierarchical["expected_evidence_coverage"]
            - flat["expected_evidence_coverage"]
        )
        if coverage_gain <= 0:
            continue
        rows.append(
            {
                "Evaluation type": result["kind"],
                "Question": result["query"],
                "Flat evidence": f"{flat['expected_evidence_coverage']:.0%}",
                "Hierarchical evidence": (
                    f"{hierarchical['expected_evidence_coverage']:.0%}"
                ),
                "Coverage lift": f"{coverage_gain:+.0%}",
                "Additional tokens": (
                    hierarchical["estimated_tokens"] - flat["estimated_tokens"]
                ),
            }
        )
    return rows


@st.cache_resource(show_spinner="Loading embedding model…")
def cached_embedding_model(model_name: str):
    return load_embedding_model(model_name)


def expected_parent_rank(
    results: list[dict[str, Any]], case: dict[str, Any] | None
) -> int | None:
    if not case:
        return None
    return next(
        (
            rank
            for rank, result in enumerate(results, 1)
            if result["source"] == case["source"]
            and int(result["table_number"]) == int(case["table_number"])
        ),
        None,
    )


def render_llm_evaluation(evaluation: dict[str, Any] | None) -> None:
    if not evaluation:
        st.warning("LLM answer and judgment were not run.")
        return
    verdict = evaluation["verdict"]
    answered = verdict["answers_query"] == "yes"
    st.metric("Answers the query?", "YES" if answered else "NO")
    if answered:
        st.success(verdict["reason"])
    else:
        st.error(verdict["reason"])
    st.markdown("**Generated response**")
    st.write(evaluation["answer"])
    grounding = "Yes" if verdict["grounded_in_context"] else "No"
    reference_complete = verdict.get("reference_complete")
    reference_label = (
        "N/A" if reference_complete is None else "Yes" if reference_complete else "No"
    )
    st.caption(
        f"Grounded in supplied context: {grounding} · "
        f"Reference complete: {reference_label} · "
        f"Answer + judge tokens: {evaluation['total_tokens']:,}"
    )
    metrics = evaluation.get("generation_metrics")
    if metrics:
        exact_code = "Yes" if metrics["exact_code_compliant"] else "No"
        st.caption(
            f"Deterministic gold-value coverage: "
            f"{metrics['expected_value_coverage']:.0%} · "
            f"Exact-code compliant: {exact_code}"
        )
        if metrics["unexpected_codes"]:
            st.error(
                "Unexpected codes in answer: " + ", ".join(metrics["unexpected_codes"])
            )
    if verdict["missing_information"]:
        st.markdown(
            "**Missing information:** " + "; ".join(verdict["missing_information"])
        )


def render_flat(
    chunks: list[dict[str, Any]],
    metrics: dict[str, Any],
    evaluation: dict[str, Any] | None,
) -> None:
    st.subheader("Flat hybrid chunks")
    st.caption(
        "Returns the top BM25 + pgvector RRF row chunks without parent expansion."
    )
    render_llm_evaluation(evaluation)
    a, b, c = st.columns(3)
    a.metric("Context units", metrics["context_units"])
    b.metric("Estimated tokens", metrics["estimated_tokens"])
    c.metric("Expected evidence", f"{metrics['expected_evidence_coverage']:.0%}")
    for rank, chunk in enumerate(chunks, 1):
        with st.expander(
            f"{rank}. {chunk['title']} · row {chunk['row_number']} · "
            f"RRF {chunk['hybrid_score']:.4f}",
            expanded=rank == 1,
        ):
            st.code(chunk["search_text"], language=None)
            vector_similarity = chunk["vector_similarity"]
            vector_label = (
                f"{vector_similarity:.3f}" if vector_similarity is not None else "—"
            )
            st.caption(
                f"Vector rank: {chunk['vector_rank'] or '—'} · "
                f"BM25 rank: {chunk['bm25_rank'] or '—'} · "
                f"Vector cosine: {vector_label} · "
                f"BM25 score: {chunk['bm25_score']:.3f}"
            )


def render_hierarchical(
    tables: list[dict[str, Any]],
    metrics: dict[str, Any],
    case: dict[str, Any] | None,
    evaluation: dict[str, Any] | None,
) -> None:
    st.subheader("Table-aware hybrid RAG")
    st.caption("Expands the same fused child-row ranking to complete parent tables.")
    render_llm_evaluation(evaluation)
    a, b, c = st.columns(3)
    a.metric("Parent tables", metrics["context_units"])
    b.metric("Estimated tokens", metrics["estimated_tokens"])
    c.metric("Expected evidence", f"{metrics['expected_evidence_coverage']:.0%}")
    rank = expected_parent_rank(tables, case)
    if case and rank:
        st.success(f"Expected parent table retrieved at rank {rank}.")
    elif case:
        st.warning("Expected parent table was not retrieved.")
    for index, table in enumerate(tables, 1):
        with st.expander(
            f"{index}. {table['title']} · {table['source']} · RRF {table['hybrid_score']:.4f}",
            expanded=index == 1,
        ):
            if isinstance(table["rows_json"], list):
                st.dataframe(
                    table["rows_json"], use_container_width=True, hide_index=True
                )
            else:
                st.code(table["full_csv"], language="text")


def render_comparison(run: dict[str, Any]) -> None:
    with st.chat_message("user"):
        st.write(run["query"])
    with st.chat_message("assistant"):
        flat_col, hierarchy_col = st.columns(2)
        with flat_col:
            render_flat(
                run["flat_chunks"],
                run["metrics"]["flat"],
                run.get("llm", {}).get("flat"),
            )
        with hierarchy_col:
            render_hierarchical(
                run["parent_tables"],
                run["metrics"]["hierarchical"],
                run["case"],
                run.get("llm", {}).get("hierarchical"),
            )

        flat = run["metrics"]["flat"]
        hierarchical = run["metrics"]["hierarchical"]
        token_delta = hierarchical["estimated_tokens"] - flat["estimated_tokens"]
        coverage_delta = (
            hierarchical["expected_evidence_coverage"]
            - flat["expected_evidence_coverage"]
        )
        st.info(
            f"Hierarchy changed estimated context by {token_delta:+,} tokens and expected "
            f"evidence coverage by {coverage_delta:+.0%}. More context is useful only when "
            "the additional neighboring rows contain required relationships."
        )


with st.sidebar:
    st.header("Experiment controls")
    database_url = st.text_input(
        "PostgreSQL URL",
        value=os.getenv("GEHA_RAG_DATABASE_URL", DEFAULT_DATABASE_URL),
        type="password",
    )
    model_name = st.text_input("Embedding checkpoint", value=DEFAULT_EMBEDDING_MODEL)
    top_chunks = st.slider("Flat chunks", 1, 10, 5)
    top_tables = st.slider("Hierarchical parents", 1, 5, 3)
    candidate_rows = st.slider("Candidate child rows", 5, 100, 30, step=5)
    st.divider()
    st.subheader("LLM evaluation")
    enable_llm = st.checkbox("Generate and judge both responses", value=True)
    answer_model = st.text_input(
        "Answer model", value=os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    )
    judge_model = st.text_input(
        "Judge model", value=os.getenv("OPENAI_JUDGE_MODEL", "gpt-4o-mini")
    )
    if enable_llm and not os.getenv("OPENAI_API_KEY"):
        st.warning("Set OPENAI_API_KEY in chunking_benchmarks/.env before submitting.")
    if st.button("Clear conversation"):
        st.session_state.comparison_runs = []

context_report = load_batch_results(APP_DIRECTORY / "hybrid_context_results.json")
if context_report:
    with st.expander("Where hierarchical context makes a difference", expanded=True):
        st.code(
            """query -> BM25 + pgvector RRF child ranking
  |-> flat: top 5 matching rows
  `-> hierarchical: group by parent -> top 3 complete tables""",
            language=None,
        )
        st.markdown(
            "The saved benchmark holds retrieval constant and changes only context "
            "assembly. **Hierarchy added expected evidence in 17 of 41 questions.**"
        )
        st.dataframe(
            context_summary_rows(context_report),
            use_container_width=True,
            hide_index=True,
        )
        with st.expander("Show the questions where hierarchy added evidence"):
            st.dataframe(
                hierarchy_gain_rows(context_report),
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("**Evaluation types to add next**")
        st.dataframe(
            [
                {
                    "Type": "Single-row fact lookup",
                    "Expected effect": "Little benefit",
                    "What it tests": "Whether expansion adds cost or distractors",
                },
                {
                    "Type": "Exhaustive multi-row list",
                    "Expected effect": "Strong benefit",
                    "What it tests": "Whether every qualifying item is preserved",
                },
                {
                    "Type": "Qualifier or exception list",
                    "Expected effect": "Strong benefit",
                    "What it tests": "Whether conditions remain attached to the rule",
                },
                {
                    "Type": "Cross-table synthesis",
                    "Expected effect": "Parent expansion alone is insufficient",
                    "What it tests": "Multi-parent retrieval and synthesis",
                },
                {
                    "Type": "Unanswerable or hard negative",
                    "Expected effect": "Possible downside",
                    "What it tests": "Abstention despite extra neighboring context",
                },
            ],
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            "Only multi-row preference lookups and row-to-column relationships are "
            "measured today. The remaining rows are proposed evaluation categories."
        )

cases = load_eval_queries()
case_by_query = {case["query"]: case for case in cases}
evaluation_type = st.selectbox(
    "Evaluation type",
    ["All measured types", *sorted({case["kind"] for case in cases})],
)
filtered_cases = [
    case
    for case in cases
    if evaluation_type == "All measured types" or case["kind"] == evaluation_type
]
default_index = next(
    (
        index
        for index, case in enumerate(filtered_cases)
        if case["id"] == "bendamustine_j9036"
    ),
    0,
)
suggested = st.selectbox(
    "Evaluation-backed example",
    filtered_cases,
    index=default_index,
    format_func=lambda case: case["query"],
)
run_example = st.button("Run selected example", type="primary")
st.caption("Run the selected case, or submit a custom question in the chat box.")

batch_report = load_batch_results(APP_DIRECTORY / "chunking_judge_results.json")
if batch_report:
    with st.expander("All suggested queries — generation evaluation", expanded=True):
        summary = batch_report["summary"]
        a, b, c, d = st.columns(4)
        a.metric("Queries completed", summary["queries_completed"])
        b.metric("Flat judge YES", f"{summary['flat_answer_yes_rate']:.1%}")
        c.metric(
            "Hierarchical judge YES",
            f"{summary['hierarchical_answer_yes_rate']:.1%}",
        )
        d.metric(
            "Hierarchical exact pass",
            f"{summary.get('hierarchical_deterministic_pass_rate', 0):.1%}",
        )
        st.dataframe(
            batch_rows(batch_report), use_container_width=True, hide_index=True
        )

if "comparison_runs" not in st.session_state:
    st.session_state.comparison_runs = []

for prior_run in st.session_state.comparison_runs:
    render_comparison(prior_run)

query = st.chat_input("Ask about a policy table…")
if run_example:
    query = suggested["query"]
if query:
    case = case_by_query.get(query.strip())
    if enable_llm and not os.getenv("OPENAI_API_KEY"):
        st.error("LLM evaluation is enabled, but OPENAI_API_KEY is not configured.")
        st.stop()
    try:
        with st.spinner("Running both context strategies…"):
            model = cached_embedding_model(model_name)
            with connect(database_url) as connection:
                hybrid_rows = retrieve_hybrid_rows(
                    connection,
                    model,
                    query,
                    limit=max(candidate_rows, top_chunks),
                    vector_candidates=max(100, candidate_rows * 3),
                )
                flat_chunks = hybrid_rows[:top_chunks]
                parent_tables = expand_hybrid_tables(
                    connection, hybrid_rows, top_tables
                )
            llm_results: dict[str, Any] = {}
            if enable_llm:
                client = OpenAI()
                reference = reference_answer(case)
                llm_results = {
                    "flat": evaluate_path(
                        client,
                        answer_model=answer_model,
                        judge_model=judge_model,
                        query=query,
                        context=flat_context(flat_chunks),
                        reference=reference,
                        case=case,
                    ),
                    "hierarchical": evaluate_path(
                        client,
                        answer_model=answer_model,
                        judge_model=judge_model,
                        query=query,
                        context=hierarchical_context(parent_tables),
                        reference=reference,
                        case=case,
                    ),
                }
    except (psycopg.Error, OSError, ValueError, OpenAIError, RuntimeError) as error:
        st.error(f"Comparison could not run: {error}")
        st.info(
            "Check PostgreSQL ingestion, OPENAI_API_KEY, model access, and network connectivity."
        )
        st.stop()

    run = {
        "query": query,
        "case": case,
        "expected_values": expected_values(case),
        "flat_chunks": flat_chunks,
        "parent_tables": parent_tables,
        "metrics": compare_contexts(flat_chunks, parent_tables, case),
        "llm": llm_results,
        "models": {"answer": answer_model, "judge": judge_model},
    }
    st.session_state.comparison_runs.append(run)
    render_comparison(run)

with st.expander("What this comparison does—and does not—prove"):
    st.markdown(
        """
        - The query, BM25 corpus, embedding model, pgvector index, and RRF ranking are identical.
        - Flat mode returns the top fused row chunks without expansion.
        - Table-aware mode expands the same fused child ranking to complete parent tables.
        - Evaluation-backed questions report how many expected values appear in each context.
        - Token counts are deterministic character-based estimates, not provider billing values.
        - The evidence display is raw retrieval output; the generated responses cannot alter it.
        - Each side is answered separately and judged separately with the same blind rubric.
        - `YES` requires a complete answer with every factual claim supported by that side's context.
        - LLM judges are useful evaluation signals, not ground truth; use labeled human-reviewed
          cases for promotion decisions.
        - This demonstrates context assembly effects; it is not a general proof that one strategy
          wins for every document type or question.
        """
    )
