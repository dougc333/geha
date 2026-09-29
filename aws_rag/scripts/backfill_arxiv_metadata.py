#!/usr/bin/env python3
"""Fill arXiv metadata (title, authors, dates, abstract, categories, ...) for
papers that are already indexed.

For every rag_documents row whose source or title contains an arXiv ID, this
fetches the paper's metadata from the arXiv API, updates the row, and writes
the sidecar JSON next to the source PDF in S3 (e.g. papers/2306.02707.json) so
that re-chunking the PDF later keeps the metadata.

    python scripts/backfill_arxiv_metadata.py [--dry-run] [--force]

DATABASE_URL comes from the environment, or else from the SSM parameter
/rag-demo/database-url. Needs boto3 and psycopg.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import boto3
import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "query"))
import arxiv_meta  # noqa: E402

COLUMNS = ("arxiv_id", "authors", "published", "updated", "abstract",
           "primary_category", "categories", "comment", "journal_ref", "doi")


def database_url(region: str, parameter: str) -> str:
    return os.environ.get("DATABASE_URL") or boto3.client("ssm", region_name=region).get_parameter(
        Name=parameter, WithDecryption=True
    )["Parameter"]["Value"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="print what would change")
    parser.add_argument("--force", action="store_true", help="refetch rows that already have metadata")
    parser.add_argument("--region", default="us-west-2")
    parser.add_argument("--parameter", default="/rag-demo/database-url")
    args = parser.parse_args()
    s3 = boto3.client("s3", region_name=args.region)

    with psycopg.connect(database_url(args.region, args.parameter)) as connection:
        rows = connection.execute(
            "SELECT id, title, source, arxiv_id FROM rag_documents ORDER BY title"
        ).fetchall()
        for doc_id, title, source, stored_id in rows:
            arxiv_id = arxiv_meta.find_arxiv_id(source) or arxiv_meta.find_arxiv_id(title)
            if not arxiv_id:
                print(f"skip (no arXiv ID): {title}")
                continue
            if stored_id and not args.force:
                print(f"skip (has metadata): {title}")
                continue
            meta = arxiv_meta.metadata(arxiv_id)
            time.sleep(3)  # arXiv asks API clients to space out requests
            if meta is None:
                print(f"skip (arXiv has no {arxiv_id}): {title}")
                continue
            print(f"{title!r} -> {meta['title']!r}: {len(meta['authors'])} authors, "
                  f"{meta['published']}, {meta['primary_category']}")
            if args.dry_run:
                continue
            connection.execute(
                f"UPDATE rag_documents SET title = %(title)s, "
                f"{', '.join(f'{c} = %({c})s' for c in COLUMNS)} WHERE id = %(id)s",
                {"id": doc_id, **meta},
            )
            location = urlparse(source)
            if location.scheme == "s3":
                key = location.path.lstrip("/").rsplit(".", 1)[0] + ".json"
                s3.put_object(Bucket=location.netloc, Key=key, Body=json.dumps(meta).encode(),
                              ContentType="application/json")
                print(f"  sidecar s3://{location.netloc}/{key}")
            else:
                print(f"  no S3 source ({source}); database updated only")
        if not args.dry_run:
            connection.commit()


if __name__ == "__main__":
    main()
