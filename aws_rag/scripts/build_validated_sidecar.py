#!/usr/bin/env python3
"""Build an AWS RAG text sidecar from one completed PDF MCP validation run."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_child(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name:
        raise ValueError("missing extraction artifact path")
    path = (root / name).resolve()
    path.relative_to(root.resolve())
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"missing or unsafe extraction artifact: {name}")
    return path


def build(pdf: Path, run_dir: Path, *, title: str | None = None) -> dict:
    batch = json.loads((run_dir / "batch.json").read_text(encoding="utf-8"))
    source_sha256 = file_sha256(pdf)
    if batch.get("source_sha256") != source_sha256:
        raise ValueError("MCP batch source SHA-256 does not match the supplied PDF")
    if batch.get("status") != "completed" or batch.get("pages_failed") != 0:
        raise ValueError("MCP run is not fully completed")

    raw_pages = batch.get("pages")
    if not isinstance(raw_pages, list) or len(raw_pages) != batch.get("page_count"):
        raise ValueError("MCP batch page_count is invalid")
    extraction_dir = run_dir / "extraction"
    pages = []
    for number, page in enumerate(raw_pages, start=1):
        if page.get("page") != number or page.get("status") != "matched":
            raise ValueError(f"page {number} has not passed visual comparison")
        markdown_path = safe_child(extraction_dir, page.get("final_markdown"))
        content = markdown_path.read_text(encoding="utf-8").strip()
        if not content:
            raise ValueError(f"page {number} has empty final Markdown")
        pages.append({
            "page_number": number,
            "validation_status": "matched",
            "extraction_method": page.get("extraction_method"),
            "correction_passes": len(page.get("passes", [])),
            "content_changed": bool(page.get("content_changed")),
            "content": content,
            "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        })

    return {
        "schema_version": 1,
        "source_pdf": pdf.name,
        "source_sha256": source_sha256,
        "validation_status": "validated",
        "page_count": len(pages),
        "metadata": {"title": title or pdf.stem.replace("-", " ").title()},
        "validation": {
            "run_id": batch.get("run_id"),
            "generated_at": batch.get("generated_at"),
            "model": batch.get("model"),
            "max_correction_passes": batch.get("max_correction_passes"),
            "pages_modified": batch.get("pages_modified"),
            "error_counts_by_pass": batch.get("error_counts_by_pass", []),
        },
        "pages": pages,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--title")
    args = parser.parse_args()
    pdf = args.pdf.expanduser().resolve()
    run_dir = args.run_dir.expanduser().resolve()
    output = (
        args.output.expanduser().resolve()
        if args.output
        else pdf.with_name(pdf.name + ".validated.json")
    )
    payload = build(pdf, run_dir, title=args.title)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(output)
    print(output)


if __name__ == "__main__":
    main()
