#!/usr/bin/env python3
"""Upload the curated GEHA corpus to the cloud-validation incoming prefix."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import boto3


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    corpus = args.corpus_dir.expanduser().resolve()
    documents = json.loads(args.manifest.read_text(encoding="utf-8"))["documents"]
    by_name = {Path(document["relative_path"]).name: document for document in documents}
    pdfs = sorted(corpus.rglob("*.pdf"))
    if len(pdfs) != len(documents):
        raise SystemExit(f"corpus has {len(pdfs)} PDFs but manifest has {len(documents)} documents")

    plan = []
    for pdf in pdfs:
        relative = pdf.relative_to(corpus).as_posix()
        document = by_name.get(pdf.name)
        if document is None:
            raise SystemExit(f"no manifest entry for {pdf.name}")
        actual = digest(pdf)
        if actual != document.get("sha256"):
            raise SystemExit(f"SHA-256 mismatch for {relative}")
        metadata = {
            "title": document["title"],
            "relative_path": relative,
            "category": document["category"],
            "program": document["program"],
            "plan_year": 2026,
            "last_updated": document.get("last_updated"),
            "tags": document.get("tags", []),
            "source_page": document.get("source_page"),
            "source_url": document.get("url"),
            "source_sha256": actual,
        }
        plan.append((pdf, "incoming/" + relative, metadata))

    if args.dry_run:
        for pdf, key, _ in plan:
            print(f"would upload {pdf} -> s3://{args.bucket}/{key}")
        print(f"validated {len(plan)} curated PDFs")
        return

    s3 = boto3.client("s3")
    for pdf, key, metadata in plan:
        s3.put_object(
            Bucket=args.bucket,
            Key=key + ".metadata.json",
            Body=(json.dumps(metadata, indent=2) + "\n").encode(),
            ContentType="application/json",
        )
        s3.upload_file(
            str(pdf), args.bucket, key,
            ExtraArgs={"ContentType": "application/pdf", "Metadata": {"source-sha256": metadata["source_sha256"]}},
        )
        print(f"queued s3://{args.bucket}/{key}")


if __name__ == "__main__":
    main()
