"""Convert a validated GEHA PDF sidecar into page-aware retrieval chunks."""

from __future__ import annotations

import hashlib
import json
import os
import urllib.parse

import boto3

from rag_core import chunk_validated_pages, validated_pages


s3 = boto3.client("s3")
OUT_BUCKET = os.environ["OUT_BUCKET"]
OUT_PREFIX = os.getenv("OUT_PREFIX", "chunks/")
SIZE = int(os.getenv("CHUNK_WORDS", "350"))
OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
SIDECAR_SUFFIX = ".validated.json"


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
    if not key.lower().endswith(".pdf"):
        raise ValueError(f"expected a PDF key, received {key!r}")
    pdf = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    document_id = hashlib.sha256(pdf).hexdigest()
    sidecar_key = key + SIDECAR_SUFFIX
    try:
        sidecar_body = s3.get_object(Bucket=bucket, Key=sidecar_key)["Body"].read()
    except Exception as exc:
        raise ValueError(f"missing required validated sidecar: {sidecar_key}") from exc

    pages, sidecar = validated_pages(sidecar_body, source_sha256=document_id)
    chunks = chunk_validated_pages(pages, size=SIZE, overlap=OVERLAP)
    metadata = sidecar.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise ValueError("validated sidecar metadata must be an object")
    required = ("title", "relative_path", "category", "program")
    missing = [field for field in required if not metadata.get(field)]
    if missing:
        raise ValueError("validated sidecar metadata missing: " + ", ".join(missing))

    source = f"s3://{bucket}/{key}"
    lines = []
    for chunk in chunks:
        row = {"document_id": document_id, "source": source, **chunk}
        if chunk["chunk_index"] == 0:
            row["metadata"] = metadata
            row["validation"] = sidecar.get("validation") or {}
        lines.append(json.dumps(row, ensure_ascii=False))

    out_key = f"{OUT_PREFIX}{document_id}.jsonl"
    s3.put_object(
        Bucket=OUT_BUCKET,
        Key=out_key,
        Body=("\n".join(lines) + "\n").encode("utf-8"),
        ContentType="application/x-ndjson",
        Metadata={"source-sha256": document_id, "ingestion": "validated-sidecar"},
    )
    print(
        f"{source} + {sidecar_key} -> s3://{OUT_BUCKET}/{out_key} "
        f"({len(chunks)} validated chunks)"
    )
