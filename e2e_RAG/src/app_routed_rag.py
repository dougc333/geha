"""Streamlit UI for comparing routed RAG strategies on an uploaded PDF."""

from __future__ import annotations

import hashlib
import gc
import os
import tempfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from routed_rag import RAGConfig, RoutedRAG, document_key


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

st.set_page_config(page_title="Routed PDF RAG", page_icon="🧭", layout="wide")
st.title("🧭 Routed PDF RAG")
st.caption(
    "Compare vector, hybrid BM25 + vector, HyDE, query expansion, and "
    "parent-child retrieval through one LangGraph workflow."
)


def save_upload(uploaded_file) -> Path:
    digest = hashlib.sha256(uploaded_file.getvalue()).hexdigest()[:16]
    target = Path(tempfile.gettempdir()) / f"routed-rag-{digest}.pdf"
    if not target.exists():
        target.write_bytes(uploaded_file.getvalue())
    return target


def show_document(document, rank: int):
    page = document.metadata.get("page", "?")
    chunk_id = document_key(document)
    rerank_score = document.metadata.get("rerank_score")
    fusion_score = document.metadata.get("fusion_score")
    channels = ", ".join(document.metadata.get("retrieval_channels", []))

    label = f"#{rank} · page {page} · {chunk_id}"
    if channels:
        label += f" · {channels}"
    if rerank_score is not None:
        label += f" · rerank {rerank_score:.1f}"
    elif fusion_score is not None:
        label += f" · fusion {fusion_score:.4f}"

    with st.expander(label, expanded=rank == 1):
        st.text(document.page_content)
        st.json(document.metadata)


with st.sidebar:
    st.header("Document and strategy")
    uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])

    strategy_labels = {
        "Auto route": "auto",
        "Vector search": "vector",
        "Hybrid: BM25 + vector": "hybrid",
        "HyDE": "hyde",
        "Query expansion": "query_expansion",
        "Parent-child": "parent_child",
    }
    selected_label = st.selectbox("Retrieval strategy", list(strategy_labels))
    selected_strategy = strategy_labels[selected_label]

    with st.expander("Index and model settings"):
        chat_model = st.text_input("Chat model", value="gpt-4.1")
        embedding_model = st.text_input(
            "Embedding model", value="text-embedding-3-small"
        )
        chunk_size = st.slider("Standard chunk size (tokens)", 100, 800, 300, 20)
        chunk_overlap = st.slider("Chunk overlap (tokens)", 0, 150, 40, 10)
        parent_size = st.slider("Parent size (tokens)", 400, 1600, 900, 50)
        child_size = st.slider("Child size (tokens)", 100, 500, 220, 20)
        candidate_k = st.slider("Candidates before reranking", 2, 10, 4)
        final_k = st.slider("Chunks sent to generation", 1, candidate_k, 2)
        use_reranker = st.checkbox("Use LLM reranker", value=True)
        st.caption("Reranker pricing (USD per 1M tokens)")
        rerank_input_price = st.number_input(
            "Input token price", min_value=0.0, value=2.00, step=0.10
        )
        rerank_cached_input_price = st.number_input(
            "Cached-input price", min_value=0.0, value=0.50, step=0.05
        )
        rerank_output_price = st.number_input(
            "Output token price", min_value=0.0, value=8.00, step=0.50
        )

    build_clicked = st.button(
        "Build / rebuild index", type="primary", use_container_width=True
    )
    reset_clicked = st.button(
        "Reset database", use_container_width=True, help="Delete both Chroma indexes"
    )


if "engine" not in st.session_state:
    st.session_state.engine = None
    st.session_state.engine_key = None
    st.session_state.messages = []
    st.session_state.database_reset = False

if reset_clicked:
    engine_to_reset = st.session_state.engine
    try:
        if engine_to_reset is not None:
            engine_to_reset.reset_indexes()
        st.session_state.engine = None
        st.session_state.engine_key = None
        st.session_state.messages = []
        st.session_state.database_reset = True
        gc.collect()
        st.success(
            "Database reset: standard and parent-child Chroma collections now contain zero records."
        )
    except Exception as exc:
        st.exception(exc)
    st.stop()

if uploaded_file is None:
    st.info("Upload a PDF, configure the strategy, and build the index.")
    st.stop()

if not os.getenv("OPENAI_API_KEY"):
    st.error("OPENAI_API_KEY is not set. Add it to e2e_RAG/.env or your shell.")
    st.stop()

