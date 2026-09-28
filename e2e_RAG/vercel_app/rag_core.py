"""Pure retrieval helpers shared by the Vercel API and unit tests."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterable


TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def bm25_rank(query: str, rows: list[dict], *, k1: float = 1.5, b: float = 0.75) -> list[dict]:
    """Return rows ordered by Okapi BM25 score.

    BM25 is calculated over the selected document's chunks. Keeping this code
    explicit makes the demo's "BM25 only" option genuinely BM25 rather than a
    PostgreSQL full-text-search approximation.
    """
    if not rows:
        return []
    query_terms = tokenize(query)
    tokenized = [tokenize(str(row["content"])) for row in rows]
    average_length = sum(map(len, tokenized)) / len(tokenized) or 1.0
    document_frequency = Counter()
    for tokens in tokenized:
        document_frequency.update(set(tokens))

    scored: list[dict] = []
    total_documents = len(rows)
    for row, tokens in zip(rows, tokenized):
        frequencies = Counter(tokens)
        score = 0.0
        for term in query_terms:
            frequency = frequencies[term]
            if not frequency:
                continue
            df = document_frequency[term]
            inverse_frequency = math.log(1.0 + (total_documents - df + 0.5) / (df + 0.5))
            denominator = frequency + k1 * (1.0 - b + b * len(tokens) / average_length)
            score += inverse_frequency * frequency * (k1 + 1.0) / denominator
        item = dict(row)
        item["score"] = score
        item["score_type"] = "bm25"
        scored.append(item)
    return sorted(scored, key=lambda item: (-item["score"], item["chunk_index"]))


def reciprocal_rank_fusion(
    ranked_lists: Iterable[list[dict]], *, rank_constant: int = 60
) -> list[dict]:
    """Combine independently ranked lists with reciprocal-rank fusion."""
    combined: dict[int, dict] = {}
    for ranked in ranked_lists:
        for rank, row in enumerate(ranked, start=1):
            chunk_id = int(row["id"])
            if chunk_id not in combined:
                combined[chunk_id] = {**row, "score": 0.0, "score_type": "rrf"}
            combined[chunk_id]["score"] += 1.0 / (rank_constant + rank)
    return sorted(combined.values(), key=lambda item: (-item["score"], item["chunk_index"]))


def chunk_text(text: str, *, size: int = 350, overlap: int = 50) -> list[str]:
    if size < 1 or overlap < 0 or overlap >= size:
        raise ValueError("Require size >= 1 and 0 <= overlap < size")
    words = text.split()
    if not words:
        return []
    step = size - overlap
    return [" ".join(words[start : start + size]) for start in range(0, len(words), step)]
