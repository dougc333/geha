"""Standalone local API for bulk GEHA PDF evidence extraction."""
from __future__ import annotations

import asyncio
import json
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pymupdf
from aiohttp import web

from .pipeline import process_document, write_json

ROOT = Path(__file__).resolve().parents[1]
RAW = Path(os.getenv('BATCH_RAW_ROOT', ROOT / 'crawl_dir' / 'raw')).resolve()
RUNS = Path(os.getenv('BATCH_RUNS_ROOT', ROOT / 'runs')).resolve()
UI = ROOT / 'ui' / 'dist'


def safe_source(relative: str) -> Path:
    if not relative.lower().endswith('.pdf'):
        raise web.HTTPBadRequest(text='Only PDFs are supported')
    source = (RAW / relative).resolve()
    try:
        source.relative_to(RAW)
    except ValueError:
        raise web.HTTPBadRequest(text='Invalid document path')
    if not source.is_file():
        raise web.HTTPNotFound(text='PDF not found')
    return source


class BatchManager:
    def __init__(self) -> None:
        RUNS.mkdir(parents=True, exist_ok=True)
        self.pool = ThreadPoolExecutor(max_workers=int(os.getenv('BATCH_WORKERS', '2')))
        self.lock = threading.Lock()

    def start(self, documents: list[str]) -> dict:
        batch_id = 'batch-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:6]
        folder = RUNS / batch_id
        folder.mkdir()
        payload = {'batch_id': batch_id, 'created_at': datetime.now(timezone.utc).isoformat(),
                   'status': 'running', 'documents': [{'path': name, 'status': 'queued'} for name in documents]}
        self.save(payload)
        for name in documents:
            future = self.pool.submit(process_document, safe_source(name), RAW, folder)
            future.add_done_callback(lambda finished, path=name, batch=batch_id: self.finish_one(batch, path, finished))
        return payload

    def load(self, batch_id: str) -> dict:
        if not batch_id.startswith('batch-') or '/' in batch_id or '..' in batch_id:
            raise web.HTTPBadRequest(text='Invalid batch ID')
        path = RUNS / batch_id / 'batch.json'
        if not path.is_file():
            raise web.HTTPNotFound(text='Batch not found')
        return json.loads(path.read_text(encoding='utf-8'))

    def save(self, payload: dict) -> None:
        write_json(RUNS / payload['batch_id'] / 'batch.json', payload)

    def finish_one(self, batch_id: str, document: str, future) -> None:
        try:
            result = future.result()
        except Exception as exc:
            result = {'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'}
        with self.lock:
            payload = self.load(batch_id)
            for item in payload['documents']:
                if item['path'] == document:
                    item.update(result)
                    break
            if all(item['status'] not in {'queued', 'running'} for item in payload['documents']):
                payload['status'] = 'completed'
                payload['finished_at'] = datetime.now(timezone.utc).isoformat()
            self.save(payload)


async def health(request: web.Request) -> web.Response:
    return web.json_response({'ready': True, 'documents': sum(1 for _ in RAW.rglob('*.pdf')),
                              'workers': request.app['manager'].pool._max_workers})


async def documents(request: web.Request) -> web.Response:
    catalog_path = ROOT / 'catalog.json'
    titles = {}
    if catalog_path.is_file():
        for item in json.loads(catalog_path.read_text(encoding='utf-8')).get('documents', []):
            titles[item.get('relative_path')] = item.get('title')
    result = []
    for path in sorted(RAW.rglob('*.pdf')):
        relative = path.relative_to(RAW).as_posix()
        try:
            with pymupdf.open(path) as pdf:
                pages = pdf.page_count
        except Exception:
            pages = None
        result.append({'path': relative, 'title': titles.get(relative) or path.stem.replace('-', ' ').title(),
                       'bytes': path.stat().st_size, 'pages': pages})
    return web.json_response({'documents': result})


async def start_batch(request: web.Request) -> web.Response:
    body = await request.json()
    names = body.get('documents')
    if not isinstance(names, list) or not 1 <= len(names) <= 10000 or not all(isinstance(x, str) for x in names):
        raise web.HTTPBadRequest(text='Provide 1 to 10000 document paths')
    names = list(dict.fromkeys(names))
    for name in names:
        safe_source(name)
    return web.json_response(request.app['manager'].start(names), status=202)


async def batches(request: web.Request) -> web.Response:
    records = []
    for path in sorted(RUNS.glob('batch-*/batch.json'), reverse=True)[:20]:
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            records.append({'batch_id': data['batch_id'], 'created_at': data['created_at'],
                            'status': data['status'], 'total': len(data['documents']),
                            'done': sum(x['status'] not in {'queued', 'running'} for x in data['documents'])})
        except (KeyError, ValueError, OSError):
            continue
    return web.json_response({'batches': records})


async def batch_detail(request: web.Request) -> web.Response:
    return web.json_response(request.app['manager'].load(request.match_info['batch_id']))


async def raw_pdf(request: web.Request) -> web.StreamResponse:
    return web.FileResponse(safe_source(request.match_info['path']), headers={'Content-Type': 'application/pdf'})


async def artifact(request: web.Request) -> web.StreamResponse:
    batch_id = request.match_info['batch_id']
    request.app['manager'].load(batch_id)
    root = (RUNS / batch_id).resolve()
    target = (root / request.match_info['path']).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise web.HTTPBadRequest(text='Invalid artifact path')
    if not target.is_file():
        raise web.HTTPNotFound(text='Artifact not found')
    return web.FileResponse(target)


async def index(request: web.Request) -> web.StreamResponse:
    if not (UI / 'index.html').is_file():
        return web.Response(text='Build the React UI with npm run build in ui/.', status=503)
    return web.FileResponse(UI / 'index.html')


def create_app() -> web.Application:
    app = web.Application(client_max_size=1024 * 1024)
    app['manager'] = BatchManager()
    app.router.add_get('/api/health', health)
    app.router.add_get('/api/documents', documents)
    app.router.add_get('/api/batches', batches)
    app.router.add_post('/api/batches', start_batch)
    app.router.add_get('/api/batches/{batch_id}', batch_detail)
    app.router.add_get('/api/raw/{path:.*}', raw_pdf)
    app.router.add_get('/api/artifacts/{batch_id}/{path:.*}', artifact)
    if (UI / 'assets').is_dir():
        app.router.add_static('/assets', UI / 'assets')
    app.router.add_get('/', index)
    return app


if __name__ == '__main__':
    web.run_app(create_app(), host=os.getenv('HOST', '0.0.0.0'), port=int(os.getenv('PORT', '8520')))
