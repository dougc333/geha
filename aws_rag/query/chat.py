"""Multi-turn chat over every indexed paper, plus arXiv ingestion.

Each turn: rewrite a follow-up into a standalone question, run hybrid retrieval
(BM25 + vector, fused with RRF) across all papers, rerank, and answer with
numbered citations. POST /api/arxiv downloads a paper into the raw S3 bucket,
where the existing chunker -> embedder pipeline indexes it.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
from typing import Literal

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, HTTPException
from langfuse import observe, propagate_attributes
from pydantic import BaseModel, Field

from app import (
    GENERATION_MODEL, RERANK_CANDIDATES, _embed_query, _rerank, converse, database, langfuse
)
import arxiv_meta
from rag_core import reciprocal_rank_fusion, tokenize

router = APIRouter()
s3 = boto3.client("s3")

RAW_BUCKET = os.getenv("RAW_BUCKET", "")
ARXIV_MAX_BYTES = int(os.getenv("ARXIV_MAX_MB", "25")) * 1024 * 1024
HISTORY_MESSAGES = 10     # earlier messages sent to the model each turn
HISTORY_CHARS = 1500      # per message, so long answers don't crowd out sources
CANDIDATES_PER_RETRIEVER = 25

REWRITE_PROMPT = (
    "Rewrite the user's latest message as a standalone search query for a library "
    "of research papers, resolving pronouns and references from the conversation. "
    "Return only the query, with no quotes or explanation. If the message is "
    "already standalone, return it unchanged."
)
ANSWER_PROMPT = (
    "You are a research assistant for a library of arXiv papers. Every question is "
    "about those papers: interpret names and terms as the papers use them (for "
    "example, a model or method a paper introduces), never in their everyday sense. "
    "For questions about the library itself (which papers exist, how many, titles, "
    "authors, dates, categories), answer from the LIBRARY list below. For questions "
    "about what the papers say, answer only from the numbered sources in the latest "
    "message, citing them inline like [1] or [2][3]. Don't use outside knowledge. If "
    "neither contains the answer, say so plainly. Be concise, and name the paper when "
    "sources come from more than one."
)
MAX_CATALOG_AUTHORS = 12  # per paper; longer lists end with "et al."


def _library(connection) -> str:
    """Catalog of every paper, sent with each turn (fine up to ~100 papers)."""
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT title, arxiv_id, authors, published, primary_category
               FROM rag_documents ORDER BY published NULLS LAST, title"""
        )
        rows = cursor.fetchall()
    lines = []
    for n, (title, arxiv_id, authors, published, category) in enumerate(rows, start=1):
        details = ", ".join(filter(None, [
            f"arXiv {arxiv_id}" if arxiv_id else None,
            f"published {published}" if published else None,
            category,
        ]))
        names = authors or []
        by = "; ".join(names[:MAX_CATALOG_AUTHORS]) + (" et al." if len(names) > MAX_CATALOG_AUTHORS else "")
        lines.append(f"{n}. {title}" + (f" ({details})" if details else "") + (f". Authors: {by}" if by else ""))
    return f"LIBRARY ({len(rows)} papers):\n" + "\n".join(lines)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)
    session_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9-]{1,64}$")  # groups traces
    document_ids: list[str] | None = Field(default=None, max_length=50)  # None = all papers
    top_k: int = Field(default=6, ge=1, le=10)


class FeedbackRequest(BaseModel):
    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    helpful: bool
    comment: str | None = Field(default=None, max_length=1000)


class ArxivRequest(BaseModel):
    paper: str = Field(min_length=4, max_length=300)  # an ID or an arxiv.org URL


def _text(response: dict) -> str:
    return "".join(
        block["text"] for block in response["output"]["message"]["content"] if "text" in block
    ).strip()


def _conversation(messages: list[ChatMessage]) -> list[dict]:
    """Converse-format history: starts with a user turn and alternates roles."""
    turns: list[dict] = []
    for message in messages:
        text = message.content[:HISTORY_CHARS]
        if turns and turns[-1]["role"] == message.role:
            turns[-1]["content"][0]["text"] += "\n\n" + text
        else:
            turns.append({"role": message.role, "content": [{"text": text}]})
    while turns and turns[0]["role"] != "user":
        turns.pop(0)
    return turns


