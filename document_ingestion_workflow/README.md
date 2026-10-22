# Document ingestion workflow

An auditable demonstration of GEHA's document-ingestion pipeline. The application
routes each curated PDF to an appropriate extraction workflow, streams the tool
decisions and processing events to a React interface, and displays the authoritative
source page beside the generated semantic HTML.

The workflow is deterministic orchestration, not an autonomous agent. Python code
selects the extraction route, controls rendering and verification, and writes an
immutable candidate run. The same ingestion capabilities are also exposed as tools by
the `geha-ingestion` MCP server in `crawl_dir/src/ingestion_mcp.py`.

> This is a demonstration for public documents. It is not production- or HIPAA-ready,
> and generated candidates are not promoted automatically.

## What the demo shows

- A catalog of curated policy, research, and form PDFs.
- Extraction-tool selection based on the document layout.
- Exact source-page rendering with PyMuPDF.
- Native PDF extraction, authored figure specifications, or bounded vision workflows.
- Browser rendering of candidate HTML with Playwright Chromium.
- A live Server-Sent Events (SSE) trace of routing, rendering, review, and correction.
- Source-PDF and semantic-HTML comparison for the current or latest saved run.
- Immutable artifacts and a final quality-control report under `crawl_dir/runs/`.

The web application uses React 19, TypeScript, Vite, and Tailwind. The backend uses
`aiohttp`; it serves the compiled UI, JSON endpoints, the SSE stream, and only approved
artifacts from `crawl_dir/raw` and `crawl_dir/runs`.

## Architecture

```text
curated PDF
    |
    v
document catalog + layout router
    |
    +-- native PDF text/structure -------------------------------+
    |                                                            |
    +-- authored figure specs -> native-text verification -------+
    |                                                            |
    +-- chart crops -> semantic HTML -> visual review/correction -+
    |                                                            |
    +-- Bill of Lading schema -> named-cell OCR ------------------+
                                                                 v
source PDF page <---- React comparison UI ----> semantic HTML candidate
                                                                 |
                                                                 v
                                               Markdown + QC report + run artifacts
```

The extraction route may vary, but visually reviewed routes always use the same
deterministic render loop:

```text
generate or correct HTML
        |
        v
render_html_with_playwright
        |
        v
compare source pixels with rendered pixels
        |
        +-- match ------> accept
        |
        +-- mismatch ---> correct and render again, up to the configured limit
```

The LLM never decides whether browser rendering can be skipped. Rendering is a required
workflow step whenever a selected route performs visual review.

## Curated documents and routing

| Document | Layout profile | Selected route | Model use |
| --- | --- | --- | --- |
| Datroway coverage policy | Mixed policy | Whole-page semantic HTML | Claude generation/review |
| Elrexfio coverage policy | Mixed policy | Whole-page semantic HTML | Claude generation/review |
| Bendamustine coverage policy | Native-text report | Native PDF text and structure | None |
| Synthetic Bill of Lading | Dense form | Versioned schema plus named-cell OCR | OpenAI for cell OCR/correction |
| 2025 EY/LIMRA Workforce Benefits Study | Hybrid figure report | Native pages plus authored figure specifications | None during the saved spec route |

The backend definitions live in `backend.py` under `DEMO_DOCUMENTS` and
`LayoutToolRouter`.

### Renderer roles

PDF evidence and candidate HTML are rendered by different tools:

| Operation | Implementation | Purpose |
| --- | --- | --- |
| PDF page to PNG | `render_pdf_page_with_pymupdf` | Produce exact page-only source pixels |
| Candidate HTML to PNG | `render_html_with_playwright` | Produce the browser rendering used for review |
| Chrome PDF viewer to PNG | `render_pdf_viewer_with_playwright_chromium` | Available fallback; not selected by default |

The trace emits `html_render_started` and `html_rendered` for every candidate render.
Those events include the page or segment, zero-based iteration, paths, renderer,
latency, and local rendering cost (`$0`).

## Figure and chart handling

Ordinary PDF text extraction can recover the strings printed inside a chart while
losing the relationships among series, categories, colors, and annotations. The
EY/LIMRA route therefore uses versioned figure specifications stored under:

