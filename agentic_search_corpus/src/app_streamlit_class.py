"""Class-based Streamlit UI corresponding to the original app_streamlit.py."""

from __future__ import annotations

import base64
import gc
import hashlib
import tempfile
import uuid
from typing import Any, Callable

from rag_client_class import RagClient
from rag_class import Rag


class StreamlitApplication:
    """Own the Streamlit session state and PDF chat UI."""

    def __init__(
        self,
        client_factory: Callable[..., Any] = RagClient,
        rag_service_factory: Callable[[], Rag] = Rag,
    ) -> None:
        self.client_factory = client_factory
        self.rag_service_factory = rag_service_factory

    def initialize_state(self, st: Any) -> None:
        if "id" not in st.session_state:
            st.session_state.id = str(uuid.uuid4())
            st.session_state.file_cache = {}
        if "messages" not in st.session_state:
            self.reset_chat(st)

    def reset_chat(self, st: Any) -> None:
        st.session_state.messages = []
        st.session_state.context = None
        gc.collect()

    @staticmethod
    def display_pdf(st: Any, file: Any) -> None:
        """Render the bytes from the currently selected upload.

        ``st.pdf`` avoids browser-specific failures with large base64 data URLs
        and, importantly, receives the selected upload's bytes rather than a
        path or a hard-coded example document.  The iframe fallback keeps the
        UI usable with older Streamlit versions.
        """
        pdf_bytes = file.getvalue()
        st.markdown("<h3>PDF Preview</h3>", unsafe_allow_html=True)
        pdf_renderer = getattr(st, "pdf", None)
        if callable(pdf_renderer):
            # A content-derived key forces Streamlit to replace the embedded
            # viewer when the user selects a different PDF.
            pdf_key = f"pdf-preview-{hashlib.sha256(pdf_bytes).hexdigest()[:16]}"
            pdf_renderer(pdf_bytes, key=pdf_key)
            # Some browser/PDF.js combinations show a blank embedded viewer
            # for otherwise valid PDFs.  Render the first page locally as a
            # reliable fallback/preview so every upload remains visible.
            try:
                import pymupdf

                with pymupdf.open(stream=pdf_bytes, filetype="pdf") as document:
                    if document.page_count:
                        page = document.load_page(0)
                        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
                        st.image(
                            pixmap.tobytes("png"),
                            caption="First page preview",
                            use_container_width=True,
                        )
            except Exception:
                # Keep the embedded viewer available even if local rasterizing
                # is unavailable for a particular file or environment.
                pass
            return

        encoded = base64.b64encode(pdf_bytes).decode("utf-8")
        st.markdown(
            f'<iframe src="data:application/pdf;base64,{encoded}" '
            'width="400" height="100%" type="application/pdf" '
            'style="height:100vh; width:100%"></iframe>',
            unsafe_allow_html=True,
        )

    def build_client(self, uploaded_file: Any, session_id: str) -> Any:
        with tempfile.NamedTemporaryFile(suffix=".pdf") as temp_file:
            temp_file.write(uploaded_file.getvalue())
            temp_file.flush()
            return self.client_factory(
                files=temp_file.name,
                rag_service=self.rag_service_factory(),
            )

    def run(self) -> None:
        import streamlit as st

        self.initialize_state(st)
        session_id = st.session_state.id
        uploaded_file = None
        client = None

        with st.sidebar:
            uploaded_file = st.file_uploader("Choose your `.pdf` file", type="pdf")
            if uploaded_file is not None:
                file_key = f"{session_id}-{uploaded_file.name}"
                with st.status("processing your document", expanded=False):
                    if file_key not in st.session_state.file_cache:
                        st.session_state.file_cache[file_key] = self.build_client(
                            uploaded_file, session_id
                        )
                    client = st.session_state.file_cache[file_key]
                    st.write("processing complete, ask your questions...")
                self.display_pdf(st, uploaded_file)

        col1, col2 = st.columns([6, 1])
        with col1:
            st.header("Chat with PDF")
        with col2:
            st.button("Clear", on_click=self.reset_chat, args=(st,))

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        prompt = st.chat_input("What's on your mind?")
        if prompt:
            if uploaded_file is None or client is None:
                st.error("Please upload a document first!")
                return
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                placeholder = st.empty()
                response = ""
                for chunk in client.stream(prompt):
                    response += chunk
                    placeholder.markdown(response + "▌")
                placeholder.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    StreamlitApplication().run()
