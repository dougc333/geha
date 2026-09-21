"""Shared Docling converters for the GEHA policy extraction pipelines."""

from __future__ import annotations

from typing import Any

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption


def native_text_converter() -> DocumentConverter:
    """Build a PDF converter that is prohibited from running OCR."""
    options = PdfPipelineOptions()
    options.do_ocr = False
    options.do_table_structure = True
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=options),
        }
    )


def require_embedded_text(document: Any, pdf_name: str) -> None:
    """Reject image-only input; the native-text pass intentionally has no OCR."""
    if not document.export_to_text().strip():
        raise ValueError(f"{pdf_name} has no extractable embedded text; OCR is disabled")