```text
crawl_dir/annotations/research/
  ey-limra-workforce-benefits-study-final-2025/
    figure-specs/page-NNN.json
```

`crawl_dir/src/pipeline/figure_specs.py`:

1. Loads the authored specification for a figure page.
2. Checks printed labels and values against native PDF text inside the figure box.
3. Renders accessible semantic HTML deterministically.
4. Adds an adjacent data table so chart relationships are explicit and retrievable.
5. Records the tool identifier and evidence in the page manifest and segment batch.

Pages without a figure specification use native PDF extraction. If a hybrid figure
report has no authored specs, the fallback is
`chart_figure_crop_html_correction`: detect figure regions, save crops and an overlay,
generate semantic HTML, render it, review it, and correct it for at most six passes.

Whole-page handling is intentional for designed research pages: prematurely cropping
the page can separate a chart from its title, legend, axes, footnotes, or explanatory
text.

## Bill of Lading workflow

The recognized synthetic Bill of Lading uses a specialist route rather than generic
layout segmentation:

1. Load the versioned eight-block geometry and named-cell contract from
   `PDF_processing/bill_lading/bill_of_lading_html_graph.py`.
2. Scale that geometry from its original 2136 x 3584 source canvas.
3. Create deterministic block and named-cell crops.
4. OCR the named cells.
5. Assemble HTML deterministically.
6. Render and compare each segment for up to six total iterations.
7. Re-OCR only the named cells implicated by a review error.

Review is deliberately limited to literal text fidelity: missing, wrong, duplicated,
extra, or reordered text. CSS, typography, borders, spacing, alignment, color, wrapping,
logos, and other presentation differences are not failures. A deterministic post-filter
places prohibited styling findings in `ignored_css_errors` without allowing them to
change the verdict.

This route is applicable only to documents matching the curated template.

## UI behavior

The interface provides:

- **Document selector** — chooses one of the curated source PDFs.
- **Tool summaries** — displays considered renderers and extraction routes.
- **Control strip** — reports backend readiness, model, run ID, and inspection pause.
- **Visual comparison** — embeds `source.pdf` beside initial or verified HTML.
- **Page navigation** — appears as soon as a page has both comparison artifacts.
- **Current/previous run selector** — loads the newest saved run for the chosen document.
- **Pipeline trace** — renders each SSE event as the run proceeds.
- **Summary** — reports pages, scanned pages, review counts, and final QC status.

Artifact HTML is served with a restrictive Content Security Policy and displayed in a
sandboxed iframe. The artifact endpoint rejects paths outside `crawl_dir/raw` and
`crawl_dir/runs`.

## Output layout

Each run is saved beneath:

```text
crawl_dir/runs/<family>/<document-id>/<run-id>/
```

A typical run contains:

```text
<run-id>/
├── candidate/
│   └── ... assembled candidate artifacts
├── pages/
│   └── page-004/
│       ├── source.pdf
│       ├── source.png
│       ├── page.md
│       ├── final.html
│       ├── page-manifest.json
│       └── segments/
│           ├── batch.json
│           ├── regions.json                 # route-dependent
│           └── figure-01/
│               ├── iteration-01.html
│               ├── iteration-01.png
│               └── final.html
└── qc-report.json
```

Files vary by route. Native pages may not have iteration artifacts; visually corrected
pages and segments preserve every HTML/render/review attempt for auditing.

## Quick start with Docker

Docker is the recommended way to run the complete demo because the image includes the
compiled React UI, Python dependencies, and Playwright Chromium.

### Prerequisites

- Docker Desktop with Compose support.
- `ANTHROPIC_API_KEY` exported in the shell. The backend currently requires Anthropic
  credentials before starting any new run.
- `OPENAI_API_KEY` exported only when running the Bill of Lading workflow.

```bash
cd /Users/dc/geha/document_ingestion_workflow
export ANTHROPIC_API_KEY="..."
export OPENAI_API_KEY="..."   # Bill of Lading only
./docker-up.sh --build
```

Open <http://127.0.0.1:8510>.

`docker-up.sh` runs Compose in detached mode, waits for the container health check, and
prints the browser URL. Generated artifacts survive container replacement because
Compose mounts `../crawl_dir/runs` into the container.

Use a different host port when 8510 is occupied:

