# GEHA document downloader

This project downloads the curated 54-document GEHA PDF test corpus using the
canonical URLs and SHA-256 hashes in `src/documents.json`.

Run it with the existing GEHA Python environment (no third-party packages are
required):

```bash
/Users/dc/geha/.venv/bin/python /Users/dc/geha/crawl_dir/src/download_geha_docs.py
```

PDFs are written to `/Users/dc/geha/crawl_dir/downloads` under the
`coverage-policies`, `dental`, and `medical` branches. Each file is downloaded
atomically and verified as a PDF. Existing files whose hashes match are safely
skipped. The run report is `/Users/dc/geha/crawl_dir/download_run.json`, leaving
the `downloads` tree as a PDF-only corpus.

By default, a document fails if its bytes no longer match the curated hash.
Use `--allow-changed` only when intentionally accepting a newer upstream PDF.

## Source corpus status

The `downloads` tree contains only the original downloaded, multipage PDFs. It
does not contain the generated single-page files found in the older
`/Users/dc/geha/downloads` processing tree.

Verified on October 7, 2026:

- 54 downloaded source PDFs are recorded by the curated corpus.
- All 54 are present under `crawl_dir/downloads` at the same relative paths.
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

The MCP caller supplies one original multipage PDF using its path relative to
`crawl_dir/downloads`. The worker creates the single-page inputs internally:

```text
Original multipage PDF
        |
        v
Create immutable source snapshot
        |
        v
Split into single-page PDFs and render source-page PNGs
        |
        v
Extract each page to initial HTML and Markdown
        |
        v
Render the candidate HTML
        |
        v
Compare candidate rendering with the corresponding source page
        |
        +-- match --------------------------> accept page
        |
        `-- mismatch --> correct --> compare again (maximum 3 passes)
                                      |
                                      v
                            write final artifacts and batch.json
```

The normal MCP entry point is:

```text
run_pdf_document(
  document="coverage-policies/example.pdf",
  allow_external_model=false,
  max_passes=3,
  force_reprocess=false
)
```

When external vision is disabled, pages requiring visual review cannot be
declared completely verified. Enabling it explicitly permits source-page images
and candidate HTML to be sent to the configured model. Only enable that option
for documents authorized for that provider.

Before processing, the MCP server hashes the source and checks prior manifests.
It reuses a result only when the exact source hash matches, every page has an
integer final error count of zero, no page needs review or failed, and every
referenced final HTML and Markdown artifact still exists. Set
`force_reprocess=true` to deliberately bypass reuse.

### Output of a complete run

```text
run_<timestamp>_<id>_mcp_server/
├── input/
│   └── source.pdf
├── pages/
│   ├── page_0001.pdf
│   ├── page_0001.png
│   └── ...
├── extraction/
│   ├── page_0001.initial.html
│   ├── page_0001.initial.md
│   ├── page_0001.final.html
│   ├── page_0001.final.md
│   ├── page_0001.pass_01.json
│   ├── page_0001.pass_01.png
│   └── ...
├── modified_extracted_text.md
├── run.json
└── batch.json
```

A document is completely verified only when `batch.json` reports:

```json
{
  "status": "completed",
  "page_count": 3,
  "pages_passed": 3,
  "pages_needing_review": 0,
  "pages_failed": 0
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
