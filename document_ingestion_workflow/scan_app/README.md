# PDF Collection Scanner

Local React + aiohttp application that scans four hardcoded ingestion-run directories:

- `/Users/dc/geha/crawl_dir/runs/population_health`
- `/Users/dc/geha/crawl_dir/runs/policy`
- `/Users/dc/geha/crawl_dir/runs/forms_directory`
- `/Users/dc/geha/crawl_dir/runs/medical`

The server discovers one canonical source PDF per run manifest, avoiding split-page PDFs and duplicate medical runs. A scan records native-text coverage, native labels in figure regions, heuristic figures/charts, canonical ingestion table totals, and form-like pages/widgets. Results persist in `data/scan_state.json`.

Qualitative figure descriptions and workflow recommendations are calibrated to the verified visual audit. Numeric page, label, figure, chart and form metrics are recalculated on every scan. Canonical table counts are read from each source's existing `qc-report.json`, matching the ingestion audit; markdown table pages are recorded separately.

## Run

```bash
cd /Users/dc/geha/document_ingestion_workflow/scan_app
npm install
npm run build
../../.venv/bin/python server.py
```

Open <http://127.0.0.1:8788>.

For UI development, one command starts both the Python API and Vite in the same terminal:

```bash
npm run dev
```

Open <http://127.0.0.1:5174>. Vite proxies `/api` to port 8788.
Press `Ctrl+C` to stop both processes.

## Per-PDF extraction

After a scan, every multipage PDF has an **Extract + chunk** button. The API
starts one memory-intensive Docling job at a time and calls the canonical
`crawl_dir.src.pipeline.runner.process_document` pipeline. Each click creates a
new immutable run under the same collection:

```text
crawl_dir/runs/<collection>/<document-id>/scan-app-<timestamp>-<hash>/
├── input/source.pdf
├── pages/page-001/
│   ├── source.pdf
│   ├── page.md
│   ├── page.html          # written when the page has a figure/chart or table
│   ├── page.spec.json     # draft native evidence for figure/chart pages
│   └── page-manifest.json
├── candidate/
│   ├── document.md        # canonical compatibility name
│   ├── <pdf-stem>.md      # one document plus consolidated logical tables
│   ├── chunks.jsonl       # full-document Docling HybridChunker output
│   └── tables/
│       ├── table-001.json
│       └── table-001.html
├── qc-report.json
└── run-manifest.json
```

Docling converts and chunks the complete PDF, not individual page PDFs. Page
provenance is retained on each chunk. Table fragments are associated with their
source pages and verified continuation fragments are consolidated into one
logical table, so a table spanning pages 6–8 remains one JSON/HTML table with
`source_pages: [6, 7, 8]`. The named `<pdf-stem>.md` file appends these
authoritative consolidated tables, while `document.md` preserves Docling's raw
full-document export for compatibility. Figure and chart specs remain
page-scoped because a
visual region cannot cross a page boundary. Generated `page.spec.json` files
contain native labels, values, geometry and a `needs_review` status; they are
evidence drafts, not silently approved authored figure specifications.

## Count definitions

- **Native labels:** extractable PDF words on detected figure/chart pages.
- **Figure count:** quantitative figure regions detected on candidate pages; decorative logos and photos are excluded by collection classification.
- **Chart count:** numeric vector/raster chart regions. If a known chart page cannot be segmented into distinct regions, it counts as one chart.
- **Table count:** canonical table count from the existing ingestion QC report, with markdown table pages listed in details.
- **Form count:** form-like pages; interactive PDF widgets are reported separately.
