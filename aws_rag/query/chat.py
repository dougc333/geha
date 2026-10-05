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
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import APIRouter, HTTPException
from langfuse import observe, propagate_attributes
from pydantic import BaseModel, Field, model_validator

from app import (
    GENERATION_MODEL, RERANK_CANDIDATES, _embed_query, _rerank, converse, database, langfuse
)
import arxiv_meta
import library
import weaviate_store
from retrieval import (
    bm25_search,
    hybrid_retrieve,
    keyword_search,
    vector_search,
)

router = APIRouter()
s3 = boto3.client("s3", config=Config(signature_version="s3v4"))  # v4: presigned figure URLs

RAW_BUCKET = os.getenv("RAW_BUCKET", "")
CHUNK_BUCKET = os.getenv("CHUNK_BUCKET", "")
FIGURE_URL_SECONDS = 3600  # presigned figure thumbnails in chat sources
ARXIV_MAX_BYTES = int(os.getenv("ARXIV_MAX_MB", "25")) * 1024 * 1024
HISTORY_MESSAGES = 10     # earlier messages sent to the model each turn
HISTORY_CHARS = 1500      # per message, so long answers don't crowd out sources
# Keyword retriever for the chatbot: "bm25" (Okapi BM25 over rag_terms; hit@5 0.95
# with rerank in evals/) or "fts" (Postgres ts_rank_cd; 0.85).

ROUTER_PROMPT = """You route messages for a chatbot over a library of arXiv papers.
Reply with ONE JSON object and nothing else:
{"route": "list" | "find" | "content", "count_only": true|false, "author": string|null,
 "year_from": int|null, "year_to": int|null, "category": string|null,
 "title_contains": string|null, "topic": string|null, "search_query": string}

route:
- "list": list or count papers by title, author, year or category.
  "show me all the titles", "how many papers do you have", "papers by Kaiming He",
  "papers from 2020 or later", "who wrote the Adam paper" (title_contains "Adam").
- "find": which papers are ABOUT a subject. "which papers are about object detection",
  "do you have anything on GANs" (topic "GAN or generative adversarial").
- "content": what papers say or explain. "what is dropout", "how was Orca evaluated",
  "compare BERT and GPT-3", "what BLEU did the Transformer get".
topic: a search expression over titles and abstracts. Add common expansions and
synonyms joined with " or ", e.g. "GAN or generative adversarial",
"object detection or object detector", "RL or reinforcement learning".
count_only: true only when the user asks how many.
category: an arXiv code when a field is named: computer vision cs.CV, NLP or language
cs.CL, machine learning cs.LG, AI cs.AI, robotics cs.RO, neural/evolutionary cs.NE,
information retrieval cs.IR, statistical ML stat.ML.
search_query: for "content", the latest message rewritten as a standalone search query,
resolving references from the conversation; otherwise the latest message unchanged.
Use null for anything not stated."""
ANSWER_PROMPT = (
    "You are a research assistant for a library of arXiv papers. Every question is "
    "about those papers: interpret names and terms as the papers use them (for "
    "example, a model or method a paper introduces), never in their everyday sense. "
    "Answer only from the numbered sources in the latest message, citing them inline "
    "like [1] or [2][3]. Don't use outside knowledge. If the sources don't contain the "
    "answer, say so plainly. Be concise, and name the paper when sources come from "
    "more than one."
)


MAX_MESSAGE_CHARS = 4000


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)

    @model_validator(mode="before")
    @classmethod
    def _trim_assistant(cls, data):
        # The page sends earlier answers back as history, and a library answer
        # (all 203 titles) is longer than the limit. Only HISTORY_CHARS of each
        # is used, so trim answers instead of rejecting the whole request.
        if isinstance(data, dict) and data.get("role") == "assistant" and isinstance(data.get("content"), str):
            data = {**data, "content": data["content"][:MAX_MESSAGE_CHARS]}
        return data


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)
    session_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9-]{1,64}$")  # groups traces
    document_ids: list[str] | None = Field(default=None, max_length=50)  # None = all papers
    top_k: int = Field(default=6, ge=1, le=10)
    backend: Literal["postgres", "weaviate"] = "postgres"  # where retrieval runs


class CompareBackendsRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    top_k: int = Field(default=8, ge=1, le=20)
    alpha: float = Field(default=0.5, ge=0.0, le=1.0)  # Weaviate: 0 = keyword only, 1 = vector only
    fusion: Literal["relative_score", "ranked"] = "relative_score"


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


def _route(messages: list[ChatMessage]) -> dict:
    """One Nova Lite call: which route, any library filters, and the search query."""
    latest = messages[-1].content
    earlier = messages[-HISTORY_MESSAGES - 1 : -1]
    history = "\n".join(f"{m.role.upper()}: {m.content[:HISTORY_CHARS]}" for m in earlier)
    text = _text(converse(
        "route",
        modelId=GENERATION_MODEL,
        system=[{"text": ROUTER_PROMPT}],
        messages=[{"role": "user", "content": [{"text":
            (f"CONVERSATION:\n{history}\n\n" if history else "") + f"LATEST MESSAGE:\n{latest}"}]}],
        inferenceConfig={"maxTokens": 300, "temperature": 0},
    ))
    try:
        decision = json.loads(text[text.index("{"): text.rindex("}") + 1])
    except ValueError:
        decision = {}
    if decision.get("route") not in {"list", "find", "content"}:
        decision["route"] = "content"  # unparseable → the safe default, normal RAG
    decision["search_query"] = (decision.get("search_query") or latest).strip() or latest
    for key in ("year_from", "year_to"):
        try:
            decision[key] = int(decision[key]) if decision.get(key) else None
        except (TypeError, ValueError):
            decision[key] = None
    return decision


def _answer_library(connection, decision: dict) -> tuple[str, list[dict]]:
    """Exact answer from rag_documents: a count or a complete numbered list."""
    filters = {k: decision.get(k) or None for k in ("author", "year_from", "year_to", "category", "title_contains")}
    topic = decision.get("topic") if decision["route"] == "find" else None
    papers = library.find_papers(connection, **filters, topic=topic)
    described = "".join(filter(None, [
        f" about {topic}" if topic else None,
        f" by {filters['author']}" if filters["author"] else None,
        f" with \"{filters['title_contains']}\" in the title" if filters["title_contains"] else None,
        f" in {filters['category']}" if filters["category"] else None,
        f" from {filters['year_from']}" if filters["year_from"] else None,
        f" up to {filters['year_to']}" if filters["year_to"] else None,
    ]))
    if not papers:
        return f"No papers in the library{' match' if described else ''}{described}.", []
    noun = "paper" if len(papers) == 1 else "papers"
    if decision.get("count_only"):
        return f"The library has {len(papers)} {noun}{described}.", papers
    few = len(papers) <= 5  # show full author lists for short answers ("who wrote X")
    lines = []
    for n, p in enumerate(papers, start=1):
        names = p["authors"]
        by = ", ".join(names) if few else (names[0] + (" et al." if len(names) > 1 else "") if names else "")
        year = (p["published"] or "")[:4]
        lines.append(f"{n}. {p['title']}" + (f" — {by}" if by else "") + (f" ({year})" if year else ""))
    return f"{len(papers)} {noun}{described}:\n" + "\n".join(lines), papers


_retrieve = hybrid_retrieve  # compatibility for eval scripts


def _retrieve_weaviate(query: str, document_ids: list[str] | None, timings: dict) -> list[dict]:
    """Same job as _retrieve (keyword + vector + fusion), done by one Weaviate hybrid query."""
    if not weaviate_store.enabled():
        raise HTTPException(status_code=503, detail="Weaviate is not configured")
    step = time.perf_counter()
    embedding = _embed_query(query)
    timings["embed_ms"] = round((time.perf_counter() - step) * 1000, 1)
    step = time.perf_counter()
    rows = weaviate_store.hybrid(query, embedding, limit=RERANK_CANDIDATES, document_ids=document_ids)
    timings["weaviate_ms"] = round((time.perf_counter() - step) * 1000, 1)
    return rows


def _brief(rows: list[dict], top_k: int) -> list[dict]:
    return [
        {"id": r["id"], "title": r["title"], "page": r["page"], "score": r["score"],
         "snippet": r["content"][:300], "explain": r.get("explain")}
        for r in rows[:top_k]
    ]


