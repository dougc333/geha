"""Export raw Docling table DataFrames to standalone HTML files."""

from __future__ import annotations

import argparse
from pathlib import Path

from .raw_table_html import save_raw_tables
from .paths import PDF_DIR, RAW_TABLES_DIR


def extract_docling_tables_html(
    pdf_path: Path, output_dir: Path | None = None,
) -> list[Path]:
    """Preserve Docling's columns and rows exactly; apply no header repair."""
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    pdf_path = pdf_path.expanduser().resolve()
    if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    output_dir = (output_dir or RAW_TABLES_DIR / pdf_path.stem).expanduser().resolve()
    options = PdfPipelineOptions()
    options.do_ocr = False
    options.do_table_structure = True
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )
    document = converter.convert(pdf_path).document
    tables = [
        (
            int(table.prov[0].page_no) if table.prov else 1,
            table.export_to_dataframe(doc=document),
        )
        for table in document.tables
    ]
    return save_raw_tables(pdf_path, output_dir, "docling", tables)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="Source PDF filename or path")
    parser.add_argument("--output-dir", type=Path, help="Defaults to clean_pdf_langgraph/raw_tables/<stem>")
    args = parser.parse_args()
    pdf_path = PDF_DIR / args.pdf if args.pdf.name == str(args.pdf) else args.pdf
    for path in extract_docling_tables_html(pdf_path, args.output_dir):
        print(path)


if __name__ == "__main__":
    main()
