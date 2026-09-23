"""Routed RAG pipeline used by the Streamlit strategy explorer.

The module deliberately keeps retrieval strategies behind a small LangGraph
workflow.  LangGraph coordinates the steps; Chroma, BM25, query rewriting,
parent/child lookup, reranking, and generation remain ordinary components.
"""

from __future__ import annotations

import hashlib
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypedDict

import pymupdf
from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field


Strategy = Literal[
    "vector",
    "hybrid",
    "hyde",
    "query_expansion",
    "parent_child",
]


class RAGState(TypedDict, total=False):
    query: str
    requested_strategy: str
    strategy: Strategy
    route_reason: str
    expanded_queries: list[str]
    hypothetical_document: str
    candidates: list[Document]
    reranked_documents: list[Document]
    rerank_metrics: dict[str, int | float | str | bool]
    answer: str


class QueryExpansion(BaseModel):
    queries: list[str] = Field(
        description="Two or three focused search queries that preserve user intent"
    )


class RankedChunk(BaseModel):
    chunk_id: str
    relevance_score: float = Field(ge=0, le=100)


class RankingResult(BaseModel):
    rankings: list[RankedChunk]


@dataclass(frozen=True)
class RAGConfig:
    chat_model: str = "gpt-4.1"
    embedding_model: str = "text-embedding-3-small"
    chunk_size: int = 300
    chunk_overlap: int = 40
    parent_size: int = 900
    child_size: int = 220
    candidate_k: int = 4
    final_k: int = 2
    use_reranker: bool = True
    rerank_input_cost_per_million: float = 2.00
    rerank_cached_input_cost_per_million: float = 0.50
    rerank_output_cost_per_million: float = 8.00

    def validate(self) -> None:
        if self.chunk_size <= 0 or self.parent_size <= 0 or self.child_size <= 0:
            raise ValueError("Chunk sizes must be positive")
        if not 0 <= self.chunk_overlap < self.chunk_size:
            raise ValueError("Chunk overlap must be between 0 and chunk_size - 1")
        if self.child_size >= self.parent_size:
            raise ValueError("Child chunks must be smaller than parent chunks")
        if self.candidate_k < 1 or self.final_k < 1:
            raise ValueError("candidate_k and final_k must be at least 1")
        if self.final_k > self.candidate_k:
            raise ValueError("final_k cannot be greater than candidate_k")
        if min(
            self.rerank_input_cost_per_million,
            self.rerank_cached_input_cost_per_million,
            self.rerank_output_cost_per_million,
        ) < 0:
            raise ValueError("Token prices cannot be negative")


def calculate_token_cost(
    *,
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int = 0,
    input_cost_per_million: float,
    cached_input_cost_per_million: float,
    output_cost_per_million: float,
) -> dict[str, float]:
    """Calculate an estimated text-token cost from reported API usage."""
    cached_input_tokens = max(0, min(cached_input_tokens, input_tokens))
    uncached_input_tokens = input_tokens - cached_input_tokens
    input_cost = (
        uncached_input_tokens * input_cost_per_million
        + cached_input_tokens * cached_input_cost_per_million
    ) / 1_000_000
    output_cost = output_tokens * output_cost_per_million / 1_000_000
    return {
        "input_cost_usd": input_cost,
        "output_cost_usd": output_cost,
        "total_cost_usd": input_cost + output_cost,
    }


