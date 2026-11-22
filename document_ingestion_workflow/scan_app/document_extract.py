"""One-PDF CLI and Swagger API over the existing crawl_dir ingestion workflows.

Run ``python document_extract.py --help`` or
``uvicorn document_extract:app --app-dir /Users/dc/geha/document_ingestion_workflow/scan_app``.
The API accepts only PDFs in the completed app_scan inventory. It creates a new
immutable run; it never promotes extracted content into a production corpus.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pymupdf
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


APP_ROOT = Path(__file__).resolve().parent
GEHA_ROOT = APP_ROOT.parents[1]
CRAWL_ROOT = GEHA_ROOT / "crawl_dir"
sys.path.insert(0, str(CRAWL_ROOT))
sys.path.insert(0, str(GEHA_ROOT))

from src.pipeline.artifact_io import atomic_json  # noqa: E402
from src.pipeline.claude_client import CLAUDE_MODEL  # noqa: E402
from src.pipeline.figure_specs import load_page_spec, process_document_with_figure_specs  # noqa: E402
from src.pipeline.model_client import (  # noqa: E402
    SUPPORTED_PROVIDERS,
    ask_model,
    use_model_provider,
)
from src.pipeline.runner import _split_pages  # noqa: E402
from src.pipeline.scanned_ingestion import (  # noqa: E402
    process_scanned_document,
    render_pdf_page_with_pymupdf,
)

DEFAULT_PROVIDER = "nous"
DEFAULT_NOUS_MODEL = "qwen/qwen3-vl-235b-a22b-instruct"


@dataclass(frozen=True)
class ScanDecision:
    pdf: Path
    family: str
    document: str
    document_id: str
    page_count: int
    image_pages: tuple[int, ...]
    figure_pages: tuple[int, ...]
    table_pages: tuple[int, ...]
    source_fingerprint: str


@dataclass(frozen=True)
class ExtractionResult:
    run_dir: Path
    decision: ScanDecision
    branches: dict[str, str]
    status: str
    missing_figure_specs: tuple[int, ...] = ()

    def payload(self) -> dict[str, Any]:
        return {
            "run_dir": str(self.run_dir),
            "decision": {**asdict(self.decision), "pdf": str(self.decision.pdf)},
            "branches": self.branches,
            "status": self.status,
            "missing_figure_specs": self.missing_figure_specs,
        }


class ExtractionRequest(BaseModel):
    pdf: str = Field(description="Absolute PDF path already present in scan_state.json")
    document_version: str = Field(default="scan-v1")
    figure_specs_dir: str | None = Field(
        default=None, description="Reviewed page-NNN.json specs; defaults to bounding_box annotations"
    )
    provider: str = Field(default=DEFAULT_PROVIDER)
    model: str | None = Field(default=None, description="Defaults to Qwen3-VL on Nous or Claude on Anthropic")
    base_url: str | None = Field(default=None)
    api_key_env: str | None = Field(default=None)


class SingleDocumentExtractor:
    """Route one scanned PDF to existing per-page extraction and review code."""

    def __init__(self, crawl_root: Path = CRAWL_ROOT, scan_root: Path = APP_ROOT):
        self.crawl_root = crawl_root.resolve()
        self.scan_root = scan_root.resolve()

    def decision(self, pdf: Path) -> ScanDecision:
        pdf = pdf.expanduser().resolve()
        state = json.loads((self.scan_root / "scan_state.json").read_text())
        registry = json.loads((self.scan_root / "scan_registry.json").read_text())
        for collection in state["collections"]:
            family = collection["key"]
            registered = registry.get("collections", {}).get(family, {})
            if (collection.get("status") != "completed"
                    or registered.get("inventoryFingerprint") != collection.get("inventoryFingerprint")):
                continue
            for record in collection.get("pdfs", []):
                if Path(record["path"]).resolve() != pdf:
                    continue
                if record.get("status") != "completed":
                    raise ValueError("PDF scan is incomplete; rescan before extraction")
                stat = pdf.stat()
                fingerprint = hashlib.sha256(
                    f"{stat.st_size}:{stat.st_mtime_ns}".encode()
                ).hexdigest()
                if fingerprint != record.get("sourceFingerprint"):
                    raise ValueError("PDF changed since app_scan; rescan before extraction")
                raw_root = (self.crawl_root / "raw" / family).resolve()
                relative = pdf.relative_to(raw_root)
                document_id = "--".join(relative.with_suffix("").parts)
                with pymupdf.open(pdf) as source:
                    if source.page_count != record["pageCount"]:
                        raise ValueError("PDF page count changed since app_scan")
                    image_pages = tuple(
                        number for number, page in enumerate(source, 1)
                        if not page.get_text().strip()
                    )
                return ScanDecision(
                    pdf, family, str(relative), document_id, record["pageCount"],
                    image_pages,
                    tuple(sorted(set(record.get("figurePages", [])) | set(record.get("chartPages", [])))),
                    tuple(sorted(set(record.get("tablePages", [])))),
                    fingerprint,
                )
        raise ValueError("PDF is absent from the completed app_scan registry")

    def _specs(self, decision: ScanDecision, supplied: Path | None) -> tuple[Path, tuple[int, ...]]:
        source_dir = supplied or (
            self.crawl_root.parent / "bounding_box" / "annotations"
            / decision.family / decision.pdf.stem / "figure-specs"
        )
        source_dir = source_dir.expanduser().resolve()
        missing = tuple(page for page in decision.figure_pages
                        if load_page_spec(source_dir, page) is None)
        return source_dir, missing

    def _tesseract(self, decision: ScanDecision, run_dir: Path) -> None:
        tesseract_dir = run_dir / "tesseract"
        pages_dir = tesseract_dir / "pages"
        input_dir = tesseract_dir / "input"
        input_dir.mkdir(parents=True)
        shutil.copy2(decision.pdf, input_dir / "source.pdf")
        records = _split_pages(input_dir / "source.pdf", pages_dir)
        text_parts: list[str] = []
        for record in records:
            page = record["page"]
            if page not in decision.image_pages:
                continue
            page_dir = pages_dir / f"page-{page:03d}"
            source = page_dir / "source.pdf"
            png = render_pdf_page_with_pymupdf(source, page_dir / "source.png")
            result = subprocess.run(
                ["tesseract", str(png), "stdout", "-l", "eng"],
                check=True, capture_output=True, text=True,
            )
            text = result.stdout.strip()
            markdown = f"# Page {page}\n\n{text}\n"
            (page_dir / "page.md").write_text(markdown, encoding="utf-8")
            (page_dir / "final.html").write_text(
                "<!doctype html><html><meta charset='utf-8'><body><pre>"
                + html.escape(text) + "</pre></body></html>", encoding="utf-8"
            )
            record.update(status="needs_visual_review", html="final.html", markdown="page.md",
                          tool_id="tesseract_ocr", table_ids=[])
            atomic_json(page_dir / "page-manifest.json", record)
            text_parts.append(markdown)
        (tesseract_dir / "tesseract.md").write_text("\n".join(text_parts), encoding="utf-8")

    def run(self, pdf: Path, *, document_version: str = "scan-v1",
            figure_specs_dir: Path | None = None,
            provider: str = DEFAULT_PROVIDER, model: str | None = None,
            base_url: str | None = None, api_key_env: str | None = None) -> ExtractionResult:
        if model is None:
            if provider == "anthropic":
                model = CLAUDE_MODEL
            elif provider == "nous":
                model = DEFAULT_NOUS_MODEL
            else:
                raise ValueError("--model is required for openai-compatible provider")
        decision = self.decision(pdf)
        source_specs, missing_specs = (
            self._specs(decision, figure_specs_dir)
            if decision.figure_pages else (None, ())
        )
        identifier = "single-document-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        run_dir = self.crawl_root / "runs" / decision.family / decision.document_id / identifier
        branches: dict[str, str] = {}
        if len(decision.image_pages) == decision.page_count:
            self._tesseract(decision, run_dir)
            branches["tesseract"] = "tesseract"
        else:
            # Four rendered candidates: iteration 00 plus at most three corrections.
            with use_model_provider(provider, base_url=base_url, api_key_env=api_key_env):
                if decision.image_pages or decision.figure_pages or decision.table_pages:
                    self._check_model_access(model, provider)
                html_run = process_scanned_document(
                    root=self.crawl_root, family=decision.family, document=decision.document,
                    document_version=document_version, model=model, max_corrections=3,
                    requested_run_id=f"{identifier}/html",
                    additional_visual_pages=list(decision.figure_pages),
                )
            branches["html"] = str(html_run.relative_to(run_dir))
            self._table_markdown(html_run)
            if source_specs is not None and len(missing_specs) < len(decision.figure_pages):
                usable_specs = run_dir / "authored-figure-specs"
                usable_specs.mkdir(parents=True)
                for page in decision.figure_pages:
                    if page not in missing_specs:
                        shutil.copy2(source_specs / f"page-{page:03d}.json", usable_specs)
                spec_run = process_document_with_figure_specs(
                    root=self.crawl_root, family=decision.family, document=decision.document,
                    document_version=document_version, specs_dir=usable_specs,
                    requested_run_id=f"{identifier}/spec",
                )
                branches["spec"] = str(spec_run.relative_to(run_dir))
                specs = spec_run / "figure-specs"
                specs.mkdir()
                for page in range(1, decision.page_count + 1):
                    page_dir = spec_run / "pages" / f"page-{page:03d}"
                    spec_path = specs / f"page-{page:03d}.json"
                    if page in decision.figure_pages and page not in missing_specs:
                        shutil.copy2(usable_specs / spec_path.name, spec_path)
                    else:
                        atomic_json(spec_path, {
                            "schema_version": 1, "document_id": decision.document_id,
                            "page": page, "figures": [],
                            "author": "app_scan_no_figure_detected" if page not in missing_specs
                                      else "missing_reviewed_figure_spec",
                            "status": "needs_spec" if page in missing_specs else "no_figure_detected",
                        })
                    shutil.copy2(spec_path, page_dir / "figure-spec.json")
                self._table_markdown(spec_run)
            elif source_specs is not None:
                # Preserve the requested spec layout even when no authored figure
                # specs exist. The copied native/HTML artifacts are explicitly
                # marked incomplete, never presented as verified spec output.
                spec_run = run_dir / "spec"
                (spec_run / "pages").mkdir(parents=True)
                (spec_run / "figure-specs").mkdir()
                for page in range(1, decision.page_count + 1):
                    target = spec_run / "pages" / f"page-{page:03d}"
                    shutil.copytree(html_run / "pages" / f"page-{page:03d}", target)
                    spec = {
                        "schema_version": 1, "document_id": decision.document_id,
                        "page": page, "figures": [], "author": "missing_reviewed_figure_spec",
                        "status": "needs_spec" if page in missing_specs else "no_figure_detected",
                    }
                    atomic_json(spec_run / "figure-specs" / f"page-{page:03d}.json", spec)
                    atomic_json(target / "figure-spec.json", spec)
                atomic_json(spec_run / "qc-report.json", {
                    "status": "failed", "structural_errors": [
                        {"issue": "missing_reviewed_figure_spec", "pages": missing_specs}
                    ],
                })
                branches["spec"] = "spec"
            if decision.image_pages:
                self._tesseract(decision, run_dir)
                branches["tesseract"] = "tesseract"
        reports = [json.loads((run_dir / branch / "qc-report.json").read_text())
                   for branch in ("html", "spec") if branch in branches]
        status = "failed" if (missing_specs or any(report.get("status") == "failed" for report in reports)) else "needs_visual_review"
        result = ExtractionResult(run_dir, decision, branches, status, missing_specs)
        atomic_json(run_dir / "extraction-manifest.json", result.payload())
        return result

    @staticmethod
    def _check_model_access(model: str, provider: str) -> None:
        """Fail before PDF conversion when the selected model rejects the credential."""
        try:
            ask_model(model, "Reply with OK.", [{"type": "text", "text": "OK"}],
                      max_tokens=8, timeout=30)
        except Exception as error:
            if getattr(error, "status_code", None) == 401:
                key_name = "NOUS_API_KEY" if provider == "nous" else (
                    "ANTHROPIC_API_KEY" if provider == "anthropic" else "the selected API key"
                )
                raise ValueError(
                    f"{provider} rejected {key_name} (HTTP 401). Update the key and retry."
                ) from None
            raise

    @staticmethod
    def _table_markdown(run_dir: Path) -> None:
        """Export existing extracted table records as a Markdown companion."""
        tables_dir = run_dir / "candidate" / "tables"
        parts: list[str] = []
        for path in sorted(tables_dir.glob("table-*.json")):
            table = json.loads(path.read_text())
            headers = table["headers"]
            parts.extend([
                f"## {table['table_id']}: {table['section']}",
                "| " + " | ".join(headers) + " |",
                "| " + " | ".join("---" for _ in headers) + " |",
            ])
            for row in table["rows"]:
                parts.append("| " + " | ".join(
                    str(row.get(header, "")).replace("|", "\\|").replace("\n", " ")
                    for header in headers
                ) + " |")
            parts.append("")
        (tables_dir / "tables.md").write_text("\n".join(parts) + "\n", encoding="utf-8")


app = FastAPI(title="Single PDF Extraction API", version="1.0.0")


@app.post("/extract", summary="Extract one scanned multipage PDF")
def extract(request: ExtractionRequest) -> dict[str, Any]:
    try:
        return SingleDocumentExtractor().run(
            Path(request.pdf), document_version=request.document_version,
            figure_specs_dir=Path(request.figure_specs_dir) if request.figure_specs_dir else None,
            provider=request.provider, model=request.model,
            base_url=request.base_url, api_key_env=request.api_key_env,
        ).payload()
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--document-version", default="scan-v1")
    parser.add_argument("--figure-specs-dir", type=Path)
    parser.add_argument("--provider", choices=SUPPORTED_PROVIDERS, default=DEFAULT_PROVIDER)
    parser.add_argument("--model", help="Defaults to Qwen3-VL on Nous or Claude on Anthropic")
    parser.add_argument("--base-url")
    parser.add_argument("--api-key-env")
    args = parser.parse_args()
    try:
        result = SingleDocumentExtractor().run(
            args.pdf, document_version=args.document_version,
            figure_specs_dir=args.figure_specs_dir,
            provider=args.provider, model=args.model,
            base_url=args.base_url, api_key_env=args.api_key_env,
        )
    except ValueError as error:
        parser.exit(2, f"error: {error}\n")
    print(json.dumps(result.payload(), indent=2))


if __name__ == "__main__":
    main()
