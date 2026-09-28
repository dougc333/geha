"""Lambda: embed chunk JSONL files from S3 and load them into Postgres/pgvector.

Writes the same rag_documents / rag_chunks rows as vercel_app/scripts/ingest.py,
so documents chunked on AWS are searchable from the Vercel app.
"""

import json
import os
import posixpath
import urllib.parse

import boto3
import psycopg
from openai import OpenAI
from pgvector.psycopg import register_vector

s3 = boto3.client("s3")
SECRET_ID = os.environ["SECRET_ID"]
MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
BATCH = int(os.getenv("EMBED_BATCH_SIZE", "100"))

_secret = None


def secret():
    """DATABASE_URL and OPENAI_API_KEY from Secrets Manager, cached per container."""
    global _secret
    if _secret is None:
        value = boto3.client("secretsmanager").get_secret_value(SecretId=SECRET_ID)
        _secret = json.loads(value["SecretString"])
    return _secret


def handler(event, context):
    failures = []
    for record in event["Records"]:  # SQS records
        try:
            # S3 sends an s3:TestEvent with no "Records" when the notification is created.
            for s3rec in json.loads(record["body"]).get("Records", []):
                process(
                    s3rec["s3"]["bucket"]["name"],
                    urllib.parse.unquote_plus(s3rec["s3"]["object"]["key"]),
                )
        except Exception as exc:
            print(f"failed {record['messageId']}: {exc}")
            failures.append({"itemIdentifier": record["messageId"]})
    return {"batchItemFailures": failures}  # retry only the failed messages


def process(bucket, key):
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode()
    chunks = [json.loads(line) for line in body.splitlines() if line.strip()]
    if not chunks:
        raise ValueError(f"empty chunk file {key}")
    chunks.sort(key=lambda c: c["chunk_index"])

    document_id = chunks[0]["document_id"]
    source = chunks[0]["source"]
    title = posixpath.splitext(posixpath.basename(source))[0]

    client = OpenAI(api_key=secret()["OPENAI_API_KEY"])
    embeddings = []
    for start in range(0, len(chunks), BATCH):
        batch = [c["content"] for c in chunks[start : start + BATCH]]
        response = client.embeddings.create(model=MODEL, input=batch)
        embeddings.extend(item.embedding for item in response.data)

    # One transaction: readers never see a document with half its chunks.
    with psycopg.connect(secret()["DATABASE_URL"]) as connection:
        register_vector(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO rag_documents (id, title, source)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, source = EXCLUDED.source""",
                (document_id, title, source),
            )
            cursor.execute("DELETE FROM rag_chunks WHERE document_id = %s", (document_id,))
            cursor.executemany(
                """INSERT INTO rag_chunks
                   (document_id, chunk_index, page_number, content, embedding)
                   VALUES (%s, %s, %s, %s, %s)""",
                [
                    (document_id, c["chunk_index"], c["page_number"], c["content"], e)
                    for c, e in zip(chunks, embeddings)
                ],
            )
    print(f"s3://{bucket}/{key} -> rag_chunks ({len(chunks)} chunks, document {document_id[:12]})")
