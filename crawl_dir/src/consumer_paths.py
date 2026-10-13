"""Stable paths for projects that consume the canonical crawl corpus.

Consumers should use raw PDFs for extraction and promoted ``reviewed``
artifacts for production retrieval. Demos may explicitly opt into the newest
structurally valid candidate while visual review is still pending.
"""

from __future__ import annotations

import json
from pathlib import Path


CRAWL_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = CRAWL_ROOT / "raw"
RUNS_ROOT = CRAWL_ROOT / "runs"
REVIEWED_ROOT = CRAWL_ROOT / "reviewed"


def raw_dir(family: str, *parts: str) -> Path:
    return RAW_ROOT.joinpath(family, *parts)


def raw_document(family: str, document: str | Path) -> Path:
    path = (RAW_ROOT / family / Path(document)).resolve()
    family_root = (RAW_ROOT / family).resolve()
    if path != family_root and family_root not in path.parents:
        raise ValueError("document must remain inside its raw family directory")
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def document_id(document: str | Path) -> str:
    return "--".join(Path(document).with_suffix("").parts)


def _newest_structurally_valid_run(family: str, identifier: str) -> Path | None:
    candidates: list[tuple[str, Path]] = []
    for run in (RUNS_ROOT / family / identifier).glob("*"):
        try:
            manifest = json.loads((run / "run-manifest.json").read_text())
            qc = json.loads((run / "qc-report.json").read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if qc.get("status") not in {"needs_visual_review", "passed"}:
            continue
        if qc.get("structural_errors"):
            continue
        if not (run / "candidate" / "chunks.jsonl").is_file():
            continue
        candidates.append((str(manifest.get("created_at") or ""), run))
    return max(candidates, default=("", None), key=lambda item: item[0])[1]


def document_artifacts(
    family: str,
    document: str | Path,
    *,
    version: str | None = None,
    allow_candidate: bool = False,
) -> Path:
    """Return a promoted document, or an explicitly allowed candidate run."""
    identifier = document_id(document)
    reviewed_document = REVIEWED_ROOT / family / identifier
    if version:
        promoted = reviewed_document / version
        if (promoted / "manifest.json").is_file():
            return promoted
    elif reviewed_document.is_dir():
        versions = [path for path in reviewed_document.iterdir() if (path / "manifest.json").is_file()]
        if versions:
            return max(versions, key=lambda path: path.name)
    if allow_candidate:
        candidate = _newest_structurally_valid_run(family, identifier)
        if candidate is not None:
            return candidate
    raise FileNotFoundError(
        f"No promoted artifacts for {family}/{document}"
        + (" and no structurally valid candidate" if allow_candidate else "")
    )


def page_root(
    family: str,
    document: str | Path,
    *,
    version: str | None = None,
    allow_candidate: bool = False,
) -> Path:
    return document_artifacts(
        family, document, version=version, allow_candidate=allow_candidate
    ) / "pages"


def page_markdown(
    family: str,
    document: str | Path,
    page: int,
    *,
    version: str | None = None,
    allow_candidate: bool = False,
) -> Path:
    return page_root(
        family, document, version=version, allow_candidate=allow_candidate
    ) / f"page-{page:03d}" / "page.md"


def document_markdown(
    family: str,
    document: str | Path,
    *,
    version: str | None = None,
    allow_candidate: bool = False,
) -> Path:
    artifacts = document_artifacts(
        family, document, version=version, allow_candidate=allow_candidate
    )
    promoted = artifacts / "document.md"
    return promoted if promoted.is_file() else artifacts / "candidate" / "document.md"


def document_chunks(
    family: str,
    document: str | Path,
    *,
    version: str | None = None,
    allow_candidate: bool = False,
) -> Path:
    artifacts = document_artifacts(
        family, document, version=version, allow_candidate=allow_candidate
    )
    promoted = artifacts / "chunks.jsonl"
    return promoted if promoted.is_file() else artifacts / "candidate" / "chunks.jsonl"


def document_tables(
    family: str,
    document: str | Path,
    *,
    version: str | None = None,
    allow_candidate: bool = False,
) -> Path:
    artifacts = document_artifacts(
        family, document, version=version, allow_candidate=allow_candidate
    )
    promoted = artifacts / "tables"
    return promoted if promoted.is_dir() else artifacts / "candidate" / "tables"
