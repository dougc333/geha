"""Local control-plane API for the document ingestion dashboard."""

from __future__ import annotations

import json
import os
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .document_router import classify_document
from .query_router import list_router_runs, load_clusters, route_jsonl, save_router_run


STAGES = (
    "queued",
    "uploading",
    "extracting",
    "routing",
    "reviewing",
    "embedding",
    "indexing",
    "complete",
)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_ROOT = PROJECT_ROOT / "runtime"
DEFAULT_SEED_LIMIT = 50
OCR_ENGINES = ("deepseek", "llamaparse")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def load_query_examples(path: Path, limit: int = 30) -> list[dict[str, Any]]:
    """Return a cluster-balanced, UI-safe projection of generated JSONL queries."""
    capped_limit = min(max(limit, 1), 30)
    grouped: dict[str, list[dict[str, Any]]] = {}
    if not path.is_file():
        return []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        query = str(record.get("user_input") or "").strip()
        cluster = str(record.get("cluster") or "unknown").strip()
        if not query:
            continue
        sources = record.get("source_documents") or []
        filenames = [
            str(source.get("filename"))
            for source in sources
            if isinstance(source, dict) and source.get("filename")
        ]
        grouped.setdefault(cluster, []).append({
            "id": str(record.get("id") or f"{cluster}-{len(grouped.get(cluster, [])) + 1}"),
            "cluster": cluster,
            "user_input": query,
            "source_documents": filenames,
        })

    examples: list[dict[str, Any]] = []
    offsets = {cluster: 0 for cluster in grouped}
    while len(examples) < capped_limit:
        added = False
        for cluster in sorted(grouped):
            offset = offsets[cluster]
            if offset >= len(grouped[cluster]):
                continue
            examples.append(grouped[cluster][offset])
            offsets[cluster] += 1
            added = True
            if len(examples) >= capped_limit:
                break
        if not added:
            break
    return examples


def safe_filename(value: str) -> str:
    """Return a basename safe for use inside a document directory."""
    name = Path(value).name.strip().replace("\x00", "")
    return name or "document.pdf"


