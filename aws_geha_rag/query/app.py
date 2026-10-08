"""Authenticated GEHA document search and grounded-answer API."""

from __future__ import annotations

import json
import os
from pathlib import Path

import boto3
import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from mangum import Mangum
from pgvector.psycopg import register_vector
from pydantic import BaseModel, Field

from core import evidence_prompt, reciprocal_rank_fusion


DATABASE_URL_PARAMETER = os.environ["DATABASE_URL_PARAMETER"]
API_KEY_PARAMETER = os.environ["API_KEY_PARAMETER"]
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0")
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1024"))
GENERATION_MODEL = os.getenv("GENERATION_MODEL", "amazon.nova-lite-v1:0")
RETRIEVAL_CANDIDATES = int(os.getenv("RETRIEVAL_CANDIDATES", "40"))
BM25_K1 = float(os.getenv("BM25_K1", "1.2"))
BM25_B = float(os.getenv("BM25_B", "0.75"))
bedrock = boto3.client("bedrock-runtime")
ssm = boto3.client("ssm")
_database_url = None
_api_key = None


def secret(name: str) -> str:
    return ssm.get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"]


def database_url() -> str:
    global _database_url
    if _database_url is None:
        _database_url = secret(DATABASE_URL_PARAMETER)
    return _database_url


def require_api_key(x_api_key: str | None = Header(default=None)):
    global _api_key
    if _api_key is None:
        _api_key = secret(API_KEY_PARAMETER)
    if not x_api_key or x_api_key != _api_key:
        raise HTTPException(status_code=401, detail="invalid API key")


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    category: str | None = None
    program: str | None = None
    limit: int = Field(default=8, ge=1, le=20)


class ChatRequest(SearchRequest):
    pass


def embedding(text: str):
    response = bedrock.invoke_model(
        modelId=EMBEDDING_MODEL,
        body=json.dumps({
            "inputText": text,
            "dimensions": EMBEDDING_DIMENSIONS,
            "normalize": True,
        }),
    )
    return json.loads(response["body"].read())["embedding"]


BM25_SQL = """
WITH query_terms AS (
    SELECT DISTINCT lexeme
    FROM unnest(tsvector_to_array(to_tsvector('english', %(query)s))) AS lexeme
), corpus_stats AS (
    SELECT count(*)::float8 AS chunk_count,
           coalesce(avg(content_len), 1)::float8 AS average_length
    FROM geha_chunks
), document_frequency AS (
    SELECT term.lexeme, count(*)::float8 AS frequency
    FROM geha_terms AS term
    JOIN query_terms USING (lexeme)
    GROUP BY term.lexeme
), scored AS (
    SELECT term.chunk_id,
           sum(
               ln(1 + (stats.chunk_count - df.frequency + 0.5) / (df.frequency + 0.5))
               * term.tf * (%(k1)s + 1)
               / (term.tf + %(k1)s * (
                   1 - %(b)s + %(b)s * chunk.content_len / stats.average_length
               ))
           ) AS score
    FROM document_frequency AS df
    CROSS JOIN LATERAL (
        SELECT chunk_id, tf FROM geha_terms
        WHERE geha_terms.lexeme = df.lexeme OFFSET 0
    ) AS term
    JOIN geha_chunks AS chunk ON chunk.id = term.chunk_id
    JOIN geha_documents AS document ON document.id = chunk.document_id
    CROSS JOIN corpus_stats AS stats
    WHERE (%(category)s::text IS NULL OR document.category = %(category)s)
      AND (%(program)s::text IS NULL OR document.program = %(program)s)
    GROUP BY term.chunk_id
    ORDER BY score DESC
    LIMIT %(candidate_limit)s
)
SELECT c.id,c.document_id,c.chunk_index,c.page_number,c.content,
       d.title,d.source,d.relative_path,d.category,d.program
FROM scored
JOIN geha_chunks AS c ON c.id = scored.chunk_id
JOIN geha_documents AS d ON d.id = c.document_id
ORDER BY scored.score DESC
"""


def search(request: SearchRequest) -> list[dict]:
    vector = embedding(request.query)
    filters = ["(%s::text IS NULL OR d.category=%s)", "(%s::text IS NULL OR d.program=%s)"]
    params = (request.category, request.category, request.program, request.program)
    columns = "c.id,c.document_id,c.chunk_index,c.page_number,c.content,d.title,d.source,d.relative_path,d.category,d.program"
    with psycopg.connect(database_url()) as connection:
        register_vector(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                f"""SELECT {columns} FROM geha_chunks c JOIN geha_documents d ON d.id=c.document_id
                    WHERE {' AND '.join(filters)}
                    ORDER BY c.embedding <=> %s::vector LIMIT %s""",
                (*params, vector, RETRIEVAL_CANDIDATES),
            )
            semantic = [dict(zip([d.name for d in cursor.description], row)) for row in cursor.fetchall()]
            cursor.execute(BM25_SQL, {
                "query": request.query,
                "category": request.category,
                "program": request.program,
                "k1": BM25_K1,
                "b": BM25_B,
                "candidate_limit": RETRIEVAL_CANDIDATES,
            })
            keyword = [dict(zip([d.name for d in cursor.description], row)) for row in cursor.fetchall()]
    return reciprocal_rank_fusion(semantic, keyword)[: request.limit]


app = FastAPI(title="GEHA Validated Document RAG", version="1.0.0")


@app.get("/api/health")
def health():
    return {"status": "ok", "corpus": "geha-validated-documents"}


@app.get("/", response_class=HTMLResponse)
def home():
    return (Path(__file__).parent / "index.html").read_text(encoding="utf-8")


@app.get("/api/documents", dependencies=[Depends(require_api_key)])
def documents():
    with psycopg.connect(database_url()) as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT id,title,relative_path,category,program,plan_year,last_updated,updated_at
               FROM geha_documents ORDER BY category,program,title"""
        )
        names = [column.name for column in cursor.description]
        return {"documents": [dict(zip(names, row)) for row in cursor.fetchall()]}


@app.post("/api/search", dependencies=[Depends(require_api_key)])
def search_api(request: SearchRequest):
    return {"results": search(request)}


@app.post("/api/chat", dependencies=[Depends(require_api_key)])
def chat(request: ChatRequest):
    rows = search(request)
    if not rows:
        return {"answer": "No validated GEHA document evidence matched the question.", "citations": []}
    prompt, citations = evidence_prompt(request.query, rows)
    response = bedrock.converse(
        modelId=GENERATION_MODEL,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"temperature": 0, "maxTokens": 1200},
    )
    answer = "".join(
        block.get("text", "") for block in response["output"]["message"]["content"]
    ).strip()
    return {"answer": answer, "citations": citations}


handler = Mangum(app)
