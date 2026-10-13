"""CLI for the canonical crawl processing pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from .pipeline.artifact_io import FAMILIES
from .pipeline.runner import process_document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("family", choices=sorted(FAMILIES))
    parser.add_argument("document", help="PDF path relative to raw/<family>")
    parser.add_argument("--document-version", required=True)
    parser.add_argument("--plan-year", type=int)
    parser.add_argument("--run-id")
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    args = parser.parse_args()
    output = process_document(
        root=args.root,
        family=args.family,
        document=args.document,
        document_version=args.document_version,
        plan_year=args.plan_year,
        requested_run_id=args.run_id,
    )
    print(output)


if __name__ == "__main__":
    main()
