# GEHA document processing corpus

## Projects using `crawl_dir`

`crawl_dir` is the canonical document boundary for the GEHA repository. These
projects consume it directly:

| Project | Corpus layer | Use |
| --- | --- | --- |
| `chunking_benchmarks_RAG` | `raw/coverage-policies`, `runs`, `reviewed` | extraction benchmarks, policy tables, and coverage-policy Q&A |
| `PDF_processing/clean_pdf_langgraph` | `raw/coverage-policies`, `runs` | PDF/table extraction and visual review |
| `dspy_dental_chatbot` | `raw/dental`, `runs`/`reviewed` | direct-PDF and page-aware dental policy retrieval |
| `dental_enrollment_chatbot` | `runs`/`reviewed` | deterministic rate-code and premium table lookups |
| `agentic_search_corpus` | `runs`/`reviewed` | BM25/vector retrieval over canonical page Markdown |
| `mcp_benefits_server` | `raw`, `runs`/`reviewed` | dental and coverage-policy MCP tools |
| `gcp_vertex_rag` | `raw/coverage-policies` | cloud-ingestion source PDFs |

Shared consumers should resolve paths through `crawl_dir.src.consumer_paths`.
Production code must use promoted `reviewed` artifacts. Demo applications may
explicitly request the newest structurally valid candidate while visual review
is pending. The legacy top-level `downloads/` tree is not the source of truth.

### MCP ingestion command for public scanned PDFs

> **Demo only.** This workflow is not production or HIPAA-ready and must only
> be used with public documents.

```bash
cd /Users/dc/geha
uv run --no-project --python 3.12 --with mcp \
  python -m crawl_dir.src.ingestion_mcp
```

The server exposes six demo tools:

- `list_public_pdfs` searches the 54-document curated manifest and returns the
  canonical document selectors available to agents.
- `download_public_pdf` previews or downloads any manifest-pinned public PDF
  from `geha.com` into its canonical location under `crawl_dir/raw`. The
  confirmed call verifies the allowed HTTPS host, PDF signature, byte stream,
  canonical destination, and SHA-256 before completing the atomic download.
- `ingest_scanned_pdf` accepts a PDF path relative to
`crawl_dir/raw/<family>`. Call it first with `data_classification="public"` and
`confirm=false` to inspect the page count and image-only pages. Call it again
with `confirm=true` to permit Claude visual processing and create an immutable,
unpromoted candidate run. Image-only pages are converted to HTML, compared with
their source page, corrected up to six times, converted deterministically to
Markdown, and included in the candidate chunks. The tool never promotes output.
- `ingest_native_pdf_with_semantic_html_charts` is the native-text counterpart used by
  the EY/LIMRA research report. It keeps Docling extraction local for every page,
  detects embedded `Figure N` labels, and sends only those complete figure pages
  through bounded visual semantic-HTML verification. Call with `confirm=false`
  to preview the routed pages and `confirm=true` to create the candidate run.
- `ingest_pdf_with_figure_specs` runs the no-model figure-spec path (see
  "Authored figure specs"). The preview lists the spec pages and any `Figure N`
  pages that lack specs; the confirmed run returns each figure's verifier result.
  It makes no model or network call and fails for documents without specs.
- `segment_document_page` detects semantic regions on one page with Claude.

Register the server with Claude Code (it must start from `/Users/dc/geha`, and
sourcing `~/.zshrc` supplies `ANTHROPIC_API_KEY`):

```bash
claude mcp add geha-ingestion -- /bin/zsh -c 'source ~/.zshrc >/dev/null 2>&1; cd /Users/dc/geha && exec .venv/bin/python -m crawl_dir.src.ingestion_mcp'
```

### React agent demo

`demo/` contains a Vite + TypeScript + Tailwind app that visualizes this MCP
workflow. It uses class components, a class-based Context provider, and an SSE
client class so live run state is shared without prop drilling. The browser
shows the source single-page PDF beside HTML before correction, pauses for five
seconds, streams the review/correction events, and then shows the corrected HTML.

```bash
cd /Users/dc/geha/crawl_dir/demo/ui
npm install
npm run build

cd /Users/dc/geha
source .venv/bin/activate
python -m crawl_dir.demo.backend
```

Open `http://127.0.0.1:8510`. Anthropic credentials (`ANTHROPIC_API_KEY` or an
`ant auth login` profile) must be present in the backend environment to start a
run; `OPENAI_API_KEY` is needed only for the bill-of-lading document. The UI is
demo-only and only accepts artifacts under `crawl_dir/raw` and `crawl_dir/runs`.

