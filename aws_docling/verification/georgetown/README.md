# Georgetown PDF local verification

Source: `/Users/dc/geha/crawl_dir/raw/benefits_research/cri.georgetown.edu/wp-content/uploads/2025/12/CRI_WP_Rao_Burke_EmpBen_Dec2025.pdf` (30 pages).

Run locally with the repository virtual environment:

```bash
cd /Users/dc/geha
.venv/bin/python aws_docling/verification/georgetown/extract_local.py \
  crawl_dir/raw/benefits_research/cri.georgetown.edu/wp-content/uploads/2025/12/CRI_WP_Rao_Burke_EmpBen_Dec2025.pdf
```

The saved `document-with-images.md` is the complete Docling Markdown output with six base64 PNG images placed where the six figure placeholders were. `figures/figure-001.png` through `figures/figure-006.png` are the separate crops. `document-with-figure-links.md` links to those PNGs using relative image paths, so GitHub and Markdown viewers that resolve local assets can display them without base64 data. `figures.json` records their PDF page numbers and boxes. Docling 2.126.0 produced these artifacts locally with `generate_page_images=True`, `generate_picture_images=True`, and `ImageRefMode.EMBEDDED`.

To review it in the React viewer, use **Add PDFs and Markdown** and select this `document-with-images.md` together with a copy of the source PDF renamed `document-with-images.pdf`, so the local filename pairing matches. The image crops render inline in the Markdown pane.

These images are readable, but the extraction is not fully verified: Table 4 still merges rows and columns, the equation is not decoded, and some conclusion paragraphs are out of order. Trying `table_structure_options.do_cell_matching=False` on pages 19–20 did not repair Table 4.

Run `audit_extraction.py` against the source PDF to regenerate `summary.json`. The audit scans the complete saved Markdown for structural errors and records source pages, Markdown lines, and evidence. It identifies errors for post-processing, but does not rewrite table cells or claim a complete transcription audit.
It also matches each figure PNG against a rendered source PDF page at the recorded bounding box. This verifies the crops' provenance and placement, not the numerical values depicted by the charts.

```bash
.venv/bin/python aws_docling/verification/georgetown/audit_extraction.py \
  crawl_dir/raw/benefits_research/cri.georgetown.edu/wp-content/uploads/2025/12/CRI_WP_Rao_Burke_EmpBen_Dec2025.pdf
.venv/bin/python aws_docling/verification/georgetown/export_tables.py
```

The table exporter writes `tables/table-1.csv` through `tables/table-7.csv` in long form. Each row retains the PDF page, Markdown line, section number, variable, column, and extracted value. `summary.json` marks Tables 4, 5, and 7 for review because their Markdown contains merged rows. These CSVs preserve the extraction; they do not correct those cells.

Docling's `do_chart_extraction=True` extracts values from chart images. The project's `transformers==5.17.0` failed in Granite Vision with `TypeError: create_causal_mask() got an unexpected keyword argument 'cache_position'`. An isolated test using `transformers==4.57.3`, `tokenizers==0.22.2`, and `huggingface-hub==0.36.0` succeeded on page 11. Its chart values are in `chart-page-011-01.csv` and `chart-page-011.md`; they match the visible bars in `figure-002.png`. Chart extraction remains disabled in the AWS worker until the container runtime is checked.

To repeat the chart test without changing the project virtual environment:

```bash
uv venv --system-site-packages /private/tmp/docling-chart-venv
uv pip install --python /private/tmp/docling-chart-venv/bin/python --no-deps \
  'transformers==4.57.3' 'tokenizers==0.22.2' 'huggingface-hub==0.36.0'
cd /Users/dc/geha
.venv/bin/python aws_docling/verification/georgetown/extract_chart_local.py \
  crawl_dir/raw/benefits_research/cri.georgetown.edu/wp-content/uploads/2025/12/CRI_WP_Rao_Burke_EmpBen_Dec2025.pdf \
  --compat-site-packages /private/tmp/docling-chart-venv/lib/python3.12/site-packages
```
