"""RAG query API: BM25 / vector / hybrid retrieval, Bedrock rerank and answer."""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from typing import Literal

import boto3
import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langfuse import get_client, observe
from pgvector.psycopg import register_vector
from pydantic import BaseModel, Field

import library
from rag_core import bm25_rank, reciprocal_rank_fusion


REGION = os.getenv("AWS_REGION", "us-west-2")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0")
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1024"))  # schema.sql vector(1024)
RERANK_MODEL = os.getenv("RERANK_MODEL", "amazon.rerank-v1:0")
# Rerank the whole fused candidate pool (up to 20 vector + 20 BM25): hybrid fusion
# can push a strong vector hit past position 20. Bedrock bills reranking per 100
# documents, so 40 candidates cost the same as 20.
RERANK_CANDIDATES = int(os.getenv("RERANK_CANDIDATES", "50"))
# List prices (USD) reported to Langfuse, which has no Bedrock embedding or
# rerank pricing of its own. Nova Lite is priced in Langfuse's model settings.
EMBEDDING_PRICE_PER_TOKEN = float(os.getenv("EMBEDDING_PRICE_PER_TOKEN", "0.00000002"))  # Titan v2
RERANK_PRICE_PER_UNIT = float(os.getenv("RERANK_PRICE_PER_UNIT", "0.001"))  # per search unit
GENERATION_MODEL = os.getenv("GENERATION_MODEL", "amazon.nova-lite-v1:0")

bedrock = boto3.client("bedrock-runtime", region_name=REGION)
bedrock_agent = boto3.client("bedrock-agent-runtime", region_name=REGION)

# Tracing to Langfuse; a no-op when LANGFUSE_PUBLIC_KEY/SECRET_KEY aren't set.
langfuse = get_client()


def converse(name: str, **kwargs) -> dict:
    """bedrock.converse, recorded as a Langfuse generation with token usage."""
    with langfuse.start_as_current_observation(
        as_type="generation",
        name=name,
        model=kwargs["modelId"],
        input={"system": kwargs.get("system"), "messages": kwargs.get("messages")},
        model_parameters=kwargs.get("inferenceConfig"),
    ) as generation:
        response = bedrock.converse(**kwargs)
        generation.update(
            output=response["output"]["message"]["content"],
            usage_details={
                "input": response["usage"]["inputTokens"],
                "output": response["usage"]["outputTokens"],
            },
        )
        return response


app = FastAPI(title="Selectable RAG Demo", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",")],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class SearchRequest(BaseModel):
    document_id: str = Field(min_length=1, max_length=128)
    query: str = Field(min_length=2, max_length=2000)
    retrieval_mode: Literal["vector", "bm25", "hybrid"] = "hybrid"
    use_reranker: bool = False
    generate_answer: bool = False
    top_k: int = Field(default=5, ge=1, le=10)


# One connection per Lambda container, reused across requests. Opening a new
# TLS connection to Neon cost ~1 s per request. A Lambda container handles one
# request at a time, so sharing it is safe. Autocommit: every query here is a
# read, so no transaction is left open between requests.
_connection: psycopg.Connection | None = None
_last_used = 0.0
IDLE_CHECK_SECONDS = 60  # Neon may drop idle connections; ping before reusing one


def _connect() -> psycopg.Connection:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    connection = psycopg.connect(url, autocommit=True)
    register_vector(connection)
    return connection


@contextmanager
def database():
    global _connection, _last_used
    if _connection is not None and not _connection.closed and time.monotonic() - _last_used > IDLE_CHECK_SECONDS:
        try:
            _connection.execute("SELECT 1")
        except psycopg.Error:
            _connection.close()
    if _connection is None or _connection.closed or _connection.broken:
        _connection = _connect()
    try:
        yield _connection
    except psycopg.OperationalError:
        _connection.close()  # connection lost mid-request; reconnect next time
        raise
    finally:
        _last_used = time.monotonic()


def _all_chunks(connection, document_id: str) -> list[dict]:
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT id, chunk_index, page_number, content
               FROM rag_chunks WHERE document_id = %s ORDER BY chunk_index""",
            (document_id,),
        )
        return [
            {
                "id": row[0],
                "chunk_index": row[1],
                "page": row[2],
                "content": row[3],
            }
            for row in cursor.fetchall()
        ]


@observe(name="embed-query", as_type="embedding", capture_output=False)
def _embed_query(query: str) -> list[float]:
    # Same model and settings as the embedder, or cosine scores are meaningless.
    response = bedrock.invoke_model(
        modelId=EMBEDDING_MODEL,
        body=json.dumps({"inputText": query, "dimensions": EMBEDDING_DIMENSIONS, "normalize": True}),
    )
    body = json.loads(response["body"].read())
    tokens = body.get("inputTextTokenCount", 0)
    langfuse.update_current_generation(
        model=EMBEDDING_MODEL,
        usage_details={"input": tokens},
        cost_details={"input": tokens * EMBEDDING_PRICE_PER_TOKEN},
    )
    return body["embedding"]


def _vector_rank(connection, document_id: str, query: str, limit: int) -> list[dict]:
    embedding = _embed_query(query)
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT id, chunk_index, page_number, content,
                      1 - (embedding <=> %s::vector) AS score
               FROM rag_chunks
               WHERE document_id = %s
               ORDER BY embedding <=> %s::vector
               LIMIT %s""",
            (embedding, document_id, embedding, limit),
        )
        return [
            {
                "id": row[0],
                "chunk_index": row[1],
                "page": row[2],
                "content": row[3],
                "score": float(row[4]),
                "score_type": "cosine",
            }
            for row in cursor.fetchall()
        ]