def extract_usage_metadata(message) -> dict[str, int]:
    """Normalize LangChain/OpenAI token metadata across supported response shapes."""
    usage = getattr(message, "usage_metadata", None) or {}
    response_metadata = getattr(message, "response_metadata", None) or {}
    legacy_usage = response_metadata.get("token_usage", {})

    input_tokens = int(
        usage.get("input_tokens", legacy_usage.get("prompt_tokens", 0)) or 0
    )
    output_tokens = int(
        usage.get("output_tokens", legacy_usage.get("completion_tokens", 0)) or 0
    )
    total_tokens = int(
        usage.get(
            "total_tokens",
            legacy_usage.get("total_tokens", input_tokens + output_tokens),
        )
        or input_tokens + output_tokens
    )
    input_details = usage.get("input_token_details", {}) or {}
    prompt_details = legacy_usage.get("prompt_tokens_details", {}) or {}
    cached_input_tokens = int(
        input_details.get(
            "cache_read",
            input_details.get(
                "cached_tokens", prompt_details.get("cached_tokens", 0)
            ),
        )
        or 0
    )
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def load_pdf(pdf_path: str | Path) -> list[Document]:
    """Extract one LangChain document per non-empty PDF page."""
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(path)

    pages: list[Document] = []
    with pymupdf.open(path) as pdf:
        for page_index, page in enumerate(pdf):
            text = page.get_text("text").strip()
            if text:
                pages.append(
                    Document(
                        page_content=text,
                        metadata={"source": str(path), "page": page_index + 1},
                    )
                )
    if not pages:
        raise ValueError(
            "No extractable text was found. This PDF may require OCR before indexing."
        )
    return pages


def _token_splitter(chunk_size: int, overlap: int = 0):
    return RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        separators=["\n\n", "\n", ". ", " ", ""],
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        add_start_index=True,
        strip_whitespace=True,
    )


def chunk_pages(
    pages: list[Document], chunk_size: int, chunk_overlap: int
) -> list[Document]:
    chunks = _token_splitter(chunk_size, chunk_overlap).split_documents(pages)
    for index, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = f"chunk-{index:05d}"
    return chunks


def build_parent_child_documents(
    pages: list[Document], parent_size: int, child_size: int
) -> tuple[list[Document], list[Document], dict[str, Document]]:
    """Create parent documents plus searchable children linked by parent_id."""
    parents = _token_splitter(parent_size).split_documents(pages)
    parent_by_id: dict[str, Document] = {}
    children: list[Document] = []
    child_splitter = _token_splitter(child_size)

    for parent_index, parent in enumerate(parents):
        parent_id = f"parent-{parent_index:05d}"
        parent.metadata["parent_id"] = parent_id
        parent.metadata["chunk_id"] = parent_id
        parent_by_id[parent_id] = parent

        for child_index, child in enumerate(child_splitter.split_documents([parent])):
            child.metadata["parent_id"] = parent_id
            child.metadata["chunk_id"] = f"{parent_id}-child-{child_index:03d}"
            children.append(child)

    return parents, children, parent_by_id


def route_query(query: str, requested_strategy: str = "auto") -> tuple[Strategy, str]:
    """Choose a retrieval path using deterministic, testable rules."""
    if requested_strategy != "auto":
        return requested_strategy, "Strategy explicitly selected in the UI"  # type: ignore[return-value]

    normalized = " ".join(query.lower().split())
    has_versioned_identifier = bool(
        re.search(r"\b[a-z][a-z0-9]*-[a-z0-9]*\d[a-z0-9-]*\b", normalized)
    )
    has_quoted_phrase = bool(re.search(r"['\"][^'\"]{2,}['\"]", query))

    if (
        re.search(
            r"\b(?:j\d{4}|cpt|hcpcs|ndc|policy\s*(?:id|number|#))\b",
            normalized,
        )
        or has_versioned_identifier
        or has_quoted_phrase
    ):
        return "hybrid", "Exact code, version, or quoted phrase detected"

    if any(
        phrase in normalized
        for phrase in (
            "entire section",
            "complete section",
            "whole table",
            "complete table",
            "approval criteria",
            "surrounding context",
        )
    ):
        return "parent_child", "Complete section or surrounding context requested"

    if any(
        word in normalized
        for word in ("compare", "difference", "all conditions", "list every", "grouped by")
    ):
        return "query_expansion", "Comparison or multi-part inventory query detected"

    if len(normalized.split()) <= 3:
        return "hyde", "Short or underspecified query detected"

    return "vector", "General semantic question"