class DocumentStore:
    """Filesystem-backed document and status store with atomic JSON updates."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.documents_root = root / "documents"
        self.documents_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._extraction_summary_cache: dict[
            str, tuple[int, int, dict[str, Any]]
        ] = {}
        self._context_source_cache: dict[
            str, tuple[int, int, dict[str, int]]
        ] = {}

    def directory(self, document_id: str) -> Path:
        if not document_id or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in document_id):
            raise ValueError("Invalid document ID")
        return self.documents_root / document_id

    def source_path(self, record: dict[str, Any]) -> Path:
        return self.directory(record["id"]) / "source.pdf"

    def pages_directory(self, document_id: str) -> Path:
        return self.directory(document_id) / "pages"

    def prepare_pages(self, document_id: str) -> dict[str, Any]:
        """Create reusable single-page PDFs before extraction can be submitted."""
        from .run_artifacts import split_pdf_pages

        record = self.get(document_id)
        expected = int(record.get("pages") or 0)
        pages_dir = self.pages_directory(document_id)
        existing = list(pages_dir.glob("page-[0-9][0-9][0-9]/source.pdf"))
        if expected > 0 and len(existing) == expected and all(path.stat().st_size for path in existing):
            current = self.get(document_id)
            return self.save({
                **current,
                "pagePreparation": {"status": "ready", "completed": expected, "total": expected},
            })

        temporary = pages_dir.with_name(f"pages-preparing-{uuid.uuid4().hex[:8]}")
        outputs = split_pdf_pages(self.source_path(record), temporary)
        if pages_dir.exists():
            shutil.rmtree(pages_dir)
        temporary.replace(pages_dir)
        current = self.get(document_id)
        return self.save({
            **current,
            "pagePreparation": {"status": "ready", "completed": len(outputs), "total": len(outputs)},
        })

    def _record_path(self, document_id: str) -> Path:
        return self.directory(document_id) / "job.json"

    def save(self, record: dict[str, Any]) -> dict[str, Any]:
        record = {**record, "updatedAt": utc_now()}
        path = self._record_path(record["id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        with self._lock:
            temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            temporary.replace(path)
        return record

    def get(self, document_id: str) -> dict[str, Any]:
        path = self._record_path(document_id)
        if not path.is_file():
            raise KeyError(document_id)
        with self._lock:
            return json.loads(path.read_text(encoding="utf-8"))

    def list(self) -> list[dict[str, Any]]:
        records = []
        for path in self.documents_root.glob("*/job.json"):
            try:
                records.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return sorted(records, key=lambda record: record.get("createdAt", ""), reverse=True)

    def with_extraction_summary(self, record: dict[str, Any]) -> dict[str, Any]:
        """Expose source-extraction readiness without changing job stage state.

        The preflight file is the authoritative first-pass page checkpoint. Its
        parsed summary is cached by file metadata because the UI polls the
        document list once per second.
        """
        preflight = self.pages_directory(record["id"]) / "docling-preflight.json"
        context_sources = self.context_source_counts(record["id"])
        contextual_units = sum(context_sources.values())
        contextual_counts: dict[str, int] = {}
        if (
            contextual_units > 0
            and record.get("contextStatus")
            in {"annotated", "contextualized", "judged", "summarized_and_embedded"}
        ):
            # Page contextualization uses one retrieval chunk per extracted page.
            # Older job records predate persisted chunk counts, so derive them
            # from the completed contextual artifact for an accurate UI summary.
            contextual_counts = {
                "chunks": int(record.get("chunks") or contextual_units),
                "retrievalUnits": int(
                    record.get("retrievalUnits") or contextual_units
                ),
            }
        if not preflight.is_file():
            return {
                **record,
                **contextual_counts,
                "extractedPages": 0,
                "sourceExtractionStatus": "pending",
                "contextSources": context_sources,
            }
        try:
            stat = preflight.stat()
            cache_key = (stat.st_mtime_ns, stat.st_size)
            cached = self._extraction_summary_cache.get(record["id"])
            if cached and cached[:2] == cache_key:
                summary = cached[2]
            else:
                data = json.loads(preflight.read_text(encoding="utf-8"))
                total = int(data.get("page_count") or record.get("pages") or 0)
                completed = int(data.get("completed_pages") or 0)
                extraction_status = (
                    "complete" if total > 0 and completed >= total
                    else "partial" if completed > 0
                    else "pending"
                )
                summary = {
                    "extractedPages": completed,
                    "sourceExtractionStatus": extraction_status,
                }
                self._extraction_summary_cache[record["id"]] = (
                    *cache_key,
                    summary,
                )
        except (OSError, ValueError, json.JSONDecodeError):
            summary = {
                "extractedPages": 0,
                "sourceExtractionStatus": "pending",
            }
        return {
            **record,
            **contextual_counts,
            **summary,
            "contextSources": context_sources,
        }

    def context_source_counts(self, document_id: str) -> dict[str, int]:
        """Count the extraction artifacts actually supplied to Claude by engine."""
        path = self.directory(document_id) / "contextual-retrieval" / "contextual-pages.jsonl"
        if not path.is_file():
            return {}
        try:
            stat = path.stat()
            cache_key = (stat.st_mtime_ns, stat.st_size)
            cached = self._context_source_cache.get(document_id)
            if cached and cached[:2] == cache_key:
                return cached[2]
            counts: dict[str, int] = {}
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                source = Path(str(record.get("source_markdown") or "")).name.lower()
                engine = next(
                    (name for name in ("docling", "deepseek", "llamaparse") if source.startswith(name)),
                    None,
                )
                if engine:
                    counts[engine] = counts.get(engine, 0) + 1
            self._context_source_cache[document_id] = (*cache_key, counts)
            return counts
        except (OSError, json.JSONDecodeError):
            return {}

    def runs(self, document_id: str) -> list[dict[str, Any]]:
        """Return immutable ingestion runs for a document, newest first."""
        record = self.get(document_id)
        current_run_id = record.get("runId")
        runs: list[dict[str, Any]] = []
        runs_root = self.root / "runs" / "documents"
        for manifest_path in runs_root.glob("*/ingestion-*/run-manifest.json"):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if manifest.get("document_id") != document_id:
                continue
            result = manifest.get("result") if isinstance(manifest.get("result"), dict) else {}
            pages = result.get("pages") if isinstance(result.get("pages"), dict) else {}
            run_id = str(manifest.get("run_id") or manifest_path.parent.name)
            runs.append({
                "run_id": run_id,
                "created_at": manifest.get("created_at"),
                "completed_at": manifest.get("completed_at"),
                "ocr_engine": manifest.get("ocr_engine", "unknown"),
                "status": "complete" if manifest.get("completed_at") else "incomplete",
                "page_count": pages.get("page_count", 0),
                "ocr_pages": pages.get("ocr_pages", 0),
                "issue_count": pages.get("issue_count", 0),
                "is_current": run_id == current_run_id,
            })
        if current_run_id and not any(item["run_id"] == current_run_id for item in runs):
            run_directory = record.get("runDirectory")
            if isinstance(run_directory, str) and (self.root / run_directory).is_dir():
                pages_dir = self.root / run_directory / "pages"
                page_count = len(list(pages_dir.glob("page-*/source.pdf")))
                engine = str(record.get("ocrEngine") or "unknown")
                ocr_pages = len(list(pages_dir.glob(f"page-*/{engine}.md")))
                runs.append({
                    "run_id": current_run_id,
                    "created_at": record.get("updatedAt"),
                    "completed_at": None,
                    "ocr_engine": engine,
                    "status": "incomplete",
                    "page_count": page_count,
                    "ocr_pages": ocr_pages,
                    "issue_count": int((record.get("llamaparseStatus") or {}).get("failed", 0)),
                    "is_current": True,
                })
        return sorted(runs, key=lambda item: item["run_id"], reverse=True)

    def run_directory(self, document_id: str, run_id: str) -> Path:
        """Resolve a run owned by ``document_id`` without trusting URL paths."""
        if not run_id.startswith("ingestion-") or "/" in run_id or "\\" in run_id:
            raise ValueError("Invalid run ID")
        runs_root = (self.root / "runs" / "documents").resolve()
        record = self.get(document_id)
        if record.get("runId") == run_id and isinstance(record.get("runDirectory"), str):
            current = (self.root / record["runDirectory"]).resolve()
            try:
                current.relative_to(runs_root)
            except ValueError:
                pass
            else:
                if current.is_dir():
                    return current
        for manifest_path in runs_root.glob(f"*/{run_id}/run-manifest.json"):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if manifest.get("document_id") == document_id:
                return manifest_path.parent.resolve()
        raise KeyError(run_id)

    def create_from_path(self, source: Path, filename: str | None = None) -> dict[str, Any]:
        document_id = f"doc-{uuid.uuid4().hex[:12]}"
        target_dir = self.directory(document_id)
        target_dir.mkdir(parents=True, exist_ok=False)
        target = target_dir / "source.pdf"
        shutil.copyfile(source, target)
        record = {
            "id": document_id,
            "filename": safe_filename(filename or source.name),
            "sizeMb": round(target.stat().st_size / 1024 / 1024, 1),
            "pages": pdf_page_count(target),
            "stage": "queued",
            "progress": 0,
            "reviewIssues": 0,
            "createdAt": utc_now(),
            "updatedAt": utc_now(),
        }
        saved = self.save(record)
        return self.prepare_pages(saved["id"])
    def create_upload(self, upload: UploadFile) -> dict[str, Any]:
        filename = safe_filename(upload.filename or "document.pdf")
        if not filename.lower().endswith(".pdf"):
            raise ValueError("Only PDF files are accepted")
        document_id = f"doc-{uuid.uuid4().hex[:12]}"
        target_dir = self.directory(document_id)
        target_dir.mkdir(parents=True, exist_ok=False)
        target = target_dir / "source.pdf"
        with target.open("wb") as stream:
            shutil.copyfileobj(upload.file, stream)
        record = {
            "id": document_id,
            "filename": filename,
            "sizeMb": round(target.stat().st_size / 1024 / 1024, 1),
            "pages": pdf_page_count(target),
            "stage": "queued",
            "progress": 0,
            "reviewIssues": 0,
            "createdAt": utc_now(),
            "updatedAt": utc_now(),
        }
        saved = self.save(record)
        return self.prepare_pages(saved["id"])


def seed_corpus_documents(store: DocumentStore, corpus: Path, limit: int) -> int:
    """Idempotently register the first ``limit`` PDFs from a local corpus."""
    if limit <= 0 or not corpus.is_dir():
        return 0

    existing = store.list()
    existing_sources = {
        record["seedSource"]
        for record in existing
        if isinstance(record.get("seedSource"), str)
    }
    # Records created by older releases did not include ``seedSource``. The
    # original seed set had unique basenames, so use filenames as a migration
    # fallback and avoid creating duplicates while increasing the limit.
    existing_filenames = {
        record["filename"]
        for record in existing
        if isinstance(record.get("filename"), str)
    }

    created = 0
    for source in sorted(corpus.rglob("*.pdf"))[:limit]:
        relative_source = source.relative_to(corpus).as_posix()
        if relative_source in existing_sources or source.name in existing_filenames:
            continue
        record = store.create_from_path(source)
        store.save({**record, "seedSource": relative_source})
        existing_sources.add(relative_source)
        existing_filenames.add(source.name)
        created += 1
    return created


def pdf_page_count(path: Path) -> int:
    try:
        from pypdf import PdfReader

        return len(PdfReader(path).pages)
    except Exception:
        return 0


class IngestionManager:
    """Runs local jobs using real extraction when configured, or a fast simulator."""

    def __init__(self, store: DocumentStore, *, mode: str = "simulate", concurrency: int = 3) -> None:
        self.store = store
        self.mode = mode
        self.executor = ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="ingestion")
        self._active: set[str] = set()
        self._lock = threading.Lock()

    def submit(self, document_id: str, *, ocr_engine: str | None = None) -> bool:
        record = self.store.get(document_id)
        selected_engine = ocr_engine or record.get("ocrEngine") or "deepseek"
        if selected_engine not in OCR_ENGINES:
            raise ValueError(f"Unsupported OCR engine: {selected_engine}")
        with self._lock:
            if document_id in self._active:
                return False
            self._active.add(document_id)
        self.store.save({
            **record,
            "ocrEngine": selected_engine,
            "stage": "queued",
            "progress": 0,
            "status": "queued",
            "error": None,
        })
        self.executor.submit(self._run_guarded, document_id)
        return True

    def submit_next(self, *, ocr_engine: str = "deepseek") -> str | None:
        """Submit one queued document and return its ID when a worker starts."""
        if ocr_engine not in OCR_ENGINES:
            raise ValueError(f"Unsupported OCR engine: {ocr_engine}")
        with self._lock:
            if self._active:
                return None
            record = next(
                (
                    item
                    for item in self.store.list()
                    if item.get("stage") == "queued"
                    and item.get("status") != "needs_review"
                ),
                None,
            )
            if record is None:
                return None
            document_id = record["id"]
            self._active.add(document_id)
        self.store.save({**record, "ocrEngine": ocr_engine})
        self.executor.submit(self._run_guarded, document_id)
        return document_id

    def _run_guarded(self, document_id: str) -> None:
        started = time.monotonic()
        try:
            if self.mode == "docling":
                record = self.store.get(document_id)
                self._run_docling(document_id, record.get("ocrEngine", "deepseek"))
            else:
                self._run_simulated(document_id)
            record = self.store.get(document_id)
            self.store.save({**record, "duration": format_duration(time.monotonic() - started)})
        except Exception as error:
            record = self.store.get(document_id)
            run_directory = record.get("runDirectory")
            if isinstance(run_directory, str):
                from .run_artifacts import append_run_error

                append_run_error(
                    self.store.root / run_directory,
                    document_id=document_id,
                    stage=str(record.get("stage", "unknown")),
                    ocr_engine=str(record.get("ocrEngine", "unknown")),
                    error=error,
                )
            self.store.save({
                **record,
                "status": "failed",
                "error": f"{type(error).__name__}: {error}",
            })
        finally:
            with self._lock:
                self._active.discard(document_id)

    def _set_stage(self, document_id: str, stage: str, **updates: Any) -> dict[str, Any]:
        record = self.store.get(document_id)
        progress = round(STAGES.index(stage) / (len(STAGES) - 1) * 100)
        return self.store.save({
            **record,
            "stage": stage,
            "progress": progress,
            "status": "running" if stage != "complete" else "succeeded",
            "error": None,
            **updates,
        })

    def _run_simulated(self, document_id: str) -> None:
        for stage in STAGES[1:]:
            time.sleep(0.35)
            updates: dict[str, Any] = {}
            if stage == "routing":
                record = self.store.get(document_id)
                classification = classify_document(record["filename"], "")
                updates.update(
                    isPolicy=classification["is_policy"],
                    route=classification["route"],
                    classification=classification,
                )
            if stage == "reviewing":
                record = self.store.get(document_id)
                if not record.get("isPolicy"):
                    self._set_stage(document_id, "complete", chunks=max(1, record.get("pages", 1)))
                    return
            if stage == "complete":
                record = self.store.get(document_id)
                updates["chunks"] = max(1, record.get("pages", 1) * 2 - 1)
            self._set_stage(document_id, stage, **updates)

    def _run_docling(self, document_id: str, ocr_engine: str) -> None:
        from .docling_chunking import chunk_document
        from .run_artifacts import (
            append_run_error,
            copy_page_markdown_checkpoints,
            create_run_directory,
            finalize_run_directory,
        )
        from .visual_processing import (
            make_bedrock_vision_describer,
            make_nous_deepseek_markdown_extractor,
            make_nous_deepseek_vision_describer,
            extract_split_pdf_markdown,
        )

        self._set_stage(document_id, "uploading")
        self._set_stage(document_id, "extracting")
        record = self.store.get(document_id)
        directory = self.store.directory(document_id)
        source = self.store.source_path(record)
        previous_run = record.get("runDirectory")
        run_id, run_dir = create_run_directory(
            self.store.root / "runs",
            filename=record["filename"],
            source=source,
            ocr_engine=ocr_engine,
            prepared_pages=self.store.pages_directory(document_id),
        )
        if isinstance(previous_run, str):
            copy_page_markdown_checkpoints(
                self.store.root / previous_run,
                run_dir,
                ocr_engine=ocr_engine,
            )
        record = self.store.save({
            **record,
            "ocrEngine": ocr_engine,
            "runId": run_id,
            "runDirectory": str(run_dir.relative_to(self.store.root)),
        })
        from .docling_preextract import preextract_docling_pages

        total_docling_pages = len(list((run_dir / "pages").glob("page-*/source.pdf")))
        self.store.save({
            **self.store.get(document_id),
            "llamaparseStatus": {
                "phase": "docling",
                "total": total_docling_pages,
                "doclingProcessed": 0,
                "doclingAccepted": 0,
                "fallbackTotal": 0,
                "submitted": 0,
                "completed": 0,
                "failed": 0,
                "pages": {},
            },
        })

        def update_docling_start(page_number: int, processed: int, total: int) -> None:
            current = self.store.get(document_id)
            tracker = dict(current.get("llamaparseStatus") or {})
            page_states = dict(tracker.get("pages") or {})
            page_states[str(page_number)] = {
                "status": "processing",
                "jobId": None,
                "message": "Docling is extracting this single-page PDF",
            }
            tracker.update({
                "phase": "docling",
                "total": total,
                "doclingProcessed": processed - 1,
                "currentPage": page_number,
                "pages": page_states,
            })
            self.store.save({**current, "llamaparseStatus": tracker})

        def update_docling_status(
            page_number: int,
            decision: dict[str, Any],
            processed: int,
            total: int,
        ) -> None:
            current = self.store.get(document_id)
            tracker = dict(current.get("llamaparseStatus") or {})
            page_states = dict(tracker.get("pages") or {})
            page_states[str(page_number)] = {
                "status": "docling" if decision["accepted"] else "fallback",
                "jobId": None,
                "message": (
                    "Docling quality gate accepted this page"
                    if decision["accepted"]
                    else "Page requires configured fallback extraction"
                ),
            }
            states = [item.get("status") for item in page_states.values()]
            tracker.update({
                "phase": "docling",
                "total": total,
                "doclingProcessed": processed,
                "doclingAccepted": states.count("docling"),
                "fallbackTotal": states.count("fallback"),
                "currentPage": page_number,
                "pages": page_states,
            })
            self.store.save({**current, "llamaparseStatus": tracker})

        docling_preflight = preextract_docling_pages(
            source,
            run_dir / "pages",
            on_page_start=update_docling_start,
            on_page=update_docling_status,
        )
        fallback_pages = set(docling_preflight["fallback_pages"])
        record = self.store.save({
            **self.store.get(document_id),
            "doclingPreflight": {
                "total": docling_preflight["page_count"],
                "accepted": docling_preflight["accepted_pages"],
                "fallback": len(fallback_pages),
            },
        })
        nous_key = os.environ.get("NOUS_API_KEY") or os.environ.get("NOUS_KEY")
        bedrock_model = os.environ.get("BEDROCK_VISION_MODEL_ID")
        page_overrides: dict[int, str] | None = None
        if ocr_engine == "deepseek":
            if fallback_pages and not nous_key:
                raise RuntimeError(
                    "NOUS_API_KEY (or NOUS_KEY) is required for DeepSeek extraction"
                )
            nous_model = os.environ.get(
                "NOUS_VISION_MODEL",
                "deepseek/deepseek-v4.1-flash-1017",
            )
            describer = (
                make_nous_deepseek_vision_describer(nous_key, model_id=nous_model)
                if nous_key
                else None
            )
            if fallback_pages:
                page_extractor = make_nous_deepseek_markdown_extractor(
                    nous_key,
                    model_id=nous_model,
                )
                page_overrides = extract_split_pdf_markdown(
                    run_dir / "pages",
                    page_extractor,
                    output_filename=f"{ocr_engine}.md",
                    include_pages=fallback_pages,
                    on_error=lambda page_number, error: append_run_error(
                        run_dir,
                        document_id=document_id,
                        stage=f"extracting:page-{page_number:03d}",
                        ocr_engine=ocr_engine,
                        error=RuntimeError(
                            f"OCR extraction failed for page-{page_number:03d}: {error}"
                        ),
                    ),
                )
            else:
                page_overrides = {}
            page_extractor = None
        elif ocr_engine == "llamaparse":
            from .llamaparse_extraction import extract_llamaparse_split_pages

            llama_key = os.environ.get("LLAMA_CLOUD_API_KEY", "")
            total_pages = len(list((run_dir / "pages").glob("page-*/source.pdf")))
            accepted_pages = set(range(1, total_pages + 1)) - fallback_pages
            self.store.save({
                **self.store.get(document_id),
                "llamaparseStatus": {
                    "phase": "fallback",
                    "total": total_pages,
                    "doclingAccepted": len(accepted_pages),
                    "fallbackTotal": len(fallback_pages),
                    "submitted": 0,
                    "completed": 0,
                    "failed": 0,
                    "pages": {
                        str(page_number): {
                            "status": "docling",
                            "jobId": None,
                            "message": "Docling quality gate accepted this page",
                        }
                        for page_number in accepted_pages
                    },
                },
            })

            def update_llamaparse_status(
                page_number: int,
                status: str,
                job_id: str | None,
                message: str | None,
            ) -> None:
                current = self.store.get(document_id)
                tracker = dict(current.get("llamaparseStatus") or {})
                page_states = dict(tracker.get("pages") or {})
                page_states[str(page_number)] = {
                    "status": status,
                    "jobId": job_id,
                    "message": message,
                }
                states = [item.get("status") for item in page_states.values()]
                tracker.update({
                    "total": total_pages,
                    "submitted": sum(item in {"submitted", "completed", "failed"} for item in states),
                    "completed": states.count("completed"),
                    "failed": states.count("failed"),
                    "doclingAccepted": states.count("docling"),
                    "fallbackTotal": len(fallback_pages),
                    "currentPage": page_number,
                    "pages": page_states,
                })
                self.store.save({**current, "llamaparseStatus": tracker})
                if status == "failed":
                    append_run_error(
                        run_dir,
                        document_id=document_id,
                        stage=f"extracting:page-{page_number:03d}",
                        ocr_engine=ocr_engine,
                        error=RuntimeError(message or "LlamaParse page extraction failed"),
                    )

            page_overrides = (
                extract_llamaparse_split_pages(
                    run_dir / "pages",
                    api_key=llama_key,
                    tier=os.environ.get("LLAMAPARSE_TIER", "agentic"),
                    on_status=update_llamaparse_status,
                    include_pages=fallback_pages,
                )
                if fallback_pages
                else {}
            )
            describer = None
            page_extractor = None
        else:
            raise ValueError(f"Unsupported OCR engine: {ocr_engine}")
        if bedrock_model and describer is None:
            describer = make_bedrock_vision_describer(
                bedrock_model,
                region_name=os.environ.get("AWS_REGION"),
            )
        result = chunk_document(
            source,
            directory / "chunks.jsonl",
            describe_figure=describer,
            extract_page_markdown=page_extractor,
            page_markdown_engine=ocr_engine,
            page_markdown_overrides=page_overrides,
        )
        if result["pages"].get("page_count", 0) == 0:
            raise RuntimeError("Docling produced no page Markdown; inspect pages/manifest.json")
        finalize_run_directory(
            run_dir,
            working_dir=directory,
            source=source,
            record=record,
            result=result,
            ocr_engine=ocr_engine,
        )
        markdown = (directory / "document.md").read_text(encoding="utf-8")
        self._set_stage(document_id, "routing")
        classification = result.get("classification") or classify_document(
            record["filename"], markdown
        )
        route = classification["route"]
        common = {
            "isPolicy": classification["is_policy"],
            "route": route,
            "classification": classification,
            "chunks": result["chunks"],
            "tables": result["visuals"]["table_count"],
            "figures": result["visuals"]["figure_count"],
            "reviewIssues": (
                result["visuals"]["issue_count"]
                + result["pages"]["issue_count"]
            ),
            "visualManifest": "visuals/manifest.json",
            "pageManifest": "pages/manifest.json",
            "deepseekPages": result["pages"]["deepseek_pages"],
            "llamaparsePages": result["pages"].get("llamaparse_pages", 0),
            "ocrPages": result["pages"].get("ocr_pages", 0),
            "ocrEngine": ocr_engine,
            "runId": run_id,
            "runDirectory": str(run_dir.relative_to(self.store.root)),
        }
        if route == "whole_document_context":
            context_model = os.environ.get("BEDROCK_CONTEXT_MODEL_ID")
            if not context_model:
                self._set_stage(
                    document_id,
                    "complete",
                    **common,
                    storageStrategy="whole_document",
                    contextStatus="pending_model_configuration",
                )
                return
            from .whole_document_context import contextualize_whole_document_file

            self._set_stage(document_id, "embedding", **common)
            context_result = contextualize_whole_document_file(
                chunks_path=directory / "chunks.jsonl",
                output_path=directory / "whole-document-context.jsonl",
                context_model=context_model,
                region_name=os.environ.get("AWS_REGION"),
            )
            self._set_stage(
                document_id,
                "indexing",
                **common,
                storageStrategy="whole_document",
                contextStatus="summarized_and_embedded",
                contextArtifact="whole-document-context.jsonl",
                embeddingDimensions=context_result["embedding_dimensions"],
            )
            self._set_stage(
                document_id,
                "complete",
                **common,
                storageStrategy="whole_document",
                contextStatus="summarized_and_embedded",
                contextArtifact="whole-document-context.jsonl",
                embeddingDimensions=context_result["embedding_dimensions"],
            )
            return
        if not classification["is_policy"]:
            self._set_stage(document_id, "complete", **common)
            return
        self._set_stage(document_id, "reviewing", **common)
        if common["reviewIssues"]:
            record = self.store.get(document_id)
            self.store.save({**record, "status": "needs_review"})
            return
        # Bedrock contextualization and managed indexing remain AWS integration boundaries.
        for stage in ("embedding", "indexing", "complete"):
            self._set_stage(document_id, stage, **common)


class ContextualRetrievalManager:
    """Runs one page-at-a-time Claude contextualization outside ingestion jobs."""

    def __init__(
        self,
        store: DocumentStore,
        *,
        generate_context: Any | None = None,
        generate_form_context: Any | None = None,
        embed_form_text: Any | None = None,
    ) -> None:
        self.store = store
        self.generate_context = generate_context
        self.generate_form_context = generate_form_context
        self.embed_form_text = embed_form_text
        self.executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="contextual-retrieval",
        )
        self._active: set[str] = set()
        self._lock = threading.Lock()

    def output_directory(self, document_id: str) -> Path:
        return self.store.directory(document_id) / "contextual-retrieval"

    def pages_directory(self, record: dict[str, Any]) -> Path:
        document_pages = self.store.pages_directory(record["id"])
        candidates = [document_pages]
        run_directory = record.get("runDirectory")
        if isinstance(run_directory, str):
            run_pages = self.store.root / run_directory / "pages"
            if run_pages.is_dir() and any(run_pages.glob("page-*/*.md")):
                candidates.append(run_pages)

        def extracted_page_count(pages_dir: Path) -> int:
            return sum(
                1
                for page_dir in pages_dir.glob("page-[0-9][0-9][0-9]")
                if any(page_dir.glob("*.md"))
            )

        # A retry run may contain only a partial snapshot while the stable
        # document directory has since been completed by the resumable Docling
        # pass.  Always use the most complete set of page checkpoints so source
        # artifact paths and contextual-retrieval page counts stay aligned.
        return max(candidates, key=extracted_page_count)

    def submit(self, document_id: str) -> bool:
        from .form_contextual_retrieval import assemble_whole_form
        from .page_contextual_retrieval import discover_page_chunks

        record = self.store.get(document_id)
        if record.get("route") == "whole_document_context":
            assemble_whole_form(
                self.pages_directory(record),
                preferred_engine=record.get("ocrEngine"),
            )
        else:
            chunks = discover_page_chunks(
                self.pages_directory(record),
                preferred_engine=record.get("ocrEngine"),
            )
            if not chunks:
                raise ValueError(
                    "No extracted page Markdown is available; finish page extraction first"
                )
        with self._lock:
            if document_id in self._active:
                return False
            self._active.add(document_id)
        self.executor.submit(self._run_guarded, document_id)
        return True

    def _run_guarded(self, document_id: str) -> None:
        from .page_contextual_retrieval import (
            CLAUDE_MODEL,
            contextualize_pages,
            read_contextual_status,
        )

        output_dir = self.output_directory(document_id)
        try:
            record = self.store.get(document_id)
            if record.get("route") == "whole_document_context":
                from .form_contextual_retrieval import (
                    FormVectorStore,
                    contextualize_whole_form,
                )

                result = contextualize_whole_form(
                    document_id=document_id,
                    filename=record["filename"],
                    document_dir=self.store.directory(document_id),
                    pages_dir=self.pages_directory(record),
                    output_dir=output_dir,
                    vector_store=FormVectorStore(
                        self.store.root / "vector-db" / "forms.sqlite3"
                    ),
                    preferred_engine=record.get("ocrEngine"),
                    context_model=os.environ.get(
                        "ANTHROPIC_CONTEXT_MODEL", CLAUDE_MODEL
                    ),
                    embedding_model=os.environ.get(
                        "FORM_EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"
                    ),
                    generate_context=self.generate_form_context,
                    embed_text=self.embed_form_text,
                )
                current = self.store.get(document_id)
                self.store.save({
                    **current,
                    "storageStrategy": "whole_document",
                    "retrievalUnits": 1,
                    "chunks": 1,
                    "contextStatus": "summarized_and_embedded",
                    "contextArtifact": str(
                        Path(result["context_artifact"]).relative_to(
                            self.store.directory(document_id)
                        )
                    ),
                    "vectorDatabase": result["vector_database"],
                    "sourceArtifact": "source.pdf",
                    "embeddingDimensions": result["embedding_dimensions"],
                })
            else:
                result = contextualize_pages(
                    document_id=document_id,
                    filename=record["filename"],
                    pages_dir=self.pages_directory(record),
                    output_dir=output_dir,
                    preferred_engine=record.get("ocrEngine"),
                    model=os.environ.get("ANTHROPIC_CONTEXT_MODEL", CLAUDE_MODEL),
                    generate_context=self.generate_context,
                )
                current = self.store.get(document_id)
                self.store.save({
                    **current,
                    "contextStatus": "contextualized",
                    "contextArtifact": str(
                        self.output_directory(document_id)
                        .joinpath("contextual-pages.jsonl")
                        .relative_to(self.store.directory(document_id))
                    ),
                    "chunks": result["completed_pages"],
                    "retrievalUnits": result["completed_pages"],
                })
        except Exception as error:
            from .page_contextual_retrieval import _write_json_atomic

            status = read_contextual_status(output_dir) or {
                "schema_version": "1.0",
                "document_id": document_id,
                "total_pages": 0,
                "completed_pages": 0,
                "pages": [],
            }
            _write_json_atomic(output_dir / "contextual-retrieval.json", {
                **status,
                "status": "failed",
                "error": f"{type(error).__name__}: {error}",
                "updated_at": utc_now(),
            })
        finally:
            with self._lock:
                self._active.discard(document_id)

    def status(self, document_id: str) -> dict[str, Any]:
        from .form_contextual_retrieval import assemble_whole_form
        from .page_contextual_retrieval import (
            CLAUDE_MODEL,
            PROMPT_VERSION,
            discover_page_chunks,
            read_contextual_status,
        )

        record = self.store.get(document_id)
        persisted = read_contextual_status(self.output_directory(document_id))
        if persisted:
            return persisted
        if record.get("route") == "whole_document_context":
            try:
                _document, source_pages = assemble_whole_form(
                    self.pages_directory(record),
                    preferred_engine=record.get("ocrEngine"),
                )
            except ValueError:
                source_pages = []
            source_path = self.store.source_path(record)
            return {
                "schema_version": "1.0",
                "status": "idle",
                "document_id": document_id,
                "filename": record["filename"],
                "model": os.environ.get("ANTHROPIC_CONTEXT_MODEL", CLAUDE_MODEL),
                "prompt_version": "anthropic-whole-form-context-v1",
                "storage_strategy": "whole_document",
                "source_page_count": len(source_pages),
                "retrieval_units": 1,
                "total_pages": 1 if source_pages else 0,
                "completed_pages": 0,
                "current_page": None,
                "error": None,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
                "source_path": str(source_path),
                "source_uri": f"/api/documents/{document_id}/source",
                "vector_database": str(
                    self.store.root / "vector-db" / "forms.sqlite3"
                ),
                "pages": [{
                    "page": 1,
                    "chunk_id": f"{document_id}:whole-document",
                    "source_markdown": "whole-document",
                    "status": "pending",
                    "contextualized_at": None,
                    "prompt_cache": {},
                }] if source_pages else [],
                "updated_at": None,
            }
        chunks = discover_page_chunks(
            self.pages_directory(record),
            preferred_engine=record.get("ocrEngine"),
        )
        return {
            "schema_version": "1.0",
            "status": "idle",
            "document_id": document_id,
            "filename": record["filename"],
            "model": os.environ.get("ANTHROPIC_CONTEXT_MODEL", CLAUDE_MODEL),
            "prompt_version": PROMPT_VERSION,
            "total_pages": len(chunks),
            "completed_pages": 0,
            "current_page": None,
            "error": None,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "pages": [{
                "page": chunk["page"],
                "chunk_id": chunk["chunk_id"],
                "source_markdown": chunk["source_markdown"],
                "status": "pending",
                "contextualized_at": None,
                "prompt_cache": {},
            } for chunk in chunks],
            "updated_at": None,
        }


class ContextualJudgeManager:
    """Runs a separate, resumable quality judgment over contextualized pages."""

    def __init__(self, store: DocumentStore, *, generate_judgment: Any | None = None) -> None:
        self.store = store
        self.generate_judgment = generate_judgment
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="contextual-judge")
        self._active: set[str] = set()
        self._lock = threading.Lock()

    def contextual_directory(self, document_id: str) -> Path:
        return self.store.directory(document_id) / "contextual-retrieval"

    def judge_directory(self, document_id: str) -> Path:
        return self.contextual_directory(document_id) / "judge"

    def submit(self, document_id: str) -> bool:
        record = self.store.get(document_id)
        if record.get("route") == "whole_document_context":
            raise ValueError("Page judge is available for page-level retrieval documents only")
        if not (self.contextual_directory(document_id) / "contextual-pages.jsonl").is_file():
            raise ValueError("Finish contextual retrieval before running the judge")
        with self._lock:
            if document_id in self._active:
                return False
            self._active.add(document_id)
        self.executor.submit(self._run_guarded, document_id)
        return True

    def _run_guarded(self, document_id: str) -> None:
        from .contextual_judge import (
            JUDGE_MODEL,
            judge_contextual_pages,
            read_judge_status,
        )
        try:
            result = judge_contextual_pages(
                document_id=document_id,
                contextual_dir=self.contextual_directory(document_id),
                model=os.environ.get("ANTHROPIC_JUDGE_MODEL", JUDGE_MODEL),
                generate_judgment=self.generate_judgment,
            )
            current = self.store.get(document_id)
            self.store.save({
                **current,
                "contextStatus": "judged",
                "judgeArtifact": str(
                    self.judge_directory(document_id)
                    .joinpath("judgments.jsonl")
                    .relative_to(self.store.directory(document_id))
                ),
                "judgedPages": result["completed_pages"],
                "judgeCounts": result["counts"],
            })
        except Exception as error:
            from .contextual_judge import _write_json_atomic

            current = read_judge_status(self.judge_directory(document_id)) or self.status(document_id)
            _write_json_atomic(self.judge_directory(document_id) / "status.json", {
                **current,
                "status": "failed",
                "error": f"{type(error).__name__}: {error}",
                "updated_at": utc_now(),
            })
        finally:
            with self._lock:
                self._active.discard(document_id)

    def status(self, document_id: str) -> dict[str, Any]:
        from .contextual_judge import JUDGE_MODEL, initial_judge_status, read_judge_status

        self.store.get(document_id)
        persisted = read_judge_status(self.judge_directory(document_id))
        if persisted:
            return persisted
        return initial_judge_status(
            self.contextual_directory(document_id),
            document_id=document_id,
            model=os.environ.get("ANTHROPIC_JUDGE_MODEL", JUDGE_MODEL),
        )


def format_duration(seconds: float) -> str:
    minutes, remainder = divmod(round(seconds), 60)
    return f"{minutes}m {remainder:02d}s"


class BatchResponse(BaseModel):
    submitted: int
    documentId: str | None = None


class RunRequest(BaseModel):
    ocr_engine: Literal["deepseek", "llamaparse"] = "deepseek"


class QueryRouterRequest(BaseModel):
    jsonl: str


class ContextualRetrievalRequest(BaseModel):
    confirm_cost: bool = False


def create_app(
    *,
    data_root: Path | None = None,
    mode: str | None = None,
    seed_test_pdfs: bool | None = None,
    contextual_generate_context: Any | None = None,
    contextual_generate_form_context: Any | None = None,
    contextual_embed_form_text: Any | None = None,
    contextual_generate_judgment: Any | None = None,
) -> FastAPI:
    root = data_root or Path(os.environ.get("AWS_WORKFLOW_DATA_DIR", DEFAULT_DATA_ROOT))
    store = DocumentStore(root.expanduser().resolve())
    processing_mode = mode or os.environ.get("AWS_WORKFLOW_PROCESSING_MODE", "docling")
    default_concurrency = "1" if processing_mode == "docling" else "3"
    manager = IngestionManager(
        store,
        mode=processing_mode,
        concurrency=int(os.environ.get("AWS_WORKFLOW_CONCURRENCY", default_concurrency)),
    )
    contextual_manager = ContextualRetrievalManager(
        store,
        generate_context=contextual_generate_context,
        generate_form_context=contextual_generate_form_context,
        embed_form_text=contextual_embed_form_text,
    )
    contextual_judge_manager = ContextualJudgeManager(
        store,
        generate_judgment=contextual_generate_judgment,
    )
    for record in store.list():
        if record.get("status") == "running":
            store.save({
                **record,
                "stage": "queued",
                "progress": 0,
                "status": "queued",
                "error": "Previous local worker was interrupted; ready to retry.",
            })
    should_seed = seed_test_pdfs if seed_test_pdfs is not None else os.environ.get("AWS_WORKFLOW_SEED_TEST_PDFS", "1") == "1"
    if should_seed:
        corpus = PROJECT_ROOT / "tests" / "documents"
        seed_corpus_documents(
            store,
            corpus,
            int(os.environ.get("AWS_WORKFLOW_SEED_LIMIT", DEFAULT_SEED_LIMIT)),
        )
    # Forms are identifiable from the six source filenames before extraction.
    # Mark their retrieval route immediately so the UI never represents them as
    # page chunks. Page PDFs remain OCR provenance only; retrieval has one unit.
    for record in store.list():
        classification = classify_document(record["filename"], "")
        if classification["route"] == "whole_document_context":
            store.save({
                **record,
                "route": "whole_document_context",
                "classification": classification,
                "storageStrategy": "whole_document",
                "retrievalUnits": 1,
                "chunks": 1,
                "sourceArtifact": "source.pdf",
            })
    # Do not expose the API/UI until every registered PDF has reusable,
    # deterministic single-page inputs. Extraction runs only consume these
    # prepared artifacts; they never split PDFs after the user clicks Run.
    for record in store.list():
        store.prepare_pages(record["id"])

    app = FastAPI(title="AWS Data Workflow", version="0.1.0")
    app.state.store = store
    app.state.manager = manager
    app.state.contextual_manager = contextual_manager
    app.state.contextual_judge_manager = contextual_judge_manager
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5175", "http://127.0.0.1:5175"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "processingMode": manager.mode, "dataRoot": str(store.root)}

    cluster_manifest = PROJECT_ROOT / "evals" / "cluster_manifest.json"

    @app.get("/api/clusters")
    def clusters() -> list[dict[str, Any]]:
        return load_clusters(cluster_manifest)

    @app.get("/api/query-examples")
    def query_examples(limit: int = 30) -> list[dict[str, Any]]:
        return load_query_examples(
            PROJECT_ROOT / "evals" / "generated" / "cluster_ragas_queries.jsonl",
            limit=limit,
        )

    @app.get("/api/vector-db/forms")
    def form_vector_records() -> list[dict[str, Any]]:
        from .form_contextual_retrieval import FormVectorStore

        return FormVectorStore(
            store.root / "vector-db" / "forms.sqlite3"
        ).list()

    @app.get("/api/query-router/runs")
    def query_router_runs(limit: int = 20) -> list[dict[str, Any]]:
        return list_router_runs(store.root, min(max(limit, 1), 100))

    @app.post("/api/query-router")
    def query_router(request: QueryRouterRequest) -> dict[str, Any]:
        result = route_jsonl(request.jsonl, cluster_manifest)
        if result["status"] == "failed":
            raise HTTPException(status_code=422, detail=result["error"])
        return save_router_run(store.root, request.jsonl, result)

    @app.get("/api/documents")
    def documents() -> list[dict[str, Any]]:
        return [store.with_extraction_summary(record) for record in store.list()]

    @app.get("/api/documents/{document_id}")
    def document(document_id: str) -> dict[str, Any]:
        try:
            return store.with_extraction_summary(store.get(document_id))
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Document not found") from error

    @app.get("/api/documents/{document_id}/contextual-retrieval")
    def contextual_retrieval_status(document_id: str) -> dict[str, Any]:
        try:
            return contextual_manager.status(document_id)
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.post(
        "/api/documents/{document_id}/contextual-retrieval/run",
        status_code=202,
    )
    def run_contextual_retrieval(
        document_id: str,
        request: ContextualRetrievalRequest,
    ) -> dict[str, Any]:
        if not request.confirm_cost:
            raise HTTPException(
                status_code=400,
                detail="Confirm one paid Claude request per uncached page",
            )
        try:
            submitted = contextual_manager.submit(document_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Document not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {"submitted": submitted, "documentId": document_id}

    @app.get("/api/documents/{document_id}/contextual-retrieval/pages/{page_number}")
    def contextual_retrieval_page(
        document_id: str,
        page_number: int,
    ) -> dict[str, Any]:
        from .page_contextual_retrieval import read_contextual_page

        if page_number < 1:
            raise HTTPException(status_code=404, detail="Contextual page not found")
        try:
            document_record = store.get(document_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Document not found") from error
        if document_record.get("route") == "whole_document_context":
            path = (
                contextual_manager.output_directory(document_id)
                / "whole-document-context.jsonl"
            )
            if page_number != 1 or not path.is_file():
                raise HTTPException(status_code=404, detail="Contextual page not found")
            lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line]
            if len(lines) != 1:
                raise HTTPException(status_code=404, detail="Contextual page not found")
            result = json.loads(lines[0])
            return {**result, "page": 1}
        record = read_contextual_page(
            contextual_manager.output_directory(document_id),
            page_number,
        )
        if record is None:
            raise HTTPException(status_code=404, detail="Contextual page not found")
        return record

    @app.get(
        "/api/documents/{document_id}/contextual-retrieval/pages/{page_number}/source"
    )
    def contextual_retrieval_page_source(
        document_id: str,
        page_number: int,
    ) -> FileResponse:
        from .page_contextual_retrieval import discover_page_chunks

        if page_number < 1:
            raise HTTPException(status_code=404, detail="Extracted page source not found")
        try:
            document_record = store.get(document_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Document not found") from error
        pages_dir = contextual_manager.pages_directory(document_record)
        chunk = next(
            (
                item
                for item in discover_page_chunks(
                    pages_dir,
                    preferred_engine=document_record.get("ocrEngine"),
                )
                if item["page"] == page_number
            ),
            None,
        )
        if chunk is None:
            raise HTTPException(status_code=404, detail="Extracted page source not found")
        path = (pages_dir.parent / chunk["source_markdown"]).resolve()
        try:
            path.relative_to(pages_dir.parent.resolve())
        except ValueError as error:
            raise HTTPException(
                status_code=404, detail="Extracted page source not found"
            ) from error
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Extracted page source not found")
        return FileResponse(path, media_type="text/markdown; charset=utf-8")

    @app.get("/api/documents/{document_id}/contextual-retrieval/judge")
    def contextual_judge_status(document_id: str) -> dict[str, Any]:
        try:
            return contextual_judge_manager.status(document_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Document not found") from error

    @app.post(
        "/api/documents/{document_id}/contextual-retrieval/judge/run",
        status_code=202,
    )
    def run_contextual_judge(
        document_id: str,
        request: ContextualRetrievalRequest,
    ) -> dict[str, Any]:
        if not request.confirm_cost:
            raise HTTPException(
                status_code=400,
                detail="Confirm one paid judge request per uncached contextual page",
            )
        try:
            submitted = contextual_judge_manager.submit(document_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Document not found") from error
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {"submitted": submitted, "documentId": document_id}

    @app.get(
        "/api/documents/{document_id}/contextual-retrieval/judge/pages/{page_number}"
    )
    def contextual_judgment(
        document_id: str,
        page_number: int,
    ) -> dict[str, Any]:
        from .contextual_judge import read_judgment

        try:
            store.get(document_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Document not found") from error
        record = read_judgment(
            contextual_judge_manager.judge_directory(document_id),
            page_number,
        )
        if record is None:
            raise HTTPException(status_code=404, detail="Page judgment not found")
        return record

    @app.get("/api/documents/{document_id}/source")
    def source(document_id: str) -> FileResponse:
        try:
            record = store.get(document_id)
            path = store.source_path(record)
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Document not found") from error
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=record["filename"],
            content_disposition_type="inline",
        )

    @app.get("/api/documents/{document_id}/runs")
    def document_runs(document_id: str) -> list[dict[str, Any]]:
        try:
            return store.runs(document_id)
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Document not found") from error

    @app.get("/api/documents/{document_id}/runs/{run_id}/source")
    def run_source(document_id: str, run_id: str) -> FileResponse:
        try:
            record = store.get(document_id)
            path = store.run_directory(document_id, run_id) / "input" / "source.pdf"
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Run not found") from error
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Run source not found")
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=record["filename"],
            content_disposition_type="inline",
        )

    @app.get("/api/documents/{document_id}/runs/{run_id}/page-manifest")
    def run_page_manifest(document_id: str, run_id: str) -> dict[str, Any]:
        try:
            run_dir = store.run_directory(document_id, run_id)
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Run not found") from error
        pages: list[dict[str, Any]] = []
        for path in sorted((run_dir / "pages").glob("page-*/page-manifest.json")):
            try:
                pages.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        try:
            record = store.get(document_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Document not found") from error
        ocr_engine = str(record.get("ocrEngine") or "deepseek")
        if not pages:
            for source_pdf in sorted((run_dir / "pages").glob("page-*/source.pdf")):
                page_dir = source_pdf.parent
                page_number = int(page_dir.name.removeprefix("page-"))
                deepseek = page_dir / "deepseek.md"
                llamaparse = page_dir / "llamaparse.md"
                docling = page_dir / "docling.md"
                selected = llamaparse if ocr_engine == "llamaparse" else deepseek
                pages.append({
                    "page": page_number,
                    "source_image": None,
                    "docling_markdown": f"{page_dir.name}/docling.md" if docling.is_file() else None,
                    "deepseek_markdown": f"{page_dir.name}/deepseek.md" if deepseek.is_file() else None,
                    "llamaparse_markdown": f"{page_dir.name}/llamaparse.md" if llamaparse.is_file() else None,
                    "ocr_engine": ocr_engine,
                    "ocr_markdown": f"{page_dir.name}/{ocr_engine}.md" if selected.is_file() else None,
                    "markdown_source": ocr_engine if selected.is_file() else None,
                    "issues": [],
                })
        if not pages:
            raise HTTPException(status_code=404, detail="Run has no prepared pages")
        ocr_engine = str(pages[0].get("ocr_engine", ocr_engine))
        return {
            "schema_version": "1.0",
            "pages": pages,
            "summary": {
                "page_count": len(pages),
                "deepseek_pages": sum(bool(item.get("deepseek_markdown")) for item in pages),
                "llamaparse_pages": sum(bool(item.get("llamaparse_markdown")) for item in pages),
                "ocr_pages": sum(bool(item.get("ocr_markdown")) for item in pages),
                "ocr_engine": ocr_engine,
                "issue_count": sum(len(item.get("issues", [])) for item in pages),
            },
        }

    @app.get("/api/documents/{document_id}/runs/{run_id}/pages/{page_number}/source")
    def run_page_source(document_id: str, run_id: str, page_number: int) -> FileResponse:
        if page_number < 1:
            raise HTTPException(status_code=404, detail="Page not found")
        try:
            run_dir = store.run_directory(document_id, run_id)
            path = run_dir / "pages" / f"page-{page_number:03d}" / "source.pdf"
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Page not found") from error
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Page not found")
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=f"page-{page_number:03d}.pdf",
            content_disposition_type="inline",
        )

    @app.get("/api/documents/{document_id}/runs/{run_id}/artifacts/{artifact_path:path}")
    def run_artifact(document_id: str, run_id: str, artifact_path: str) -> FileResponse:
        try:
            directory = store.run_directory(document_id, run_id)
            path = (directory / artifact_path).resolve()
            path.relative_to(directory)
        except (KeyError, ValueError, OSError) as error:
            raise HTTPException(status_code=404, detail="Run artifact not found") from error
        if not path.is_file() or path.name == "source.pdf":
            raise HTTPException(status_code=404, detail="Run artifact not found")
        return FileResponse(path)

    @app.get("/api/documents/{document_id}/artifacts/{artifact_path:path}")
    def artifact(document_id: str, artifact_path: str) -> FileResponse:
        try:
            directory = store.directory(document_id).resolve()
            path = (directory / artifact_path).resolve()
            path.relative_to(directory)
        except (ValueError, OSError) as error:
            raise HTTPException(status_code=404, detail="Artifact not found") from error
        if not path.is_file() or path.name == "source.pdf":
            raise HTTPException(status_code=404, detail="Artifact not found")
        return FileResponse(path)

    @app.post("/api/documents", status_code=201)
    def upload_documents(files: list[UploadFile] = File(...)) -> list[dict[str, Any]]:
        records = []
        for upload in files:
            try:
                record = store.create_upload(upload)
                classification = classify_document(record["filename"], "")
                if classification["route"] == "whole_document_context":
                    record = store.save({
                        **record,
                        "route": "whole_document_context",
                        "classification": classification,
                        "storageStrategy": "whole_document",
                        "retrievalUnits": 1,
                        "chunks": 1,
                        "sourceArtifact": "source.pdf",
                    })
                records.append(record)
            except ValueError as error:
                raise HTTPException(status_code=400, detail=str(error)) from error
            finally:
                upload.file.close()
        return records

    @app.post("/api/documents/{document_id}/run", status_code=202)
    def run_document(
        document_id: str,
        request: RunRequest | None = None,
    ) -> dict[str, Any]:
        try:
            submitted = manager.submit(
                document_id,
                ocr_engine=(request or RunRequest()).ocr_engine,
            )
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Document not found") from error
        return {"submitted": submitted, "documentId": document_id}

    @app.post("/api/documents/{document_id}/retry", status_code=202)
    def retry_document(document_id: str) -> dict[str, Any]:
        try:
            record = store.get(document_id)
            store.save({**record, "stage": "queued", "progress": 0, "status": "queued", "error": None})
            submitted = manager.submit(document_id)
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=404, detail="Document not found") from error
        return {"submitted": submitted, "documentId": document_id}

    @app.post("/api/jobs/run-next", status_code=202, response_model=BatchResponse)
    def run_next(request: RunRequest | None = None) -> BatchResponse:
        selected = request or RunRequest()
        document_id = manager.submit_next(ocr_engine=selected.ocr_engine)
        return BatchResponse(
            submitted=int(document_id is not None),
            documentId=document_id,
        )

    web_dist = PROJECT_ROOT / "web" / "dist"
    if web_dist.is_dir():
        app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")
    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("aws_data_workflow.server:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
