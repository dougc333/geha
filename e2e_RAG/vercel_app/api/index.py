"""Vercel Python API for the selectable RAG comparison demo."""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from typing import Literal

import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pgvector.psycopg import register_vector
from pydantic import BaseModel, Field

from rag_core import bm25_rank, reciprocal_rank_fusion


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


@contextmanager
def database():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    with psycopg.connect(url) as connection:
        register_vector(connection)
        yield connection


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


def _vector_rank(connection, document_id: str, query: str, limit: int) -> list[dict]:
    client = OpenAI()
    embedding = client.embeddings.create(
        model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        input=query,
    ).data[0].embedding
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


def _rerank(query: str, rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    client = OpenAI()
    candidates = [
        {"chunk_id": int(row["id"]), "text": row["content"]}
        for row in rows
    ]
    response = client.responses.create(
        model=os.getenv("OPENAI_RERANK_MODEL", "gpt-4o-mini"),
        store=False,
        instructions=(
            "Rank the candidate chunks by usefulness for answering the query. "
            "Use only the supplied candidates and return every chunk_id exactly once."
        ),
        input=f"QUERY:\n{query}\n\nCANDIDATES:\n{json.dumps(candidates)}",
        text={
            "format": {
                "type": "json_schema",
                "name": "chunk_ranking",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "chunk_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                        }
                    },
                    "required": ["chunk_ids"],
                    "additionalProperties": False,
                },
            }
        },
    )
    order = json.loads(response.output_text)["chunk_ids"]
    by_id = {int(row["id"]): row for row in rows}
    ordered = [by_id[chunk_id] for chunk_id in order if chunk_id in by_id]
    ordered.extend(row for row in rows if int(row["id"]) not in set(order))
    for rank, row in enumerate(ordered, start=1):
        row["rerank_position"] = rank
    return ordered


def _answer(query: str, rows: list[dict]) -> str:
    context = "\n\n".join(
        f"[chunk {row['id']}, page {row['page']}]\n{row['content']}" for row in rows
    )
    response = OpenAI().responses.create(
        model=os.getenv("OPENAI_GENERATION_MODEL", "gpt-4o-mini"),
        store=False,
        instructions=(
            "Answer only from the supplied document chunks. Cite supporting chunks as "
            "[chunk ID]. If the answer is absent, say it was not found in the document."
        ),
        input=f"QUESTION:\n{query}\n\nDOCUMENT CHUNKS:\n{context}",
    )
    return response.output_text


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/documents")
def documents() -> dict:
    try:
        with database() as connection, connection.cursor() as cursor:
            cursor.execute(
                """SELECT d.id, d.title, d.source, count(c.id)
                   FROM rag_documents d
                   LEFT JOIN rag_chunks c ON c.document_id = d.id
                   GROUP BY d.id, d.title, d.source ORDER BY d.title"""
            )
            return {
                "documents": [
                    {"id": row[0], "title": row[1], "source": row[2], "chunks": row[3]}
                    for row in cursor.fetchall()
                ]
            }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/search")
def search(request: SearchRequest) -> dict:
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
                ranked = _rerank(request.query, ranked[:20])
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