```bash
INGESTION_PORT=8511 ./docker-up.sh --build
```

To follow logs or use foreground mode:

```bash
docker compose up --build
```

Stop the service without deleting saved runs:

```bash
docker compose down
```

## Local development

Build the UI first because the Python backend serves `ui/dist`:

```bash
cd /Users/dc/geha/document_ingestion_workflow/ui
npm ci
npm run build
```

Then run the backend from the repository root so package imports resolve correctly:

```bash
cd /Users/dc/geha
source .venv/bin/activate
export ANTHROPIC_API_KEY="..."
export OPENAI_API_KEY="..."   # Bill of Lading only
python -m document_ingestion_workflow.backend
```

Open <http://127.0.0.1:8510>.

For UI-only development, run Vite separately:

```bash
cd /Users/dc/geha/document_ingestion_workflow/ui
npm run dev
```

The production demo does not use the Vite development server; it serves the compiled
assets from the Python process.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `HOST` | `127.0.0.1` locally; `0.0.0.0` in Docker | Backend bind address |
| `PORT` | `8510` | Backend/container port |
| `INGESTION_PORT` | `8510` | Docker host port |
| `ANTHROPIC_API_KEY` | unset | Claude generation and visual review |
| `OPENAI_API_KEY` | unset | Bill of Lading named-cell OCR/correction |

Local Anthropic CLI credentials from `ant auth login` are supported by the Python
pipeline when available in the backend environment. Docker Compose passes API keys from
the current shell; it does not mount host CLI credentials.

## HTTP API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Read readiness, active models, and server instance ID |
| `GET` | `/api/documents` | List curated demo documents and page metadata |
| `GET` | `/api/previous-run?document=...` | Load the newest saved comparison for a document |
| `POST` | `/api/runs` | Start a new immutable run |
| `GET` | `/api/runs/{run_id}/events` | Stream run events over SSE |
| `GET` | `/api/artifact?path=...` | Serve an approved raw or run artifact |

Example run request:

```bash
curl -X POST http://127.0.0.1:8510/api/runs \
  -H 'Content-Type: application/json' \
  -d '{
    "document": "research/ey-limra-workforce-benefits-study-final-2025.pdf",
    "delay_seconds": 0
  }'
```

`delay_seconds` must be between 0 and 15. The React demo uses five seconds so each
before/after stage remains visible during a live run.

## Tests

Run the backend unit tests from the repository root:

```bash
cd /Users/dc/geha
source .venv/bin/activate
python -m unittest document_ingestion_workflow.test_backend
```

Build the frontend as its compile-time check:

```bash
cd /Users/dc/geha/document_ingestion_workflow/ui
npm run build
```

The tests cover routing, curated-document metadata, authored-spec preference,
Bill-of-Lading geometry, text-only review filtering, deterministic HTML assembly, and
bounded iteration logging.

## Limitations

- A successful render does not prove semantic accuracy; consult `qc-report.json` and
  the saved evidence.
- Vision models can misread small text, colors, legends, and spatial relationships.
- Authored figure specs apply only to the document version they describe.
- The Bill of Lading graph is a template-specific adapter, not a generic form parser.
- API latency and cost depend on model availability and the number of correction passes.
- Model-call cost is not fully instrumented; do not infer dollars from call count.
- New runs are immutable candidates and require an explicit downstream promotion step.

## Source map

| Path | Responsibility |
| --- | --- |
| `backend.py` | Document catalog, routing, API, SSE, artifact serving |
| `bill_of_lading_workflow.py` | Schema segmentation, named-cell OCR, review, correction |
| `ui/src/DemoContext.tsx` | Shared React state and live-run lifecycle |
| `ui/src/RunClient.ts` | API and SSE client |
| `ui/src/components/ComparisonWorkspace.tsx` | PDF/HTML comparison and run navigation |
| `crawl_dir/src/pipeline/scanned_ingestion.py` | Shared ingestion orchestration and artifact creation |
| `crawl_dir/src/pipeline/figure_specs.py` | Figure-spec validation and semantic HTML rendering |
| `crawl_dir/src/pipeline/figure_segmentation.py` | Generic figure detection and correction fallback |
| `crawl_dir/src/ingestion_mcp.py` | MCP tools exposing the same ingestion operations |