def document_key(document: Document) -> str:
    explicit = document.metadata.get("chunk_id")
    if explicit:
        return str(explicit)
    raw = f"{document.metadata.get('source')}::{document.page_content}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def reciprocal_rank_fusion(
    result_lists: list[list[Document]], rrf_k: int = 60, final_k: int = 10
) -> list[Document]:
    """Fuse ranked lists without assuming their raw scores share a scale."""
    scores: dict[str, float] = {}
    documents: dict[str, Document] = {}

    for results in result_lists:
        for rank, document in enumerate(results, start=1):
            key = document_key(document)
            if key in documents:
                existing = documents[key]
                merged_metadata = {
                    **existing.metadata,
                    **document.metadata,
                }
                existing_channels = existing.metadata.get("retrieval_channels", [])
                new_channels = document.metadata.get("retrieval_channels", [])
                merged_metadata["retrieval_channels"] = list(
                    dict.fromkeys([*existing_channels, *new_channels])
                )
                existing_queries = existing.metadata.get("retrieval_queries", [])
                new_queries = document.metadata.get("retrieval_queries", [])
                merged_metadata["retrieval_queries"] = list(
                    dict.fromkeys([*existing_queries, *new_queries])
                )
                documents[key] = Document(
                    page_content=existing.page_content,
                    metadata=merged_metadata,
                )
            else:
                documents[key] = document
            scores[key] = scores.get(key, 0.0) + 1.0 / (rrf_k + rank)

    ordered = sorted(scores, key=scores.get, reverse=True)
    fused: list[Document] = []
    for key in ordered[:final_k]:
        document = documents[key]
        document.metadata["fusion_score"] = scores[key]
        fused.append(document)
    return fused


