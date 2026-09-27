import os
import hashlib
import json
import re
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_classic.retrievers import EnsembleRetriever
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from loguru import logger

from rag import (
    create_parent_retriever,
    load_or_create_bm25,
    load_embedding_model,
    load_pdf,
    rerank_docs,
)


class rag_client:
    CLIENT_VERSION = 4
    INDEX_VERSION = 2
    RETRIEVAL_MODES = ("Vector only", "BM25 only", "Hybrid")
    embedding_model = load_embedding_model(model_name="BAAI/bge-large-en-v1.5") #model_name="BAAI/bge-large-en-v1.5"

    def __init__(self, files, document_id=None, index_root=None):
        if document_id is None:
            document_id = hashlib.sha256(
                Path(files).read_bytes()
            ).hexdigest()

        index_config = {
            "version": self.INDEX_VERSION,
            "embedding_model": "BAAI/bge-large-en-v1.5",
            "parent_chunk_size": 512,
            "child_chunk_size": 256,
            "bm25_chunk_size": 512,
            "preserve_pdf_pages": True,
        }
        config_id = hashlib.sha256(
            json.dumps(index_config, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]

        if index_root is None:
            index_root = Path(__file__).resolve().parent.parent / "index_cache"

        self.index_dir = (
            Path(index_root) / document_id / config_id
        )
        self.index_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = self.index_dir / "manifest.json"
        index_exists = manifest_path.exists()

        logger.info(
            "{} persistent index at {}",
            "Loading" if index_exists else "Building",
            self.index_dir,
        )

        docs = load_pdf(files=files)
        if not docs:
            raise ValueError("The PDF did not contain extractable text")

        self.front_page = docs[0].page_content
        self.vector_retriever = create_parent_retriever(
            docs,
            self.embedding_model,
            collection_name=f"pdf_{document_id[:24]}",
            top_k=10,
            persist_directory=self.index_dir / "chroma",
            parent_store_directory=self.index_dir / "parents",
            index_exists=index_exists,
        )
        self.bm25_retriever = load_or_create_bm25(
            docs,
            self.index_dir / "bm25.pkl",
            chunk_size=index_config["bm25_chunk_size"],
            top_k=10,
        )
        self.hybrid_retriever = EnsembleRetriever(
            retrievers=[
                self.vector_retriever,
                self.bm25_retriever,
            ],
            weights=[0.5, 0.5],
        )

        if not index_exists:
            manifest_path.write_text(
                json.dumps(
                    {
                        "document_id": document_id,
                        "config": index_config,
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            logger.success("Persistent indexes created")
        else:
            logger.success("Persistent indexes loaded")

        # OpenAI is optional. Retrieval-only mode can inspect the ranked chunks
        # without creating an LLM client or sending any content externally.
        self.chain = None

    def _get_generation_chain(self):
        if self.chain is not None:
            return self.chain

        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Either export it before starting "
                "Streamlit or turn off 'Generate answer with OpenAI'."
            )

        llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0,
        )
        prompt_template = ChatPromptTemplate.from_template(
            (
                """
            Answer the QUESTION using only the supplied CONTEXT.
            If the answer is not present, say that it was not found in the
            provided document. Do not use outside knowledge.

            For questions about the paper's title, authors, affiliation,
            publication date, or year, treat DOCUMENT FRONT PAGE as the
            authoritative source. Do not mistake names in citations or the
            bibliography for the paper's authors.

                QUESTION: ```{question}```\n
                CONTEXT: ```{context}```\n"""
            )
        )
        self.chain = prompt_template | llm | StrOutputParser()
        return self.chain

    def stream(
        self,
        query,
        retrieval_mode="Vector only",
        use_reranker=False,
    ):
        try:
            context_list = self.retrieve_context(
                query,
                retrieval_mode=retrieval_mode,
                use_reranker=use_reranker,
            )
            print(f"Context: {context_list}")
            retrieved_context = "\n\n".join(context_list[:3])

            identity_question = re.search(
                r"\b(title|authors?|autors?|written by|who wrote|"
                r"affiliation|published|publication date|year|date)\b",
                query,
                flags=re.IGNORECASE,
            )

            if identity_question:
                context = (
                    "DOCUMENT FRONT PAGE:\n"
                    f"{self.front_page}\n\n"
                    "RETRIEVED PASSAGES:\n"
                    f"{retrieved_context}"
                )
            else:
                context = "RETRIEVED PASSAGES:\n" + retrieved_context
            print(context)
        except Exception:
            # Never pass an internal exception to the LLM as document context.
            logger.exception("Retrieval or reranking failed for query={!r}", query)
            raise
        logger.info(context)
        chain = self._get_generation_chain()
        for r in chain.stream({"context": context, "question": query}):
            yield r

    def retrieve_documents(
        self,
        query,
        retrieval_mode="Vector only",
        top_k=None,
    ):
        if retrieval_mode == "Vector only":
            retriever = self.vector_retriever
        elif retrieval_mode == "BM25 only":
            retriever = self.bm25_retriever
        elif retrieval_mode == "Hybrid":
            retriever = self.hybrid_retriever
        else:
            raise ValueError(
                f"Unknown retrieval mode {retrieval_mode!r}. "
                f"Choose one of {self.RETRIEVAL_MODES}."
            )

        documents = retriever.invoke(query)
        if top_k is not None:
            if top_k < 1:
                raise ValueError("top_k must be at least 1")
            documents = documents[:top_k]
        logger.info(
            "retrieval_mode={!r} raw_results={}",
            retrieval_mode,
            len(documents),
        )
        for rank, document in enumerate(documents, start=1):
            logger.debug(
                "raw_rank={} mode={!r} page={} excerpt={!r}",
                rank,
                retrieval_mode,
                document.metadata.get("page"),
                document.page_content[:300],
            )
        return documents

    def top_k_results(
        self,
        query,
        retrieval_mode="Vector only",
        use_reranker=False,
        top_k=5,
    ):
        """Return display-ready retrieval results without calling OpenAI."""
        documents = self.retrieve_documents(
            query,
            retrieval_mode=retrieval_mode,
        )

        if use_reranker:
            logger.info("Applying ColBERT reranker for retrieval-only results")
            reranked_texts = rerank_docs(
                query=query,
                retrieved_docs=documents,
                reranker_model="colbert",
            )
            documents_by_text = {
                document.page_content: document for document in documents
            }
            ordered_results = [
                (
                    text,
                    documents_by_text.get(text).metadata
                    if text in documents_by_text
                    else {},
                )
                for text in reranked_texts
            ]
        else:
            ordered_results = [
                (document.page_content, document.metadata)
                for document in documents
            ]

        return [
            {
                "rank": rank,
                "filename": metadata.get("filename", "unknown"),
                "page": metadata.get("page"),
                "content": content,
            }
            for rank, (content, metadata) in enumerate(
                ordered_results[:top_k],
                start=1,
            )
        ]

    def retrieve_context(
        self,
        query,
        retrieval_mode="Vector only",
        use_reranker=False,
    ):
        documents = self.retrieve_documents(query, retrieval_mode)

        if use_reranker:
            logger.info("Applying ColBERT reranker")
            return rerank_docs(
                query=query,
                retrieved_docs=documents,
                reranker_model="colbert",
            )

        return [document.page_content for document in documents]

    def generate(self, query):
        contexts = self.retrieve_context(query)
        # print(contexts)
        text = ""
        for i,cont in enumerate(contexts):
            if i <3:
                text = text +"\n"+ cont
            else:
                break
        print(f"Here is the text: {text}")
        return {
            "contexts": text,
            "response": self._get_generation_chain().invoke(
                {"context": text, "question": query}
            ),
        }
