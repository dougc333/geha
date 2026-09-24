"""Intentionally naive pdfplumber and raw Docling extraction.

Do not promote numeric DataFrame headers or merge next-page table fragments here.
Those are deliberate QC targets, not omissions to repair in this module.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .schema import ChunkArtifact, TableArtifact


def write_new(path: Path, content: str) -> None:
    """Never overwrite an earlier extraction or review artifact."""
    with path.open("x", encoding="utf-8") as stream:
        stream.write(content)


def source_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def correct_pdfplumber_tables(tables: list[TableArtifact]) -> list[TableArtifact]:
    """Apply conservative, non-LLM repairs to PDFPlumber table artifacts.

    PDFPlumber often returns a numeric DataFrame header when it cannot identify
    the first row as a header.  Promote that first non-empty row only when the
    header is entirely numeric, and discard rows that are completely empty.
    Page-boundary decisions are deliberately left untouched for human review.
    """
    import pandas as pd

    corrected: list[TableArtifact] = []
    for table in tables:
        columns = list(table["columns"])
        rows = [[str(cell).strip() for cell in row] for row in table["rows"]]
        rows = [row for row in rows if any(cell for cell in row)]
        numeric_header = columns and all(column.isdigit() for column in columns)
        if numeric_header and rows and len(rows[0]) == len(columns):
            candidate = rows.pop(0)
            if any(candidate):
                columns = candidate
        corrected.append({
            **table,
            "columns": columns,
            "rows": rows,
            "markdown": pd.DataFrame(rows, columns=columns).to_markdown(index=False),
        })
    return corrected


def naive_pdf_extract(pdf_path: Path, output_dir: Path) -> dict[str, Any]:
    """Extract each PDF page independently with pdfplumber, preserving errors.

    DataFrame's default 0/1/2 columns are retained. The first extracted row is
    *not* promoted to a header, and tables spanning pages are *not* joined.
    """
    import pandas as pd
    import pdfplumber

    sections: list[str] = []
    tables: list[TableArtifact] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, 1):
            sections.append(f"## Page {page_number}\n\n{page.extract_text() or ''}")
            for rows in page.extract_tables():
                if not rows:
                    continue
                frame = pd.DataFrame(rows)  # Intentionally leave numeric headers.
                number = len(tables) + 1
                markdown = frame.to_markdown(index=False)
                tables.append({
                    "extractor": "pdfplumber",
                    "number": number,
                    "page": page_number,
                    "markdown": markdown,
                    "columns": [str(column) for column in frame.columns],
                    "rows": frame.fillna("").astype(str).values.tolist(),
                })
                sections.append(f"### pdfplumber table {number} (page {page_number})\n\n{markdown}")
        page_count = len(pdf.pages)

    markdown_path = output_dir / f"{pdf_path.stem}_pdfplumber.md"
    write_new(markdown_path, "\n\n".join(sections) + "\n")
    corrected_tables = correct_pdfplumber_tables(tables)
    corrected_sections = [
        f"### corrected pdfplumber table {table['number']} (page {table['page']})\n\n"
        f"{table['markdown']}"
        for table in corrected_tables
    ]
    corrected_path = output_dir / f"{pdf_path.stem}_pdfplumber_corrected.md"
    write_new(corrected_path, "\n\n".join(corrected_sections) + "\n")
    return {
        "page_count": page_count,
        "pdfplumber_markdown": str(markdown_path),
        "pdfplumber_tables": tables,
        "pdfplumber_corrected_markdown": str(corrected_path),
        "pdfplumber_corrected_tables": corrected_tables,
    }


def docling_extract(pdf_path: Path, output_dir: Path) -> dict[str, Any]:
    """Export raw Docling Markdown, chunks, and table DataFrames once."""
    from docling.chunking import HybridChunker
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer

    options = PdfPipelineOptions()
    options.do_ocr = False
    options.do_table_structure = True
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )
    document = converter.convert(pdf_path).document
    tokenizer = HuggingFaceTokenizer.from_pretrained(
        model_name="BAAI/bge-small-en-v1.5", max_tokens=700
    )
    chunker = HybridChunker(tokenizer=tokenizer, merge_peers=True)

    chunks: list[ChunkArtifact] = []
    for number, chunk in enumerate(chunker.chunk(document), 1):
        pages = sorted({
            int(prov.page_no)
            for item in (getattr(chunk.meta, "doc_items", None) or [])
            for prov in (getattr(item, "prov", None) or [])
            if getattr(prov, "page_no", None)
        })
        chunks.append({
            "number": number,
            "pages": pages,
            "headings": list(getattr(chunk.meta, "headings", None) or []),
            "text": chunker.contextualize(chunk),
        })

    tables: list[TableArtifact] = []
    for number, table in enumerate(document.tables, 1):
        frame = table.export_to_dataframe(doc=document)
        page = int(table.prov[0].page_no) if table.prov else 1
        tables.append({
            "extractor": "docling",
            "number": number,
            "page": page,
            "markdown": frame.to_markdown(index=False),  # Raw 0/1/2 headers stay raw.
            "columns": [str(column) for column in frame.columns],
            "rows": frame.fillna("").astype(str).values.tolist(),
        })

    markdown_path = output_dir / f"{pdf_path.stem}.docling.md"
    chunks_path = output_dir / f"{pdf_path.stem}.docling_chunks.md"
    tables_path = output_dir / f"{pdf_path.stem}_docling_tables.md"
    write_new(markdown_path, document.export_to_markdown())
    write_new(
        chunks_path,
        "\n\n".join(
            f"## Chunk {chunk['number']}\n\n"
            f"Pages: {', '.join(map(str, chunk['pages'])) or 'unknown'}\n\n"
            f"Headings: {' > '.join(chunk['headings']) or 'none'}\n\n{chunk['text']}"
            for chunk in chunks
        ) + "\n",
    )
    write_new(
        tables_path,
        "\n\n".join(
            f"## Docling table {table['number']} (page {table['page']})\n\n{table['markdown']}"
            for table in tables
        ) + "\n",
    )
    return {
        "docling_markdown": str(markdown_path),
        "docling_chunks_markdown": str(chunks_path),
        "docling_tables_markdown": str(tables_path),
        "docling_chunks": chunks,
        "docling_tables": tables,
    }


def render_pdf_pages(pdf_path: Path, output_dir: Path, page_count: int, dpi: int = 160) -> list[str]:
    """Render source pages locally without requiring a Poppler executable."""
    if not 100 <= dpi <= 220:
        raise ValueError("dpi must be between 100 and 220")
    import pypdfium2 as pdfium

    paths: list[str] = []
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        if len(pdf) != page_count:
            raise ValueError("Extracted page count does not match the source PDF")
        for page_number in range(1, page_count + 1):
            target = output_dir / f"{pdf_path.stem}_images_{page_number}.png"
            if target.exists():
                raise FileExistsError(f"Review image already exists: {target}")
            page = pdf[page_number - 1]
            try:
                bitmap = page.render(scale=dpi / 72)
                try:
                    image = bitmap.to_pil()
                    try:
                        image.save(target, format="PNG")
                    finally:
                        image.close()
                finally:
                    bitmap.close()
            finally:
                page.close()
            if not target.is_file() or target.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
                raise RuntimeError(f"Could not render page {page_number} as PNG")
            paths.append(str(target))
    finally:
        pdf.close()
    return paths
