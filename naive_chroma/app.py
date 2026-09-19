"""Streamlit search UI for the plain-chunk GEHA Chroma baseline."""

from pathlib import Path

import streamlit as st

from index import DEFAULT_DB_DIR, DEFAULT_PDF_DIR, build_index, open_index, search

st.set_page_config(page_title="GEHA Plain-Chunk Search", page_icon="🔎", layout="wide")
st.title("GEHA Plain-Chunk Search")
st.caption("Search all coverage-policy PDFs with plain text chunks. Results are excerpts, not generated answers.")

with st.sidebar:
    st.header("Index")
    st.write(f"PDF folder: `{DEFAULT_PDF_DIR}`")
    st.write("Chunking: 180 words, 30-word overlap, within each page")
    st.caption("Tables are treated as ordinary extracted text; rows are not separately indexed.")
    st.caption("Pages without embedded text are skipped. OCR is disabled.")
    if st.button("Build or refresh index", type="secondary"):
        try:
            with st.spinner("Extracting PDFs and embedding chunks. This can take a few minutes…"):
                summary = build_index()
            st.cache_resource.clear()
            st.success(
                f"Indexed {summary['indexed_pdfs']}/{summary['pdfs']} PDFs, "
                f"{summary['indexed_pages']}/{summary['pages']} pages, "
                f"{summary['chunks']} chunks."
            )
            if summary["skipped_pages"]:
                skipped = {}
                for item in summary["skipped_pages"]:
                    skipped.setdefault(item["source_file"], []).append(item["page"])
                st.warning("Skipped pages without embedded text: " + "; ".join(
                    f"{name} pages {', '.join(map(str, pages))}" for name, pages in skipped.items()
                ))
        except Exception as exc:
            st.error(f"Indexing failed: {exc}")


@st.cache_resource
def cached_index():
    return open_index()


try:
    collection = cached_index()
except Exception:
    st.info("No search index yet. Click **Build or refresh index** in the sidebar, or run `uv run python index.py` here.")
    st.stop()

indexed = collection.get(include=["metadatas"])
sources = sorted({item["source_file"] for item in indexed["metadatas"]})
st.caption(f"{len(sources)} PDFs · {collection.count()} indexed chunks · local Chroma database")

with st.form("search_form"):
    question = st.text_input("Search the policies", placeholder="e.g., Is Firmagon preferred?")
    col1, col2 = st.columns([3, 1])
    with col1:
        source = st.selectbox("Document", ["All PDFs", *sources])
    with col2:
        top_k = st.slider("Results", 1, 10, 4)
    submitted = st.form_submit_button("Search", type="primary")

if submitted:
    if not question.strip():
        st.warning("Enter a search question or phrase.")
    else:
        try:
            with st.spinner("Searching…"):
                st.session_state["search_results"] = search(
                    collection,
                    question,
                    k=top_k,
                    source_file=None if source == "All PDFs" else source,
                )
            st.session_state["search_question"] = question
        except Exception as exc:
            st.error(f"Search failed: {exc}")
            st.session_state.pop("search_results", None)

if "search_results" in st.session_state:
    results = st.session_state["search_results"]
    st.subheader(f"Results for: {st.session_state['search_question']}")
    if not results:
        st.info("No matching chunks were returned.")
    for rank, result in enumerate(results, start=1):
        metadata = result["metadata"]
        label = f"{rank}. {metadata['source_file']} · page {metadata['page']} · chunk {metadata['chunk']}"
        with st.expander(label, expanded=rank == 1):
            st.write(result["text"])
            st.caption(f"Chroma distance: {result['distance']:.4f} (lower is closer; not a confidence score)")
            pdf_path = Path(DEFAULT_PDF_DIR) / metadata["source_file"]
            if pdf_path.is_file():
                st.download_button(
                    "Download source PDF",
                    pdf_path.read_bytes(),
                    file_name=pdf_path.name,
                    mime="application/pdf",
                    key=f"download-{rank}-{result['id']}",
                )