**Figure specs for the source documents.** Of the five demo source documents,
only the EY/LIMRA workforce benefits report has figure spec files
(`annotations/research/ey-limra-workforce-benefits-study-final-2025/figure-specs/`);
the router uses them instead of a model for its charts. Datroway, Elrexfio,
Bendamustine and the bill of lading have no charts and need no specs. Any new
document with charts needs its own spec files (see "Authored figure specs"
below); without them its charts fall back to the Claude `figure_segmentation`
loop.

This project downloads the curated 54-document GEHA PDF test corpus using the
canonical URLs and SHA-256 hashes in `src/documents.json`.

Run it with the existing GEHA Python environment (no third-party packages are
required):

```bash
/Users/dc/geha/.venv/bin/python /Users/dc/geha/crawl_dir/src/download_geha_docs.py
```

PDFs are written to `/Users/dc/geha/crawl_dir/raw` under the
`coverage-policies`, `dental`, and `medical` branches. Each file is downloaded
atomically and verified as a PDF. Existing files whose hashes match are safely
skipped. The run report is `/Users/dc/geha/crawl_dir/download_run.json`, leaving
the `raw` tree as a PDF-only corpus.

## Canonical processing code

All new processing code lives under `crawl_dir/src`; legacy implementations
remain in their original directories only for comparison and compatibility.

```text
src/
├── download_geha_docs.py
├── process_document.py
├── process_all.py
├── promote_run.py
├── models/
│   └── artifacts.py
└── pipeline/
    ├── artifact_io.py
    ├── chunks.py
    ├── pdf_conversion.py
    ├── promotion.py
    ├── runner.py
    ├── table_extraction.py
    └── tables.py
```

Create a new immutable processing run with:

```bash
cd /Users/dc/geha
uv run python -m crawl_dir.src.process_document \
  coverage-policies geha-coverage-policy-bendamustine.pdf \
  --document-version 2025-10-01 \
  --plan-year 2026
```

The command splits the source into page PDFs, performs Docling extraction with
a 380-token body budget plus a hard 512-token final-input check,
repairs recognizable numeric table headers, consolidates verified next-page
table continuations, writes provenance-rich `chunks.jsonl`, and produces a
structural `qc-report.json`. It never promotes a candidate automatically.

Process or resume the complete corpus with:

```bash
cd /Users/dc/geha
uv run python -m crawl_dir.src.process_all \
  --batch-id batch-20261009-all \
  --document-version 2026 \
  --plan-year 2026
```

The batch writes `runs/<batch-id>.json` after every document, so an interrupted
run can be safely resumed with the same arguments.

### Authored figure specs

Specs exist because charts are where a model invents things: wrong numbers,
made-up category labels, bars in the wrong order. Plain text and forms have
their own extraction paths that work.

A spec (`annotations/<family>/<document>/figure-specs/page-NNN.json`) records
each figure's labels, values, colours and PDF box. `src/pipeline/figure_specs.py`
checks every printed percentage and label against the native PDF text inside the
box, then renders semantic HTML without a model. Only chart-heavy documents need
specs; the EY/LIMRA report is currently the only one. Specs are written by hand.

```bash
cd /Users/dc/geha
uv run python -m crawl_dir.src.pipeline.figure_specs \
  --family research --document ey-limra-workforce-benefits-study-final-2025.pdf \
  --document-version 2025 \
  --specs crawl_dir/annotations/research/ey-limra-workforce-benefits-study-final-2025/figure-specs
```

## Artifact layout

```text
crawl_dir/
├── raw/
│   ├── coverage-policies/
│   ├── medical/
│   ├── dental/
│   └── research/
├── cache/
│   └── page-splits/<source-sha256>/
├── runs/
│   ├── coverage-policies/
│   ├── medical/
│   └── dental/
└── reviewed/
    ├── coverage-policies/
    ├── medical/
    └── dental/
```

- `raw` contains immutable source PDFs downloaded from the curated manifest.
- `cache/page-splits` stores content-addressed single-page PDFs. A source is split
  only once per SHA-256; later immutable runs hard-link or copy the validated cached
  pages into their own `pages/page-NNN/source.pdf` paths. Cache manifests bind the
  source hash, page count, page filenames, and per-page hashes.
- `raw/research` also contains explicitly imported public research reports, including
  the 29-page 2025 EY/LIMRA Workforce Benefits Study used by the React demo.