class RoutedRAG:
    """Own the indexes and compiled LangGraph workflow for one PDF."""

    def __init__(self, pdf_path: str | Path, config: RAGConfig):
        config.validate()
        self.config = config
        self.pages = load_pdf(pdf_path)
        self.chunks = chunk_pages(
            self.pages, config.chunk_size, config.chunk_overlap
        )
        self.parents, self.children, self.parent_by_id = build_parent_child_documents(
            self.pages, config.parent_size, config.child_size
        )

        self.embeddings = OpenAIEmbeddings(model=config.embedding_model)
        self.llm = ChatOpenAI(model=config.chat_model, temperature=0)

        collection_suffix = uuid.uuid4().hex[:10]
        self.vectorstore = Chroma.from_documents(
            self.chunks,
            self.embeddings,
            collection_name=f"routed_rag_{collection_suffix}",
            collection_metadata={"hnsw:space": "cosine"},
        )
        self.child_vectorstore = Chroma.from_documents(
            self.children,
            self.embeddings,
            collection_name=f"routed_rag_children_{collection_suffix}",
            collection_metadata={"hnsw:space": "cosine"},
        )

        self.vector_retriever = self.vectorstore.as_retriever(
            search_kwargs={"k": config.candidate_k}
        )
        self.child_retriever = self.child_vectorstore.as_retriever(
            search_kwargs={"k": config.candidate_k}
        )
        self.bm25_retriever = BM25Retriever.from_documents(self.chunks)
        self.bm25_retriever.k = config.candidate_k

        self.graph = self._build_graph()

    def _route_node(self, state: RAGState):
        strategy, reason = route_query(
            state["query"], state.get("requested_strategy", "auto")
        )
        return {"strategy": strategy, "route_reason": reason}

    @staticmethod
    def _route_edge(state: RAGState):
        return state["strategy"]

    def _vector_search(self, query: str) -> list[Document]:
        results = self.vectorstore.similarity_search_with_relevance_scores(
            query, k=self.config.candidate_k
        )
        return [
            Document(
                page_content=document.page_content,
                metadata={
                    **document.metadata,
                    "vector_rank": rank,
                    "vector_score": float(score),
                    "retrieval_channels": ["vector"],
                    "retrieval_queries": [query],
                },
            )
            for rank, (document, score) in enumerate(results, start=1)
        ]

    def _vector_node(self, state: RAGState):
        return {"candidates": self._vector_search(state["query"])}

    def _hybrid_node(self, state: RAGState):
        vector = self._vector_search(state["query"])
        keyword = [
            Document(
                page_content=document.page_content,
                metadata={
                    **document.metadata,
                    "bm25_rank": rank,
                    "retrieval_channels": ["bm25"],
                    "retrieval_queries": [state["query"]],
                },
            )
            for rank, document in enumerate(
                self.bm25_retriever.invoke(state["query"]), start=1
            )
        ]
        return {
            "candidates": reciprocal_rank_fusion(
                [vector, keyword], final_k=self.config.candidate_k
            )
        }

    def _hyde_node(self, state: RAGState):
        prompt = ChatPromptTemplate.from_template(
            """Write a short hypothetical passage that would directly answer the
question. Do not mention that it is hypothetical. The passage is used only for
semantic retrieval.\n\nQuestion: {query}\n\nPassage:"""
        )
        hypothetical = (prompt | self.llm | StrOutputParser()).invoke(
            {"query": state["query"]}
        )
        return {
            "hypothetical_document": hypothetical,
            "candidates": self._vector_search(hypothetical),
        }

    def _query_expansion_node(self, state: RAGState):
        prompt = ChatPromptTemplate.from_template(
            """Generate 2 focused search queries that retrieve complementary evidence
for the user's question. Preserve exact names, codes, and version identifiers.

User question: {query}"""
        )
        expansion = (prompt | self.llm.with_structured_output(QueryExpansion)).invoke(
            {"query": state["query"]}
        )
        queries = [state["query"], *expansion.queries[:2]]
        result_lists = [self._vector_search(query) for query in queries]
        return {
            "expanded_queries": queries,
            "candidates": reciprocal_rank_fusion(
                result_lists, final_k=self.config.candidate_k
            ),
        }

    def _parent_child_node(self, state: RAGState):
        matched_children = self.child_retriever.invoke(state["query"])
        parents: list[Document] = []
        seen: set[str] = set()
        for child in matched_children:
            parent_id = str(child.metadata["parent_id"])
            if parent_id not in seen:
                seen.add(parent_id)
                parent = self.parent_by_id[parent_id]
                parents.append(
                    Document(
                        page_content=parent.page_content,
                        metadata={
                            **parent.metadata,
                            "matched_child_id": document_key(child),
                            "retrieval_channels": ["parent_child"],
                            "retrieval_queries": [state["query"]],
                        },
                    )
                )
        return {"candidates": parents[: self.config.candidate_k]}

    def _rerank_node(self, state: RAGState):
        candidates = state.get("candidates", [])
        if not candidates or not self.config.use_reranker:
            return {
                "reranked_documents": candidates[: self.config.final_k],
                "rerank_metrics": {
                    "enabled": False,
                    "model": self.config.chat_model,
                    "api_calls": 0,
                    "candidate_count": len(candidates),
                    "input_tokens": 0,
                    "cached_input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "input_cost_usd": 0.0,
                    "output_cost_usd": 0.0,
                    "total_cost_usd": 0.0,
                    "latency_ms": 0.0,
                },
            }

        prompt = ChatPromptTemplate.from_template(
            """Rank every candidate by how directly it provides evidence for the
query. Return every chunk_id exactly once and score relevance from 0 to 100.

Query: {query}

Candidates:
{candidates}"""
        )
        rendered = "\n\n".join(
            f"CHUNK_ID: {document_key(doc)}\nPAGE: {doc.metadata.get('page')}\n{doc.page_content}"
            for doc in candidates
        )
        started = time.perf_counter()
        response = (
            prompt
            | self.llm.with_structured_output(RankingResult, include_raw=True)
        ).invoke(
            {"query": state["query"], "candidates": rendered}
        )
        latency_ms = (time.perf_counter() - started) * 1000
        result = response["parsed"]
        if result is None:
            raise ValueError(f"Reranker returned invalid structured output: {response['parsing_error']}")

        usage = extract_usage_metadata(response["raw"])
        costs = calculate_token_cost(
            input_tokens=usage["input_tokens"],
            cached_input_tokens=usage["cached_input_tokens"],
            output_tokens=usage["output_tokens"],
            input_cost_per_million=self.config.rerank_input_cost_per_million,
            cached_input_cost_per_million=(
                self.config.rerank_cached_input_cost_per_million
            ),
            output_cost_per_million=self.config.rerank_output_cost_per_million,
        )
        metrics: dict[str, int | float | str | bool] = {
            "enabled": True,
            "model": self.config.chat_model,
            "api_calls": 1,
            "candidate_count": len(candidates),
            "latency_ms": latency_ms,
            **usage,
            **costs,
        }
        by_id = {document_key(doc): doc for doc in candidates}
        ranked = sorted(
            (item for item in result.rankings if item.chunk_id in by_id),
            key=lambda item: item.relevance_score,
            reverse=True,
        )
        output: list[Document] = []
        for item in ranked[: self.config.final_k]:
            document = by_id[item.chunk_id]
            document.metadata["rerank_score"] = item.relevance_score
            output.append(document)

        # Structured output can occasionally omit an ID. Preserve a useful fallback.
        if len(output) < self.config.final_k:
            selected = {document_key(doc) for doc in output}
            output.extend(
                doc
                for doc in candidates
                if document_key(doc) not in selected
            )
        return {
            "reranked_documents": output[: self.config.final_k],
            "rerank_metrics": metrics,
        }

    def _generate_node(self, state: RAGState):
        documents = state.get("reranked_documents", [])
        context = "\n\n".join(
            f"[page {doc.metadata.get('page')}; {document_key(doc)}]\n{doc.page_content}"
            for doc in documents
        )
        prompt = ChatPromptTemplate.from_template(
            """Answer using only the supplied document context. If the context does
not contain the answer, say: "I cannot answer this from the retrieved document."
Cite supporting pages as [page N]. Keep the answer concise.

Question: {query}

Context:
{context}"""
        )
        answer = (prompt | self.llm | StrOutputParser()).invoke(
            {"query": state["query"], "context": context}
        )
        return {"answer": answer}

    def _build_graph(self):
        builder = StateGraph(RAGState)
        builder.add_node("route", self._route_node)
        builder.add_node("vector", self._vector_node)
        builder.add_node("hybrid", self._hybrid_node)
        builder.add_node("hyde", self._hyde_node)
        builder.add_node("query_expansion", self._query_expansion_node)
        builder.add_node("parent_child", self._parent_child_node)
        builder.add_node("rerank", self._rerank_node)
        builder.add_node("generate", self._generate_node)

        builder.add_edge(START, "route")
        builder.add_conditional_edges(
            "route",
            self._route_edge,
            {
                "vector": "vector",
                "hybrid": "hybrid",
                "hyde": "hyde",
                "query_expansion": "query_expansion",
                "parent_child": "parent_child",
            },
        )
        for node in (
            "vector",
            "hybrid",
            "hyde",
            "query_expansion",
            "parent_child",
        ):
            builder.add_edge(node, "rerank")
        builder.add_edge("rerank", "generate")
        builder.add_edge("generate", END)
        return builder.compile()

    def ask(self, query: str, strategy: str = "auto") -> RAGState:
        if not query.strip():
            raise ValueError("Query cannot be empty")
        return self.graph.invoke(
            {"query": query.strip(), "requested_strategy": strategy}
        )

    def reset_indexes(self) -> None:
        """Delete both Chroma collections owned by this PDF session."""
        self.vectorstore.delete_collection()
        self.child_vectorstore.delete_collection()
