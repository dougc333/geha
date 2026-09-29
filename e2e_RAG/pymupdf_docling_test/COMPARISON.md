# PyMuPDF vs Docling: table extraction on "Attention Is All You Need"

Test PDF: `../data/1706.03762v7.pdf` (15 pages, born-digital arXiv paper).
Re-run with `/Users/dc/geha/.venv/bin/python run_test.py [pdf]`, which writes
the files below. The run on 2026-09-28 used PyMuPDF 1.28.2 and Docling 2.126.0
on CPU, with Docling's models already cached.

The paper has **4 real tables**: Table 1 (page 6, layer complexity), Table 2
(page 8, BLEU scores), Table 3 (page 9, model variations) and Table 4 (page 10,
parsing results).

## Results

| | PyMuPDF `find_tables()` `lines` (default) | PyMuPDF `find_tables()` `text` | Docling |
|---|---|---|---|
| Tables reported | 6 | 15 | **4** |
| Real tables found | 2 of 4 (Tables 3, 4) | 0 usable | **4 of 4** |
| Missed | **Table 1 and Table 2 (the BLEU table)** | n/a | none |
| False positives | 4 (attention-visualisation figures on pages 13–15, output as grids of word fragments) | 15 (every page, including the title page, turned into a text grid) | 0 |
| Captions | No | No | **Yes**, "Table N: …" attached to each table |
| Structure of found tables | Rows collapsed: each row group is one cell with values joined by `<br>`, so values aren't aligned with their columns | n/a | **One row per model, values aligned with headers**; multi-level headers flattened ("BLEU - EN-DE") |
| Time (15 pages) | 4.9 s | 61 s | 22.9 s |
| Output | `pymupdf_lines/tables.md` | `pymupdf_text/tables.md` | `docling/tables.md`, `docling/document.md` |

## What went wrong with PyMuPDF

- **`lines` (default)** finds tables from drawn ruling lines. arXiv papers use
  "booktabs" tables with only a few horizontal rules and no vertical lines, so
  Tables 1 and 2 weren't detected at all. Table 3 was found, but every row
  group, e.g. (A) with four variants, came out as a single cell, with the
  numbers stacked as `1<br>512<br>512<br>4<br>128…`. Row alignment is lost,
  which is the same problem as the current flattened text. The figures on pages
  13–15 have many lines, so they were misread as tables.
- **`text`** infers columns from word alignment. Ordinary paragraphs are
  aligned too, so it treated each whole page as a table: 15 "tables" and no
  usable ones.

## Docling's minor issues

- **Math loses formatting:** `O ( n 2 · d )` for O(n²·d), `2 . 3 · 10 19` for
  2.3·10¹⁹. The values are correct but spaced, and superscripts are flattened.
- **Merged cells are repeated:** Table 3's row (E), "positional embedding
  instead of sinusoids", spans columns, so the text repeats in each. Row-group
  labels (A)–(D) sit on one row of their group rather than every row.
- **The caption appears twice** in `tables.md` (once from this script, once in
  Docling's Markdown export).
- **Heavier to run:** PyTorch/ONNX layout and table models (about 23 s per
  15-page paper on a laptop CPU). That doesn't fit the current zip-packaged
  Lambda chunker; it needs a container-image Lambda (up to 10 GB) or Fargate.

## Verdict for arXiv-style papers

**Docling is clearly better for tables.** It found every table, with captions,
correct rows and columns, and no false positives. PyMuPDF's table detection is
unusable for booktabs-style academic tables: it misses half of them, scrambles
the rest, and invents tables from figures.

PyMuPDF is still the right tool for fast plain-text extraction, which is what
the `aws_rag` chunker uses it for. For table-aware chunking, the practical
design is:

1. Docling for layout and tables. Emit each table as one chunk, in Markdown with
   its caption.
2. Docling's (or PyMuPDF's) text for the rest of the page, chunked as today.

That needs the chunker to move to a container-image Lambda. Textract (about
$0.015/page) is the managed alternative if running Docling is undesirable.

One paper is a small sample. The same script can be run on the Orca, Self-RAG
and QLoRA PDFs before committing to a design.
