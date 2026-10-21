"""Persist ingestion outputs in the auditable run layout used by the demo workflow."""

from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def document_slug(filename: str) -> str:
    stem = Path(filename).stem.casefold()
    slug = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")
    return slug or "document"


def create_run_directory(
    runs_root: Path,
    *,
    filename: str,
    source: Path,
    ocr_engine: str,
    prepared_pages: Path | None = None,
) -> tuple[str, Path]:
    """Create a versioned run with an immutable copy of the input PDF."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"ingestion-{stamp}-{uuid.uuid4().hex[:6]}"
    run_dir = runs_root / "documents" / document_slug(filename) / run_id
    input_dir = run_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(source, input_dir / "source.pdf")
    (input_dir / "source-reference.json").write_text(
        json.dumps(
            {
                "filename": filename,
                "ocr_engine": ocr_engine,
                "source": str(source),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    if prepared_pages is not None:
        page_sources = list(prepared_pages.glob("page-[0-9][0-9][0-9]/source.pdf"))
        if not page_sources:
            raise ValueError(f"No prepared page PDFs found under {prepared_pages}")
        shutil.copytree(prepared_pages, run_dir / "pages")
    else:
        split_pdf_pages(input_dir / "source.pdf", run_dir / "pages")
    (run_dir / "errors.json").write_text(
        json.dumps({"schema_version": "1.0", "errors": []}, indent=2) + "\n",
        encoding="utf-8",
    )
    return run_id, run_dir


def append_run_error(
    run_dir: Path,
    *,
    document_id: str,
    stage: str,
    ocr_engine: str,
    error: Exception,
) -> Path:
    """Append a structured processing error to one run's JSON error log."""
    path = run_dir / "errors.json"
    payload: dict[str, Any] = {"schema_version": "1.0", "errors": []}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and isinstance(loaded.get("errors"), list):
                payload = loaded
        except (OSError, json.JSONDecodeError):
            pass
    payload["errors"].append(
        {
            "at": datetime.now(UTC).isoformat(),
            "document_id": document_id,
            "stage": stage,
            "ocr_engine": ocr_engine,
            "error_type": type(error).__name__,
            "message": str(error),
        }
    )
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def _copy_if_file(source: Path, target: Path) -> None:
    if source.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def _write_single_page_pdf(source: Path, page_index: int, target: Path) -> None:
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(source)
    if not 0 <= page_index < len(reader.pages):
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    writer.add_page(reader.pages[page_index])
    with target.open("wb") as stream:
        writer.write(stream)


def split_pdf_pages(source: Path, pages_dir: Path) -> list[Path]:
    """Split a PDF into deterministic, one-page PDF artifacts."""
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(source)
    outputs: list[Path] = []
    for page_index, page in enumerate(reader.pages):
        target = pages_dir / f"page-{page_index + 1:03d}" / "source.pdf"
        target.parent.mkdir(parents=True, exist_ok=True)
        writer = PdfWriter()
        writer.add_page(page)
        with target.open("wb") as stream:
            writer.write(stream)
        outputs.append(target)
    return outputs


def copy_page_markdown_checkpoints(
    previous_run: Path,
    next_run: Path,
    *,
    ocr_engine: str,
) -> int:
    """Copy successful per-page OCR outputs into a retry run."""
    copied = 0
    for source in previous_run.glob(f"pages/page-[0-9][0-9][0-9]/{ocr_engine}.md"):
        if not source.read_text(encoding="utf-8").strip():
            continue
        target = next_run / source.relative_to(previous_run)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        copied += 1
    return copied


def finalize_run_directory(
    run_dir: Path,
    *,
    working_dir: Path,
    source: Path,
    record: dict[str, Any],
    result: dict[str, Any],
    ocr_engine: str,
) -> None:
    """Mirror current artifacts into input/candidate/pages run directories."""
    candidate = run_dir / "candidate"
    candidate.mkdir(parents=True, exist_ok=True)
    _copy_if_file(working_dir / "document.md", candidate / "document.md")
    _copy_if_file(working_dir / "chunks.jsonl", candidate / "chunks.jsonl")
    if (working_dir / "visuals").is_dir():
        shutil.copytree(
            working_dir / "visuals",
            candidate / "visuals",
            dirs_exist_ok=True,
        )

    manifest_path = working_dir / "pages" / "manifest.json"
    page_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in page_manifest.get("pages", []):
        page_number = int(item["page"])
        current_page_dir = working_dir / "pages" / f"page-{page_number:03d}"
        page_dir = run_dir / "pages" / f"page-{page_number:03d}"
        page_dir.mkdir(parents=True, exist_ok=True)
        if not (page_dir / "source.pdf").is_file():
            _write_single_page_pdf(source, page_number - 1, page_dir / "source.pdf")
        _copy_if_file(current_page_dir / "source.png", page_dir / "source.png")
        _copy_if_file(current_page_dir / "docling.md", page_dir / "docling.md")
        engine_markdown = current_page_dir / f"{ocr_engine}.md"
        _copy_if_file(engine_markdown, page_dir / f"{ocr_engine}.md")
        selected = engine_markdown if engine_markdown.is_file() else current_page_dir / "docling.md"
        _copy_if_file(selected, page_dir / "page.md")
        (page_dir / "page-manifest.json").write_text(
            json.dumps(item, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    run_manifest = {
        "schema_version": "1.0",
        "run_id": record.get("runId"),
        "document_id": record["id"],
        "filename": record["filename"],
        "ocr_engine": ocr_engine,
        "created_at": record.get("createdAt"),
        "completed_at": datetime.now(UTC).isoformat(),
        "artifacts": {
            "input": "input/source.pdf",
            "document_markdown": "candidate/document.md",
            "chunks": "candidate/chunks.jsonl",
            "pages": "pages",
            "errors": "errors.json",
        },
        "result": result,
    }
    (run_dir / "run-manifest.json").write_text(
        json.dumps(run_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (run_dir / "qc-report.json").write_text(
        json.dumps(
            {
                "ocr_engine": ocr_engine,
                "page_count": result["pages"]["page_count"],
                "ocr_pages": result["pages"].get("ocr_pages", 0),
                "issue_count": result["pages"]["issue_count"]
                + result["visuals"]["issue_count"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

