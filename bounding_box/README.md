# Spec Files
This has been superceeded with spec files. Use chatGPT or Claude to create spec files which are bounding boxes and make a langgraph error correction loop. Much faster. 
10x




# PDF Figure Bounding-Box Workflow

This directory contains a local annotation and reconstruction workflow for
figures, charts, tables, logos, photos, diagrams, and other non-running-text
regions in PDF documents.

It supports four related but separate tasks:

1. **Manual annotation** in a React interface.
2. **Automatic annotation** by a vision-capable Claude browser agent.
3. **Evidence-backed prompt generation** for reconstructing annotated figures.
4. **Bounded visual correction** that compares a source PNG crop with rendered
   semantic HTML.

The annotations are resolution-independent JSON. The source PDF is never
modified.

## Workflow

```text
PDF
 |
 +--> render page PNGs
 |
 +--> manual React annotation --------+
 |                                     |
 +--> Claude browser annotation -------+--> figure-bounding-boxes.json
                                               |
                                               +--> native PDF evidence
                                               |
                                               +--> reconstruction prompts
                                               |
                                               +--> PNG crops + semantic HTML
                                                    + visual correction report
```

Annotation and reconstruction are intentionally decoupled. Drawing a box does
not automatically extract, interpret, or rebuild the content inside it.

## Components

| Path | Purpose |
|---|---|
| `figure_bbox_app/backend.py` | Serves rendered PDF pages, validates annotations, and writes JSON atomically |
| `figure_bbox_app/ui/` | React/Vite annotation and prompt-review interface |
| `figure_bbox_app/browser_bbox_agent.py` | Uses Claude vision and Playwright mouse actions to annotate arbitrary PDFs |
| `figure_bbox_app/generate_reconstruction_prompts.py` | Extracts native PDF evidence and writes one reconstruction prompt per saved region |
| `figure_bbox_app/process_annotated_page.py` | Crops one annotated page and runs the semantic-HTML correction pipeline |
| `figure_bbox_app/tailwind_figure_loop.py` | Specialized Tailwind reconstruction checkpoint for the EY page-4 chart |
| `annotations/` | Saved boxes, agent sidecars, prompts, approved prompts, and figure specifications |

## Prerequisites

The workflow uses the repository's Python environment and a separately built
React frontend.

```bash
cd /Users/dc/geha
source .venv/bin/activate

cd bounding_box/figure_bbox_app/ui
npm install
npm run build

# Required by the browser agent and HTML-rendering workflows.
python -m playwright install chromium
```

Relevant Python packages include `aiohttp`, `PyMuPDF`, `Pillow`, `playwright`,
`anthropic`, and `openai`. They are already part of the GEHA development
environment; this directory does not maintain a separate Python requirements
file.

## Run the manual annotator

### Default EY + LIMRA document

The default configuration opens:

```text
/Users/dc/geha/crawl_dir/raw/research/ey-limra-workforce-benefits-study-final-2025.pdf
```

Start the backend from the repository root:

```bash
cd /Users/dc/geha
source .venv/bin/activate
python -m bounding_box.figure_bbox_app.backend --port 8511
```

Open <http://127.0.0.1:8511/>.

Annotations are written to:

```text
/Users/dc/geha/bounding_box/annotations/research/ey-limra-workforce-benefits-study-final-2025/figure-bounding-boxes.json
```

### Any other PDF

```bash
cd /Users/dc/geha
source .venv/bin/activate

python -m bounding_box.figure_bbox_app.backend \
  --pdf /absolute/path/to/document.pdf \
  --out-dir /absolute/path/to/annotation-output \
  --port 8511
```

If `--out-dir` is omitted, the default is:

```text
/Users/dc/geha/bounding_box/annotations/other/<pdf-stem>/
```

The backend binds to `127.0.0.1` by default. Use `--host` only when you
intentionally need a different interface; the app has no authentication.

## Use the annotation interface

1. Select a page with the arrows or page dropdown.
2. Drag a tight rectangle around each non-running-text region.
3. Select the region and assign a type: `figure`, `chart`, `table`, `image`, or
   `other`.
