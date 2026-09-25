# Single-page Docling table review

`single_page_table_graph.py` reuses the table-review and correction nodes from
`/Users/dc/geha/clean_pdf_langgraph`. It processes each split one-page PDF with
Docling independently. Every page PDF is a separate LangGraph input and gets
its own output directory. The original three-policy relationship is retained
in `batch_summary.json` as `source_pdf` and `original_page` metadata.

The default output layout mirrors the existing batch runs:

```text
src_tables/review_runs/run-<timestamp>-<id>/
  batch_summary.json
  <policy-stem>-page-001/
    checkpoint.sqlite
    <policy-stem>-page-001.docling.md
    <policy-stem>-page-001.docling_chunks.md
    <policy-stem>-page-001_docling_tables.md
    <policy-stem>-page-001_docling_tables.html
    <policy-stem>-page-001_docling_tables_corrected.html
    <policy-stem>-page-001_docling_errors.md
    <policy-stem>-page-001_images_1.png
```

Discover the inputs without creating files:

```bash
cd /Users/dc/geha
.venv/bin/python \
  downloads/coverage-policies/aa_source_not_consistent/src_tables/single_page_table_graph.py \
  --list
```

Run extraction and the approved vision review:

```bash
cd /Users/dc/geha
GEHA_NO_BROWSER=1 .venv/bin/python \
  downloads/coverage-policies/aa_source_not_consistent/src_tables/single_page_table_graph.py \
  --approve
```

Without `--approve`, extraction still runs but the tables are recorded as
unverified and no page image or table content is sent to OpenAI.
