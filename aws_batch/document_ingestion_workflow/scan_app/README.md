# PDF Collection Scanner

Local React + aiohttp application that scans every immediate collection directory
under `/Users/dc/geha/crawl_dir/raw` (14 directories at the time of this update).

The server discovers one canonical source PDF per run manifest, avoiding split-page PDFs and duplicate runs. It also discovers every raw PDF before it has a run. A scan records native-text coverage, native labels in figure regions, heuristic figures/charts, table locations, and form-like pages/widgets. Table totals come from canonical ingestion QC when available; raw-only PDFs use PyMuPDF table detection, printed table captions, and numeric continuation cues for borderless tables. Every PDF's scan results persist in `scan_state.json` beside `package.json`. Collection scan timestamps and PDF inventory fingerprints persist beside it in `scan_registry.json`. A normal scan reuses completed PDF results and only queues new or pending files; **Rescan all** remains the explicit force option.

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

## Single-document extraction CLI and Swagger API

The extractor accepts one PDF already present in the completed `scan_state.json` and
`scan_registry.json` inventory. It checks the source fingerprint before starting.
Run it from this directory with the repository virtual environment:

```bash
../../.venv/bin/python document_extract.py /absolute/path/to/document.pdf
../../.venv/bin/python -m uvicorn document_extract:app --host 127.0.0.1 --port 8790
```

Swagger is at <http://127.0.0.1:8790/docs>; `POST /extract` accepts `pdf`,
`document_version`, optional `figure_specs_dir`, `provider`, `model`, `base_url`,
and `api_key_env`. The default is Nous Portal with
`qwen/qwen3-vl-235b-a22b-instruct`; set `NOUS_API_KEY` in the shell before
starting the CLI or API. The extractor makes a small model access check before
PDF conversion so a rejected key fails promptly. To use Anthropic, pass
`--provider anthropic` (or set `provider` to `anthropic` in Swagger) and provide
a valid `ANTHROPIC_API_KEY`.

The request is
synchronous and may take a long time for a multipage report. A new run is stored
under `crawl_dir/runs/<family>/<document-id>/single-document-<timestamp>/`:

```text
html/pages/page-001/{source.pdf,page.md,final.html,page-manifest.json}
html/candidate/tables/{table-001.json,table-001.html,tables.md}
spec/figure-specs/page-001.json
spec/pages/page-001/{source.pdf,page.md,final.html,page-manifest.json,figure-spec.json}
tesseract/tesseract.md
tesseract/pages/page-001/{source.pdf,source.png,page.md,final.html,page-manifest.json}
extraction-manifest.json
```

Only relevant branches are created. The HTML branch uses the existing
`process_scanned_document` page splitter, Docling native export and table
extraction. Text-backed table-only pages take the native Docling path; figure
and image-only pages use the existing rendered HTML review/correction loop. It
stores up to four `iteration-XX.png` attempts per reviewed visual page. The spec branch uses `figure_specs.py` to validate reviewed
figure specs against native PDF words and render semantic HTML. It renders once
because that validator has no spec correction loop. For pages without figures,
the spec branch records an empty page spec; for figure pages lacking a reviewed
spec, it records `needs_spec` and marks the whole extraction failed. It never
claims those pages were verified. Use the existing `bounding_box` spec authoring
workflow to provide reviewed specs. Image-only pages are OCRed with Tesseract
and remain `needs_visual_review`.

Each branch retains its own `qc-report.json`. The extraction manifest reports
remaining missing specs and failed reviews. Neither an empty error list from a
model reviewer nor a successful Tesseract command proves exact source fidelity;
review those artifacts before using extracted content downstream.

## Count definitions

- **Native labels:** extractable PDF words on detected figure/chart pages.
- **Figure count:** quantitative figure regions detected on candidate pages; decorative logos and photos are excluded by collection classification.
- **Chart count:** numeric vector/raster chart regions. If a known chart page cannot be segmented into distinct regions, it counts as one chart.
- **Table count:** canonical table count from the existing ingestion QC report, with markdown table pages listed in details.
- **Form count:** form-like pages; interactive PDF widgets are reported separately.