4. Give it a short, descriptive label.
5. Confirm that the header says **All changes saved**.

Changes autosave after every edit. The **Save bounding boxes** button creates an
additional explicit save request.

Keyboard shortcuts:

| Shortcut | Action |
|---|---|
| `Cmd/Ctrl+S` | Save now |
| Left/Right arrow | Previous/next page |
| Delete or Backspace | Delete the selected region |
| Escape | Clear the current selection |

**Clear page** removes every region on the current page after confirmation.

If reconstruction prompts already exist, the right panel displays the prompts
for the current page and lets you copy them. The panel does not generate prompts
itself; run the prompt generator described below.

## Annotation format

`figure-bounding-boxes.json` uses 1-based page keys and normalized coordinates
from `0` to `1000`:

```json
{
  "schema_version": 1,
  "document_id": "example",
  "source_pdf": "/absolute/path/to/example.pdf",
  "page_count": 1,
  "coordinate_system": "normalized_0_1000",
  "pages": {
    "1": [
      {
        "id": "page-001-region-1234abcd",
        "kind": "table",
        "label": "Itemized charges table",
        "x1": 60.8,
        "y1": 472.1,
        "x2": 938.2,
        "y2": 622.7
      }
    ]
  }
}
```

Coordinates are relative to the rendered page:

```text
x_pdf = x_normalized * page_width_points / 1000
y_pdf = y_normalized * page_height_points / 1000
```

The backend validates page numbers, unique IDs, region types, coordinate bounds,
minimum box size, and a maximum of 64 regions per page. Writes use a temporary
file followed by an atomic replace.

## Automatic annotation with the browser agent

`browser_bbox_agent.py` launches the same local app, opens it in Playwright
Chromium, sends page screenshots to Claude, and executes Claude's `draw_box`,
`delete_box`, and `finish` tool calls as browser mouse actions. A fresh
screenshot is returned after each action so the agent can correct a bad box.

Set the Anthropic key, then run:

```bash
cd /Users/dc/geha
source .venv/bin/activate
export ANTHROPIC_API_KEY="..."

python -m bounding_box.figure_bbox_app.browser_bbox_agent \
  --pdf /Users/dc/ocr-mini-bench/bench_documents/Invoices/medical_bill_en.pdf \
  --headed
```

Useful options:

| Option | Meaning |
|---|---|
| `--pages 1,3,5` | Process only selected 1-based pages |
| `--out-dir PATH` | Override the annotation output directory |
| `--model MODEL` | Override the Claude model |
| `--port PORT` | Backend port; default `8512` |
| `--max-turns N` | Maximum tool-call rounds per page |
| `--headed` | Show the Chromium window |

Outputs:

- `figure-bounding-boxes.json`: the same normalized annotation schema used by
  the manual interface;
- `browser-agent-run.json`: run metadata, page summaries, token usage in current
  runs, and each region converted to PDF-point coordinates.

Automatic boxes are model outputs, not ground truth. Review them in the manual
interface before using them for extraction or evaluation.

## Generate reconstruction prompts

The prompt generator currently targets the default EY document and its saved
annotations. It does not accept `--pdf` or `--out-dir`.

```bash
cd /Users/dc/geha
source .venv/bin/activate
python -m bounding_box.figure_bbox_app.generate_reconstruction_prompts
```

For every region it:

- extracts native PDF text, font names, numbers, percentages, and token
  coordinates;
- tries to map percentage labels to vector chart marks from geometry;
- records unmatched labels and ambiguous mappings rather than inventing a chart
  relationship;
- writes an individual Markdown prompt and a combined JSON catalog.

Outputs:

```text
bounding_box/annotations/research/ey-limra-workforce-benefits-study-final-2025/
├── figure-reconstruction-prompts.json
└── reconstruction-prompts/page-NNN/<region-id>.md
```

Selected reviewed prompts live under `approved-reconstruction-prompts/` and are
copied unchanged during regeneration. Treat those files as curated inputs.

