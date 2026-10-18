from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pymupdf as fitz
from aiohttp import web


APP_DIR = Path(__file__).resolve().parent
REPO_DIR = APP_DIR.parents[1]
BOUNDING_BOX_DIR = APP_DIR.parent
CRAWL_DIR = REPO_DIR / "crawl_dir"
DOCUMENT_ID = "ey-limra-workforce-benefits-study-final-2025"
SOURCE_RELATIVE = Path("raw/research") / f"{DOCUMENT_ID}.pdf"
SOURCE_PDF = CRAWL_DIR / SOURCE_RELATIVE
ANNOTATIONS_DIR = BOUNDING_BOX_DIR / "annotations"
ANNOTATION_DIR = ANNOTATIONS_DIR / "research" / DOCUMENT_ID
ANNOTATION_PATH = ANNOTATION_DIR / "figure-bounding-boxes.json"
PROMPTS_PATH = ANNOTATION_DIR / "figure-reconstruction-prompts.json"
CACHE_DIR = APP_DIR / ".page-cache" / DOCUMENT_ID
UI_DIST = APP_DIR / "ui" / "dist"
COORDINATE_MAX = 1000
TITLE = "EY + LIMRA 2025 Workforce Benefits Study"
EXPECTED_PAGES: int | None = 29


def configure(pdf: Path, annotation_dir: Path | None = None) -> None:
    """Point the app at any PDF instead of the default EY study."""
    global DOCUMENT_ID, SOURCE_RELATIVE, SOURCE_PDF, ANNOTATION_DIR, ANNOTATION_PATH
    global PROMPTS_PATH, CACHE_DIR, TITLE, EXPECTED_PAGES
    SOURCE_PDF = pdf.resolve()
    if not SOURCE_PDF.is_file():
        raise RuntimeError(f"Source PDF not found: {SOURCE_PDF}")
    DOCUMENT_ID = SOURCE_PDF.stem
    try:
        SOURCE_RELATIVE = SOURCE_PDF.relative_to(CRAWL_DIR)
    except ValueError:
        SOURCE_RELATIVE = SOURCE_PDF
    ANNOTATION_DIR = (annotation_dir or ANNOTATIONS_DIR / "other" / DOCUMENT_ID).resolve()
    ANNOTATION_PATH = ANNOTATION_DIR / "figure-bounding-boxes.json"
    PROMPTS_PATH = ANNOTATION_DIR / "figure-reconstruction-prompts.json"
    CACHE_DIR = APP_DIR / ".page-cache" / DOCUMENT_ID
    TITLE = DOCUMENT_ID
    EXPECTED_PAGES = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def pdf_page_count() -> int:
    if not SOURCE_PDF.is_file():
        raise RuntimeError(f"Source PDF not found: {SOURCE_PDF}")
    with fitz.open(SOURCE_PDF) as document:
        return document.page_count


def empty_annotations() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "document_id": DOCUMENT_ID,
        "source_pdf": SOURCE_RELATIVE.as_posix(),
        "page_count": pdf_page_count(),
        "coordinate_system": "normalized_0_1000",
        "updated_at": utc_now(),
        "pages": {},
    }


