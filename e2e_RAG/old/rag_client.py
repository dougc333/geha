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
    load_or_create_docling_hybrid_chunks,
    load_or_create_bm25,
    load_embedding_model,
    load_pdf,
    rerank_docs,
)


class rag_client:
    CLIENT_VERSION = 6
    # Version 3 rebuilds BM25 with normalized, stop-word-aware tokenization.
    INDEX_VERSION = 4
    RETRIEVAL_MODES = ("Vector only", "BM25 only", "Hybrid")
    DEFAULT_VECTOR_SCORE_THRESHOLD = 0.55
    embedding_model = load_embedding_model(model_name="BAAI/bge-large-en-v1.5") #model_name="BAAI/bge-large-en-v1.5"

    def __init__(
        self,
        files,
        document_id=None,
        index_root=None,
        source_name=None,
    ):
        if document_id is None:
            document_id = hashlib.sha256(
                Path(files).read_bytes()
            ).hexdigest()

        index_config = {
            "version": self.INDEX_VERSION,
            "embedding_model": "BAAI/bge-large-en-v1.5",
            "chunker": "docling.HybridChunker",
            "chunking_scope": "full_document",
            "chunk_tokenizer": "BAAI/bge-large-en-v1.5",
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

        page_docs = load_pdf(files=files)
        if not page_docs:
            raise ValueError("The PDF did not contain extractable text")

        self.front_page = page_docs[0].page_content
        docs = load_or_create_docling_hybrid_chunks(
            files,
            self.index_dir / "docling_hybrid_chunks.jsonl",
            source_name=source_name,
            tokenizer_model=index_config["chunk_tokenizer"],
            max_tokens=index_config["parent_chunk_size"],
        )
        self.vector_retriever = create_parent_retriever(
            docs,
            self.embedding_model,
            collection_name=f"pdf_{document_id[:24]}",
            top_k=10,
            persist_directory=self.index_dir / "chroma",
            parent_store_directory=self.index_dir / "parents",
            index_exists=index_exists,
            preserve_parent_documents=True,
        )
        self.bm25_retriever = load_or_create_bm25(
            docs,
            self.index_dir / "bm25.pkl",
            chunk_size=index_config["bm25_chunk_size"],
            top_k=10,
            documents_are_chunks=True,
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
        vector_score_threshold=None,
    ):
        try:
            context_list = self.retrieve_context(
                query,
                retrieval_mode=retrieval_mode,
                use_reranker=use_reranker,
                vector_score_threshold=vector_score_threshold,
            )
            print(f"Context: {context_list}")
            retrieved_context = "\n\n".join(context_list[:3])

            identity_question = re.search(
                r"\b(what is|what are|define|definition of|title|authors?|"
                r"autors?|written by|who wrote|affiliation|published|"
                r"publication date|year|date)\b",
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

    def _vector_top_score(self, query):
        scored_children = (
            self.vector_retriever.vectorstore
            .similarity_search_with_relevance_scores(query, k=1)
        )
        if not scored_children:
            return float("-inf")
        return float(scored_children[0][1])

    def _retrieve_positive_bm25_documents(self, query):
        retriever = self.bm25_retriever
        processed_query = retriever.preprocess_func(query)
        scores = retriever.vectorizer.get_scores(processed_query)

        # Pure term-frequency BM25 tends to rank tables containing many
        # repetitions of an entity above the title/abstract that defines it.
        # For definition-style questions, favor introductory front matter
        # while retaining the BM25 score as the lexical relevance signal.
        definition_query = bool(
            re.match(
                r"^\s*(?:what\s+(?:is|are)|define|definition\s+of)\b",
                query,
                flags=re.IGNORECASE,
            )
        )

        def heading_terms(text):
            terms = set()
            for term in retriever.preprocess_func(text):
                terms.add(term)
                if "-" in term:
                    terms.add(term.replace("-", ""))
                    terms.update(part for part in term.split("-") if part)
            return terms

        query_heading_terms = heading_terms(query)

        def adjusted_score(index):
            score = float(scores[index])
            if score <= 0.0:
                return score

            document = retriever.docs[index]
            page = document.metadata.get("page")
            headings = str(document.metadata.get("headings", ""))
            document_heading_terms = heading_terms(headings)
            if not definition_query:
                # A section-title match is stronger evidence than the same
                # words appearing incidentally in a table or paragraph.
                score += 0.75 * len(
                    query_heading_terms & document_heading_terms
                )
                return score

            if isinstance(page, int) and page <= 2:
                score += 1.0
            if re.search(r"\babstract\b", headings, flags=re.IGNORECASE):
                score += 0.75
            query_terms = set(processed_query)
            if query_terms and query_terms.issubset(document_heading_terms):
                score += 0.5
            return score

        ranked_indices = sorted(
            range(len(scores)),
            key=adjusted_score,
            reverse=True,
        )
        return [
            retriever.docs[index]
            for index in ranked_indices
            if float(scores[index]) > 0.0
        ][: retriever.k]

    def retrieve_documents(
        self,
        query,
        retrieval_mode="Vector only",
        top_k=None,
        vector_score_threshold=None,
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

        threshold = (
            self.DEFAULT_VECTOR_SCORE_THRESHOLD
            if vector_score_threshold is None
            else vector_score_threshold
        )

        if retrieval_mode == "Vector only":
            top_score = self._vector_top_score(query)
            logger.info(
                "vector_top_score={:.4f} threshold={:.4f}",
                top_score,
                threshold,
            )
            documents = (
                retriever.invoke(query)
                if top_score >= threshold
                else []
            )
        elif retrieval_mode == "BM25 only":
            documents = self._retrieve_positive_bm25_documents(query)
        else:
            top_score = self._vector_top_score(query)
            logger.info(
                "hybrid_vector_top_score={:.4f} threshold={:.4f}",
                top_score,
                threshold,
            )
            if top_score >= threshold:
                documents = retriever.invoke(query)
            else:
                logger.info(
                    "Hybrid vector leg rejected; falling back to BM25"
                )
                documents = self._retrieve_positive_bm25_documents(query)
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
        vector_score_threshold=None,
    ):
        """Return display-ready retrieval results without calling OpenAI."""
        documents = self.retrieve_documents(
            query,
            retrieval_mode=retrieval_mode,
            vector_score_threshold=vector_score_threshold,
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
        vector_score_threshold=None,
    ):
        documents = self.retrieve_documents(
            query,
            retrieval_mode,
            vector_score_threshold=vector_score_threshold,
        )

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
