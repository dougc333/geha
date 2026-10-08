#!/usr/bin/env python3
"""ECS entry point: validate one incoming PDF and publish it for RAG ingestion."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import boto3

from build_validated_sidecar import build
from pdf_worker import run


s3 = boto3.client("s3")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def upload_evidence(bucket: str, prefix: str, run_dir: Path) -> None:
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file() or path.name == "source.pdf":
            continue
        relative = path.relative_to(run_dir).as_posix()
        s3.upload_file(str(path), bucket, prefix + relative)


def main() -> None:
    bucket = os.environ["DOCUMENT_BUCKET"]
    key = os.environ["DOCUMENT_KEY"]
    if not key.startswith("incoming/") or not key.lower().endswith(".pdf"):
        raise ValueError("DOCUMENT_KEY must be an incoming/*.pdf object")
    relative = key.removeprefix("incoming/")
    model = os.getenv("VISION_MODEL_ID", "us.amazon.nova-pro-v1:0")
    max_passes = int(os.getenv("MAX_CORRECTION_PASSES", "7"))
    max_pages = int(os.getenv("MAX_PAGES", "200"))
    metadata_key = key + ".metadata.json"
    metadata = json.loads(
        s3.get_object(Bucket=bucket, Key=metadata_key)["Body"].read().decode("utf-8")
    )
    metadata["relative_path"] = relative

    with tempfile.TemporaryDirectory(prefix="geha_pdf_") as temporary:
        root = Path(temporary)
        source = root / "source.pdf"
        source.write_bytes(s3.get_object(Bucket=bucket, Key=key)["Body"].read())
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        run_id = f"run_{utc_stamp()}_{digest[:12]}_aws_processor"
        run_dir = root / run_id
        run_dir.mkdir()
        try:
            batch = run(
                source,
                run_dir,
                model=model,
                allow_external_model=True,
                max_passes=max_passes,
                max_pages=max_pages,
                source_name=relative,
            )
            sidecar = build(source, run_dir, title=metadata.get("title"))
            sidecar["source_pdf"] = relative
            sidecar["metadata"] = metadata
            sidecar_body = (json.dumps(sidecar, indent=2, ensure_ascii=False) + "\n").encode()
            validated_key = "validated/" + relative
            # Publish evidence and the sidecar before the PDF. Only the PDF triggers chunking.
            upload_evidence(bucket, f"runs/{run_id}/", run_dir)
            s3.put_object(
                Bucket=bucket,
                Key=validated_key + ".validated.json",
                Body=sidecar_body,
                ContentType="application/json",
                Metadata={"source-sha256": digest, "validation-run": run_id},
            )
            s3.copy_object(
                Bucket=bucket,
                Key=validated_key,
                CopySource={"Bucket": bucket, "Key": key},
                ContentType="application/pdf",
                MetadataDirective="REPLACE",
                Metadata={"source-sha256": digest, "validation-run": run_id},
            )
            print(json.dumps({
                "status": "validated",
                "run_id": run_id,
                "source": key,
                "validated_pdf": validated_key,
                "page_count": batch["page_count"],
            }))
        except Exception as exc:
            failure_prefix = f"quarantine/{relative}/{run_id}/"
            if run_dir.exists():
                upload_evidence(bucket, failure_prefix, run_dir)
            s3.put_object(
                Bucket=bucket,
                Key=failure_prefix + "error.json",
                Body=(json.dumps({
                    "status": "failed",
                    "run_id": run_id,
                    "source": key,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:2000],
                }, indent=2) + "\n").encode(),
                ContentType="application/json",
            )
            raise


if __name__ == "__main__":
    main()
