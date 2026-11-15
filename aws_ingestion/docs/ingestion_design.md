# Scalable multipage PDF ingestion with human approval

Status: design draft. Nothing here is implemented yet.

## Goals

Turn the hardest PDFs in `crawl_results/most_complex_pdfs.md` into verified page HTML and Markdown. Run two pipelines per page, compare them, and require a human approval check before any page reaches RAG.

## Shared stage: segmentation

1. Split each PDF into one-page PDFs with PyMuPDF.
2. Render each page to PNG (150 dpi for review, 300 dpi for OCR).
3. Record per page: `doc_sha256`, `page_no`, `has_text_layer` (chars > threshold), image count, table hint, language guess.
4. Every later artifact is keyed by `(doc_sha256, page_no, pipeline, pipeline_version)`, so work is idempotent and resumable.

`has_text_layer` decides routing in pipeline 2. Pages are the unit of work.

## Pipeline 1: tesseract baseline, then ReAct repair

```
page.pdf -> tesseract (hOCR) -> baseline.html -> ReAct loop (max 5) -> final.html -> docling -> page.md
```

- hOCR is already HTML with bounding boxes, so the baseline needs only a light cleanup into semantic HTML (headings, paragraphs, tables, figures).
- The loop repairs the HTML directly.
- Docling converts the final HTML to Markdown, and Docling runs after the loop, never inside it.

## Pipeline 2: spec first, then ReAct repair

```
page.pdf -> text layer? --yes--> pymupdf blocks --\
                         \--no--> tesseract -------> page.spec.json -> render -> html -> ReAct loop -> spec' -> html' -> docling -> page.md
```

- The page spec is a JSON document: page size, ordered blocks (`heading`, `paragraph`, `table`, `figure`, `list`, `footnote`), bboxes, text, table cells, figure data tables, and provenance per block (`pymupdf`, `tesseract`, `agent`).
- The spec is the source of truth and the HTML is derived from it by a deterministic renderer. The agent edits the spec with JSON-patch operations and never edits HTML directly. This makes every fix reviewable, diffable and replayable.
- Answer to "can the spec render to HTML": yes. One renderer (`spec_to_html`) serves the loop, the review UI and the Docling input. Pipeline 1 could also emit the same spec, so both pipelines would share one review format later.

## ReAct verification loop (both pipelines)

Tools the agent gets:

| Tool | Purpose |
|---|---|
| `render(html) -> png` | Playwright screenshot at the page's aspect ratio |
| `diff_regions(pdf_png, html_png)` | Ranked list of mismatched regions with crops |
| `text_diff(reference, html_text)` | Word-level adds, drops, substitutions |
| `numeric_check()` | Every number, percent and currency token in the reference must appear in the HTML |
| `crop(bbox)` | Zoomed view of one region of the source page |
| `patch(ops)` | Apply edits (spec patch in pipeline 2, HTML edit in pipeline 1) |

Loop: observe errors, reason, patch, re-render, re-measure.

Stop when any of these holds:
- Error count is 0 (early stop).
- Iteration 5 is reached.
- No improvement for 2 consecutive iterations.

Error count is the sum of: missing or extra words, mismatched numeric tokens, table row or column count mismatches, and regions the vision check flags as different.

Reference text:
- Pages with a text layer use PyMuPDF text as ground truth, so text errors are objective.
- Scanned pages have no ground truth. The vision judge looks at the same pixels that tesseract misread, so errors are correlated. Flag these pages `low_confidence` and send them to the front of the human queue.

"Same" means semantically equal (text, numbers, table structure, reading order, figure data), not pixel-identical.

## Scaling

