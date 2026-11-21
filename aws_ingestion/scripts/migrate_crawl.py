"""Copy crawl_dir raw PDFs and run artifacts to the Terraform S3 bucket.

The source is an explicit one-time input; deployed code reads only S3 and its
own files. Existing S3 objects are preserved and no destination objects are deleted.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True,
                        help="The crawl_dir containing raw/ and runs/ to migrate")
    parser.add_argument("--bucket", required=True, help="Terraform artifact_bucket output")
    parser.add_argument("--profile", default="geha-terraform")
    parser.add_argument("--execute", action="store_true", help="Upload; otherwise dry-run")
    parser.add_argument("--raw-only", action="store_true")
    parser.add_argument("--runs-only", action="store_true")
    args = parser.parse_args()
    if args.raw_only and args.runs_only:
        parser.error("Select at most one of --raw-only and --runs-only")
    source = args.source.expanduser().resolve()
    groups = ["raw"] if args.raw_only else ["runs"] if args.runs_only else ["raw", "runs"]
    for group in groups:
        folder = source / group
        if not folder.is_dir():
            parser.error(f"Missing {folder}")
        files = [p for p in folder.rglob("*") if p.is_file()]
        size = sum(p.stat().st_size for p in files)
        destination = f"s3://{args.bucket}/{group}/"
        print(f"{folder} -> {destination}: {len(files)} files, {size:,} bytes")
        command = ["aws", "--profile", args.profile, "s3", "sync", str(folder), destination,
                   "--no-progress", "--only-show-errors"]
        if not args.execute:
            print("Dry-run. Execute with --execute when the selected AWS profile is authenticated.")
            continue
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
