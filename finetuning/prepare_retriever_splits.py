"""Create leakage-resistant GEHA retriever train/validation/test source splits."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any, Iterable

try:
    from .generate_ragas_qa import table_of_contents_reason
except ImportError:  # Permit direct execution from finetuning/.
    from generate_ragas_qa import table_of_contents_reason


ROOT = Path("/Users/dc/geha")
GUIDE_CHUNKS = ROOT / (
    "crawl_dir/runs/dental/fedvip--2026-geha-dental-benefits-guide/"
    "batch-20261009-token-safe/candidate/chunks.jsonl"
)
BROCHURE_CHUNKS = ROOT / (
    "crawl_dir/runs/dental/fedvip--2026-geha-dental-plan-brochure/"
    "batch-20261009-token-safe/candidate/chunks.jsonl"
)
BROCHURE_QA = BROCHURE_CHUNKS.parent / "ragas/qa_pairs.jsonl"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def substantive(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if table_of_contents_reason(row) is None]


def group_split(
    rows: list[dict[str, Any]], *, validation_fraction: float, seed: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split whole sections so no section label appears in both sets."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row.get("section") or "Unsectioned"), []).append(row)

    keys = list(groups)
    random.Random(seed).shuffle(keys)
    target = max(1, round(len(rows) * validation_fraction))
    validation_keys: set[str] = set()
    validation_size = 0
    for key in keys:
        if validation_size >= target:
            break
        validation_keys.add(key)
        validation_size += len(groups[key])

    training = [row for row in rows if str(row.get("section") or "Unsectioned") not in validation_keys]
    validation = [row for row in rows if str(row.get("section") or "Unsectioned") in validation_keys]
    if not training or not validation:
        raise ValueError("The section-grouped split produced an empty partition")
    return training, validation


def prepare(output_dir: Path, *, validation_fraction: float, seed: int) -> dict[str, int]:
    guide = substantive(read_jsonl(GUIDE_CHUNKS))
    brochure = substantive(read_jsonl(BROCHURE_CHUNKS))
    training, validation = group_split(
        guide, validation_fraction=validation_fraction, seed=seed
    )

    write_jsonl(output_dir / "train/chunks.jsonl", training)
    write_jsonl(output_dir / "validation/chunks.jsonl", validation)
    write_jsonl(output_dir / "test/chunks.jsonl", brochure)

    # This filtered file is useful immediately, but a fresh 50-question test set
    # should be generated from test/chunks.jsonl before the final experiment.
    allowed_test_ids = {row["chunk_id"] for row in brochure}
    existing_test = read_jsonl(BROCHURE_QA)
    filtered_test = [
        row
        for row in existing_test
        if row.get("source_chunk_ids")
        and set(row["source_chunk_ids"]).issubset(allowed_test_ids)
    ]
    write_jsonl(output_dir / "test/qa_pairs.filtered-existing.jsonl", filtered_test)

    train_sections = {str(row.get("section")) for row in training}
    validation_sections = {str(row.get("section")) for row in validation}
    assert train_sections.isdisjoint(validation_sections)
    assert {row["chunk_id"] for row in training}.isdisjoint(
        row["chunk_id"] for row in validation
    )

    return {
        "train_chunks": len(training),
        "validation_chunks": len(validation),
        "test_chunks": len(brochure),
        "existing_test_questions_after_toc_filter": len(filtered_test),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "data",
    )
    parser.add_argument("--validation-fraction", type=float, default=0.20)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if not 0 < args.validation_fraction < 1:
        raise SystemExit("--validation-fraction must be between zero and one")
    summary = prepare(
        args.output_dir,
        validation_fraction=args.validation_fraction,
        seed=args.seed,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
