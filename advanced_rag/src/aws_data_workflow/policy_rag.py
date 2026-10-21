"""Hybrid retrieval and citation-bound answers over reviewed policy chunks."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable

from .contextual_embeddings import make_titan_embedder, read_jsonl


Embedder = Callable[[str], list[float]]
AnswerGenerator = Callable[[str, list[dict[str, Any]]], str]
TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*")
APPROVED_STATUSES = {"approved", "passed"}


def tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(
        sum(value * value for value in right)
    )
    if denominator == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / denominator


def bm25_rank(
    query: str,
    records: list[dict[str, Any]],
    *,
    limit: int,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[tuple[str, float]]:
    """Return chunk IDs ranked by Okapi BM25 over contextual retrieval text."""
    query_terms = tokenize(query)
    documents = [
        tokenize(record.get("contextual_retrieval_text") or record["text"])
        for record in records
    ]
    if not query_terms or not documents:
        return []
    average_length = sum(map(len, documents)) / len(documents) or 1.0
    document_frequency = Counter(
        term for document in documents for term in set(document)
    )
    scores: list[tuple[str, float]] = []
    for record, terms in zip(records, documents):
        frequencies = Counter(terms)
        score = 0.0
        for term in query_terms:
            frequency = frequencies[term]
            if not frequency:
                continue
            matches = document_frequency[term]
            inverse_frequency = math.log(
                1 + (len(documents) - matches + 0.5) / (matches + 0.5)
            )
            length_factor = 1 - b + b * len(terms) / average_length
            score += inverse_frequency * (
                frequency * (k1 + 1) / (frequency + k1 * length_factor)
            )
        scores.append((record["chunk_id"], score))
    return sorted(scores, key=lambda item: (-item[1], item[0]))[:limit]


def vector_rank(
    query_vector: list[float],
    records: list[dict[str, Any]],
    *,
    limit: int,
) -> list[tuple[str, float]]:
    scores = [
        (record["chunk_id"], cosine_similarity(query_vector, record["embedding"]))
        for record in records
        if isinstance(record.get("embedding"), list)
    ]
    return sorted(scores, key=lambda item: (-item[1], item[0]))[:limit]


def reciprocal_rank_fusion(
    rankings: Iterable[list[tuple[str, float]]],
    *,
    k: int = 60,
) -> list[tuple[str, float]]:
    fused: Counter[str] = Counter()
    for ranking in rankings:
        for rank, (chunk_id, _score) in enumerate(ranking, start=1):
            fused[chunk_id] += 1 / (k + rank)
    return sorted(fused.items(), key=lambda item: (-item[1], item[0]))


def retrieve(
    query: str,
    records: list[dict[str, Any]],
    *,
    embed_query: Embedder,
    candidate_k: int = 20,
    top_k: int = 6,
    allow_unreviewed: bool = False,
) -> list[dict[str, Any]]:
    """Retrieve evidence with BM25 + vector search and RRF fusion."""
    eligible = [
        record
        for record in records
        if allow_unreviewed or record.get("review_status") in APPROVED_STATUSES
    ]
    if not eligible:
        return []
    query_vector = embed_query(query)
    lexical = bm25_rank(query, eligible, limit=candidate_k)
    semantic = vector_rank(query_vector, eligible, limit=candidate_k)
    fused = reciprocal_rank_fusion([lexical, semantic])
    by_id = {record["chunk_id"]: record for record in eligible}
    return [
        {**by_id[chunk_id], "retrieval_score": score, "retrieval_rank": rank}
        for rank, (chunk_id, score) in enumerate(fused[:top_k], start=1)
    ]


def source_pages(record: dict[str, Any]) -> list[int]:
    """Collect page numbers from common Docling provenance shapes."""
    explicit = record.get("pages")
    if isinstance(explicit, list):
        return sorted({int(page) for page in explicit if isinstance(page, int)})
    pages: set[int] = set()
    metadata = record.get("metadata", {})
    for item in metadata.get("doc_items", []) if isinstance(metadata, dict) else []:
        for provenance in item.get("prov", []) if isinstance(item, dict) else []:
            page = provenance.get("page_no") if isinstance(provenance, dict) else None
            if isinstance(page, int):
                pages.add(page)
    return sorted(pages)


def build_answer_prompt(query: str, sources: list[dict[str, Any]]) -> str:
    evidence = []
    for number, source in enumerate(sources, start=1):
        pages = source_pages(source)
        page_label = ", ".join(map(str, pages)) if pages else "unknown"
        evidence.append(
            f"[{number}] {source.get('source_name', 'policy')} page {page_label}; "
            f"chunk {source['chunk_id']}\n{source['text']}"
        )
    joined = "\n\n".join(evidence)
    return f"""Answer the policy question using only the evidence below.

