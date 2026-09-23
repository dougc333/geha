"""Class-based PDF RAG client used by the refactored CLI and Streamlit app."""

from __future__ import annotations

from typing import Any, Callable, Iterable

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from rag_class import Rag
from reranking_models_class import RerankingModels


class RagClient:
    """Index one or more PDFs and answer questions over retrieved context."""

    def __init__(
        self,
        files: str | list[str],
        *,
        embedding_model: Any | None = None,
        retriever: Any | None = None,
        llm: Any | None = None,
        reranker: RerankingModels | None = None,
        embedding_model_name: str = "BAAI/bge-large-en-v1.5",
        collection_name: str = "split_documents",
        multi_query: bool = False,
        rag_service: Rag | None = None,
    ) -> None:
        self.rag = rag_service or Rag()
        self.embedding_model = embedding_model or self.rag.load_embedding_model(embedding_model_name)
        docs = self.rag.load_pdf(files=files)
        self.llm = llm or ChatOpenAI(model_name="gpt-4o")
        if retriever is not None:
            self.retriever = retriever
        else:
            base_retriever = self.rag.create_parent_retriever(
                docs,
                self.embedding_model,
                collection_name=collection_name,
            )
            self.retriever = (
                self.rag.create_multi_query_retriever(base_retriever, self.llm)
                if multi_query
                else base_retriever
            )
        self.reranker = reranker or RerankingModels()
        prompt = ChatPromptTemplate.from_template(
            """
You are a helpful AI Assistant. Extract information from CONTEXT based on the user question.
Use only relevant information from CONTEXT and provide a detailed response.

QUESTION: ```{question}```
CONTEXT: ```{context}```
"""
        )
        self.chain = prompt | self.llm | StrOutputParser()

    def retrieve_context_reranked(self, query: str, reranker_model: str = "colbert") -> list[str]:
        documents = self.retriever.invoke(query)
        return self.reranker.rerank(documents, query, model=reranker_model)

    @staticmethod
    def format_context(contexts: Iterable[str], limit: int = 3) -> str:
        return "\n".join(str(context) for context in list(contexts)[:limit])

    def stream(self, query: str, reranker_model: str = "colbert"):
        context = self.format_context(self.retrieve_context_reranked(query, reranker_model))
        yield from self.chain.stream({"context": context, "question": query})

    def generate(self, query: str, reranker_model: str = "colbert") -> dict[str, str]:
        context = self.format_context(self.retrieve_context_reranked(query, reranker_model))
        return {
            "contexts": context,
            "response": self.chain.invoke({"context": context, "question": query}),
        }