def _standalone_question(messages: list[ChatMessage]) -> str:
    latest = messages[-1].content
    earlier = messages[-HISTORY_MESSAGES - 1 : -1]
    if not earlier:
        return latest
    history = "\n".join(f"{m.role.upper()}: {m.content[:HISTORY_CHARS]}" for m in earlier)
    response = converse(
        "rewrite",
        modelId=GENERATION_MODEL,
        system=[{"text": REWRITE_PROMPT}],
        messages=[{
            "role": "user",
            "content": [{"text": f"CONVERSATION:\n{history}\n\nLATEST MESSAGE:\n{latest}"}],
        }],
        inferenceConfig={"maxTokens": 200, "temperature": 0},
    )
    return _text(response) or latest


@observe(name="retrieve", as_type="retriever", capture_input=False, capture_output=False)
def _retrieve(connection, query: str, document_ids: list[str] | None, timings: dict) -> list[dict]:
    langfuse.update_current_span(input={"query": query, "document_ids": document_ids})
    where, params = ("WHERE c.document_id = ANY(%s)", [document_ids]) if document_ids else ("", [])
    select = """SELECT c.id, c.chunk_index, c.page_number, c.content, d.id, d.title
                FROM rag_chunks c JOIN rag_documents d ON d.id = c.document_id"""

    def rows(cursor) -> list[dict]:
        return [
            {"id": r[0], "chunk_index": r[1], "page": r[2], "content": r[3],
             "document_id": r[4], "title": r[5]}
            for r in cursor.fetchall()
        ]

    # Keyword search runs in Postgres (GIN index on rag_chunks.tsv): any query
    # word may match ("or"), stopwords are dropped, and ts_rank_cd ranks by term
    # frequency and proximity. Unlike the lab's Python BM25 it never loads every
    # chunk, so it scales to the whole library.
    step = time.perf_counter()
    terms = tokenize(query)
    lexical: list[dict] = []
    if terms:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""SELECT c.id, c.chunk_index, c.page_number, c.content, d.id, d.title
                    FROM rag_chunks c JOIN rag_documents d ON d.id = c.document_id,
                         websearch_to_tsquery('english', %s) AS q
                    WHERE c.tsv @@ q {"AND c.document_id = ANY(%s)" if document_ids else ""}
                    ORDER BY ts_rank_cd(c.tsv, q, 32) DESC LIMIT %s""",
                [" or ".join(terms)] + ([document_ids] if document_ids else []) + [CANDIDATES_PER_RETRIEVER],
            )
            lexical = rows(cursor)
    timings["keyword_ms"] = round((time.perf_counter() - step) * 1000, 1)

    step = time.perf_counter()
    embedding = _embed_query(query)
    with connection.cursor() as cursor:
        cursor.execute(
            f"{select} {where} ORDER BY c.embedding <=> %s::vector LIMIT %s",
            params + [embedding, CANDIDATES_PER_RETRIEVER],
        )
        semantic = rows(cursor)
    timings["vector_ms"] = round((time.perf_counter() - step) * 1000, 1)

    fused = reciprocal_rank_fusion([semantic, lexical])
    langfuse.update_current_span(
        output={"keyword_hits": len(lexical), "vector_hits": len(semantic), "fused": len(fused)},
        metadata={k: timings[k] for k in ("keyword_ms", "vector_ms")},
    )
    return fused


@router.post("/api/chat")
def chat(request: ChatRequest) -> dict:
    if request.messages[-1].role != "user":
        raise HTTPException(status_code=422, detail="The last message must be from the user")
    # Set before the root span opens so every observation carries the session.
    with propagate_attributes(session_id=request.session_id, tags=["chat"]):
        return _chat_turn(request)


@observe(name="chat-turn", capture_input=False, capture_output=False)
def _chat_turn(request: ChatRequest) -> dict:
    langfuse.update_current_span(input=request.messages[-1].content)
    started = time.perf_counter()
    timings: dict[str, float] = {}
    try:
        step = time.perf_counter()
        query = _standalone_question(request.messages)
        timings["rewrite_ms"] = round((time.perf_counter() - step) * 1000, 1)

        with database() as connection:
            library = _library(connection)
            candidates = _retrieve(connection, query, request.document_ids, timings)

        step = time.perf_counter()
        sources = _rerank(query, candidates[:RERANK_CANDIDATES])[: request.top_k]
        timings["rerank_ms"] = round((time.perf_counter() - step) * 1000, 1)

        if sources:
            context = "\n\n".join(
                f"[{n}] {s['title']}, page {s['page']}\n{s['content']}"
                for n, s in enumerate(sources, start=1)
            )
            turns = _conversation(request.messages[-HISTORY_MESSAGES - 1 : -1])
            question = (
                f"SOURCES:\n{context}\n\nQUESTION (answer from the sources above, "
                f"with citations):\n{request.messages[-1].content}"
            )
            if turns and turns[-1]["role"] == "user":  # e.g. the previous turn got no answer
                turns[-1]["content"][0]["text"] += "\n\n" + question
            else:
                turns.append({"role": "user", "content": [{"text": question}]})
            step = time.perf_counter()
            answer = _text(converse(
                "answer",
                modelId=GENERATION_MODEL,
                system=[{"text": f"{ANSWER_PROMPT}\n\n{library}"}],
                messages=turns,
                inferenceConfig={"maxTokens": 1024, "temperature": 0.2},
            ))
            timings["generation_ms"] = round((time.perf_counter() - step) * 1000, 1)
        else:
            answer = "No papers are indexed yet. Add one by arXiv ID to get started."

        timings["total_ms"] = round((time.perf_counter() - started) * 1000, 1)
        langfuse.update_current_span(
            output=answer, metadata={"standalone_question": query, "timings": timings}
        )
        return {
            "answer": answer,
            "trace_id": langfuse.get_current_trace_id(),  # for /api/feedback
            "standalone_question": query,
            "sources": [
                {
                    "n": n,
                    "title": s["title"],
                    "document_id": s["document_id"],
                    "page": s["page"],
                    "chunk_id": s["id"],
                    "rerank_score": s.get("rerank_score"),
                    "snippet": s["content"][:400],
                }
                for n, s in enumerate(sources, start=1)
            ],
            "timings": timings,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/api/feedback")
def feedback(request: FeedbackRequest) -> dict:
    """Thumbs up/down on an answer, stored as a Langfuse score on its trace."""
    langfuse.create_score(
        name="user-feedback",
        value=1 if request.helpful else 0,
        data_type="BOOLEAN",
        trace_id=request.trace_id,
        comment=request.comment,
    )
    return {"status": "ok"}


@router.post("/api/arxiv")
def add_arxiv(request: ArxivRequest) -> dict:
    if not RAW_BUCKET:
        raise HTTPException(status_code=503, detail="RAW_BUCKET is not configured")
    arxiv_id = arxiv_meta.find_arxiv_id(request.paper)
    if not arxiv_id:
        raise HTTPException(
            status_code=400, detail="Enter an arXiv ID like 2305.14314 or an arxiv.org link"
        )
    key = f"arxiv/{arxiv_id}.pdf"
    try:
        head = s3.head_object(Bucket=RAW_BUCKET, Key=key)
        title = urllib.parse.unquote(head["Metadata"].get("title", arxiv_id))
        return {"status": "exists", "arxiv_id": arxiv_id, "title": title}
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in {"404", "NoSuchKey", "NotFound"}:
            raise

    meta = arxiv_meta.metadata(arxiv_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"arXiv has no paper {arxiv_id}")
    try:
        pdf = arxiv_meta.fetch(f"https://arxiv.org/pdf/{arxiv_id}", ARXIV_MAX_BYTES)
    except ValueError:
        raise HTTPException(status_code=413, detail=f"PDF is larger than {ARXIV_MAX_BYTES // 2**20} MB")
    if not pdf.startswith(b"%PDF"):
        raise HTTPException(status_code=502, detail="arXiv did not return a PDF")
    # Sidecar first: the PDF upload triggers the chunker, which reads it.
    s3.put_object(
        Bucket=RAW_BUCKET,
        Key=f"arxiv/{arxiv_id}.json",
        Body=json.dumps(meta).encode(),
        ContentType="application/json",
    )
    s3.put_object(
        Bucket=RAW_BUCKET,
        Key=key,
        Body=pdf,
        ContentType="application/pdf",
        Metadata={"title": urllib.parse.quote(meta["title"][:300])},  # S3 metadata must be ASCII
    )
    return {"status": "queued", "arxiv_id": arxiv_id, "title": meta["title"]}