### Raw-file path validation

The canonical family allowlist in `src/pipeline/artifact_io.py` includes
`coverage-policies`, `medical`, `dental`, `forms`, and `research`. All ingestion,
demo, segmentation, CLI, and batch-processing callers must resolve source files
through `resolve_raw_document(...)`. The validator resolves both the family root and
requested file, rejects unknown families and directory traversal, and accepts only an
existing `.pdf` contained by `crawl_dir/raw/<family>`. The processing CLI imports the
same `FAMILIES` set, preventing its accepted choices from drifting from runtime path
validation. This change allows the EY/LIMRA report under `raw/research` without
weakening the containment check.
- `runs` contains timestamped extraction, correction, and QC artifacts.
- `reviewed` contains only explicitly approved Markdown, JSON, HTML, and
  manifests. It is the only tree eligible for production indexing.
- `verified` is retained as legacy review evidence. `crawl_dir/downloads` is an
  exact duplicate of `raw` and can be removed; new code must not read or write
  it. The separate repository-level `downloads/` tree still contains legacy
  scripts and is not deleted by this migration.

Run directories use this shape:

```text
runs/<family>/<document-id>/<run-id>/
├── run-manifest.json
├── input/
├── pages/
├── iterations/
├── candidate/
└── qc-report.json
```

Approved artifacts use:

```text
reviewed/<family>/<document-id>/<document-version>/
├── manifest.json
├── source.pdf
├── document.md
├── chunks.jsonl
├── pages/
└── tables/
```

By default, a document fails if its bytes no longer match the curated hash.
Use `--allow-changed` only when intentionally accepting a newer upstream PDF.

## Source corpus status

The `raw` tree contains only the original downloaded, multipage PDFs. It
does not contain the generated single-page files found in the older
`/Users/dc/geha/downloads` processing tree.

Verified on October 7, 2026:

- 54 downloaded source PDFs are recorded by the curated corpus.
- All 54 are present under `crawl_dir/raw` at the same relative paths.
- All 54 have SHA-256 hashes identical to the originals in
  `/Users/dc/geha/downloads`.
- All 54 contain more than one page.
- No source PDF is missing, unreadable, extra, or changed.

The source distribution is 35 coverage-policy PDFs, 2 dental PDFs, and 17
medical PDFs.

## Complete PDF-to-HTML verification

In this project, complete verification does not mean that the HTML and PDF
files have identical bytes. They are different formats. It means that rendered
HTML accurately preserves the source PDF page's:

- text and reading order;
- tables and values;
- images and meaningful visual elements;
- layout, spacing, and page structure; and
- absence of omitted, duplicated, or invented content.

Table-only comparison or text-token equivalence is useful evidence, but neither
one is complete page verification.

### Input and control flow

The processing CLI supplies one original multipage PDF using its path relative
to `crawl_dir/raw/<family>`. It creates the single-page inputs internally:

```text
Original multipage PDF
        |
        v
Create immutable source snapshot
        |
        v
Split into immutable single-page PDFs
        |
        v
Extract document Markdown, tables, and contextual chunks
        |
        v
Repair numeric headers and consolidate table continuations
        |
        v
Write the candidate and structural QC report
        |
        |
        v
Run page-level visual review and correction
        |
        +-- all pages pass --> permit explicit promotion
        `-- any page fails -> retain run; do not index
