"""Class-based reranking adapters for the e2e RAG demo."""

from __future__ import annotations

import json
from typing import Any, Iterable

from openai import OpenAI


class RerankingModels:
    """Run one of the demo's optional reranking strategies.

    External clients/models are injectable so the CLI can be unit-tested without
    network access or downloading a reranker model.
    """

    def __init__(
        self,
        *,
        openai_client: Any | None = None,
    ) -> None:
        self.openai_client = openai_client

    @staticmethod
    def _text(document: Any) -> str:
        return getattr(document, "page_content", str(document))

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


    def rerank(self, documents: Iterable[Any], query: str, model: str = "gpt") -> list[str]:
        docs = list(documents)
        if model == "gpt":
            return self.reranking_gpt(docs, query)
        return [self._text(doc) for doc in docs]
