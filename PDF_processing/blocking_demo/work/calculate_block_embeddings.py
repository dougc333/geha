"""Calculate reproducible embeddings for each synthetic claim-page block.

The GEHA project uses character n-gram hashing to tolerate OCR corruption.
This implementation keeps that 1,024-dimensional, L2-normalized approach but
uses BLAKE2b rather than Python's randomized ``hash()`` so vectors are stable
across processes and machines.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path


DIMENSIONS = 1024
NGRAMS = (2, 3, 4)
HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE.parent / "outputs"

BLOCKS = [
    {
        "id": "patient_information",
        "label": "Patient information",
        "bbox_normalized": [0.05, 0.14, 0.90, 0.17],
        "text": (
            "Member ID P300. Date of birth 04/18/1978. "
            "Patient Sample Patient. Service date 08/22/2026."
        ),
    },
    {
        "id": "billing_provider",
        "label": "Billing provider",
        "bbox_normalized": [0.05, 0.32, 0.90, 0.15],
        "text": (
            "Provider Example Family Medicine. NPI NPI300. "
            "Location Los Angeles California. Tax ID XX-XXX0300."
        ),
    },
    {
        "id": "service_lines",
        "label": "Service lines",
        "bbox_normalized": [0.05, 0.48, 0.90, 0.21],
        "text": (
            "08/22/2026 CPT 99213 established patient visit hypertension "
            "follow-up charge 165.00. 08/22/2026 CPT 80048 basic metabolic "
            "panel charge 80.00."
        ),
    },
    {
        "id": "claim_totals",
        "label": "Claim totals",
        "bbox_normalized": [0.52, 0.70, 0.43, 0.11],
        "text": "Total charge 245.00. Two service lines.",
    },
    {
        "id": "supporting_narrative",
        "label": "Supporting narrative",
        "bbox_normalized": [0.05, 0.82, 0.90, 0.13],
        "text": (
            "Corrected submission. Established-patient evaluation for high "
            "blood pressure follow-up; basic blood chemistry panel performed."
        ),
    },
]


def stable_bucket(value: str) -> int:
    digest = hashlib.blake2b(value.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % DIMENSIONS


def embed(text: str) -> list[float]:
    normalized = " ".join(text.lower().strip().split())
    vector = [0.0] * DIMENSIONS

    for size in NGRAMS:
        for start in range(max(0, len(normalized) - size + 1)):
            gram = normalized[start : start + size]
            vector[stable_bucket(f"n{size}:{gram}")] += 1.0

    for token in normalized.split():
        vector[stable_bucket(f"token:{token}")] += 1.0

    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude:
        vector = [value / magnitude for value in vector]
    return vector


def cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def vector_checksum(vector: list[float]) -> str:
    encoded = ",".join(f"{value:.8f}" for value in vector).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records = []

    for block in BLOCKS:
        vector = embed(block["text"])
        records.append(
            {
                **block,
                "dimensions": DIMENSIONS,
                "l2_norm": round(math.sqrt(sum(v * v for v in vector)), 8),
                "nonzero_dimensions": sum(value != 0.0 for value in vector),
                "sha256": vector_checksum(vector),
                "embedding": [round(value, 8) for value in vector],
            }
        )

    payload = {
        "model": "stable-character-ngram-hashing-v1",
        "dimensions": DIMENSIONS,
        "ngrams": list(NGRAMS),
        "normalization": "L2",
        "source": "synthetic claim blocking analysis demo",
        "blocks": records,
    }
    json_path = OUTPUT_DIR / "block_embeddings.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    matrix_path = OUTPUT_DIR / "block_embedding_cosine.csv"
    with matrix_path.open("w", newline="", encoding="utf-8") as handle:
        ids = [record["id"] for record in records]
        writer = csv.writer(handle)
        writer.writerow(["block"] + ids)
        for left in records:
            writer.writerow(
                [left["id"]]
                + [
                    f"{cosine(left['embedding'], right['embedding']):.6f}"
                    for right in records
                ]
            )

    summary_path = OUTPUT_DIR / "block_embedding_summary.csv"
    with summary_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "block_id",
                "label",
                "dimensions",
                "nonzero_dimensions",
                "l2_norm",
                "sha256",
                "bbox_normalized",
                "text",
            ],
        )
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "block_id": record["id"],
                    "label": record["label"],
                    "dimensions": record["dimensions"],
                    "nonzero_dimensions": record["nonzero_dimensions"],
                    "l2_norm": record["l2_norm"],
                    "sha256": record["sha256"],
                    "bbox_normalized": json.dumps(record["bbox_normalized"]),
                    "text": record["text"],
                }
            )

    print(json_path)
    print(matrix_path)
    print(summary_path)


if __name__ == "__main__":
    main()
