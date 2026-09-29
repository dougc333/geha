"""Lambda: chunk PDFs uploaded to S3 and write one JSONL file per document."""

import hashlib
import json
import os
import urllib.parse

import boto3
import pymupdf

from rag_core import chunk_text

s3 = boto3.client("s3")
OUT_BUCKET = os.environ["OUT_BUCKET"]
OUT_PREFIX = os.getenv("OUT_PREFIX", "chunks/")
SIZE = int(os.getenv("CHUNK_WORDS", "350"))
OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))


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


def sidecar(bucket, key):
    """Paper metadata stored next to the PDF as <name>.json (e.g. from arXiv), if any."""
    try:
        body = s3.get_object(Bucket=bucket, Key=key.rsplit(".", 1)[0] + ".json")["Body"].read()
    except s3.exceptions.NoSuchKey:
        return {}
    return json.loads(body)


def process(bucket, key):
    obj = s3.get_object(Bucket=bucket, Key=key)
    data = obj["Body"].read()
    doc_id = hashlib.sha256(data).hexdigest()
    # Optional display title (set by the chatbot's arXiv loader, URL-quoted
    # because S3 metadata must be ASCII); the embedder falls back to the file name.
    title = urllib.parse.unquote(obj.get("Metadata", {}).get("title", ""))
    metadata = sidecar(bucket, key)
    title = metadata.get("title") or title
    out_key = f"{OUT_PREFIX}{doc_id}.jsonl"

    lines, index = [], 0
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        for page_no, page in enumerate(pdf, start=1):
            text = " ".join(page.get_text("text").split())
            for chunk in chunk_text(text, size=SIZE, overlap=OVERLAP):
                lines.append(json.dumps({
                    "document_id": doc_id,
                    "source": f"s3://{bucket}/{key}",
                    **({"title": title} if title else {}),
                    "chunk_index": index,
                    "page_number": page_no,
                    "content": chunk,
                }))
                index += 1

    if not lines:
        raise ValueError(f"no extractable text in {key} (scanned? use Textract)")
    if metadata:  # once per document, on the first chunk, for the embedder
        first = json.loads(lines[0])
        first["metadata"] = metadata
        lines[0] = json.dumps(first)
    s3.put_object(
        Bucket=OUT_BUCKET,
        Key=out_key,
        Body="\n".join(lines).encode(),
        ContentType="application/x-ndjson",
    )
    print(f"s3://{bucket}/{key} -> s3://{OUT_BUCKET}/{out_key} ({index} chunks)")
