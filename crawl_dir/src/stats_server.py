"""API for the chunk stats app: list runs, load saved stats, recompute on request."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from aiohttp import web

from .pipeline.chunk_noise import compute_run_stats, list_runs, load_run_stats

CRAWL_DIR = Path(__file__).resolve().parents[1]
RUNS_ROOT = web.AppKey("runs_root", Path)
STATS_ROOT = web.AppKey("stats_root", Path)
UI_DIST = CRAWL_DIR / "stats_app" / "dist"


async def get_runs(request: web.Request) -> web.Response:
    runs_root, stats_root = request.app[RUNS_ROOT], request.app[STATS_ROOT]
    runs = list_runs(runs_root)
    for run in runs:
        run["has_stats"] = (stats_root / run["id"] / "chunk-noise.json").is_file()
    return web.json_response(runs)


def _run_id(request: web.Request) -> str:
    run_id = request.query.get("run", "")
    if not run_id:
        raise web.HTTPBadRequest(text="Missing ?run=family/document/run")
    return run_id


async def get_stats(request: web.Request) -> web.Response:
    try:
        stats = load_run_stats(request.app[RUNS_ROOT], request.app[STATS_ROOT], _run_id(request))
    except ValueError as error:
        raise web.HTTPNotFound(text=str(error)) from error
    if stats is None:
        # Not an error: the run exists but its stats have not been computed yet.
        return web.Response(status=204)
    return web.json_response(stats)


async def post_stats(request: web.Request) -> web.Response:
    run_id = _run_id(request)
    try:
        stats = await asyncio.to_thread(
            compute_run_stats, request.app[RUNS_ROOT], request.app[STATS_ROOT], run_id
        )
    except ValueError as error:
        raise web.HTTPNotFound(text=str(error)) from error
    return web.json_response(stats)


async def index(_request: web.Request) -> web.StreamResponse:
    return web.FileResponse(UI_DIST / "index.html")


def create_app(runs_root: Path, stats_root: Path) -> web.Application:
    app = web.Application()
    app[RUNS_ROOT] = runs_root.resolve()
    app[STATS_ROOT] = stats_root.resolve()
    app.router.add_get("/api/runs", get_runs)
    app.router.add_get("/api/stats", get_stats)
    app.router.add_post("/api/stats", post_stats)
    if UI_DIST.exists():
        app.router.add_get("/", index)
        app.router.add_static("/assets", UI_DIST / "assets")
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, default=CRAWL_DIR / "runs")
    parser.add_argument("--stats-root", type=Path, default=CRAWL_DIR / "stats")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8520)
    args = parser.parse_args()
    web.run_app(create_app(args.runs_root, args.stats_root), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
