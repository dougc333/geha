"""Class-based reranking adapters for the e2e RAG demo."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Iterable

import torch
from openai import OpenAI
from transformers import AutoModel, AutoTokenizer


class RerankingModels:
    """Run one of the demo's optional reranking strategies.

    External clients/models are injectable so the CLI can be unit-tested without
    network access or downloading a reranker model.
    """

    def __init__(
        self,
        *,
        openai_client: Any | None = None,
        cohere_client: Any | None = None,
        colbert_tokenizer: Any | None = None,
        colbert_model: Any | None = None,
    ) -> None:
        self.openai_client = openai_client
        self.cohere_client = cohere_client
        self.colbert_tokenizer = colbert_tokenizer
        self.colbert_model = colbert_model

    @staticmethod
    def _text(document: Any) -> str:
        return getattr(document, "page_content", str(document))

    @staticmethod
    def maxsim(query_embedding: torch.Tensor, document_embedding: torch.Tensor) -> torch.Tensor:
        expanded_query = query_embedding.unsqueeze(2)
        expanded_doc = document_embedding.unsqueeze(1)
        sim_matrix = torch.nn.functional.cosine_similarity(
            expanded_query, expanded_doc, dim=-1
        )
        max_sim_scores, _ = torch.max(sim_matrix, dim=2)
        return torch.mean(max_sim_scores, dim=1)

    def reranking_gpt(self, documents: list[Any], query: str) -> list[str]:
        client = self.openai_client or OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert relevance ranker. Given a list of documents "
                        "and a query, score each document from 0.0 to 100.0. Return "
                        "JSON with a documents array containing content and score."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {"query": query, "documents": [self._text(d) for d in documents]}
                    ),
                },
            ],
        )
        scored = json.loads(response.choices[0].message.content)["documents"]
        return [item["content"] for item in sorted(scored, key=lambda x: x["score"], reverse=True)]

    def _load_colbert(self) -> tuple[Any, Any]:
        if self.colbert_tokenizer is None:
            self.colbert_tokenizer = AutoTokenizer.from_pretrained("colbert-ir/colbertv2.0")
        if self.colbert_model is None:
            self.colbert_model = AutoModel.from_pretrained("colbert-ir/colbertv2.0")
        return self.colbert_tokenizer, self.colbert_model

    def reranking_colbert(self, documents: list[Any], query: str) -> list[str]:
        tokenizer, model = self._load_colbert()
        query_encoding = tokenizer(query, return_tensors="pt")
        with torch.no_grad():
            query_embedding = model(**query_encoding).last_hidden_state.mean(dim=1)

        scored: list[tuple[float, str]] = []
        for document in documents:
            text = self._text(document)
            encoding = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
            with torch.no_grad():
                document_embedding = model(**encoding).last_hidden_state
                score = self.maxsim(query_embedding.unsqueeze(0), document_embedding).item()
            scored.append((score, text))
        return [text for _, text in sorted(scored, key=lambda item: item[0], reverse=True)]

    def reranking_cohere(self, documents: list[Any], query: str) -> list[str]:
        if self.cohere_client is None:
            import cohere

            self.cohere_client = cohere.Client(os.environ["COHERE_API_KEY"])
        results = self.cohere_client.rerank(
            query=query,
            documents=[self._text(d) for d in documents],
            top_n=min(4, len(documents)),
            model="rerank-english-v3.0",
            return_documents=True,
        )
        return [result.document.text for result in results.results]

    def rerank(self, documents: Iterable[Any], query: str, model: str = "gpt") -> list[str]:
        docs = list(documents)
        if model == "gpt":
            return self.reranking_gpt(docs, query)
        if model == "colbert":
            return self.reranking_colbert(docs, query)
        if model == "cohere":
            return self.reranking_cohere(docs, query)
        return [self._text(doc) for doc in docs]
