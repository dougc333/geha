#!/usr/bin/env python3
"""Check that the bill-of-lading row review still refers to the current PDF and gold rows.

This checks provenance integrity. It does not repeat the human visual review.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows_digest(rows: list[dict]) -> str:
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> None:
    review = json.loads((HERE / "bill_of_lading_gold_review.json").read_text(encoding="utf-8"))
    source = HERE / "../blocking_demo/bill_of_lading_alt_1.pdf"
    gold = HERE / "bill_of_lading_gold_fields.json"
    rows = json.loads(gold.read_text(encoding="utf-8"))["containers"]
    checks = {
        "source_pdf_sha256": digest(source) == review["source_pdf"]["sha256"],
        "answer_key_sha256": digest(gold) == review["answer_key"]["sha256"],
        "approved_rows_sha256": rows_digest(rows) == review["approved_rows_sha256"],
        "row_count": len(rows) == review["row_count"] == 2,
    }
    print(json.dumps({"status": "passed" if all(checks.values()) else "failed", "checks": checks}, indent=2))
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
