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

## Count definitions

- **Native labels:** extractable PDF words on detected figure/chart pages.
- **Figure count:** quantitative figure regions detected on candidate pages; decorative logos and photos are excluded by collection classification.
- **Chart count:** numeric vector/raster chart regions. If a known chart page cannot be segmented into distinct regions, it counts as one chart.
- **Table count:** canonical table count from the existing ingestion QC report, with markdown table pages listed in details.
- **Form count:** form-like pages; interactive PDF widgets are reported separately.
