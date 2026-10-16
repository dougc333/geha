"""Local React dashboard backend for canonical corpus ingestion and contextual retrieval."""

from __future__ import annotations

import asyncio
import json
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiohttp import web

from crawl_dir.src.pipeline.claude_client import CLAUDE_MODEL, claude_credentials_available
from crawl_dir.src.pipeline.artifact_io import atomic_json
from crawl_dir.src.pipeline.contextual_retrieval import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    USER_TEMPLATE,
    contextualize_candidate,
    make_claude_context_generator,
)
from crawl_dir.src.process_all import process_all


ROOT = Path(__file__).resolve().parents[1] / "crawl_dir"
RUNS_ROOT = (ROOT / "runs").resolve()
RAW_ROOT = (ROOT / "raw" / "coverage-policies").resolve()
UI_DIST = Path(__file__).resolve().parent / "ui" / "dist"
CACHE_TEST_REPORT = RUNS_ROOT / "contextual-prompt-cache-test.json"
BATCH_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,79}$")
REACT_CONVERTED_DOCUMENTS = {
    "geha-coverage-policy-datroway.pdf",
    "geha-coverage-policy-elrexfio.pdf",
}
RECOMMENDED_DOCUMENT = "geha-coverage-policy-gemcitabine.pdf"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _source_documents() -> list[str]:
    return [str(path.relative_to(RAW_ROOT)) for path in sorted(RAW_ROOT.rglob("*.pdf"))]


