"""Synthetic claim duplicate scoring examples.

This is a demonstration, not an adjudication or automatic-denial rule.
It sends only the synthetic descriptions below to the embedding API.
"""

from __future__ import annotations

import csv
import itertools
import json
import math
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings


@dataclass
class Claim:
    claim_id: str
    claim_type: str
    patient_id: str
    provider_id: str
    service_date: str
    procedure_code: str
    amount: float
    lines: list[str]
    tooth: str | None = None
    surfaces: str | None = None


CASES: list[tuple[str, Claim, Claim]] = [
    (
        "1. Exact duplicate medical claim",
        Claim(
            "M1001", "medical", "P100", "NPI100", "2026-08-20",
            "99213", 125.00, ["Established patient office visit, level 3"],
        ),
        Claim(
            "M1002", "medical", "P100", "NPI100", "2026-08-20",
            "99213", 125.00, ["Established patient office visit, level 3"],
        ),
    ),
    (
        "2. Semantic duplicate dental claim",
        Claim(
            "D2001", "dental", "P200", "NPI200", "2026-08-21",
            "D2392", 210.00,
            ["Posterior resin filling, two surfaces, tooth 30, mesial occlusal"],
            tooth="30", surfaces="MO",
        ),
        Claim(
            "D2002", "dental", "P200", "NPI200", "2026-08-21",
            "D2392", 210.00,
            ["Two-surface composite restoration on #30, occlusal-mesial"],
            tooth="30", surfaces="OM",
        ),
    ),
    (
        "3. Corrected/resubmitted multi-line medical claim",
        Claim(
            "M3001", "medical", "P300", "NPI300", "2026-08-22",
            "99213", 240.00,
            ["Hypertension follow-up office visit", "Basic metabolic panel"],
        ),
        Claim(
            "M3002", "medical", "P300", "NPI300", "2026-08-22",
            "99213", 245.00,
            ["Basic blood chemistry panel", "Established-patient visit for high blood pressure follow-up"],
        ),
    ),
    (
        "4. Similar service but distinct dental claim",
        Claim(
            "D4001", "dental", "P400", "NPI400", "2026-08-23",
            "D2392", 210.00,
            ["Two-surface composite restoration on tooth 30, MO"],
            tooth="30", surfaces="MO",
        ),
        Claim(
            "D4002", "dental", "P400", "NPI400", "2026-08-23",
            "D2392", 210.00,
            ["Two-surface composite restoration on tooth 31, MO"],
            tooth="31", surfaces="MO",
        ),
    ),
    (
        "5. Clearly different medical claims",
        Claim(
            "M5001", "medical", "P500", "NPI500", "2026-08-24",
            "71046", 85.00, ["Chest radiograph, two views"],
        ),
        Claim(
            "M5002", "medical", "P501", "NPI501", "2026-08-28",
            "93000", 65.00, ["Routine twelve-lead electrocardiogram"],
        ),
    ),
]


class LocalConceptEmbeddings:
    """Transparent offline fallback for demonstrating the scoring pipeline.

    This is a canonicalized bag-of-concepts vectorizer, not a transformer model.
    It exists so the synthetic examples can be calculated without a valid API key.
    """

    REPLACEMENTS = {
        "posterior resin filling": "composite restoration",
        "resin filling": "composite restoration",
        "two surface": "two surface",
        "2 surface": "two surface",
        "occlusal mesial": "mesial occlusal",
        "om": "mesial occlusal",
        "mo": "mesial occlusal",
        "high blood pressure": "hypertension",
        "established patient visit": "office visit",
        "basic blood chemistry panel": "basic metabolic panel",
        "chest radiograph": "chest xray",
        "twelve lead electrocardiogram": "ecg",
    }
    STOPWORDS = {
        "a", "an", "and", "for", "of", "on", "the", "to", "with",
    }

    @classmethod
    def tokens(cls, text: str) -> list[str]:
        normalized = text.lower().replace("#", " tooth ")
        normalized = re.sub(r"[^a-z0-9]+", " ", normalized).strip()
        for source, target in cls.REPLACEMENTS.items():
            normalized = re.sub(
                rf"\b{re.escape(source)}\b", target, normalized
            )
        return [token for token in normalized.split() if token not in cls.STOPWORDS]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        tokenized = [self.tokens(text) for text in texts]
        vocabulary = sorted({token for row in tokenized for token in row})
        return [
            [float(tokens.count(term)) for term in vocabulary]
            for tokens in tokenized
        ]


def dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def norm(a: list[float]) -> float:
    return math.sqrt(dot(a, a))


def unit(a: list[float]) -> list[float]:
    magnitude = norm(a)
    return [x / magnitude for x in a]


def cosine(a: list[float], b: list[float]) -> float:
    return dot(a, b) / (norm(a) * norm(b))


def l1(a: list[float], b: list[float]) -> float:
    return sum(abs(x - y) for x, y in zip(a, b))


