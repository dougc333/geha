# GEHA table screenshots

Table-region screenshots exported from the original coverage-policy PDFs in
`/Users/dc/geha/downloads/coverage-policies`.

## Current export

- 35 original PDF documents processed; 99 table-region screenshots exported.
- Duplicate OCR-derived `*_openai.pdf` files were excluded.
- One folder per document, named after the source PDF without `.pdf`.
- Screenshots are lossless PNG crops rendered at 216 DPI with a 4-point margin.
- Source PDFs are not modified. No OCR, LLM calls, or external uploads are used.

These counts describe the current export, not a guarantee that every possible
table in the source collection was detected. See `batch-summary.json` for the
machine-readable report.

## Folder layout

```text
table-screenshots/
  README.md
  batch-summary.json
  contact-sheet-01.png
  ...
  geha-coverage-policy-bendamustine/
    page-01-table-01.png
    page-02-table-01.png
    page-03-table-01.png
    manifest.json
    tables.md
  <other-document-name>/
    ...
```

Page numbers are one-based. Table numbering restarts on each page, ordered from
top to bottom, then left to right. A table spanning multiple PDF pages is saved
as separate page-level crops; the exporter does not stitch these together.

## Files

- **`page-XX-table-YY.png`**: rendered source pixels, not reconstructed table text.
- **`manifest.json`**: source path and SHA-256, page information, detection method,
  table boundaries, row/column counts, available cell text, screenshot dimensions,
  screenshot SHA-256, and text-availability flags.
- **`tables.md`**: extracted cells formatted with Markdown pipe separators. Tables
  without embedded text are marked as requiring OCR instead of presenting empty
  cells as successful extraction.
- **`contact-sheet-XX.png`**: thumbnail grids for visual review. Use the individual
  PNGs for full-resolution reading.
- **`batch-summary.json`**: per-document page/table counts, processing status,
  and pages without embedded text.

Bounding boxes use PDF points (72 points per inch), with a top-left origin:
`[x0, top, x1, bottom]`. The screenshot includes padding beyond the table box.

## How detection works

1. `pdfplumber` identifies thin filled rectangles representing table borders.
2. If that finds no tables on a page, a strict vector-line detector is tried.
   This avoids treating ordinary filled text rectangles as table boundaries.
3. Candidates must contain at least two rows and two columns.
4. PDFium renders the page at 3x scale (216 DPI), then the detected region is cropped.
5. Each PNG is reopened to verify it can be decoded and its dimensions match.
6. Manifests, Markdown cell text, and contact sheets are written.

The batch script reuses `detect()` from `render_table_detection_apng.py`.
It exports screenshots and contact sheets, not an animation for every document.
The earlier Bendamustine animation remains in the parent outputs folder.

## Review and limitations

The exported contact sheets were visually reviewed. One Imdelltra page-1
paragraph was a false positive; the fallback was tightened and that crop was
moved outside this collection to
`../rejected-table-detections/imdelltra-page-01-not-a-table.png`.

Three captured tables have no embedded cell text and need OCR for searchable text:

- Datroway: page 1, table 1; page 3, table 1.
- Elrexfio: page 2, table 1.

The screenshots remain readable because rendering does not require embedded text.
A page's `review_needed` flag currently means it lacks embedded characters; it is
not a record of whether a human has visually reviewed the page.

Important limits:

- Borderless tables and image-only table borders may be missed.
- Single-column or single-row structures are excluded.
- A successful status means processing succeeded, not that recall or text accuracy
  was independently certified.
- Merged cells, continuation rows, and missing/repeated headers need review before
  using `tables.md` as RAG ground truth. The Markdown formatter assumes the first
  extracted row is a header, which is not always true on continuation pages.
- Screenshot hashes support integrity checks; they do not make the collection an
  immutable audit log or establish clinical correctness.

## Rerun the export

Scripts:

- `/Users/dc/geha/cv/work/export_all_table_screenshots.py`
- `/Users/dc/geha/cv/work/render_table_detection_apng.py` (required sibling module)

Python dependencies: `pdfplumber`, `pypdfium2`, and `Pillow`.

Using the bundled Python environment used for this export:

```bash
/Users/dc/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  /Users/dc/geha/cv/work/export_all_table_screenshots.py \
  --source-dir /Users/dc/geha/downloads/coverage-policies \
  --output-dir /Users/dc/geha/cv/outputs/table-screenshots
```

Alternatively, run the same script with a Python environment containing those
dependencies. Input discovery is nonrecursive and excludes `*_openai.pdf`.

**Rerun caution:** existing files with matching names are overwritten. Stale
screenshots from older detections are not automatically removed. For a clean
comparison or retained history, choose a new `--output-dir` rather than reusing
this folder. Inspect `batch-summary.json` for errors after each run.
