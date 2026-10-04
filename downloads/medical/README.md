# Medical PDF HTML reconstruction

The current FEHB and PSHB input set contains **844 single-page PDFs**. The
LangGraph workflow in `pdf_html_langgraph.py` extracts each page to HTML,
compares the rendered HTML with the source PDF, and applies at most six
correction passes.

Run artifacts are stored in `html_review_runs/<run-id>/`. Each page directory
contains every HTML version, rendered PNG, structured review, and its final
result. The run-level `batch.json` contains aggregate error counts and the
final zero-error verification.

## Latest six-pass batch result

<!-- PDF_HTML_BATCH_RESULT_START -->
Run `run-20261002T172114` was stopped after processing 5 of the planned 844
pages. Three pages matched with zero model-reported errors; two pages reached
the six-pass limit with 14 total reported errors remaining. This partial run
must not be treated as a completed 844-page error-rate measurement.
<!-- PDF_HTML_BATCH_RESULT_END -->

The reported page error rate is:

`pages that did not finish matched with zero errors / 844 total pages`

The report also includes the total initial and final model-reported errors so
the error-reduction rate can be calculated separately.

## Elevate Plus and Elevate HTML text-equivalence result

The 132 Markdown files in
`fehb/single_pages/2026-geha-fehb-elevate-plus-and-elevate-options-medical-plan-brochure/`
were converted to HTML files in the same directory. Each HTML file was checked
against the authoritative text layer of its paired single-page PDF, with a
maximum of eight correction passes.

- Files processed: **132**
- Files text-equivalent to their PDFs: **132**
- Failed files: **0**
- Final normalized text errors: **0**
- Maximum correction passes used by any file: **1 of 8**
- Initial aggregate token/order errors: **3,328**

Text equivalence means there are no missing or extra normalized text tokens and
no normalized ordering mismatch. It does not verify pixel-level appearance,
fonts, spacing, or visual table layout. The visible corrected HTML uses the PDF
text layer as its authority; the original Docling/Markdown structure, including
tables, is retained in an inert HTML `<template>` for downstream recovery.

Detailed per-file results are recorded in the brochure directory's
`batch.json`.
