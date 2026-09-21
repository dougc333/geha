# One-pass PDF extraction and visual review

This deliberately preserves first-pass extraction defects. The `pdfplumber`
export uses default numeric DataFrame columns and leaves tables split at page
boundaries. Docling separately creates full Markdown, contextualized chunks,
and raw table exports. Source PDF pages are rendered locally with Poppler;
an OpenAI vision model compares each table and chunk with those page images.
No node rewrites extraction output or approves the data for ingestion.

Graph: `pdfplumber_extract → docling_extract → render_pdf_pages → vision_compare`
then `write_errors → END` when any mismatch or uncertainty exists, otherwise
`END`. The state schema is in `schema.py`. The run is fixed to one iteration.

Source PDFs are read from `/Users/dc/geha/downloads/coverage-policies`.
Review artifacts remain under `/Users/dc/geha/clean_pdf_langgraph`; the
shared PDF directory is not used for generated output. From the workflow directory:

```bash
# Install/update project dependencies in the GEHA environment first.
cd /Users/dc/geha
uv sync

cd /Users/dc/geha/clean_pdf_langgraph
OPENAI_API_KEY=... /Users/dc/geha/.venv/bin/python -m src.cleaning_graph \
  --pdf geha-coverage-policy-ziihera.pdf

# Or inspect every top-level PDF in downloads/coverage-policies (many vision calls):
/Users/dc/geha/.venv/bin/python -m src.cleaning_graph --all

# Offline extraction smoke test: still writes an uncertainty report.
/Users/dc/geha/.venv/bin/python -m src.cleaning_graph \
  --pdf geha-coverage-policy-ziihera.pdf --no-vision
```

The sample outputs, created in `first_pass/<pdf-stem>/`, are
`geha-coverage-policy-ziihera_pdfplumber.md`,
`geha-coverage-policy-ziihera.docling.md`,
`geha-coverage-policy-ziihera.docling_chunks.md`,
`geha-coverage-policy-ziihera_docling_tables.md`, and
`geha-coverage-policy-ziihera_images_1.png` through the final page.
If anything mismatches or cannot be verified, the graph also writes
`geha-coverage-policy-ziihera_errors.md` and stops for human review.

Existing outputs are never overwritten. To run a fresh iteration, archive the
old `first_pass/<pdf-stem>/` artifacts after reviewing them. The CLI accepts
only top-level filenames from the shared coverage-policy directory.

The vision service receives the extracted unit and relevant rendered PDF page
images. Do not run it on PDFs containing protected member data without an
approved data-transfer path. Requests use `store=False`.

## Raw HTML for human side-by-side review

These are two independent, correction-free exporters. Each creates one
self-contained HTML file per table under `raw_tables/<pdf-stem>/` by default. File names
include `_pdfplumber_` or `_docling_`, the table number, and the source page.
The CSS comes from the earlier `extract_pdf_tables_html.py` design, but **no**
header promotion, continuation repair, or revision-history filtering is used.

```bash
cd /Users/dc/geha/clean_pdf_langgraph
/Users/dc/geha/.venv/bin/python -m src.extract_pdfplumber_tables_html \
  geha-coverage-policy-ziihera.pdf
/Users/dc/geha/.venv/bin/python -m src.extract_docling_tables_html \
  geha-coverage-policy-ziihera.pdf
```

These HTML exports are for human QC; the one-pass graph's vision node still
compares raw Markdown against source PDF page images. The HTML programs read
the PDFs directly rather than transforming a Markdown file, so compare their
cells with the corresponding raw Markdown when investigating parser output.

## Batch LangGraph: both extractors and HTML-vs-PDF review

`batch_review_graph.py` loops over all top-level PDFs in the shared coverage-policy
directory. For each PDF it creates a new subdirectory in a unique local `review_runs` run directory,
so older extractions are not overwritten. Its nodes are:

`pdfplumber_extract → docling_extract → build_combined_html → render_pdf_pages
→ human_review → vision_compare → write_extractor_reports`.

The `human_review` node interrupts before any data is sent to OpenAI. Its
payload lists the local Markdown, HTML, and page-image paths for inspection.
An SQLite checkpoint in the per-PDF output directory lets a later CLI process
resume without repeating extraction. Approval runs the vision comparison;
rejection skips the model call and writes unverified reports. This is one
approval per PDF, not one per extraction step.

The combined files `<stem>_pdfplumber_tables.html` and
`<stem>_docling_tables.html` each contain every raw table from that extractor.
They reuse the same captured rows as the Markdown output, with no header or
page-boundary repair. The model receives the HTML table markup as text and the
corresponding source PDF page PNGs as images. It checks table-data fidelity,
not pixel-perfect CSS styling. Results go to `<stem>_pdfplumber_errors.md` and
`<stem>_docling_errors.md` separately. Any failed model call is marked
unverified; it is never treated as a match.

```bash
cd /Users/dc/geha/clean_pdf_langgraph

# Extract one PDF. The command stops before any vision request and prints the
# per-PDF output_dir containing the HTML, Markdown, and page PNG files:
/Users/dc/geha/.venv/bin/python -m src.batch_review_graph \
  --pdf geha-coverage-policy-ziihera.pdf --vision-model gpt-4o-mini

# After inspecting the files, resume the exact output_dir printed above:
/Users/dc/geha/.venv/bin/python -m src.batch_review_graph \
  --resume /Users/dc/geha/clean_pdf_langgraph/review_runs/RUN_ID/geha-coverage-policy-ziihera \
  --approve

# Or decline external vision review (no OpenAI call):
/Users/dc/geha/.venv/bin/python -m src.batch_review_graph \
  --resume /Users/dc/geha/clean_pdf_langgraph/review_runs/RUN_ID/geha-coverage-policy-ziihera \
  --reject
```

Only `--approve` invokes the OpenAI Responses API with `store=False`. Source-page
PNGs and extracted HTML table text leave the machine in that mode. The older
`cleaning_graph.py` remains separate and does not generate the combined HTML.

## Local slideshow

Use the local slideshow to cycle through source PDF-page PNGs and Docling HTML
tables side by side every three seconds. It does not call an external service.

```bash
cd /Users/dc/geha/clean_pdf_langgraph
/Users/dc/geha/.venv/bin/python artifact_slideshow.py --policy ziihera
```

Open `http://127.0.0.1:8765/`. Use `--recursive` to include artifacts inside
`review_runs`, `--interval` to change the delay, or `--port` to select another
local port. The viewer also provides pause, previous, and next controls. If the
selected policy has no existing artifacts, the command creates them locally in
`slideshow_cache/<pdf-stem>/` with vision disabled; this preparation makes no
OpenAI request.
