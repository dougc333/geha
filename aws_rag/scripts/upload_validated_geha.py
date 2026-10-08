#!/usr/bin/env python3
"""Upload GEHA PDFs and validated sidecars to the AWS RAG raw bucket."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import boto3


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", type=Path, required=True)
    parser.add_argument("--validated-dir", type=Path, required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--prefix", default="geha/")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    corpus = args.corpus_dir.expanduser().resolve()
    validated = args.validated_dir.expanduser().resolve()
    pdfs = sorted(corpus.rglob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"no PDFs found under {corpus}")

    plan = []
    for pdf in pdfs:
        relative = pdf.relative_to(corpus)
        sidecar = validated / relative.parent / (relative.name + ".validated.json")
        if not sidecar.is_file():
            raise SystemExit(f"missing validated sidecar: {sidecar}")
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
        if payload.get("validation_status") != "validated" or payload.get("source_sha256") != sha256(pdf):
            raise SystemExit(f"invalid or mismatched validated sidecar: {sidecar}")
        key = args.prefix.rstrip("/") + "/" + relative.as_posix()
        plan.append((pdf, sidecar, key))

    if args.dry_run:
        for pdf, sidecar, key in plan:
            print(f"would upload {sidecar} -> s3://{args.bucket}/{key}.validated.json")
            print(f"would upload {pdf} -> s3://{args.bucket}/{key}")
        print(f"validated {len(plan)} PDF/sidecar pairs")
        return

    s3 = boto3.client("s3")
    for pdf, sidecar, key in plan:
        # Upload the sidecar first. The subsequent PDF event can then consume it.
        s3.upload_file(
            str(sidecar), args.bucket, key + ".validated.json",
            ExtraArgs={"ContentType": "application/json"},
        )
        s3.upload_file(
            str(pdf), args.bucket, key,
            ExtraArgs={"ContentType": "application/pdf"},
        )
        print(f"uploaded s3://{args.bucket}/{key}")


if __name__ == "__main__":
    main()
