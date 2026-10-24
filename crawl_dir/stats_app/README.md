# Chunk stats app

React 19 + Vite + TypeScript + Tailwind viewer for chunk length and noise
stats of one processed run in `crawl_dir/runs`. Pick a run in the selector;
the EY/LIMRA research report is selected by default, and `?run=` in the URL
keeps the selection.

Stats are saved at `crawl_dir/stats/<family>/<document>/<run>/chunk-noise.json`,
the same path as the run under `crawl_dir/runs`. Selecting a run loads the
saved file without recomputing; a run with no saved stats is computed once and
saved. **Recompute** recalculates and overwrites the file.

## Run

From the repository root, start the API and the dev server:

```bash
.venv/bin/python -m crawl_dir.src.stats_server   # http://127.0.0.1:8520
npm --prefix crawl_dir/stats_app install
npm --prefix crawl_dir/stats_app run dev         # http://localhost:5180
```

Vite proxies `/api` to the API. After `npm run build`, the API also serves the
built app at http://127.0.0.1:8520.

## API

- `GET /api/runs` lists runs that have `candidate/chunks.jsonl`, newest first.
- `GET /api/stats?run=<family/document/run>` returns saved stats, or 204 if none.
- `POST /api/stats?run=<family/document/run>` recomputes and saves stats.

State lives in one React context (`src/store.tsx`, read with `useStats()`), so
components read what they need without prop drilling. The flag heuristics are
in `crawl_dir/src/pipeline/chunk_noise.py`.