@router.post("/api/compare-backends")
def compare_backends(request: CompareBackendsRequest) -> dict:
    """Postgres (full-text + pgvector + RRF) vs Weaviate hybrid on the same query vector."""
    if not weaviate_store.enabled():
        raise HTTPException(status_code=503, detail="Weaviate is not configured")
    return _compare_backends(request)


# Traced separately: FastAPI must see the endpoint's own signature, not a wrapper's.
@observe(name="compare-backends")
def _compare_backends(request: CompareBackendsRequest) -> dict:
    try:
        step = time.perf_counter()
        embedding = _embed_query(request.query)
        embed_ms = round((time.perf_counter() - step) * 1000, 1)

        pg_timings: dict[str, float] = {}
        step = time.perf_counter()
        with database() as connection:
            postgres = _retrieve(connection, request.query, None, pg_timings, embedding=embedding)
        pg_timings["total_ms"] = round((time.perf_counter() - step) * 1000, 1)

        step = time.perf_counter()
        weaviate = weaviate_store.hybrid(request.query, embedding, alpha=request.alpha,
                                         fusion=request.fusion, limit=request.top_k)
        weaviate_ms = round((time.perf_counter() - step) * 1000, 1)

        top_pg = [r["id"] for r in postgres[: request.top_k]]
        top_wv = [r["id"] for r in weaviate[: request.top_k]]
        return {
            "postgres": _brief(postgres, request.top_k),
            "weaviate": _brief(weaviate, request.top_k),
            "overlap": len(set(top_pg) & set(top_wv)),
            "same_first": bool(top_pg and top_wv and top_pg[0] == top_wv[0]),
            "timings": {"embed_ms": embed_ms, "postgres": pg_timings, "weaviate_ms": weaviate_ms},
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _figure_urls(connection, chunk_ids: list[int]) -> dict[int, str]:
    """Presigned URLs for the figure images of these chunks (only figure chunks
    have rag_chunks.image). Looked up by ID after reranking, so it works for both
    backends (Weaviate objects carry the Postgres chunk ID)."""
    if not CHUNK_BUCKET or not chunk_ids:
        return {}
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, image FROM rag_chunks WHERE id = ANY(%s) AND image IS NOT NULL", (chunk_ids,))
        return {chunk_id: s3.generate_presigned_url("get_object", Params={"Bucket": CHUNK_BUCKET, "Key": key},
                                                    ExpiresIn=FIGURE_URL_SECONDS)
                for chunk_id, key in cursor.fetchall()}


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
        decision = _route(request.messages)
        query = decision["search_query"]
        timings["route_ms"] = round((time.perf_counter() - step) * 1000, 1)
        langfuse.update_current_span(metadata={"route": decision})

        if decision["route"] in {"list", "find"}:
            step = time.perf_counter()
            with database() as connection:
                answer, papers = _answer_library(connection, decision)
            timings["library_ms"] = round((time.perf_counter() - step) * 1000, 1)
            timings["total_ms"] = round((time.perf_counter() - started) * 1000, 1)
            langfuse.update_current_span(output=answer)
            return {
                "answer": answer,
                "route": decision["route"],
                "papers": [{k: p[k] for k in ("title", "arxiv_id", "authors", "published", "primary_category")}
                           for p in papers],
                "trace_id": langfuse.get_current_trace_id(),
                "standalone_question": query,
                "sources": [],
                "timings": timings,
            }

        with database() as connection:
            if request.backend == "weaviate":
                candidates = _retrieve_weaviate(query, request.document_ids, timings)
            else:
                candidates = _retrieve(connection, query, request.document_ids, timings)

        step = time.perf_counter()
        sources = _rerank(query, candidates[:RERANK_CANDIDATES])[: request.top_k]
        timings["rerank_ms"] = round((time.perf_counter() - step) * 1000, 1)
        with database() as connection:
            figure_urls = _figure_urls(connection, [s["id"] for s in sources])

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
                system=[{"text": ANSWER_PROMPT}],
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
            "route": "content",
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
                    "image_url": figure_urls.get(s["id"]),
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
