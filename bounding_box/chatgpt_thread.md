# ChatGPT thread: figure bounding-box agent

Saved: 2026-10-18 (America/Los_Angeles)

This is a sanitized record of the part of the conversation that produced the
figure bounding-box tooling. Credentials, API keys, tunnel tokens, and unrelated
earlier topics are intentionally omitted.

## Goal

Build a browser-operated agent that finds figures in PDFs, draws bounding boxes
in the existing annotation UI, and saves machine-readable coordinates for later
figure reconstruction and retrieval.

## Decisions and results

- The annotator is a React 19 + TypeScript + Vite UI served by an `aiohttp`
  backend.
- The browser agent uses Playwright to operate the same UI a person uses. It
  renders each PDF page, asks a multimodal model to identify non-running-text
  regions, draws boxes with mouse drags, checks the updated screenshot, and lets
  the UI autosave.
- Claude vision was used for the working implementation. Other viable backends
  discussed were OpenAI vision, DeepSeek multimodal models, Docling, PaddleOCR,
  PyMuPDF heuristics, and hybrid OCR/layout pipelines.
- The browser agent was tested on
  `/Users/dc/ocr-mini-bench/bench_documents/Invoices/medical_bill_en.pdf`.
  It found six regions on the single page: logo, patient information, insurance
  information, provider/diagnosis information, itemized charges, and account
  summary.
- Saved boxes use normalized `0..1000` coordinates. The browser-agent sidecar
  also stores PDF point coordinates, model usage, and page summaries.
- `figure_specs.py` remains reusable pipeline code. Per-figure state belongs in
  JSON/Markdown artifacts and is not written back into that Python module during
  HTML-to-PNG matching iterations.
- The app was moved from `crawl_dir/figure_bbox_app` to
  `bounding_box/figure_bbox_app`.
- Annotation artifacts were moved from `crawl_dir/annotations` to
  `bounding_box/annotations` so the application and its data live under one
  top-level feature directory.

## Current layout

```text
bounding_box/
├── __init__.py
├── chatgpt_thread.md
├── annotations/
│   ├── other/medical_bill_en/
│   └── research/ey-limra-workforce-benefits-study-final-2025/
└── figure_bbox_app/
    ├── backend.py
    ├── browser_bbox_agent.py
    ├── generate_reconstruction_prompts.py
    ├── process_annotated_page.py
    ├── README.md
    └── ui/
```

## Run the annotator

```bash
cd /Users/dc/geha/bounding_box/figure_bbox_app/ui
npm install
npm run build

cd /Users/dc/geha
.venv/bin/python -m bounding_box.figure_bbox_app.backend --port 8511
```

Open <http://127.0.0.1:8511/>.

The default EY/LIMRA annotations are stored at:

```text
/Users/dc/geha/bounding_box/annotations/research/ey-limra-workforce-benefits-study-final-2025/
```

## Run the browser agent on any PDF

```bash
cd /Users/dc/geha
.venv/bin/python -m bounding_box.figure_bbox_app.browser_bbox_agent \
  --pdf /Users/dc/ocr-mini-bench/bench_documents/Invoices/medical_bill_en.pdf \
  --headed
```

The default output directory is:

```text
/Users/dc/geha/bounding_box/annotations/other/<pdf-stem>/
```

The agent requires `ANTHROPIC_API_KEY` when using the Claude backend. Never save
the key in this file or commit it to Git.

## Generated artifacts

- `figure-bounding-boxes.json`: document/page regions with normalized boxes.
- `browser-agent-run.json`: source, model, usage, summaries, normalized boxes,
  and PDF-point boxes.
- `figure-reconstruction-prompts.json`: combined reconstruction-prompt catalog.
- `reconstruction-prompts/`: per-page Markdown prompts.
- `approved-reconstruction-prompts/`: protected manually corrected prompts.

## Representation discussion

PNG is the visual ground truth and can be processed only by a vision-capable
model or image embedding pipeline. Semantic HTML extracted from the image can be
tokenized by a text model and is useful for accessibility, lexical/semantic
retrieval, validation, and downstream parsing. Tables represented in HTML can
also be normalized into database rows for structured queries. A practical agent
can route a question among structured table search, semantic text search, and
vision retrieval, then combine evidence with provenance.

## Security note

The original conversation contained credentials or tokens in unrelated earlier
messages. They have not been copied here. Any exposed token should be treated as
compromised and rotated at its provider.
