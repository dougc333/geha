"""Coverage-policy locations in the canonical ``crawl_dir`` corpus.

Source PDFs live in ``crawl_dir/raw/coverage-policies``. Docling outputs live
one folder per document in ``crawl_dir/verified/coverage-policies/<stem>/``,
and the reviewed HTML tables in its ``html_tables`` folder. Helpers here also
accept the older flat layout (all artifacts directly in one directory), so a
custom ``input_dir`` and temporary test fixtures keep working.
"""

from __future__ import annotations

from pathlib import Path


CRAWL_ROOT = Path(__file__).resolve().parents[1] / "crawl_dir"
POLICY_PDF_DIR = CRAWL_ROOT / "raw" / "coverage-policies"
POLICY_ARTIFACT_DIR = CRAWL_ROOT / "verified" / "coverage-policies"


def document_files(root: Path, suffix: str) -> list[Path]:
    """Return one ``<stem><suffix>`` file per document directly under ``root``.

    Matches ``root/<stem><suffix>`` (flat) and ``root/<stem>/<stem><suffix>``
    (per-document folders). Other nested folders, such as archives, are ignored.
    """
    flat = root.glob(f"*{suffix}")
    nested = (
        path for path in root.glob(f"*/*{suffix}")
        if path.name == f"{path.parent.name}{suffix}"
    )
    return sorted(path for path in (*flat, *nested) if path.is_file())


def document_file(root: Path, stem: str, suffix: str) -> Path:
    """Return a document's artifact in either layout, preferring its own folder."""
    nested = root / stem / f"{stem}{suffix}"
    return nested if nested.exists() else root / f"{stem}{suffix}"