## Process one annotated page

This workflow also currently targets the default EY document. It crops the
saved regions from one page, records locked PDF evidence, generates semantic
HTML, renders the HTML in Chromium, and performs a bounded source-PNG versus
rendered-PNG correction loop.

```bash
cd /Users/dc/geha
source .venv/bin/activate
export OPENAI_API_KEY="..."

python -m bounding_box.figure_bbox_app.process_annotated_page \
  --page 4 \
  --model gpt-4.1-mini \
  --max-iterations 6 \
  --dpi 180
```

Runs are written beneath:

```text
crawl_dir/runs/research/ey-limra-workforce-benefits-study-final-2025/<run-id>/
```

The run preserves the page PDF and PNG, cropped figures, bounding-box overlay,
region metadata, every HTML/PNG correction attempt, structured review errors,
`batch.json`, final selected HTML, an event log, a run manifest, and a
side-by-side `segments/index.html` report.

Use `--run-id` for a stable name. Existing run directories are never
overwritten. `--max-iterations` must be between 1 and the pipeline limit, and
`--dpi` must be between 144 and 600.

## Tailwind page-4 checkpoint

`tailwind_figure_loop.py` is a specialized experiment, not a general PDF
command. It expects the existing page-4 checkpoint paths embedded in the file.

```bash
cd /Users/dc/geha
source .venv/bin/activate
export OPENAI_API_KEY="..."

python -m bounding_box.figure_bbox_app.tailwind_figure_loop \
  --model gpt-4.1-mini \
  --max-iterations 6
```

It compiles Tailwind locally and allows supplemental inline CSS and inline SVG.
It rejects scripts, canvas, embedded images, external resources, and SVG
`image`, `use`, or `foreignObject` content. Every iteration retains source HTML,
compiled CSS, browser HTML, a fixed-size Chromium screenshot, and structured
review findings.

## Existing benchmark artifacts

The repository currently includes:

- 24 regions across 21 pages of the 29-page EY + LIMRA study;
- 24 corresponding reconstruction prompts;
- figure specifications for selected EY pages;
- a six-region browser-agent example for `medical_bill_en.pdf`.

These are saved examples, not guarantees that every page or every figure is
fully annotated.

## Development checks

Build the UI:

```bash
cd /Users/dc/geha/bounding_box/figure_bbox_app/ui
npm run build
```

Check each Python entry point without invoking an API:

```bash
cd /Users/dc/geha
source .venv/bin/activate

python -m bounding_box.figure_bbox_app.backend --help
python -m bounding_box.figure_bbox_app.browser_bbox_agent --help
python -m bounding_box.figure_bbox_app.generate_reconstruction_prompts --help
python -m bounding_box.figure_bbox_app.process_annotated_page --help
python -m bounding_box.figure_bbox_app.tailwind_figure_loop --help
```

## Troubleshooting

**`503 UI is not built`**

Run `npm install && npm run build` in `figure_bbox_app/ui`, then restart the
backend.

**Chromium executable is missing**

Run `python -m playwright install chromium` from the active GEHA environment.

**The default PDF is missing or has the wrong page count**

The default backend expects the EY source PDF at the path above and verifies
that it has 29 pages. Use `--pdf` for another document.

**The UI shows boxes but no reconstruction prompts**

Annotations and prompts are separate artifacts. Run
`generate_reconstruction_prompts`, then reload the UI.

**Port 8511 or 8512 is already in use**

Pass another `--port` value. The manual backend defaults to `8511`; the browser
agent defaults to `8512`.

## Safety and scope

- The app is a local research tool and has no authentication or authorization.
- Do not expose it to an untrusted network.
- API calls can incur cost; restrict `--pages` and `--max-turns` for pilot runs.
- Do not send sensitive, private, or regulated documents to external vision or
  language-model APIs without authorization.
- Bounding boxes identify regions; they do not prove that OCR, chart values, or
  reconstructed HTML are correct. Preserve source evidence and review outputs.