def _latest_chunk_estimates() -> dict[str, int]:
    estimates: dict[str, int] = {}
    for source in sorted(RAW_ROOT.rglob("*.pdf")):
        source_key = str(source.relative_to(RAW_ROOT))
        document_id = "--".join(source.relative_to(RAW_ROOT).with_suffix("").parts)
        candidates = sorted(
            (RUNS_ROOT / "coverage-policies" / document_id).glob("*/candidate/chunks.jsonl"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            estimates[source_key] = len(_jsonl(candidates[0]))
        else:
            estimates[source_key] = 0
    return estimates


def _document_readiness() -> dict[str, dict[str, Any]]:
    readiness: dict[str, dict[str, Any]] = {}
    for source in sorted(RAW_ROOT.rglob("*.pdf")):
        source_key = str(source.relative_to(RAW_ROOT))
        document_id = "--".join(source.relative_to(RAW_ROOT).with_suffix("").parts)
        markdown = sorted(
            (RUNS_ROOT / "coverage-policies" / document_id).glob(
                "batch-*/candidate/document.md"
            ),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        valid = [path for path in markdown if path.stat().st_size > 0]
        readiness[source_key] = {
            "batch_markdown_available": bool(valid),
            "batch_markdown": str(valid[0]) if valid else None,
            "react_converted_source": source_key in REACT_CONVERTED_DOCUMENTS,
        }
    return readiness


def _cache_test_candidate() -> tuple[Path, str, list[dict[str, Any]]]:
    """Choose the smallest existing document safely above prompt-cache minimums."""
    candidates: list[tuple[int, Path, str, list[dict[str, Any]]]] = []
    for document_path in RUNS_ROOT.glob(
        "coverage-policies/*/*/candidate/document.md"
    ):
        if not document_path.parents[1].name.startswith("batch-"):
            continue
        chunks_path = document_path.parent / "chunks.jsonl"
        if not chunks_path.is_file():
            continue
        document = document_path.read_text(encoding="utf-8")
        chunks = _jsonl(chunks_path)
        if len(document) >= 8_000 and len(chunks) >= 2:
            candidates.append((len(document), document_path, document, chunks))
    if not candidates:
        raise FileNotFoundError(
            "No canonical candidate is long enough for a prompt-cache test"
        )
    _, path, document, chunks = min(candidates, key=lambda item: item[0])
    return path, document, chunks


def _run_cache_test() -> dict[str, Any]:
    path, document, chunks = _cache_test_candidate()
    generate = make_claude_context_generator(CLAUDE_MODEL)
    first = generate(document, chunks[0]["text"])
    second = generate(document, chunks[1]["text"])
    if isinstance(first, str) or isinstance(second, str):
        raise RuntimeError("Claude generator did not return cache telemetry")
    cache_was_available = (
        first["cache_creation_input_tokens"] > 0
        or first["cache_read_input_tokens"] > 0
    )
    passed = cache_was_available and second["cache_read_input_tokens"] > 0
    return {
        "passed": passed,
        "model": CLAUDE_MODEL,
        "document": str(path.relative_to(ROOT)),
        "document_chars": len(document),
        "prompt_version": PROMPT_VERSION,
        "cache_control": {"type": "ephemeral"},
        "first": {key: first[key] for key in (
            "input_tokens", "output_tokens", "cache_creation_input_tokens",
            "cache_read_input_tokens",
        )},
        "second": {key: second[key] for key in (
            "input_tokens", "output_tokens", "cache_creation_input_tokens",
            "cache_read_input_tokens",
        )},
        "explanation": (
            "PASS means the second request reported cache_read_input_tokens > 0. "
            "The entire <document> system block is the cache breakpoint."
        ),
    }


@dataclass
class DashboardRun:
    run_id: str
    events: list[dict[str, Any]] = field(default_factory=list)
    complete: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)

    def emit(self, event: dict[str, Any]) -> None:
        with self.lock:
            self.events.append({
                **event,
                "seq": len(self.events) + 1,
                "at": _utc_now(),
            })

    def finish(self) -> None:
        with self.lock:
            self.complete = True

    def snapshot(self, offset: int) -> tuple[list[dict[str, Any]], bool]:
        with self.lock:
            return self.events[offset:], self.complete


class Registry:
    def __init__(self) -> None:
        self._runs: dict[str, DashboardRun] = {}
        self._lock = threading.Lock()

    def create(self) -> DashboardRun:
        with self._lock:
            if any(not run.complete for run in self._runs.values()):
                raise RuntimeError("A corpus run is already active")
            run = DashboardRun(uuid.uuid4().hex)
            self._runs[run.run_id] = run
            return run

    def get(self, run_id: str) -> DashboardRun:
        try:
            return self._runs[run_id]
        except KeyError as exc:
            raise web.HTTPNotFound(text="Unknown dashboard run") from exc


REGISTRY = Registry()


class BatchWorker:
    def __init__(self, run: DashboardRun, config: dict[str, Any]) -> None:
        self.run = run
        self.config = config

    def execute(self) -> None:
        try:
            contextual_failures = 0
            contextual_documents = 0
            self.run.emit({
                "type": "contextual_batch_started",
                "total": 1 if self.config.get("document") else len(_source_documents()),
                "model": CLAUDE_MODEL,
            })

            def handle_canonical_event(event: dict[str, Any]) -> None:
                nonlocal contextual_failures, contextual_documents
                self.run.emit(event)
                if (
                    event.get("type") != "canonical_document_finished"
                    or event.get("status") == "failed"
                ):
                    return
                contextual_documents += 1
                run_dir = Path(str(event["run"]))
                markdown_path = run_dir / "candidate" / "document.md"
                if not markdown_path.is_file() or markdown_path.stat().st_size == 0:
                    contextual_failures += 1
                    self.run.emit({
                        "type": "contextual_document_failed",
                        "index": event.get("index"),
                        "total": event.get("total"),
                        "source": event["source"],
                        "run": str(run_dir),
                        "error_type": "MissingCanonicalMarkdown",
                        "error": "candidate/document.md is missing or empty; Claude was not called",
                    })
                    return
                self.run.emit({
                    "type": "canonical_markdown_verified",
                    "index": event.get("index"),
                    "total": event.get("total"),
                    "source": event["source"],
                    "run": str(run_dir),
                    "markdown": str(markdown_path),
                    "markdown_chars": len(markdown_path.read_text(encoding="utf-8")),
                })
                self.run.emit({
                    "type": "contextual_document_started",
                    "index": event.get("index"),
                    "total": event.get("total"),
                    "source": event["source"],
                    "run": str(run_dir),
                })
                try:
                    output = contextualize_candidate(
                        run_dir, model=CLAUDE_MODEL, event_sink=self.run.emit
                    )
                    count = len(_jsonl(output))
                    self.run.emit({
                        "type": "contextual_document_finished",
                        "index": event.get("index"),
                        "total": event.get("total"),
                        "source": event["source"],
                        "run": str(run_dir),
                        "chunks": count,
                    })
                except Exception as exc:  # preserve other documents and resumability
                    contextual_failures += 1
                    self.run.emit({
                        "type": "contextual_document_failed",
                        "index": event.get("index"),
                        "total": event.get("total"),
                        "source": event["source"],
                        "run": str(run_dir),
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    })

            report_path = process_all(
                root=ROOT,
                batch_id=self.config["batch_id"],
                document_version=self.config["document_version"],
                plan_year=self.config["plan_year"],
                families=["coverage-policies"],
                documents=[self.config["document"]] if self.config.get("document") else None,
                event_sink=handle_canonical_event,
            )
            self.run.emit({
                "type": "batch_finished",
                "batch_id": self.config["batch_id"],
                "documents": contextual_documents,
                "contextual_failures": contextual_failures,
                "report": str(report_path),
            })
        except Exception as exc:
            self.run.emit({
                "type": "batch_failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
            })
        finally:
            self.run.finish()


async def health(_: web.Request) -> web.Response:
    documents = _source_documents()
    chunk_estimates = _latest_chunk_estimates()
    readiness = _document_readiness()
    return web.json_response({
        "ready": claude_credentials_available(),
        "model": CLAUDE_MODEL,
        "source_documents": len(documents),
        "estimated_context_calls": sum(chunk_estimates.values()),
        "estimated_context_calls_by_document": chunk_estimates,
        "documents": documents,
        "document_readiness": readiness,
        "recommended_document": (
            RECOMMENDED_DOCUMENT
            if readiness.get(RECOMMENDED_DOCUMENT, {}).get("batch_markdown_available")
            else next(
                (document for document in documents
                 if readiness[document]["batch_markdown_available"]
                 and not readiness[document]["react_converted_source"]),
                "",
            )
        ),
        "canonical_chunker": "Docling HybridChunker / BAAI bge-small-en-v1.5 / 380-token body",
    })


async def prompt_contract(_: web.Request) -> web.Response:
    return web.json_response({
        "prompt_version": PROMPT_VERSION,
        "system_prompt": SYSTEM_PROMPT,
        "document_block": "<document>\n{{WHOLE_DOCUMENT}}\n</document>",
        "document_cache_control": {"type": "ephemeral"},
        "user_template": USER_TEMPLATE,
        "cache_scope": (
            "The complete document system block is reused across all chunk calls "
            "for that document; only the user chunk changes."
        ),
    })


async def test_prompt_cache(_: web.Request) -> web.Response:
    if not claude_credentials_available():
        raise web.HTTPConflict(text=json.dumps({
            "error": "Anthropic credentials are required for the live cache test."
        }), content_type="application/json")
    try:
        result = await asyncio.to_thread(_run_cache_test)
    except Exception as exc:
        raise web.HTTPBadGateway(text=json.dumps({
            "error": str(exc), "error_type": type(exc).__name__,
        }), content_type="application/json") from exc
    result["tested_at"] = _utc_now()
    atomic_json(CACHE_TEST_REPORT, result)
    return web.json_response(result)


async def last_prompt_cache_test(_: web.Request) -> web.Response:
    if not CACHE_TEST_REPORT.is_file():
        return web.json_response({"available": False})
    result = json.loads(CACHE_TEST_REPORT.read_text(encoding="utf-8"))
    return web.json_response({"available": True, **result})


async def start_batch(request: web.Request) -> web.Response:
    body = await request.json()
    if body.get("confirm_contextualization_cost") is not True:
        raise web.HTTPBadRequest(text=json.dumps({
            "error": "Confirm the one-Claude-call-per-chunk cost before starting."
        }), content_type="application/json")
    if not claude_credentials_available():
        raise web.HTTPConflict(text=json.dumps({
            "error": "Set ANTHROPIC_API_KEY or run `ant auth login` for the backend process."
        }), content_type="application/json")
    batch_id = str(body.get("batch_id", ""))
    if not BATCH_ID.fullmatch(batch_id):
        raise web.HTTPBadRequest(text=json.dumps({
            "error": "batch_id must be 3-80 letters, numbers, dots, underscores, or hyphens."
        }), content_type="application/json")
    selected_document = body.get("document")
    readiness = _document_readiness()
    if selected_document is not None:
        selected_document = str(selected_document)
        if selected_document not in _source_documents():
            raise web.HTTPBadRequest(text=json.dumps({
                "error": "document must be one of the 35 coverage-policy source PDFs"
            }), content_type="application/json")
        if not readiness[selected_document]["batch_markdown_available"]:
            raise web.HTTPConflict(text=json.dumps({
                "error": f"No non-empty canonical batch document.md exists for {selected_document}"
            }), content_type="application/json")
    else:
        missing_markdown = [
            document for document, state in readiness.items()
            if not state["batch_markdown_available"]
        ]
        if missing_markdown:
            raise web.HTTPConflict(text=json.dumps({
                "error": "Full-corpus run requires canonical batch Markdown for every source",
                "missing_document_md": missing_markdown,
            }), content_type="application/json")
    try:
        run = REGISTRY.create()
    except RuntimeError as exc:
        raise web.HTTPConflict(text=json.dumps({"error": str(exc)}),
                               content_type="application/json") from exc
    config = {
        "batch_id": batch_id,
        "document_version": str(body.get("document_version", "2026")),
        "plan_year": int(body.get("plan_year", 2026)),
        "document": selected_document,
    }
    thread = threading.Thread(
        target=BatchWorker(run, config).execute,
        name=f"contextual-{run.run_id}",
        daemon=True,
    )
    thread.start()
    return web.json_response({
        "run_id": run.run_id,
        "events": f"/api/batches/{run.run_id}/events",
    })


async def stream_events(request: web.Request) -> web.StreamResponse:
    run = REGISTRY.get(request.match_info["run_id"])
    response = web.StreamResponse(headers={
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })
    await response.prepare(request)
    offset = 0
    try:
        while True:
            events, complete = run.snapshot(offset)
            for event in events:
                await response.write(f"data: {json.dumps(event)}\n\n".encode())
                offset += 1
            if complete and not events:
                await response.write(b"event: end\ndata: {}\n\n")
                break
            await asyncio.sleep(0.2)
    except (ConnectionResetError, asyncio.CancelledError):
        pass
    return response


def _safe_run(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if path != RUNS_ROOT and RUNS_ROOT not in path.parents:
        raise web.HTTPForbidden(text="Run path is outside crawl_dir/runs")
    if not path.is_dir():
        raise web.HTTPNotFound(text="Run does not exist")
    return path


async def chunks(request: web.Request) -> web.Response:
    run = _safe_run(request.query.get("run", ""))
    canonical = _jsonl(run / "candidate" / "chunks.jsonl")
    contextual = {
        row["chunk_id"]: row
        for row in _jsonl(run / "candidate" / "contextual-chunks.jsonl")
    }
    pairs = []
    for chunk in canonical:
        enriched = contextual.get(chunk["chunk_id"], {})
        pairs.append({
            "chunk_id": chunk["chunk_id"],
            "pages": chunk.get("pages", []),
            "section": chunk.get("section"),
            "text": chunk.get("text", ""),
            "deterministic_contextualized_text": chunk.get("contextualized_text", ""),
            "retrieval_context": enriched.get("retrieval_context"),
            "contextual_retrieval_text": enriched.get("contextual_retrieval_text"),
            "model": enriched.get("contextual_retrieval_model"),
            "prompt_cache": enriched.get("prompt_cache"),
        })
    return web.json_response({
        "run": str(run),
        "document": run.name,
        "completed": len(contextual),
        "total": len(canonical),
        "chunks": pairs,
    })


async def index(_: web.Request) -> web.FileResponse:
    if not (UI_DIST / "index.html").is_file():
        raise web.HTTPServiceUnavailable(
            text="Build the dashboard UI first: cd contextual_retrieval_dashboard/ui && npm run build"
        )
    return web.FileResponse(UI_DIST / "index.html")


def create_app() -> web.Application:
    app = web.Application(client_max_size=1024 * 1024)
    app.router.add_get("/api/health", health)
    app.router.add_get("/api/prompt", prompt_contract)
    app.router.add_get("/api/prompt-cache-test", last_prompt_cache_test)
    app.router.add_post("/api/prompt-cache-test", test_prompt_cache)
    app.router.add_post("/api/batches", start_batch)
    app.router.add_get("/api/batches/{run_id}/events", stream_events)
    app.router.add_get("/api/chunks", chunks)
    if UI_DIST.exists():
        app.router.add_static("/assets", UI_DIST / "assets", show_index=False)
    app.router.add_get("/{tail:.*}", index)
    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="127.0.0.1", port=8511)
