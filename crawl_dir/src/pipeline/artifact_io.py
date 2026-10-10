"""Filesystem primitives and canonical run paths."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FAMILIES = {"coverage-policies", "medical", "dental", "forms", "research"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


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
