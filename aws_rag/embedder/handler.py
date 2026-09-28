"""Lambda: embed chunk JSONL files from S3 and load them into Postgres/pgvector.

Embeds with Amazon Titan Text Embeddings v2 on Bedrock (the query API must use the same model)
and replaces the document's rag_chunks rows in one transaction.
"""

import json
import os
import posixpath
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import boto3
import psycopg
from pgvector.psycopg import register_vector

s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime")
DATABASE_URL_PARAMETER = os.environ["DATABASE_URL_PARAMETER"]
MODEL = os.getenv("EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0")
DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1024"))  # schema.sql vector(1024)
WORKERS = int(os.getenv("EMBED_CONCURRENCY", "8"))  # Titan embeds one text per call

_database_url = None


def database_url():
    """DATABASE_URL from an SSM SecureString parameter, cached per container."""
    global _database_url
    if _database_url is None:
        _database_url = boto3.client("ssm").get_parameter(
            Name=DATABASE_URL_PARAMETER, WithDecryption=True
        )["Parameter"]["Value"]
    return _database_url


def embed(text):
    response = bedrock.invoke_model(
        modelId=MODEL,
        body=json.dumps({"inputText": text, "dimensions": DIMENSIONS, "normalize": True}),
    )
    return json.loads(response["body"].read())["embedding"]


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
    title = chunks[0].get("title") or posixpath.splitext(posixpath.basename(source))[0]

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        embeddings = list(pool.map(embed, [c["content"] for c in chunks]))  # keeps order

    # One transaction: readers never see a document with half its chunks.
    with psycopg.connect(database_url()) as connection:
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
