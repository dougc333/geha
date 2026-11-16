"""Shared PDF and Docling converter primitives."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _docling_converter(*, do_ocr: bool) -> Any:
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions()
    options.do_ocr = do_ocr
    options.do_table_structure = True
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )


def native_text_converter() -> Any:
    return _docling_converter(do_ocr=False)


def ocr_table_converter() -> Any:
    return _docling_converter(do_ocr=True)


def require_embedded_text(document: Any, pdf_name: str) -> None:
    if not document.export_to_text().strip():
        raise ValueError(f"{pdf_name} has no extractable embedded text; OCR is disabled")


def split_pdf_pages(source: Path, pages_dir: Path) -> list[Path]:
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(source)
    outputs: list[Path] = []
    for page_index, page in enumerate(reader.pages):
        target = pages_dir / f"page-{page_index + 1:03d}" / "source.pdf"
        target.parent.mkdir(parents=True, exist_ok=True)
        writer = PdfWriter()
        writer.add_page(page)
        with target.open("wb") as stream:
            writer.write(stream)
        outputs.append(target)
    return outputs
