"""Run one alt-2 extraction in Fargate and persist its artifacts to S3."""

from __future__ import annotations

import json
import logging
import os
import re
import hashlib
import mimetypes
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from crawl_dir.src.ingestion_mcp import ROOT
from document_ingestion_workflow.backend import IngestionDemoAgent
from document_ingestion_workflow.run_store import DurableRun, RunStore


LOGGER = logging.getLogger(__name__)
DOCUMENT = "forms/bill_of_lading_alt_2.pdf"
DOCUMENT_ID = "bill_of_lading_alt_2"
SAFE_RUN_ID = re.compile(r"\A[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}\Z")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _put_status(s3, bucket: str, run_id: str, status: str, **details) -> None:
    body = {"run_id": run_id, "status": status, "updated_at": _now(), **details}
    s3.put_object(
        Bucket=bucket,
        Key=f"runs/{run_id}/status.json",
        Body=(json.dumps(body, indent=2) + "\n").encode(),
        ContentType="application/json",
    )


def _upload_artifacts(s3, bucket: str, run_id: str, run_dir: Path) -> int:
    uploaded = 0
    if run_dir.is_dir():
        for path in sorted(run_dir.rglob("*")):
            if path.is_file():
                mime, _ = mimetypes.guess_type(path.name)
                args = {"ContentType": mime} if mime else None
                s3.upload_file(
                    str(path), bucket,
                    f"runs/{run_id}/artifacts/{path.relative_to(run_dir).as_posix()}",
                    ExtraArgs=args,
                )
                uploaded += 1
    return uploaded


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    bucket = os.environ["AWS_FORMS_BUCKET"]
    run_id = os.environ["AWS_FORMS_RUN_ID"]
    input_key = os.environ["AWS_FORMS_INPUT_KEY"]
    if not SAFE_RUN_ID.fullmatch(run_id):
        raise ValueError("AWS_FORMS_RUN_ID contains unsafe characters")
    if input_key != f"incoming/{run_id}/source.pdf":
        raise ValueError("Input must be the source PDF under this run ID")
    s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-west-2"))

    # A repeated RunTask request for the same run must not perform paid OCR twice.
    try:
        s3.put_object(Bucket=bucket, Key=f"runs/{run_id}/claim", Body=b"", IfNoneMatch="*")
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in {"PreconditionFailed", "ConditionalRequestConflict"}:
            LOGGER.info("Run %s was already claimed; skipping duplicate task", run_id)
            return
        raise

    run_dir = ROOT / "runs" / "forms" / DOCUMENT_ID / run_id
    try:
        _put_status(s3, bucket, run_id, "starting", input_key=input_key)
        source = ROOT / "raw" / DOCUMENT
        source.parent.mkdir(parents=True, exist_ok=True)
        s3.download_file(bucket, input_key, str(source))
        if source.stat().st_size == 0:
            raise ValueError("Uploaded PDF is empty")
        with source.open("rb") as stream:
            source_hash = hashlib.file_digest(stream, "sha256").hexdigest()
        if source_hash != os.environ["AWS_FORMS_SOURCE_SHA256"]:
            raise ValueError("PDF does not match the reviewed alt-2 template fixture")

        store = RunStore()
        store.create(run_id, DOCUMENT)
        _put_status(s3, bucket, run_id, "processing", input_key=input_key)
        IngestionDemoAgent(DurableRun(store, run_id), DOCUMENT, 0, "anthropic").execute()
        state = store.get(run_id)
        events, _ = store.snapshot(run_id, 0)
        events_path = run_dir / "events.json"
        run_dir.mkdir(parents=True, exist_ok=True)
        events_path.write_text(json.dumps(events, indent=2) + "\n")
        count = _upload_artifacts(s3, bucket, run_id, run_dir)
        qc_path = run_dir / "qc-report.json"
        qc = json.loads(qc_path.read_text()) if qc_path.exists() else None
        succeeded = bool(state and state["status"] == "succeeded" and qc)
        _put_status(
            s3, bucket, run_id, "needs_visual_review" if succeeded else "failed",
            input_key=input_key, artifact_count=count, qc=qc,
            error=None if succeeded else (state or {}).get("error"),
        )
        if not succeeded:
            raise RuntimeError(f"Forms extraction failed for {run_id}")
        LOGGER.info("Completed run %s with %d artifacts", run_id, count)
    except Exception as exc:
        LOGGER.exception("Run %s failed", run_id)
        _upload_artifacts(s3, bucket, run_id, run_dir)
        _put_status(s3, bucket, run_id, "failed", input_key=input_key, error=str(exc))
        raise


if __name__ == "__main__":
    main()
