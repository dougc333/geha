"""Copy the minimal canonical crawl corpus needed by the Lambda tools."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from crawl_dir.src.consumer_paths import document_artifacts, raw_dir


def _copy_module(output: Path) -> None:
    for relative in (
        Path("crawl_dir/__init__.py"),
        Path("crawl_dir/src/__init__.py"),
        Path("crawl_dir/src/consumer_paths.py"),
    ):
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / relative, target)


def _copy_document(output: Path, family: str, relative: Path, *, pages: bool) -> None:
    source = raw_dir(family) / relative
    raw_target = output / "crawl_dir" / "raw" / family / relative
    raw_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, raw_target)

    artifacts = document_artifacts(family, relative, allow_candidate=True)
    run_relative = artifacts.relative_to(REPO / "crawl_dir")
    run_target = output / "crawl_dir" / run_relative
    if "reviewed" in run_relative.parts:
        shutil.copytree(artifacts, run_target)
        return
    run_target.mkdir(parents=True, exist_ok=True)
    for name in ("run-manifest.json", "qc-report.json"):
        shutil.copy2(artifacts / name, run_target / name)
    shutil.copytree(artifacts / "candidate", run_target / "candidate")
    if pages:
        shutil.copytree(artifacts / "pages", run_target / "pages")


def main(output: Path) -> None:
    _copy_module(output)
    for name in (
        "2026-geha-dental-benefits-guide.pdf",
        "2026-geha-dental-plan-brochure.pdf",
    ):
        _copy_document(output, "dental", Path("fedvip") / name, pages=True)
    for pdf in sorted(raw_dir("coverage-policies").rglob("*.pdf")):
        _copy_document(
            output,
            "coverage-policies",
            pdf.relative_to(raw_dir("coverage-policies")),
            pages=False,
        )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: package_crawl_corpus.py OUTPUT_DIR")
    main(Path(sys.argv[1]).resolve())
