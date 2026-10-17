"""Build the small runtime benefit database from canonical extraction output."""

from __future__ import annotations

import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from crawl_dir.src.consumer_paths import page_markdown  # noqa: E402
from structured_benefits import build_benefit_database  # noqa: E402


SOURCE_DOCUMENT = "fedvip/2026-geha-dental-benefits-guide.pdf"
DATABASE = Path(__file__).resolve().parents[1] / "data" / "dental_benefits.sqlite"


def main() -> None:
    source = page_markdown("dental", SOURCE_DOCUMENT, 5, allow_candidate=True)
    output = build_benefit_database(DATABASE, source)
    print(f"Built {output} from {source}")


if __name__ == "__main__":
    main()
