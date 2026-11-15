"""Serve a one-page PDF beside its managed Unstructured API extraction."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any, Literal

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .client import DEFAULT_API_URL, ExtractionError, extract_document

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DOCUMENT = Path(
    "/Users/dc/geha/crawl_dir/runs/research/"
    "ey-limra-workforce-benefits-study-final-2025/"
    "agent-demo-20261010T125607Z-e93043/pages/page-001/source.pdf"
)
UI_DIST = PROJECT_ROOT / "ui" / "dist"
RESULTS_DIR = PROJECT_ROOT / "results"


class ExtractionRequest(BaseModel):
    strategy: Literal["auto", "fast", "hi_res", "ocr_only", "vlm"] = "hi_res"
    infer_table_structure: bool = True
    force: bool = False


def configured_document() -> Path:
    return Path(os.getenv("UNSTRUCTURED_TEST_DOCUMENT", str(DEFAULT_DOCUMENT))).expanduser().resolve()


def _cache_path(document: Path, request: ExtractionRequest) -> Path:
    stat = document.stat()
    identity = (
        f"{document}:{stat.st_size}:{stat.st_mtime_ns}:"
        f"{request.strategy}:{request.infer_table_structure}"
    )
    digest = hashlib.sha256(identity.encode()).hexdigest()[:16]
    return RESULTS_DIR / f"{document.stem}-{request.strategy}-{digest}.json"


def _response_payload(
    elements: list[dict[str, Any]], *, elapsed_seconds: float, cached: bool, strategy: str
) -> dict[str, Any]:
    counts = Counter(str(element.get("type", "Unknown")) for element in elements)
    return {
        "elements": elements,
        "summary": {
            "element_count": len(elements),
            "type_counts": dict(sorted(counts.items())),
            "elapsed_seconds": round(elapsed_seconds, 3),
            "cached": cached,
            "strategy": strategy,
        },
    }


def create_app() -> FastAPI:
    load_dotenv(PROJECT_ROOT / ".env")
    app = FastAPI(title="Unstructured Cloud Extraction Compare")

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/document")
    def document_info() -> dict[str, Any]:
        document = configured_document()
        if not document.is_file():
            raise HTTPException(status_code=404, detail=f"Configured PDF not found: {document}")
        return {
            "filename": document.name,
            "size_bytes": document.stat().st_size,
            "page_count": 1,
            "source_url": "/api/source.pdf",
        }

    @app.get("/api/source.pdf", response_class=FileResponse)
    def source_pdf() -> FileResponse:
        document = configured_document()
        if not document.is_file():
            raise HTTPException(status_code=404, detail=f"Configured PDF not found: {document}")
        return FileResponse(
            document,
            media_type="application/pdf",
            filename=document.name,
            content_disposition_type="inline",
        )

    @app.post("/api/extract")
    async def extract(request: ExtractionRequest) -> dict[str, Any]:
        document = configured_document()
        if not document.is_file():
            raise HTTPException(status_code=404, detail=f"Configured PDF not found: {document}")

        cache_path = _cache_path(document, request)
        if cache_path.is_file() and not request.force:
            elements = json.loads(cache_path.read_text(encoding="utf-8"))
            return _response_payload(
                elements, elapsed_seconds=0, cached=True, strategy=request.strategy
            )

        api_key = os.getenv("UNSTRUCTURED_API_KEY", "").strip()
        if not api_key:
            raise HTTPException(
                status_code=503,
                detail="Set UNSTRUCTURED_API_KEY in .env before running cloud extraction.",
            )

        started = time.perf_counter()
        try:
            elements = await run_in_threadpool(
                extract_document,
                document,
                api_key=api_key,
                api_url=os.getenv("UNSTRUCTURED_API_URL", DEFAULT_API_URL),
                strategy=request.strategy,
                infer_table_structure=request.infer_table_structure,
            )
        except (ExtractionError, ValueError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(elements, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return _response_payload(
            elements,
            elapsed_seconds=time.perf_counter() - started,
            cached=False,
            strategy=request.strategy,
        )

    if UI_DIST.exists():
        app.mount("/assets", StaticFiles(directory=UI_DIST / "assets"), name="assets")

        @app.get("/{path:path}", response_class=FileResponse)
        def react_app(path: str) -> FileResponse:
            return FileResponse(UI_DIST / "index.html")

    return app


app = create_app()


def main() -> None:
    uvicorn.run(
        "unstructured_cloud_test.server:app",
        host=os.getenv("UNSTRUCTURED_UI_HOST", "127.0.0.1"),
        port=int(os.getenv("UNSTRUCTURED_UI_PORT", "8512")),
    )


if __name__ == "__main__":
    main()