Rules:
- Cite every factual claim with one or more source numbers such as [1].
- Never treat retrieval context as policy evidence; use the original source text shown.
- If the evidence is insufficient, say that the policy documents provided do not answer it.
- Do not infer eligibility, coverage, or payment beyond the exact policy language.
- Mention conflicts, plan years, options, limitations, and exceptions when material.

Question: {query}

Evidence:
{joined}
"""


def make_bedrock_answer_generator(
    model_id: str,
    *,
    region_name: str | None = None,
) -> AnswerGenerator:
    import boto3

    client = boto3.client("bedrock-runtime", region_name=region_name)

    def generate(query: str, sources: list[dict[str, Any]]) -> str:
        response = client.converse(
            modelId=model_id,
            system=[{
                "text": (
                    "You answer questions about policy documents. Be precise, "
                    "conservative, and citation-bound."
                )
            }],
            messages=[{
                "role": "user",
                "content": [{"text": build_answer_prompt(query, sources)}],
            }],
            inferenceConfig={"maxTokens": 800, "temperature": 0},
        )
        return " ".join(
            block["text"]
            for block in response["output"]["message"]["content"]
            if block.get("text")
        ).strip()

    return generate


def answer_policy_question(
    query: str,
    records: list[dict[str, Any]],
    *,
    embed_query: Embedder,
    generate_answer: AnswerGenerator,
    candidate_k: int = 20,
    top_k: int = 6,
    allow_unreviewed: bool = False,
) -> dict[str, Any]:
    sources = retrieve(
        query,
        records,
        embed_query=embed_query,
        candidate_k=candidate_k,
        top_k=top_k,
        allow_unreviewed=allow_unreviewed,
    )
    if not sources:
        return {
            "query": query,
            "answer": "No reviewed policy evidence is available to answer this question.",
            "sources": [],
        }
    answer = generate_answer(query, sources)
    return {
        "query": query,
        "answer": answer,
        "sources": [
            {
                "number": number,
                "chunk_id": source["chunk_id"],
                "source_name": source.get("source_name"),
                "pages": source_pages(source),
                "score": source["retrieval_score"],
                "text": source["text"],
            }
            for number, source in enumerate(sources, start=1)
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--answer-model", default=os.environ.get("BEDROCK_ANSWER_MODEL_ID"))
    parser.add_argument("--embedding-model", default="amazon.titan-embed-text-v2:0")
    parser.add_argument("--dimensions", type=int, default=1024)
    parser.add_argument("--region", default=os.environ.get("AWS_REGION"))
    parser.add_argument("--candidate-k", type=int, default=20)
    parser.add_argument("--top-k", type=int, default=6)
    parser.add_argument(
        "--allow-unreviewed",
        action="store_true",
        help="Development only: query pending chunks",
    )
    args = parser.parse_args()
    if not args.answer_model:
        parser.error("--answer-model or BEDROCK_ANSWER_MODEL_ID is required")

    records = read_jsonl(args.chunks.expanduser().resolve())
    embedder = make_titan_embedder(
        args.embedding_model,
        dimensions=args.dimensions,
        region_name=args.region,
    )
    generator = make_bedrock_answer_generator(
        args.answer_model,
        region_name=args.region,
    )
    result = answer_policy_question(
        args.query,
        records,
        embed_query=embedder,
        generate_answer=generator,
        candidate_k=args.candidate_k,
        top_k=args.top_k,
        allow_unreviewed=args.allow_unreviewed,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