- Page-level queue (SQS or a Postgres job table), stateless workers, results written to object storage (S3, as `aws/` already suggests) plus a Postgres row per page.
- Per-page cost cap: the OCR and the 5-iteration loop are bounded, so cost is predictable. Cache by page hash, so repeated template pages are free.
- Huge directories (4,000+ pages) cannot be reviewed page by page. Compute a risk score per page: loop hit the cap, `low_confidence`, residual errors, table-heavy, numeric mismatch. Humans review in risk order. Clean pages get a random sample audit (for example 5%). A failed sample re-opens its neighbors.
- Run the benchmark set from `most_complex_pdfs.md` first: `Guia-sencilla-sobre-medicare.pdf` (scanned), `2024_white_paper.pdf` (figures), `PA_Chip_Application_ES.pdf` (forms), `allstatesums-hwc2022.pdf` (repeated tables), and a 50-page slice of `TX-STAR-Kids-Provider-Directory-Houston.pdf`.
- The existing `src/ey_docling_pipeline.py` and `src/repair_ey_page24.py` already follow this shape: page PDFs, semantic HTML, a visual verification JSON, and a manual repair. They become the first reference run.

## Data model

```
document(id, sha256, source_url, page_count)
page(doc_id, page_no, has_text_layer, risk_score, status)
run(doc_id, page_no, pipeline, version, iterations, errors_final, stop_reason, html_uri, spec_uri, md_uri)
approval(doc_id, page_no, run_id, content_sha256, reviewer, decision, note, at)
```

`status`: `pending -> needs_review -> approved | rejected -> reprocess`.

An approval stores the SHA-256 of the exact HTML and spec it covered. Any later edit invalidates it.

## Review app

Stack: TypeScript, React 18, Tailwind, Vite, TanStack Query, pdf.js for the source page, a sandboxed `<iframe srcdoc>` for the HTML.

Screens:
1. **Queue**: filter by document, status, risk, pipeline, `low_confidence`. Sorted by risk.
2. **Page review**:
   - Left pane is the source page (pdf.js). Right pane is the rendered HTML. Zoom and scroll are synced.
   - Three view modes: side by side, overlay with opacity slider, and difference heatmap.
   - Block-level linking: hover a block in the HTML to highlight its bbox on the PDF, and the reverse.
   - Pipeline selector: A (tesseract + repair), B (spec + repair), or A vs B. In A vs B mode, differing blocks are listed and the reviewer picks per block.
   - Residual-error panel: the numeric and word diffs the loop could not close, with crops.
   - Spec editor (pipeline 2): edit a block's text or table cells, then re-render.
3. **Approval gate**: a per-page checkmark (`A` approve, `R` reject with reason, `J/K` next and previous page). A document is `approved` only when every page is approved, or when the risk-ordered review plus sample audit policy is satisfied. The Markdown export and RAG indexing run only on approved pages.

API sketch:
```
GET  /documents/:id/pages?status=&sort=risk
GET  /pages/:doc/:n/runs            # both pipelines, metrics, artifacts
GET  /pages/:doc/:n/diff?a=1&b=2
PUT  /pages/:doc/:n/spec            # reviewer edits, triggers re-render
POST /pages/:doc/:n/approval        # {run_id, content_sha256, decision, note}
POST /documents/:id/export          # approved pages only
```

## Build order

1. Segmenter, manifest and page routing (text layer detection).
2. `spec_to_html` renderer and the spec JSON schema, with unit tests (well-formedness, round-trip, every block has a bbox).
3. Pipeline 1 and pipeline 2 baselines with no agent, giving an operating point per page.
4. ReAct loop and metrics, evaluated on the benchmark set against PyMuPDF ground truth.
5. Review app and approval API.
6. Queue workers and risk scoring.

## Verifiers

- Unit tests: spec schema validity, renderer determinism, numeric-token extraction, stop-condition logic, approval invalidated on content change.
- Evals: loop error reduction on pages with known text, pipeline A vs B agreement, reviewer-found errors on sampled auto-clean pages.

## Open questions

- Which model drives the ReAct loop and the vision judge.
- Whether Docling should also run on the source PDF as a third cross-check.
- Reviewer identity and storage for approvals (local SQLite for the demo, Postgres in AWS).
