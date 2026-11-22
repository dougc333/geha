# Split benefits research PDFs into single pages

This wrapper calls the existing `geha_processing.pdf.split_pdf_pages()` function.
It does not implement PDF splitting itself.

```bash
cd /Users/dc/geha
.venv/bin/python minimal/split_single_page/split_all.py
```

Each source keeps its relative path below `split_single_page`. For example,
`benefits_research/cri.georgetown.edu/wp-content/uploads/2025/12/CRI_WP_Rao_Burke_EmpBen_Dec2025.pdf`
produces `split_single_page/cri.georgetown.edu/wp-content/uploads/2025/12/CRI_WP_Rao_Burke_EmpBen_Dec2025/page-001/source.pdf`
through `page-030/source.pdf`.
