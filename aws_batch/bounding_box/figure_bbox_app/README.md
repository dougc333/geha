# Figure bounding-box app

The canonical setup, annotation, browser-agent, prompt-generation, and visual
correction documentation is in [`../README.md`](../README.md).

Quick start:

```bash
cd /Users/dc/geha/bounding_box/figure_bbox_app/ui
npm install
npm run build

cd /Users/dc/geha
source .venv/bin/activate
python -m bounding_box.figure_bbox_app.backend --port 8511
```

Open <http://127.0.0.1:8511/>.

## Evidence-grounded figure specs

The UI's **Generate specs** button turns saved bounding boxes into structured,
page-level JSON. The workflow loads the newest passed page artifact already in
`crawl_dir`, assembles a supported chart/diagram spec locally, and validates it
with `crawl_dir.src.pipeline.figure_specs.verify_figure`. No report content is
sent to an external model. Live progress follows:

`Boxed → Crawl data loaded → Spec assembled → Validating → Spec saved`

Specs are written atomically to `figure-specs/page-NNN.json`. Existing page
specs are skipped by default, so reviewed work is not replaced. The CLI exposes
the same resumable workflow:

```bash
python -m bounding_box.figure_bbox_app.generate_figure_specs \
  --pdf /path/to/report.pdf \
  --annotations /path/to/figure-bounding-boxes.json \
  --specs-dir /path/to/figure-specs \
  --status /path/to/spec-generation-status.json \
  --crawl-runs /path/to/crawl_dir/runs/research/document-id \
  --pages 3
```

Use `--overwrite` only when intentionally regenerating reviewed specs.
