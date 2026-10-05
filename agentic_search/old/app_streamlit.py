# Adapted from https://docs.streamlit.io/knowledge-base/tutorials/build-conversational-apps#build-a-simple-chatbot-gui-with-streaming
import os

import gc
import hashlib
import tempfile
import uuid

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


def reset_chat():
    st.session_state.messages = []
    st.session_state.context = None
    gc.collect()


def display_pdf(file):
    st.markdown("### PDF Preview")
    # Native viewer avoids browser restrictions on base64 data-URL iframes.
    # getvalue() returns the complete upload regardless of the current cursor.
    st.pdf(file.getvalue(), height=800)


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

    uploaded_file = st.file_uploader("Choose your `.pdf` file", type="pdf")
    if uploaded_file is not None:
        uploaded_bytes = uploaded_file.getvalue()
        document_id = hashlib.sha256(uploaded_bytes).hexdigest()

        with tempfile.NamedTemporaryFile() as temp_file, st.status(
            "processing your document", expanded=False, state="running"
        ):
            with open(temp_file.name, "wb") as f:
                f.write(uploaded_bytes)
            # Include the index version so a code/index upgrade cannot reuse a
            # stale rag_client preserved in Streamlit session state.
            file_key = (
                f"client-v{rag_client.CLIENT_VERSION}-"
                f"index-v{rag_client.INDEX_VERSION}-{document_id}"
            )
            st.write("indexing in progress...")
            if file_key not in st.session_state.file_cache:
                client = rag_client(
                    files=temp_file.name,
                    document_id=document_id,
                )
                st.session_state.file_cache[file_key] = client
            else:
                client = st.session_state.file_cache[file_key]
            st.write("processing complete, ask your questions...")

        display_pdf(uploaded_file)


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


# Accept user input
if prompt := st.chat_input("What's on your mind?"):
    if uploaded_file is None:
        st.exception(FileNotFoundError("Please upload a document first!"))
        st.stop()

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
            )
            lines = [
                f"### Top {len(results)} retrieval results",
                f"Mode: **{retrieval_mode}** · "
                f"ColBERT reranker: **{'on' if use_reranker else 'off'}** · "
                "OpenAI: **off**",
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