def l2(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def field_score(a: Claim, b: Claim) -> tuple[float, dict[str, bool]]:
    """Weighted agreement on fields relevant to the supplied claim type."""
    comparisons: dict[str, tuple[float, bool]] = {
        "patient": (0.22, a.patient_id == b.patient_id),
        "provider": (0.15, a.provider_id == b.provider_id),
        "service_date": (0.16, a.service_date == b.service_date),
        "procedure_code": (0.22, a.procedure_code == b.procedure_code),
        "amount": (0.10, abs(a.amount - b.amount) <= 5.00),
    }
    if a.claim_type == "dental" and b.claim_type == "dental":
        comparisons["tooth"] = (0.10, a.tooth == b.tooth)
        comparisons["surfaces"] = (
            0.05,
            set((a.surfaces or "").upper()) == set((b.surfaces or "").upper()),
        )
    else:
        # Reallocate dental-only weight to the medical procedure code.
        comparisons["procedure_code"] = (0.37, a.procedure_code == b.procedure_code)

    total_weight = sum(weight for weight, _ in comparisons.values())
    matched_weight = sum(weight for weight, matched in comparisons.values() if matched)
    flags = {name: matched for name, (_, matched) in comparisons.items()}
    return matched_weight / total_weight, flags


def transport_cost(
    a_vectors: list[list[float]], b_vectors: list[list[float]]
) -> tuple[float, float]:
    """Equal-weight optimal transport for the small, equal-sized examples.

    Ground cost is cosine distance (1 - cosine similarity). The best permutation
    gives the minimum average transport cost.
    """
    if len(a_vectors) != len(b_vectors):
        raise ValueError("Demo transport implementation expects equal line counts")

    best_cost = math.inf
    for permutation in itertools.permutations(range(len(b_vectors))):
        cost = sum(
            1.0 - cosine(a_vectors[i], b_vectors[j])
            for i, j in enumerate(permutation)
        ) / len(a_vectors)
        best_cost = min(best_cost, cost)

    similarity = max(0.0, min(1.0, 1.0 - best_cost))
    return best_cost, similarity


def classify(score: float, critical_mismatch: bool) -> str:
    if critical_mismatch:
        return "manual review / unlikely duplicate"
    if score >= 0.90:
        return "likely duplicate"
    if score >= 0.75:
        return "manual review"
    return "unlikely duplicate"


def calculate(embedding_model: object, embedding_source: str) -> list[dict]:
    results: list[dict] = []

    for case_name, claim_a, claim_b in CASES:
        aggregate_vectors = embedding_model.embed_documents(
            [" | ".join(claim_a.lines), " | ".join(claim_b.lines)]
        )
        aggregate_a, aggregate_b = map(unit, aggregate_vectors)

        all_line_vectors = embedding_model.embed_documents(claim_a.lines + claim_b.lines)
        split_at = len(claim_a.lines)
        line_vectors_a = [unit(v) for v in all_line_vectors[:split_at]]
        line_vectors_b = [unit(v) for v in all_line_vectors[split_at:]]

        cosine_score = cosine(aggregate_a, aggregate_b)
        l1_distance = l1(aggregate_a, aggregate_b)
        l2_distance = l2(aggregate_a, aggregate_b)
        wasserstein_cost, wasserstein_similarity = transport_cost(
            line_vectors_a, line_vectors_b
        )
        structured_score, matches = field_score(claim_a, claim_b)

        # Illustrative formula. Calibrate weights and thresholds with labeled data.
        raw_duplicate_score = 0.65 * wasserstein_similarity + 0.35 * structured_score
        critical_mismatch = (
            not matches["patient"]
            or not matches["service_date"]
            or ("tooth" in matches and not matches["tooth"])
        )
        duplicate_score = raw_duplicate_score
        if not matches["patient"]:
            duplicate_score = min(duplicate_score, 0.20)
        elif not matches["service_date"]:
            duplicate_score = min(duplicate_score, 0.49)
        elif "tooth" in matches and not matches["tooth"]:
            duplicate_score = min(duplicate_score, 0.49)

        results.append(
            {
                "case": case_name,
                "embedding_source": embedding_source,
                "claim_a": asdict(claim_a),
                "claim_b": asdict(claim_b),
                "cosine_similarity": round(cosine_score, 4),
                "l1_distance": round(l1_distance, 4),
                "l2_distance": round(l2_distance, 4),
                "wasserstein_cost": round(wasserstein_cost, 4),
                "wasserstein_similarity": round(wasserstein_similarity, 4),
                "structured_field_score": round(structured_score, 4),
                "field_matches": matches,
                "duplicate_score": round(100 * duplicate_score, 2),
                "classification": classify(duplicate_score, critical_mismatch),
            }
        )

    return results


def save(results: list[dict], prefix: str = "") -> None:
    output_dir = Path(__file__).resolve().parent
    (output_dir / f"{prefix}claim_duplicate_scores.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )

    with (output_dir / f"{prefix}claim_duplicate_scores.csv").open(
        "w", newline="", encoding="utf-8"
    ) as file:
        columns = [
            "case", "embedding_source", "cosine_similarity", "l1_distance", "l2_distance",
            "wasserstein_cost", "wasserstein_similarity",
            "structured_field_score", "duplicate_score", "classification",
        ]
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for result in results:
            writer.writerow({column: result[column] for column in columns})


if __name__ == "__main__":
    # The user's existing project keeps its API key in this location.
    load_dotenv(Path("/Users/dc/lca-engine/.env"), override=False)
    use_local = "--local" in sys.argv
    if use_local:
        selected_model = LocalConceptEmbeddings()
        source = "offline canonicalized bag-of-concepts (not OpenAI embeddings)"
        prefix = "local_"
    else:
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY was not found")
        selected_model = OpenAIEmbeddings(model="text-embedding-3-small")
        source = "OpenAI text-embedding-3-small"
        prefix = ""

    calculated = calculate(selected_model, source)
    save(calculated, prefix=prefix)

    for item in calculated:
        print(
            f"{item['case']}: {item['duplicate_score']:.2f}/100 "
            f"({item['classification']})"
        )
