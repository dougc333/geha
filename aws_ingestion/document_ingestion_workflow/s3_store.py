"""S3 backing for raw PDFs and immutable run artifacts in AWS mode."""
from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path
from typing import Any

import boto3


class S3ArtifactStore:
    def __init__(self, root: Path, bucket: str | None = None, client: Any = None) -> None:
        self.root = root.resolve()
        self.bucket = bucket or os.environ["INGESTION_BUCKET"]
        self.client = client or boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-west-2"))

    def key_for(self, path: Path) -> str:
        relative = path.resolve().relative_to(self.root)
        if not relative.parts or relative.parts[0] not in {"raw", "runs"}:
            raise ValueError("Artifact must be inside crawl_dir/raw or crawl_dir/runs")
        return relative.as_posix()

    def ensure_raw(self, document: str) -> Path:
        relative = Path(document)
        if relative.is_absolute() or ".." in relative.parts or relative.suffix.lower() != ".pdf":
            raise ValueError("Invalid raw document path")
        target = self.root / "raw" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, self.key_for(target), str(target))
        return target

    def upload_run(self, run_dir: Path) -> list[str]:
        run_dir = run_dir.resolve()
        if self.root / "runs" not in run_dir.parents:
            raise ValueError("Run directory must be under crawl_dir/runs")
        keys = []
        for path in sorted(run_dir.rglob("*"), key=lambda item: (item.name == "qc-report.json", item.as_posix())):
            if not path.is_file():
                continue
            key = self.key_for(path)
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            self.client.upload_file(str(path), self.bucket, key, ExtraArgs={"ContentType": content_type})
            keys.append(key)
        return keys

    def list_keys(self, prefix: str) -> list[str]:
        keys = []
        for page in self.client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=prefix):
            keys.extend(obj["Key"] for obj in page.get("Contents", []))
        return keys

    def get_json(self, key: str) -> dict[str, Any]:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return json.loads(response["Body"].read())


def configured_store(root: Path) -> S3ArtifactStore | None:
    return S3ArtifactStore(root) if os.getenv("INGESTION_BUCKET") else None
