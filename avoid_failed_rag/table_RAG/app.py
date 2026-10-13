import json
import os
import streamlit as st
from rag import ROOT, Retriever, build_graph
from evaluate import run_evals

st.set_page_config(page_title="GEHA Policy Explorer", page_icon="📄", layout="wide")
st.title("GEHA Policy Explorer")
st.caption("Two source policies • local document search • answers with page references")


@st.cache_resource
def index():
    return Retriever()


with st.sidebar:
    st.header("Answer settings")
    generate = st.toggle("Generate model answers", value=False)
    st.caption(
        "Search runs locally. Enabling answers sends the question and retrieved excerpts to your chosen endpoint."
    )
    url = st.text_input(
        "Compatible API base URL",
        os.getenv("MODEL_BASE_URL", "http://localhost:11434/v1"),
    )
    model = st.text_input("Model", os.getenv("MODEL_NAME", "llama3.2:3b"))
    key = st.text_input(
        "API key (if required)", value=os.getenv("MODEL_API_KEY", ""), type="password"
    )
    document = st.selectbox("Search documents", ["all", "bendamustine", "bevacizumab"])
    st.caption("Local Ollama: ollama pull llama3.2:3b")
    st.caption("The model server must be running before enabling model answers.")

try:
    with st.spinner(
        "Loading local search index… First use downloads an embedding model."
    ):
        retriever = index()
except Exception as exc:
    st.error(f"Could not load index: {exc}")
    st.stop()

search, sources, evaluation = st.tabs(["Ask a question", "Documents", "Evaluations"])
with search:
    st.caption(
        f"{len(retriever.chunks)} indexed chunks. Each question is independent; previous chat turns are not included."
    )
    if "last_result" not in st.session_state:
        st.session_state.last_result = None
    if "query_prefilled" not in st.session_state:
        st.session_state.policy_query = (
            "Is Treanda preferred, and what is its HCPCS code?"
        )
        st.session_state.query_prefilled = True
    question = st.chat_input("Ask a policy question", key="policy_query")
    if question:
        try:
            with st.spinner("Retrieving evidence and preparing response…"):
                st.session_state.last_result = (
                    question,
                    build_graph(retriever, url, model, key, generate).invoke(
                        {"question": question, "document": document}
                    ),
                )
        except Exception as exc:
            st.session_state.last_result = None
            st.error(f"Request failed: {exc}")
    if st.session_state.last_result:
        question, result = st.session_state.last_result
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            st.write(result["answer"])
            for c in result["citations"]:
                st.caption(
                    f"[{c['id']}] {c['metadata']['source_file']} · page {c['metadata']['page']}"
                )
        st.subheader("Retrieved evidence")
        for c in result["chunks"]:
            with st.expander(
                f"{c['metadata']['document_id']} · page {c['metadata']['page']} · {c['metadata']['kind']}",
                expanded=True,
            ):
                st.markdown(c["text"])
                st.caption(
                    f"Chunk {c['id']} · reciprocal-rank score {c['score']} (not confidence)"
                )

with sources:
    for path in sorted((ROOT / "data/documents").glob("*.md")):
        with st.expander(path.stem):
            st.markdown(path.read_text())
            source = ROOT / "data/sources" / (path.stem + ".pdf")
            st.download_button(
                "Download original PDF",
                source.read_bytes(),
                source.name,
                "application/pdf",
                key=path.stem,
            )
    st.info(
        "Source wording is preserved, including Bevacizumab page 3 “Jobeyne” and “No otherwise classified”. These are source inconsistencies."
    )

with evaluation:
    st.write(
        "Eight reference cases: six answerable questions and two cases that should abstain. The answer key is not indexed."
    )
    st.dataframe(json.loads((ROOT / "evals/cases.json").read_text()), hide_index=True)
    st.caption(
        "This button tests retrieval only. It does not call a generation API or score answer correctness."
    )
    if st.button("Run retrieval evaluation"):
        with st.spinner("Checking retrieval…"):
            st.session_state.eval_results = run_evals(retriever)
    if "eval_results" in st.session_state:
        rows = st.session_state.eval_results
        graded = [r for r in rows if r["retrieval_pass"] is not None]
        st.metric(
            "Evidence checks passed",
            f"{sum(r['retrieval_pass'] for r in graded)}/{len(graded)}",
        )
        st.dataframe(rows, hide_index=True)
        st.download_button(
            "Download results",
            json.dumps(rows, indent=2),
            "retrieval-results.json",
            "application/json",
        )
