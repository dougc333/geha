"""Reusable Postgres hybrid retrieval for chat, signup, and evaluations."""

from __future__ import annotations

import os
import time

from langfuse import observe

from app import _embed_query, langfuse
from rag_core import reciprocal_rank_fusion, tokenize


CANDIDATES_PER_RETRIEVER = 25
KEYWORD_SEARCH = os.getenv("KEYWORD_SEARCH", "bm25")

_CHUNK_SELECT = """SELECT c.id, c.chunk_index, c.page_number, c.content, d.id, d.title
                   FROM rag_chunks c JOIN rag_documents d ON d.id = c.document_id"""


def _rows(cursor) -> list[dict]:
    return [
        {
            "id": row[0],
            "chunk_index": row[1],
            "page": row[2],
            "content": row[3],
            "document_id": row[4],
            "title": row[5],
        }
        for row in cursor.fetchall()
    ]


def keyword_search(
    connection,
    query: str,
    document_ids: list[str] | None = None,
    limit: int = CANDIDATES_PER_RETRIEVER,
) -> list[dict]:
    """Postgres full-text retrieval using the generated ``tsv`` column."""
    terms = tokenize(query)
    if not terms:
        return []
    with connection.cursor() as cursor:
        cursor.execute(
            f"""{_CHUNK_SELECT}, websearch_to_tsquery('english', %s) AS q
                WHERE c.tsv @@ q {"AND c.document_id = ANY(%s)" if document_ids else ""}
                ORDER BY ts_rank_cd(c.tsv, q, 32) DESC LIMIT %s""",
            [" or ".join(terms)] + ([document_ids] if document_ids else []) + [limit],
        )
        return _rows(cursor)


BM25_SQL = """
WITH q AS (
    SELECT DISTINCT lexeme FROM unnest(tsvector_to_array(to_tsvector('english', %(query)s))) AS lexeme
), stats AS (
    SELECT count(*)::float8 AS n, avg(content_len)::float8 AS avglen FROM rag_chunks
), df AS (
    SELECT t.lexeme, count(*)::float8 AS df FROM rag_terms t JOIN q USING (lexeme) GROUP BY t.lexeme
), scored AS (
    SELECT t.chunk_id,
           sum(ln(1 + (s.n - df.df + 0.5) / (df.df + 0.5))
               * t.tf * (%(k1)s + 1)
               / (t.tf + %(k1)s * (1 - %(b)s + %(b)s * c.content_len / s.avglen))) AS score
    FROM df
    CROSS JOIN LATERAL (SELECT chunk_id, tf FROM rag_terms
                        WHERE rag_terms.lexeme = df.lexeme OFFSET 0) AS t
    JOIN rag_chunks c ON c.id = t.chunk_id
    CROSS JOIN stats s
    {document_filter}
    GROUP BY t.chunk_id
    ORDER BY score DESC
    LIMIT %(limit)s
)
SELECT c.id, c.chunk_index, c.page_number, c.content, d.id, d.title
FROM scored JOIN rag_chunks c ON c.id = scored.chunk_id JOIN rag_documents d ON d.id = c.document_id
ORDER BY scored.score DESC
"""


def bm25_search(
    connection,
    query: str,
    document_ids: list[str] | None = None,
    limit: int = CANDIDATES_PER_RETRIEVER,
    k1: float = 1.2,
    b: float = 0.75,
) -> list[dict]:
    """Okapi BM25 over the ``rag_terms`` inverted index."""
    if not tokenize(query):
        return []
    sql = BM25_SQL.format(
        document_filter="WHERE c.document_id = ANY(%(docs)s)" if document_ids else ""
    )
    with connection.cursor() as cursor:
        cursor.execute(
            sql,
            {
                "query": query,
                "k1": k1,
                "b": b,
                "limit": limit,
                "docs": document_ids,
            },
        )
        return _rows(cursor)


def vector_search(
    connection,
    embedding: list[float],
    document_ids: list[str] | None = None,
    limit: int = CANDIDATES_PER_RETRIEVER,
) -> list[dict]:
    """pgvector cosine nearest-neighbour retrieval."""
    with connection.cursor() as cursor:
        cursor.execute(
            f"""{_CHUNK_SELECT} {"WHERE c.document_id = ANY(%s)" if document_ids else ""}
                ORDER BY c.embedding <=> %s::vector LIMIT %s""",
            ([document_ids] if document_ids else []) + [embedding, limit],
        )
        return _rows(cursor)


@observe(name="retrieve", as_type="retriever", capture_input=False, capture_output=False)
def hybrid_retrieve(
    connection,
    query: str,
    document_ids: list[str] | None,
    timings: dict,
    embedding: list[float] | None = None,
    trace_query: bool = True,
) -> list[dict]:
    """Run lexical and vector retrieval and combine them with RRF."""
    langfuse.update_current_span(input=(
        {"query": query, "document_ids": document_ids}
        if trace_query
        else {"query_redacted": True, "document_ids": document_ids}
    ))
    step = time.perf_counter()
    lexical = (
        keyword_search(connection, query, document_ids)
        if KEYWORD_SEARCH == "fts"
        else bm25_search(connection, query, document_ids)
    )
    timings["keyword_ms"] = round((time.perf_counter() - step) * 1000, 1)

    step = time.perf_counter()
    semantic = vector_search(connection, embedding or _embed_query(query), document_ids)
    timings["vector_ms"] = round((time.perf_counter() - step) * 1000, 1)

    fused = reciprocal_rank_fusion([semantic, lexical])
    langfuse.update_current_span(
        output={
            "keyword_hits": len(lexical),
            "vector_hits": len(semantic),
            "fused": len(fused),
        },
        metadata={key: timings[key] for key in ("keyword_ms", "vector_ms")},
    )
    return fused
