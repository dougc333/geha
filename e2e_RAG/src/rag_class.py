"""Class-based RAG services extracted from the procedural ``rag.py`` module."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

import pymupdf
import torch
from langchain_chroma import Chroma
from langchain_classic.retrievers.ensemble import EnsembleRetriever
from langchain_classic.retrievers.multi_query import MultiQueryRetriever
from langchain_classic.retrievers.parent_document_retriever import ParentDocumentRetriever
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.stores import InMemoryStore
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from transformers import AutoTokenizer


class Rag:
    """Own document ingestion, embeddings, and retriever construction."""

    @staticmethod
    def clean_extra_whitespace(text: str) -> str:
        return " ".join(text.split())

    @staticmethod
    def group_broken_paragraphs(text: str) -> str:
        return text.replace("\n", " ").replace("\r", " ")

    def load_pdf(self, files: str | Iterable[str]) -> list[Document]:
        paths = [files] if isinstance(files, (str, Path)) else list(files)
        documents: list[Document] = []
        for file_path in paths:
            path = str(file_path)
            with pymupdf.open(path) as pdf:
                text = "".join(page.get_text("text") for page in pdf)
            text = self.group_broken_paragraphs(self.clean_extra_whitespace(text))
            documents.append(Document(page_content=text, metadata={"source": path}))
        return documents

    def split_documents(
        self,
        chunk_size: int,
        knowledge_base: Iterable[Document],
        tokenizer_name: str = "openai",
    ) -> list[Document]:
        if tokenizer_name == "openai":
            splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
                separators=["\n\n\n", "\n\n", "\n", ".", ""],
                chunk_size=chunk_size,
                chunk_overlap=chunk_size // 10,
                model_name="gpt-4",
                is_separator_regex=False,
                add_start_index=True,
                strip_whitespace=True,
            )
        else:
            splitter = RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
                AutoTokenizer.from_pretrained(tokenizer_name),
                chunk_size=chunk_size,
                chunk_overlap=chunk_size // 10,
                add_start_index=True,
                strip_whitespace=True,
            )

        unique: list[Document] = []
        seen: set[str] = set()
        for document in knowledge_base:
            for chunk in splitter.split_documents([document]):
                if chunk.page_content not in seen:
                    seen.add(chunk.page_content)
                    unique.append(chunk)
        return unique

    def load_embedding_model(self, model_name: str = "openai") -> Any:
        if model_name == "openai":
            return OpenAIEmbeddings(model="text-embedding-3-small")

        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = "mps"
        elif torch.cuda.is_available():
            device = "cuda"
        else:
            device = "cpu"
        return HuggingFaceBgeEmbeddings(
            model_name=model_name,
            model_kwargs={"device": device},
            encode_kwargs={"normalize_embeddings": True},
        )

    def create_parent_retriever(
        self,
        docs: list[Document],
        embeddings_model: Any,
        collection_name: str = "split_documents",
        parent_chunk_size: int = 512,
        child_chunk_size: int = 256,
        persist_directory: str | None = None,
    ) -> Any:
        parent_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            separators=["\n\n\n", "\n\n", "\n", ".", ""],
            chunk_size=parent_chunk_size,
            chunk_overlap=0,
            model_name="gpt-4",
            is_separator_regex=False,
        )
        child_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            separators=["\n\n\n", "\n\n", "\n", ".", ""],
            chunk_size=child_chunk_size,
            chunk_overlap=0,
            model_name="gpt-4",
            is_separator_regex=False,
        )
        vectorstore = Chroma(
            collection_name=collection_name,
            embedding_function=embeddings_model,
            persist_directory=persist_directory,
        )
        retriever = ParentDocumentRetriever(
            vectorstore=vectorstore,
            docstore=InMemoryStore(),
            child_splitter=child_splitter,
            parent_splitter=parent_splitter,
            k=10,
        )
        retriever.add_documents(docs)
        return retriever

    def create_multi_query_retriever(self, base_retriever: Any, llm: Any) -> Any:
        return MultiQueryRetriever.from_llm(base_retriever, llm)

    def get_ensemble_retriever(
        self,
        docs: list[Document],
        embedding_model: Any,
        collection_name: str = "test",
        top_k: int = 3,
    ) -> Any:
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        vector_store = Chroma.from_documents(
            documents=docs,
            embedding=embedding_model,
            collection_name=collection_name,
        )
        vector_retriever = vector_store.as_retriever(search_kwargs={"k": top_k})
        keyword_retriever = BM25Retriever.from_documents(docs)
        keyword_retriever.k = top_k
        return EnsembleRetriever(
            retrievers=[vector_retriever, keyword_retriever],
            weights=[0.5, 0.5],
        )

    def retrieve_context_reranked(
        self,
        query: str,
        retriever: Any,
        reranker: Any,
        reranker_model: str = "gpt",
    ) -> list[str]:
        documents = retriever.invoke(query)
        return reranker.rerank(documents, query, model=reranker_model)


RagPipeline = Rag
