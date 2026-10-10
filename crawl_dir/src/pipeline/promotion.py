"""Promote only fully reviewed candidates into the production corpus."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .artifact_io import atomic_json, sha256_file


def promote_run(run_dir: Path, reviewed_root: Path) -> Path:
    run_dir = run_dir.resolve()
    manifest_path = run_dir / "run-manifest.json"
    qc_path = run_dir / "qc-report.json"
    manifest = json.loads(manifest_path.read_text())
    qc = json.loads(qc_path.read_text())
    if qc.get("status") != "passed":
        raise ValueError("Run cannot be promoted until qc-report.json status is passed")
    visual = qc.get("visual_verification") or {}
    if visual.get("status") != "passed" or visual.get("passed_pages") != visual.get("total_pages"):
        raise ValueError("Run cannot be promoted until every page passes visual verification")
    if qc.get("structural_errors"):
        raise ValueError("Run cannot be promoted with structural errors")

    page_dirs = sorted((run_dir / "pages").glob("page-*"))
    if len(page_dirs) != qc.get("page_count"):
        raise ValueError("Run page artifacts do not match the QC page count")
    for page_dir in page_dirs:
        page_manifest_path = page_dir / "page-manifest.json"
        if not page_manifest_path.is_file():
            raise ValueError(f"Missing page manifest: {page_manifest_path}")
        page = json.loads(page_manifest_path.read_text())
        if page.get("status") != "passed":
            raise ValueError(f"Page has not passed review: {page_dir.name}")
        for required in ("source.pdf", "page.md", "page.html"):
            if not (page_dir / required).is_file():
                raise ValueError(f"Missing reviewed page artifact: {page_dir / required}")

    destination = (
        reviewed_root.resolve()
        / manifest["family"]
        / manifest["document_id"]
        / manifest["document_version"]
    )
    if destination.exists():
        raise FileExistsError(destination)
    destination.mkdir(parents=True)
    source = run_dir / "input" / "source.pdf"
    if sha256_file(source) != manifest["source_sha256"]:
        raise ValueError("Run source hash no longer matches its manifest")
    shutil.copy2(source, destination / "source.pdf")
    shutil.copytree(run_dir / "pages", destination / "pages")
    shutil.copy2(run_dir / "candidate" / "document.md", destination / "document.md")
    shutil.copy2(run_dir / "candidate" / "chunks.jsonl", destination / "chunks.jsonl")
    shutil.copytree(run_dir / "candidate" / "tables", destination / "tables")
    atomic_json(destination / "manifest.json", {
        **manifest,
        "promotion_status": "promoted",
        "source_run": str(run_dir),
        "qc": qc,
    })
    return destination