```

The visual-review engine is a separate, required stage. Until it writes a
`page.html` and a passing `page-manifest.json` for every page, the run remains
`needs_visual_review`. The promotion command verifies those files, page counts,
QC state, and source hash instead of trusting a top-level flag alone.

Every candidate-HTML comparison includes the mandatory deterministic tool step
`render_html_with_playwright`. The page and Bill-of-Lading segment loops emit
`html_render_started` and `html_rendered` trace events containing the page or segment,
iteration, PNG artifact, Playwright Chromium browser, latency, and `$0` local-render
cost. The agent can choose an extraction strategy, but it cannot skip this render step
when visual verification is required.

The React demo's extraction router selects `chart_figure_crop_html_correction` for every
page of the 2025 EY/LIMRA report. A vision layout call draws a labeled bounding box around
each chart, graph, infographic, diagram, or meaningful figure. The page directory stores
`segments/figures-overlay.png`, `segments/regions.json`, and a PNG crop for every detected
visual. Each crop receives its own semantic HTML generation and Playwright visual-review
loop, stopping at a clean match or six attempts. Before generation, the crop's pixel box is
mapped back to its single-page `source.pdf`; PyMuPDF extracts the embedded words and PDF
coordinates inside that box into `segments/figure-NN/native-evidence.json`. That literal text
and its numeric tokens are immutable evidence in generation, review, and correction prompts,
so visual feedback cannot reinterpret a printed sign, year, percentage, label, or value.
`segments/batch.json` records each visible title, kind, bounding box, evidence path, HTML and
rendered-PNG attempt, candidate SHA-256, verdict, errors, latency, and selected final artifact.
The loop detects repeated candidate hashes and stops an A→B→A correction cycle immediately;
on failure it retains the lowest-error candidate instead of blindly promoting the sixth attempt.
Verified crop HTML is then supplied when assembling the complete page HTML, which
also passes through the bounded page-level correction loop. This document-level override is
intentional: pages without a literal `Figure N` marker still contain designed findings grids,
photography, infographics, or complex composition that native text extraction does not
preserve. Review is strict: overlapping or clipped labels, detached legends/categories,
incorrect stacking, and disagreement between the visual chart and semantic table must
produce a `mismatch` and enter correction rather than being accepted. The React
comparison workspace displays the first page
as soon as both of its comparison artifacts are ready, then keeps that page fixed
while the remaining pages are collected. Previous, Next, and the page selector gain
each page as soon as that page finishes; navigation never advances automatically.
Native pages show local semantic
HTML and figure pages retain initial and corrected views. Bounding-box
segmentation is reserved for dense forms;
using it on charts can separate axes, legends, series, and category groups. The
selected figure-page numbers are recorded as
`visual_reconstruction_pages` in the run manifest, findings, QC report, and live trace.
The comparison header also offers a two-item run selector: the active run and only
the most recent previous saved run for the selected document. Older runs are not
enumerated in the UI. Every semantic HTML comparison displays the extraction
`tool_id` that produced that page, including tool metadata reconstructed from saved
previous-run artifacts.

### External-resource correction guard

Extraction and visual correction remain agent-visible tool calls. External-resource
sanitation is deterministic middleware around those calls, so the agent cannot skip
it. External styles, media, and active resource attributes are removed and recorded
in per-page sanitation reports. External anchors are unwrapped to plain visible text
before the next correction; printed URLs remain readable but are never active links.
Native Docling exports expose this step in the live trace as the deterministic
`sanitize_external_links_to_text` tool. This lets native policy pages continue into
table and chunk assembly without loading remote content.

The correction prompt also forbids recreating links or resource-bearing attributes.
If a model nevertheless reintroduces the same external-resource signature twice, the
pipeline keeps the deterministically sanitized candidate, performs one final visual
review, and stops further correction calls. The trace emits
`external_resource_recurrence_stopped`, and rejected model output remains available
for audit. This prevents sanitize/correct oscillation while preserving provenance.

### Output of a complete run

```text
runs/<family>/<document-id>/<run-id>/
├── input/
│   └── source.pdf
│   ├── source-reference.json
│   └── source.sha256
├── pages/page-001/
│   ├── source.pdf
│   ├── page.md
│   └── page-manifest.json
├── iterations/iteration-001/
│   ├── document.md
│   ├── table-fragments/
│   └── findings.json
├── candidate/
│   ├── document.md
│   ├── chunks.jsonl
│   └── tables/
├── run-manifest.json
└── qc-report.json
```

A document is completely verified only when `qc-report.json` reports:

```json
{
  "status": "passed",
  "page_count": 3,
  "structural_errors": [],
  "visual_verification": {
    "status": "passed",
    "passed_pages": 3,
    "total_pages": 3
  }
}
```

Every page record must also have `status` equal to `matched` or `passed`,
`final_error_count` equal to integer `0`, and existing `final_html` and
`final_markdown` files. Missing files, `null` error counts, partial review,
table-only review, and text-only equivalence do not meet the complete standard.

### Current verification inventory

The `verified` tree preserves existing result artifacts while their manifests
record the verification scope. At the time of this audit:

- 1 PDF is completely page-verified: the Bendamustine coverage policy.
- 31 coverage policies have table-only vision verification.
- 1 medical brochure has text-content and reading-order verification for all
  132 pages, but not visual-layout verification.
- 21 PDFs have no complete verification evidence.

Therefore, under the complete HTML-versus-PDF definition, 1 of the 54 source
documents is verified and 53 still require complete page verification.
