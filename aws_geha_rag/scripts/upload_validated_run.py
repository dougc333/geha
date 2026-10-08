#!/usr/bin/env python3
"""Publish one locally validated MCP PDF run to the GEHA ingestion bucket."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = ROOT / "scripts" / "build_validated_sidecar.py"
SPEC = importlib.util.spec_from_file_location("validated_sidecar_builder", BUILDER_PATH)
BUILDER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(BUILDER)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    pdf = args.pdf.expanduser().resolve()
    run_dir = args.run_dir.expanduser().resolve()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    documents = manifest.get("documents", [])
    document = next(
        (item for item in documents if Path(item["relative_path"]).name == pdf.name),
        None,
    )
    if document is None:
        raise SystemExit(f"{pdf.name} is not present in the curated manifest")

    relative_path = document["relative_path"]
    sidecar = BUILDER.build(pdf, run_dir, title=document["title"])
    if sidecar["source_sha256"] != document["sha256"]:
        raise SystemExit("validated source SHA-256 does not match the curated manifest")
    sidecar["source_pdf"] = relative_path
    sidecar["metadata"] = {
        "title": document["title"],
        "relative_path": relative_path,
        "category": document["category"],
        "program": document["program"],
        "plan_year": 2026,
        "last_updated": document.get("last_updated"),
        "tags": document.get("tags", []),
        "source_page": document.get("source_page"),
        "source_url": document.get("url"),
        "source_sha256": document["sha256"],
    }
    key = "validated/" + relative_path
    print(f"validated {sidecar['page_count']} pages for s3://{args.bucket}/{key}")
    if args.dry_run:
        return

    import boto3

    client = boto3.client("s3")
    client.put_object(
        Bucket=args.bucket,
        Key=key + ".validated.json",
        Body=(json.dumps(sidecar, indent=2, ensure_ascii=False) + "\n").encode(),
        ContentType="application/json",
        Metadata={
            "source-sha256": sidecar["source_sha256"],
            "validation-run": sidecar["validation"]["run_id"],
        },
    )
    client.upload_file(
        str(pdf),
        args.bucket,
        key,
        ExtraArgs={
            "ContentType": "application/pdf",
            "Metadata": {
                "source-sha256": sidecar["source_sha256"],
                "validation-run": sidecar["validation"]["run_id"],
            },
        },
    )
    print(f"published s3://{args.bucket}/{key}")


if __name__ == "__main__":
    main()
