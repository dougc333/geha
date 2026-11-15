# Spec: ingestion pipelines

Review status: DRAFT for human review. Not implemented.

## Common contract

- Input: single-page PDF plus `page.png` (150 dpi) from the segmenter.
- Output per run: `final.html`, `page.md`, `run.json` (metrics, stop reason), and in pipeline 2 also `page.spec.json` (see `page_spec.schema.json`).
- Idempotency key: `(doc_sha256, page_no, pipeline, pipeline_version)`. A run with an existing key is skipped unless `--force`.
- Markdown is produced only by Docling from `final.html`, after the loop ends.

## Segmenter

- MUST split with PyMuPDF; one output PDF per page; zero-padded page numbers.
- MUST write `pages.json` with: `page_no`, `has_text_layer` (chars >= 20), `image_count`, `language_guess`.
- Corrupt pages MUST be recorded with `status: "error"` and not abort the document.

## Pipeline 1: tesseract then ReAct

1. Run tesseract on 300 dpi render with `hocr` output and language from `pages.json`.
2. Clean hOCR into semantic HTML (`h1-h6`, `p`, `table`, `figure`). Keep `data-bbox` attributes.
3. Run the ReAct loop (`react_loop.md`) editing the HTML.
4. Run Docling on `final.html` to produce `page.md`.

## Pipeline 2: spec first

1. If `has_text_layer`: extract blocks with PyMuPDF `get_text("dict")`; provenance `pymupdf`.
   Otherwise: tesseract TSV grouped into blocks; provenance `tesseract`.
2. Validate against `page_spec.schema.json`; reject on failure.
3. Render with deterministic `spec_to_html` (same spec MUST produce byte-identical HTML).
4. Run the ReAct loop editing the spec via JSON Patch only; re-render each iteration.
5. Run Docling on `final.html` to produce `page.md`.

## Acceptance criteria

- Pages with a text layer: final word-level error rate vs PyMuPDF text <= 0.5% or the page is marked `needs_review`.
- All numeric tokens in the reference appear in the HTML, or the page is marked `needs_review`.
- Scanned pages are always `low_confidence` and `needs_review`.
