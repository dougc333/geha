from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable, Sequence
from typing import Protocol

from .models import KnowledgeChunk


TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_./-]*", re.IGNORECASE)


class EmbeddingProvider(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class HashingEmbeddingProvider:
    """Dependency-free embedding adapter for tests and local demonstrations.

    It is a signed feature-hashing encoder, not a production semantic model.
    Its purpose is to keep this reference runnable without downloading a model.
    Replace it with an approved embedding service or local model in production.
    """

    def __init__(self, dimensions: int = 512):
        if dimensions < 32:
            raise ValueError("dimensions must be at least 32")
        self.dimensions = dimensions

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = TOKEN_RE.findall(text.lower())
        features = tokens + [f"{a}::{b}" for a, b in zip(tokens, tokens[1:])]

        for feature in features:
            digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
            value = int.from_bytes(digest, "big")
            index = value % self.dimensions
            sign = 1.0 if (value >> 8) & 1 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm:
            vector = [value / norm for value in vector]
        return vector


class SentenceTransformerEmbeddingProvider:
    """Optional local semantic-embedding adapter."""

    def __init__(self, model_name: str):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise RuntimeError(
                "Install the 'embeddings' extra to use SentenceTransformers"
            ) from error
        self._model = SentenceTransformer(model_name)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        values = self._model.encode(
            list(texts),
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return values.astype("float32").tolist()


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


class InMemoryVectorIndex:
    """Small exact-search index with metadata filtering before scoring."""

    def __init__(
        self,
        chunks: Iterable[KnowledgeChunk],
        embedder: EmbeddingProvider,
    ):
        self._chunks = list(chunks)
        self._embedder = embedder
        self._vectors = embedder.embed([chunk.text for chunk in self._chunks])

    def search(
        self,
        query: str,
        *,
        limit: int = 4,
        metadata_filter: dict[str, object] | None = None,
    ) -> list[tuple[float, KnowledgeChunk]]:
        query_vector = self._embedder.embed([query])[0]
        filters = metadata_filter or {}
        candidates: list[tuple[float, KnowledgeChunk]] = []

        for vector, chunk in zip(self._vectors, self._chunks):
            if any(chunk.metadata.get(key) != value for key, value in filters.items()):
                continue
            candidates.append((_dot(query_vector, vector), chunk))

        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[:limit]
