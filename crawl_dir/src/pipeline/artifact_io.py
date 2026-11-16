"""Filesystem primitives and canonical run paths."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from geha_processing.io import atomic_json as _atomic_json
from geha_processing.io import sha256_file as _sha256_file


atomic_json = _atomic_json
sha256_file = _sha256_file


FAMILIES = {
    "coverage-policies", "medical", "dental", "forms", "research",
    # Retrieval clusters from advanced_rag/evals/cluster_manifest.json
    # ("research" above doubles as the research cluster).
    "policy", "clinical_guidance", "population_health", "benefits_research", "forms_directory",
}


def run_id(now: datetime | None = None) -> str:
    value = now or datetime.now(timezone.utc)
    return value.strftime("%Y-%m-%dT%H%M%SZ")


def resolve_raw_document(root: Path, family: str, document: str) -> Path:
    if family not in FAMILIES:
        raise ValueError(f"Unknown family: {family}")
    base = (root / "raw" / family).resolve()
    candidate = (base / document).resolve()
    if candidate != base and base not in candidate.parents:
        raise ValueError("Document path escapes its raw family directory")
    if not candidate.is_file() or candidate.suffix.casefold() != ".pdf":
        raise FileNotFoundError(candidate)
    return candidate
