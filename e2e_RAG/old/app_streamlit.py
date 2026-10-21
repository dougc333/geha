# Adapted from https://docs.streamlit.io/knowledge-base/tutorials/build-conversational-apps#build-a-simple-chatbot-gui-with-streaming
import os

import gc
import hashlib
import tempfile
import uuid
from pathlib import Path

import streamlit as st

from rag_client import rag_client
from loguru import logger

if "loguru_file_sink" not in st.session_state:
    st.session_state.loguru_file_sink = logger.add(
        "rag_app.log",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
    )

logger.info("Streamlit application rerun")

if "id" not in st.session_state:
    st.session_state.id = uuid.uuid4()
    st.session_state.file_cache = {}

session_id = st.session_state.id
client = None
DEFAULT_PDF_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "2306.02707.pdf"
)


def reset_chat():
    st.session_state.messages = []
    st.session_state.context = None
    gc.collect()


def display_pdf(pdf_bytes):
    st.markdown("### PDF Preview")
    # Native viewer avoids browser restrictions on base64 data-URL iframes.
    st.pdf(pdf_bytes, height=800)


def load_cached_client(pdf_path, pdf_bytes, source_name):
    document_id = hashlib.sha256(pdf_bytes).hexdigest()
    file_key = (
        f"client-v{rag_client.CLIENT_VERSION}-"
        f"index-v{rag_client.INDEX_VERSION}-{document_id}"
    )
    if file_key not in st.session_state.file_cache:
        st.session_state.file_cache[file_key] = rag_client(
            files=str(pdf_path),
            document_id=document_id,
            source_name=source_name,
        )
    return st.session_state.file_cache[file_key]


with st.sidebar:
    generate_with_openai = st.toggle(
        "Generate answer with OpenAI",
        value=False,
        help=(
            "Off: do retrieval only and display the raw top-K chunks. "
            "On: send selected excerpts and the question to OpenAI to "
            "generate an answer."
        ),
    )
    retrieval_mode = st.radio(
        "Retrieval mode",
        options=rag_client.RETRIEVAL_MODES,
        index=0,
        help=(
            "Vector only and BM25 only keep retrieval isolated. "
            "Hybrid deliberately combines their rankings."
        ),
    )
    use_reranker = st.toggle(
        "Enable ColBERT reranker",
        value=False,
        help="Leave this off to inspect the raw retrieval order.",
    )
    top_k = st.slider(
        "Chunks to display",
        min_value=1,
        max_value=10,
        value=5,
        disabled=generate_with_openai,
        help="Used in retrieval-only mode. No OpenAI request is made.",
    )
    vector_score_threshold = st.slider(
        "Minimum vector relevance",
        min_value=0.0,
        max_value=1.0,
        value=rag_client.DEFAULT_VECTOR_SCORE_THRESHOLD,
        step=0.01,
        disabled=retrieval_mode == "BM25 only",
        help=(
            "Vector-only queries below this score return no semantic match. "
            "The default was calibrated against this Orca document."
        ),
    )
    st.caption(
        f"Active vector threshold: **{vector_score_threshold:.2f}**"
    )
    st.caption("Chunker: **Docling HybridChunker · full document**")

    uploaded_file = st.file_uploader(
        "Optional: replace the default Orca PDF",
        type="pdf",
    )
    if uploaded_file is None:
        if not DEFAULT_PDF_PATH.exists():
            st.error(f"Default Orca PDF is missing: {DEFAULT_PDF_PATH}")
            active_pdf_bytes = None
        else:
            active_pdf_bytes = DEFAULT_PDF_PATH.read_bytes()
            with st.status(
                "loading saved Orca index",
                expanded=False,
                state="running",
            ):
                client = load_cached_client(
                    DEFAULT_PDF_PATH,
                    active_pdf_bytes,
                    DEFAULT_PDF_PATH.name,
                )
                st.write("Orca index ready")
            st.caption(f"Default document: **{DEFAULT_PDF_PATH.name}**")
    else:
        active_pdf_bytes = uploaded_file.getvalue()
        with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_file, st.status(
            "processing uploaded document", expanded=False, state="running"
        ):
            with open(temp_file.name, "wb") as f:
                f.write(active_pdf_bytes)
            st.write("indexing in progress...")
            client = load_cached_client(
                temp_file.name,
                active_pdf_bytes,
                uploaded_file.name,
            )
            st.write("processing complete, ask your questions...")

    if active_pdf_bytes is not None:
        display_pdf(active_pdf_bytes)


col1, col2 = st.columns([6, 1])

with col1:
    st.header(f"Chat with PDF")

with col2:
    st.button("Clear ↺", on_click=reset_chat)


# Initialize chat history
if "messages" not in st.session_state:
    reset_chat()


# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


# Offer the two fixed benchmark queries as mutually exclusive choices. A
# missing default PDF is an expected UI state, not an application exception.
if client is None:
    st.info("Add the default Orca PDF or upload a PDF to enable retrieval.")

benchmark_queries = (
    "What is Orca",
    "How does Orca compare with Vicuna on BigBench-Hard reasoning tasks?",
)
selected_query = st.selectbox(
    "Search query",
    options=benchmark_queries,
    index=0,
    disabled=client is None,
    help="Select exactly one of the two benchmark queries.",
)
prompt = selected_query if st.button(
    "Run selected query",
    type="primary",
    disabled=client is None,
) else None

if prompt:

    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)

    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        if generate_with_openai:
            message_placeholder = st.empty()
            full_response = ""
            for chunk in client.stream(
                prompt,
                retrieval_mode=retrieval_mode,
                use_reranker=use_reranker,
                vector_score_threshold=vector_score_threshold,
            ):
                full_response += chunk
                message_placeholder.markdown(full_response + "▌")
            message_placeholder.markdown(full_response)
        else:
            results = client.top_k_results(
                prompt,
                retrieval_mode=retrieval_mode,
                use_reranker=use_reranker,
                top_k=top_k,
                vector_score_threshold=vector_score_threshold,
            )
            mode_line = (
                f"Mode: **{retrieval_mode}** · "
                f"ColBERT reranker: **{'on' if use_reranker else 'off'}** · "
                "OpenAI: **off**"
            )
            if retrieval_mode == "Vector only" and not results:
                lines = [
                    "### No semantic match",
                    mode_line,
                    (
                        "The best vector relevance score was below the "
                        f"configured threshold of **{vector_score_threshold:.2f}**."
                    ),
                ]
            elif retrieval_mode == "BM25 only" and not results:
                lines = [
                    "### No lexical match",
                    mode_line,
                    "BM25 found no positive-score term matches in the document.",
                ]
            elif retrieval_mode == "Hybrid" and not results:
                lines = [
                    "### No hybrid match",
                    mode_line,
                    (
                        "The vector score was below the configured threshold "
                        "and BM25 found no positive-score lexical match."
                    ),
                ]
            else:
                lines = [
                    f"### Top {len(results)} retrieval results",
                    mode_line,
                ]
                for result in results:
                    page = result["page"]
                    page_label = "unknown" if page is None else str(page)
                    lines.extend(
                        [
                            "",
                            f"#### {result['rank']}. {result['filename']} "
                            f"— page {page_label}",
                            result["content"],
                        ]
                    )
            full_response = "\n".join(lines)
            st.markdown(full_response)

    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": full_response})
