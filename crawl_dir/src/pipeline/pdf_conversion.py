"""Shared Docling converters for the GEHA policy extraction pipelines."""

from __future__ import annotations

from geha_processing.pdf import native_text_converter, require_embedded_text

__all__ = ["native_text_converter", "require_embedded_text"]
