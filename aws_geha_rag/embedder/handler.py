"""Embed validated GEHA chunks and atomically replace a document in pgvector."""

from __future__ import annotations

import json
import os
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import boto3
import psycopg
from pgvector.psycopg import register_vector
from psycopg.types.json import Jsonb


s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime")
DATABASE_URL_PARAMETER = os.environ["DATABASE_URL_PARAMETER"]
MODEL = os.getenv("EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0")
DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1024"))
WORKERS = int(os.getenv("EMBED_CONCURRENCY", "8"))
MAX_EMBED_CHARS = int(os.getenv("MAX_EMBED_CHARS", "10000"))
_database_url = None


def database_url():
    global _database_url
    if _database_url is None:
        _database_url = boto3.client("ssm").get_parameter(
            Name=DATABASE_URL_PARAMETER, WithDecryption=True
        )["Parameter"]["Value"]
    return _database_url


def embed(text: str):
    for attempt in range(4):
        try:
            response = bedrock.invoke_model(
                modelId=MODEL,
                body=json.dumps({
                    "inputText": text[:MAX_EMBED_CHARS],
                    "dimensions": DIMENSIONS,
                    "normalize": True,
                }),
            )
            return json.loads(response["body"].read())["embedding"]
        except bedrock.exceptions.ModelErrorException:
            if attempt == 3:
                raise
            time.sleep(0.5 * 2**attempt)


def handler(event, context):
    failures = []
    for record in event.get("Records", []):
        try:
            for s3_record in json.loads(record["body"]).get("Records", []):
                process(
                    s3_record["s3"]["bucket"]["name"],
                    urllib.parse.unquote_plus(s3_record["s3"]["object"]["key"]),
                )
        except Exception as exc:
            print(f"failed {record.get('messageId', 'unknown')}: {exc}")
            failures.append({"itemIdentifier": record.get("messageId", "unknown")})
    return {"batchItemFailures": failures}


def process(bucket: str, key: str) -> None:
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
    chunks = [json.loads(line) for line in body.splitlines() if line.strip()]
    if not chunks:
        raise ValueError(f"empty chunk file {key}")
    chunks.sort(key=lambda row: row["chunk_index"])
    document_id = chunks[0]["document_id"]
    if any(row.get("document_id") != document_id for row in chunks):
        raise ValueError("chunk file mixes document IDs")
    metadata = next((row.get("metadata") for row in chunks if row.get("metadata")), {})
    validation = next((row.get("validation") for row in chunks if "validation" in row), {})
    required = ("title", "relative_path", "category", "program")
    if not isinstance(metadata, dict) or any(not metadata.get(field) for field in required):
        raise ValueError("chunk file is missing required GEHA metadata")

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        embeddings = list(pool.map(embed, [row["content"] for row in chunks]))

    with psycopg.connect(database_url()) as connection:
        register_vector(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO geha_documents
                   (id, title, source, relative_path, category, program, plan_year,
                    last_updated, tags, validation)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET
                     title=EXCLUDED.title, source=EXCLUDED.source,
                     relative_path=EXCLUDED.relative_path, category=EXCLUDED.category,
                     program=EXCLUDED.program, plan_year=EXCLUDED.plan_year,
                     last_updated=EXCLUDED.last_updated, tags=EXCLUDED.tags,
                     validation=EXCLUDED.validation, updated_at=now()""",
                (
                    document_id, metadata["title"], chunks[0]["source"],
                    metadata["relative_path"], metadata["category"], metadata["program"],
                    metadata.get("plan_year"), metadata.get("last_updated"),
                    metadata.get("tags", []), Jsonb(validation),
                ),
            )
            cursor.execute("DELETE FROM geha_chunks WHERE document_id=%s", (document_id,))
            cursor.executemany(
                """INSERT INTO geha_chunks
                   (document_id, chunk_index, page_number, content, embedding)
                   VALUES (%s, %s, %s, %s, %s)""",
                [
                    (document_id, row["chunk_index"], row["page_number"], row["content"], vector)
                    for row, vector in zip(chunks, embeddings)
                ],
            )
    print(f"s3://{bucket}/{key} -> geha_chunks ({len(chunks)} chunks, {document_id[:12]})")