pdf_path = save_upload(uploaded_file)
config = RAGConfig(
    chat_model=chat_model,
    embedding_model=embedding_model,
    chunk_size=chunk_size,
    chunk_overlap=chunk_overlap,
    parent_size=parent_size,
    child_size=child_size,
    candidate_k=candidate_k,
    final_k=final_k,
    use_reranker=use_reranker,
    rerank_input_cost_per_million=rerank_input_price,
    rerank_cached_input_cost_per_million=rerank_cached_input_price,
    rerank_output_cost_per_million=rerank_output_price,
)
engine_key = (hashlib.sha256(uploaded_file.getvalue()).hexdigest(), config)

needs_build = st.session_state.engine_key != engine_key

if build_clicked or (needs_build and not st.session_state.database_reset):
    try:
        with st.status("Extracting, chunking, embedding, and indexing…", expanded=True):
            st.session_state.engine = RoutedRAG(pdf_path, config)
            st.session_state.engine_key = engine_key
            st.session_state.messages = []
            st.session_state.database_reset = False
            st.write(f"Pages with text: {len(st.session_state.engine.pages)}")
            st.write(f"Standard chunks: {len(st.session_state.engine.chunks)}")
            st.write(f"Parent chunks: {len(st.session_state.engine.parents)}")
            st.write(f"Searchable child chunks: {len(st.session_state.engine.children)}")
    except Exception as exc:
        st.exception(exc)
        st.stop()

if st.session_state.engine is None:
    st.info("The database is empty. Click **Build / rebuild index** to index this PDF.")
    empty_metrics = st.columns(4)
    empty_metrics[0].metric("Pages", 0)
    empty_metrics[1].metric("Chunks", 0)
    empty_metrics[2].metric("Parents", 0)
    empty_metrics[3].metric("Children", 0)
    st.stop()

engine: RoutedRAG = st.session_state.engine

metrics = st.columns(4)
metrics[0].metric("Pages", len(engine.pages))
metrics[1].metric("Chunks", len(engine.chunks))
metrics[2].metric("Parents", len(engine.parents))
metrics[3].metric("Children", len(engine.children))

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if query := st.chat_input("Ask a question about the uploaded PDF"):
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        try:
            with st.spinner("Routing, retrieving, reranking, and generating…"):
                result = engine.ask(query, selected_strategy)

            st.markdown(result["answer"])
            st.session_state.messages.append(
                {"role": "assistant", "content": result["answer"]}
            )

            st.success(
                f"Route: {result['strategy']} — {result['route_reason']}",
                icon="🧭",
            )

            rerank_metrics = result.get("rerank_metrics", {})
            st.markdown("#### Reranker usage and estimated cost")
            usage_columns = st.columns(5)
            usage_columns[0].metric(
                "Input tokens", f"{rerank_metrics.get('input_tokens', 0):,}"
            )
            usage_columns[1].metric(
                "Cached input", f"{rerank_metrics.get('cached_input_tokens', 0):,}"
            )
            usage_columns[2].metric(
                "Output tokens", f"{rerank_metrics.get('output_tokens', 0):,}"
            )
            usage_columns[3].metric(
                "Total tokens", f"{rerank_metrics.get('total_tokens', 0):,}"
            )
            usage_columns[4].metric(
                "Estimated cost",
                f"${rerank_metrics.get('total_cost_usd', 0.0):.6f}",
            )
            st.caption(
                f"Model: {rerank_metrics.get('model', chat_model)} · "
                f"API calls: {rerank_metrics.get('api_calls', 0)} · "
                f"Candidates: {rerank_metrics.get('candidate_count', 0)} · "
                f"Latency: {rerank_metrics.get('latency_ms', 0.0):,.0f} ms · "
                "Cost uses the configurable standard token rates in the sidebar."
            )
            with st.expander("Reranker cost breakdown"):
                st.json(rerank_metrics)

            if result.get("expanded_queries"):
                st.markdown("**Expanded queries**")
                for expanded in result["expanded_queries"]:
                    st.markdown(f"- {expanded}")

            if result.get("hypothetical_document"):
                with st.expander("HyDE hypothetical document"):
                    st.write(result["hypothetical_document"])

            candidate_tab, final_tab = st.tabs(
                ["Retrieved candidates", "Context sent to generation"]
            )
            with candidate_tab:
                for rank, document in enumerate(result.get("candidates", []), 1):
                    show_document(document, rank)
            with final_tab:
                for rank, document in enumerate(
                    result.get("reranked_documents", []), 1
                ):
                    show_document(document, rank)
        except Exception as exc:
            st.exception(exc)