def load_annotations() -> dict[str, Any]:
    if not ANNOTATION_PATH.exists():
        return empty_annotations()
    return json.loads(ANNOTATION_PATH.read_text(encoding="utf-8"))


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_annotations(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Annotation payload must be an object")
    page_count = pdf_page_count()
    if payload.get("document_id") != DOCUMENT_ID:
        raise ValueError("document_id does not match the configured PDF")
    pages = payload.get("pages")
    if not isinstance(pages, dict):
        raise ValueError("pages must be an object keyed by 1-based page number")

    cleaned_pages: dict[str, list[dict[str, Any]]] = {}
    seen_ids: set[str] = set()
    for page_key, raw_boxes in pages.items():
        try:
            page_number = int(page_key)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid page key: {page_key!r}") from exc
        if str(page_number) != str(page_key) or not 1 <= page_number <= page_count:
            raise ValueError(f"Page {page_key!r} is outside 1..{page_count}")
        if not isinstance(raw_boxes, list) or len(raw_boxes) > 64:
            raise ValueError(f"Page {page_number} boxes must be a list of at most 64 items")

        cleaned_boxes: list[dict[str, Any]] = []
        for index, raw_box in enumerate(raw_boxes, start=1):
            if not isinstance(raw_box, dict):
                raise ValueError(f"Page {page_number} box {index} must be an object")
            box_id = str(raw_box.get("id", "")).strip()
            if not box_id or len(box_id) > 100 or box_id in seen_ids:
                raise ValueError(f"Page {page_number} box {index} has an invalid or duplicate id")
            seen_ids.add(box_id)
            label = str(raw_box.get("label", "")).strip()[:160]
            kind = str(raw_box.get("kind", "figure")).strip()
            if kind not in {"figure", "chart", "table", "image", "other"}:
                raise ValueError(f"Page {page_number} box {index} has invalid kind {kind!r}")
            coords: dict[str, float] = {}
            for name in ("x1", "y1", "x2", "y2"):
                value = raw_box.get(name)
                if not _finite_number(value) or not 0 <= float(value) <= COORDINATE_MAX:
                    raise ValueError(f"Page {page_number} box {index} has invalid {name}")
                coords[name] = round(float(value), 3)
            if coords["x2"] - coords["x1"] < 2 or coords["y2"] - coords["y1"] < 2:
                raise ValueError(f"Page {page_number} box {index} is too small")
            cleaned_boxes.append(
                {
                    "id": box_id,
                    "kind": kind,
                    "label": label,
                    **coords,
                }
            )
        if cleaned_boxes:
            cleaned_pages[str(page_number)] = cleaned_boxes

    return {
        "schema_version": 1,
        "document_id": DOCUMENT_ID,
        "source_pdf": SOURCE_RELATIVE.as_posix(),
        "page_count": page_count,
        "coordinate_system": "normalized_0_1000",
        "updated_at": utc_now(),
        "pages": cleaned_pages,
    }


def save_annotations(payload: Any) -> dict[str, Any]:
    cleaned = validate_annotations(payload)
    ANNOTATION_DIR.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix="figure-bounding-boxes.", suffix=".json", dir=ANNOTATION_DIR
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            json.dump(cleaned, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(ANNOTATION_PATH)
    finally:
        temporary_path.unlink(missing_ok=True)
    return cleaned


def render_page(page_number: int) -> Path:
    count = pdf_page_count()
    if not 1 <= page_number <= count:
        raise web.HTTPNotFound(text=f"Page must be between 1 and {count}")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    output = CACHE_DIR / f"page-{page_number:03d}.png"
    if output.exists() and output.stat().st_mtime_ns >= SOURCE_PDF.stat().st_mtime_ns:
        return output
    with fitz.open(SOURCE_PDF) as document:
        page = document.load_page(page_number - 1)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2.25, 2.25), alpha=False)
        pixmap.save(output)
    return output


async def get_document(_request: web.Request) -> web.Response:
    with fitz.open(SOURCE_PDF) as document:
        first = document.load_page(0)
        metadata = {
            "document_id": DOCUMENT_ID,
            "title": TITLE,
            "source_pdf": str(SOURCE_PDF),
            "page_count": document.page_count,
            "page_aspect_ratio": first.rect.width / first.rect.height,
            "annotation_path": str(ANNOTATION_PATH),
            "prompt_path": str(PROMPTS_PATH),
        }
    return web.json_response(metadata)


async def get_annotations(_request: web.Request) -> web.Response:
    return web.json_response(load_annotations())


async def get_prompts(_request: web.Request) -> web.Response:
    if not PROMPTS_PATH.is_file():
        return web.json_response({
            "schema_version": 1,
            "document_id": DOCUMENT_ID,
            "region_count": 0,
            "pages": {},
        })
    return web.json_response(json.loads(PROMPTS_PATH.read_text(encoding="utf-8")))


async def put_annotations(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
        saved = save_annotations(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        raise web.HTTPBadRequest(text=str(exc)) from exc
    return web.json_response(saved)


async def get_page(request: web.Request) -> web.FileResponse:
    try:
        page_number = int(request.match_info["page"])
    except ValueError as exc:
        raise web.HTTPNotFound(text="Invalid page number") from exc
    return web.FileResponse(render_page(page_number), headers={"Cache-Control": "public, max-age=31536000"})


async def index(_request: web.Request) -> web.StreamResponse:
    index_path = UI_DIST / "index.html"
    if not index_path.exists():
        raise web.HTTPServiceUnavailable(
            text="UI is not built. Run `cd ui && npm install && npm run build`."
        )
    return web.FileResponse(index_path)


def create_app() -> web.Application:
    app = web.Application(client_max_size=2 * 1024 * 1024)
    app.router.add_get("/api/document", get_document)
    app.router.add_get("/api/annotations", get_annotations)
    app.router.add_get("/api/prompts", get_prompts)
    app.router.add_put("/api/annotations", put_annotations)
    app.router.add_get("/api/pages/{page}.png", get_page)
    if UI_DIST.exists():
        assets = UI_DIST / "assets"
        if assets.exists():
            app.router.add_static("/assets", assets)
    app.router.add_get("/{tail:.*}", index)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Manual figure bounding-box annotation app")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8511)
    parser.add_argument("--pdf", type=Path, help="annotate this PDF instead of the EY study")
    parser.add_argument("--out-dir", type=Path, help="where figure-bounding-boxes.json is written (with --pdf)")
    args = parser.parse_args()
    if args.pdf:
        configure(args.pdf, args.out_dir)
    count = pdf_page_count()
    if EXPECTED_PAGES is not None and count != EXPECTED_PAGES:
        raise RuntimeError(f"Expected {EXPECTED_PAGES} pages for {DOCUMENT_ID}; found {count}")
    if not ANNOTATION_PATH.exists():
        save_annotations(empty_annotations())
    web.run_app(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