@observe(name="rerank", as_type="generation", capture_input=False, capture_output=False)
def _rerank(query: str, rows: list[dict]) -> list[dict]:
    """Reorder candidates with a Bedrock reranking model (cross-encoder scores)."""
    if not rows:
        return []
    # Bedrock bills reranking per search unit: up to 100 documents per query.
    # (Documents over 512 tokens count extra; our ~450-token chunks don't.)
    units = -(-len(rows) // 100)
    langfuse.update_current_generation(
        input={"query": query, "candidates": len(rows)},
        model=RERANK_MODEL,
        usage_details={"search_units": units},
        cost_details={"total": units * RERANK_PRICE_PER_UNIT},  # "total" is what Langfuse sums
    )
    response = bedrock_agent.rerank(
        queries=[{"type": "TEXT", "textQuery": {"text": query}}],
        sources=[
            {
                "type": "INLINE",
                "inlineDocumentSource": {"type": "TEXT", "textDocument": {"text": row["content"]}},
            }
            for row in rows
        ],
        rerankingConfiguration={
            "type": "BEDROCK_RERANKING_MODEL",
            "bedrockRerankingConfiguration": {
                "numberOfResults": len(rows),
                "modelConfiguration": {
                    "modelArn": f"arn:aws:bedrock:{REGION}::foundation-model/{RERANK_MODEL}"
                },
            },
        },
    )
    ordered = []
    for rank, result in enumerate(response["results"], start=1):
        row = rows[result["index"]]
        row["rerank_position"] = rank
        row["rerank_score"] = result["relevanceScore"]
        ordered.append(row)
    langfuse.update_current_generation(output=[
        {"chunk_id": r["id"], "page": r["page"], "score": round(r["rerank_score"], 4)}
        for r in ordered[:10]
    ])
    return ordered


def _answer(query: str, rows: list[dict]) -> str:
    context = "\n\n".join(
        f"[chunk {row['id']}, page {row['page']}]\n{row['content']}" for row in rows
    )
    response = converse(
        "answer",
        modelId=GENERATION_MODEL,
        system=[{
            "text": (
                "Answer only from the supplied document chunks. Cite supporting chunks as "
                "[chunk ID]. If the answer is absent, say it was not found in the document."
            )
        }],
        messages=[{
            "role": "user",
            "content": [{"text": f"QUESTION:\n{query}\n\nDOCUMENT CHUNKS:\n{context}"}],
        }],
        inferenceConfig={"maxTokens": 1024, "temperature": 0.2},
    )
    return "".join(
        block["text"] for block in response["output"]["message"]["content"] if "text" in block
    )


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/documents")
def documents(author: str | None = None, year_from: int | None = None, year_to: int | None = None,
              category: str | None = None, q: str | None = None) -> dict:
    """Papers in the library with their metadata. Optional filters: author
    (partial name), year_from / year_to (published year), category (arXiv,
    e.g. cs.CV) and q (words in the title or abstract, ranked by relevance)."""
    try:
        with database() as connection:
            return {"documents": library.find_papers(
                connection, author=author, year_from=year_from, year_to=year_to,
                category=category, topic=q)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/search")
def search(request: SearchRequest) -> dict:
    return _search(request)


# Traced separately: FastAPI must see the endpoint's own signature, not a wrapper's
# (with the decorator on the endpoint, it treated `request` as a query parameter).
@observe(name="lab-search", capture_output=False)
def _search(request: SearchRequest) -> dict:
    started = time.perf_counter()
    timings: dict[str, float] = {}
    try:
        with database() as connection:
            if request.retrieval_mode in {"bm25", "hybrid"}:
                step = time.perf_counter()
                lexical = [
                    row
                    for row in bm25_rank(
                        request.query,
                        _all_chunks(connection, request.document_id),
                    )
                    if row["score"] > 0
                ][:20]
                timings["bm25_ms"] = round((time.perf_counter() - step) * 1000, 1)
            else:
                lexical = []

            if request.retrieval_mode in {"vector", "hybrid"}:
                step = time.perf_counter()
                semantic = _vector_rank(connection, request.document_id, request.query, 20)
                timings["vector_ms"] = round((time.perf_counter() - step) * 1000, 1)
            else:
                semantic = []

            if request.retrieval_mode == "bm25":
                ranked = lexical
            elif request.retrieval_mode == "vector":
                ranked = semantic
            else:
                ranked = reciprocal_rank_fusion([semantic, lexical])

            if request.use_reranker:
                step = time.perf_counter()
                ranked = _rerank(request.query, ranked[:RERANK_CANDIDATES])
                timings["rerank_ms"] = round((time.perf_counter() - step) * 1000, 1)

            results = ranked[: request.top_k]
            answer = None
            if request.generate_answer:
                step = time.perf_counter()
                answer = _answer(request.query, results)
                timings["generation_ms"] = round((time.perf_counter() - step) * 1000, 1)

        timings["total_ms"] = round((time.perf_counter() - started) * 1000, 1)
        return {
            "configuration": request.model_dump(),
            "answer": answer,
            "results": results,
            "timings": timings,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
