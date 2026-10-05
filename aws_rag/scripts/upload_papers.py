#!/usr/bin/env python3
"""Upload downloaded papers (<id>.pdf + <id>.json sidecar) into the pipeline.

    python scripts/upload_papers.py ../agentic_search/data/arxiv_top300 --top 100 [--dry-run]

Takes papers in manifest.json rank order (or every PDF with a sidecar if there
is no manifest), skips arXiv IDs already in rag_documents, and uploads each
sidecar and then its PDF to s3://<raw bucket>/papers/. The sidecar goes first
because the PDF upload triggers the chunker, which reads it. The chunker and
embedder then index each paper in about 10 seconds; with the embedder capped
at 2 concurrent runs, 100 papers take several minutes.

DATABASE_URL comes from the environment or the /rag-demo/database-url SSM
parameter; the bucket from the sam-app stack's RawBucketName output.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import boto3
import psycopg


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--top", type=int, default=None, help="only the first N new papers by rank")
    parser.add_argument("--prefix", default="papers/")
    parser.add_argument("--stack", default="sam-app")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    manifest = args.folder / "manifest.json"
    if manifest.exists():
        ids = [p["arxiv_id"] for p in sorted(json.loads(manifest.read_text()), key=lambda p: p["rank"])]
    else:
        ids = sorted(p.stem for p in args.folder.glob("*.pdf") if p.with_suffix(".json").exists())
    ids = [i for i in ids if (args.folder / f"{i}.pdf").exists() and (args.folder / f"{i}.json").exists()]

    region = args.region
    url = os.environ.get("DATABASE_URL") or boto3.client("ssm", region_name=region).get_parameter(
        Name="/rag-demo/database-url", WithDecryption=True)["Parameter"]["Value"]
    with psycopg.connect(url) as connection:
        indexed = {row[0].split("v")[0] for row in connection.execute(
            "SELECT arxiv_id FROM rag_documents WHERE arxiv_id IS NOT NULL")}
    bucket = boto3.client("cloudformation", region_name=region).describe_stacks(StackName=args.stack)[
        "Stacks"][0]["Outputs"]
    bucket = next(o["OutputValue"] for o in bucket if o["OutputKey"] == "RawBucketName")
    s3 = boto3.client("s3", region_name=region)

    skipped = [i for i in ids if i.split("v")[0] in indexed]
    for arxiv_id in skipped:
        print(f"skip {arxiv_id} (already indexed)")
    ids = [i for i in ids if i not in skipped]
    ids = ids[: args.top] if args.top else ids  # --top counts new papers only

    uploaded = 0 if not args.dry_run else len(ids)
    for arxiv_id in ids:
        title = json.loads((args.folder / f"{arxiv_id}.json").read_text())["title"]
        print(f"{'would upload' if args.dry_run else 'upload'} {arxiv_id}  {title[:70]}", flush=True)
        if args.dry_run:
            continue
        s3.upload_file(str(args.folder / f"{arxiv_id}.json"), bucket, f"{args.prefix}{arxiv_id}.json",
                       ExtraArgs={"ContentType": "application/json"})
        s3.upload_file(str(args.folder / f"{arxiv_id}.pdf"), bucket, f"{args.prefix}{arxiv_id}.pdf",
                       ExtraArgs={"ContentType": "application/pdf"})
        uploaded += 1
    print(f"{uploaded} papers {'to upload' if args.dry_run else 'uploaded'} to s3://{bucket}/{args.prefix}")


if __name__ == "__main__":
    main()
