# EY figure bounding-box annotator

Separate local React app for manually annotating every figure, chart, table, or image in the 29-page EY + LIMRA Workforce Benefits Study.

## Run

```bash
cd /Users/dc/geha/bounding_box/figure_bbox_app/ui
npm install
npm run build

cd /Users/dc/geha
.venv/bin/python -m bounding_box.figure_bbox_app.backend --port 8511
```

Open <http://127.0.0.1:8511/>.

Drag on a PDF page to create a region. Use the small arrow controls or page dropdown to navigate. Label and classify each region in the right panel. Every change is autosaved atomically, and **Save bounding boxes** (or `Cmd/Ctrl+S`) creates an explicit save checkpoint at:

```text
/Users/dc/geha/bounding_box/annotations/research/ey-limra-workforce-benefits-study-final-2025/figure-bounding-boxes.json
```

Coordinates use a resolution-independent `0..1000` system. Multiple regions can be stored per page. The source PDF remains unchanged.

## Browser agent (automatic boxes for any PDF)

`browser_bbox_agent.py` starts this app for any PDF (`backend.py --pdf ... --out-dir ...`), opens it in
Playwright Chromium, and lets Claude draw the boxes with mouse drags. After each box it gets a fresh
screenshot, so it can delete and redraw bad ones. Boxes autosave through the normal UI, in the same
`figure-bounding-boxes.json` format (0..1000). A sidecar `browser-agent-run.json` adds PDF-point coordinates.

```bash
cd /Users/dc/geha
.venv/bin/python -m bounding_box.figure_bbox_app.browser_bbox_agent \
  --pdf /Users/dc/ocr-mini-bench/bench_documents/Invoices/medical_bill_en.pdf --headed
```

Needs `ANTHROPIC_API_KEY`. Output defaults to `bounding_box/annotations/other/<pdf stem>/`.
Options: `--pages 1,3`, `--model`, `--port` (default 8512), `--max-turns`.

## Generate and review reconstruction prompts

Create one evidence-backed reconstruction prompt for every saved figure or image region:

```bash
cd /Users/dc/geha
.venv/bin/python -m bounding_box.figure_bbox_app.generate_reconstruction_prompts
```

The generator reads each saved bounding box, extracts native PDF text and embedded font names,
and preserves every percentage token's page coordinates. It matches tokens to colored vector
marks and builds vertical or horizontal bar mappings from geometry rather than PDF text order.
Legend thresholds, bracket annotations, and other unmatched percentages remain separate. When
the geometry is insufficient, the prompt is marked `ambiguous` and explicitly forbids assigning
the flat percentage sequence to bars.

Page 4 and the two manually corrected Page 5 prompts are protected as `user_approved` inputs.
Regenerating the catalog copies those approved prompts byte-for-byte instead of rewriting them.
The combined catalog is written to:

```text
/Users/dc/geha/bounding_box/annotations/research/ey-limra-workforce-benefits-study-final-2025/figure-reconstruction-prompts.json
```

Individual Markdown prompts are stored under `reconstruction-prompts/page-NNN/`. The React viewer
loads the catalog through `/api/prompts` and displays expandable, copyable prompts for the regions
on the currently selected page. Pages with multiple regions show a separate prompt for each one.
Protected Page 5 sources are stored under `approved-reconstruction-prompts/`.

## Process one annotated page

Run a single-page checkpoint before processing the rest of the document:

```bash
cd /Users/dc/geha
.venv/bin/python -m bounding_box.figure_bbox_app.process_annotated_page \
  --page 4 --max-iterations 6
```

The command crops only the saved page-4 boxes, extracts locked native PDF evidence,
generates semantic HTML, renders it with Playwright Chromium, and performs at most six
PNG-versus-HTML correction passes. The run directory retains every HTML, rendered PNG,
review error, `batch.json`, final HTML, and a side-by-side `segments/index.html` report.
Each saved bounding box is captured by headless Playwright Chromium. The resulting artifact
is described by its exact pixel dimensions rather than presenting DPI as a browser-screenshot property.

### Tailwind figure reconstruction

The page-4 checkpoint can be reconstructed with locally compiled Tailwind CSS and a bounded
Playwright visual-correction loop:

```bash
cd /Users/dc/geha
.venv/bin/python -m bounding_box.figure_bbox_app.tailwind_figure_loop --max-iterations 6
```

The workflow uses locally compiled Tailwind and allows supplemental inline CSS plus inline SVG
for precise chart geometry. It forbids scripts, canvas, embedded images, SVG
`image`/`use`/`foreignObject` content, and external resources. Each iteration stores source HTML,
compiled Tailwind CSS, browser-ready HTML, a fixed-size Chromium screenshot, and structured
review errors.
