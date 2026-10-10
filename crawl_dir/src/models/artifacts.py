"""Typed JSON contracts for durable crawl artifacts.

These are intentionally plain ``TypedDict`` objects so the on-disk JSON stays
portable and does not depend on a particular validation framework.
"""

from __future__ import annotations

from typing import Literal, NotRequired, TypedDict


class PageRecord(TypedDict):
    page: int
    source_pdf: str
    source_sha256: str
    markdown: str
    html: NotRequired[str]
    table_ids: list[str]
    status: Literal["pending", "passed", "failed"]


class TableRecord(TypedDict):
    table_id: str
    document_id: str
    document_version: str
    plan_year: int | None
    section: str
    source_pages: list[int]
    source_table_numbers: list[int]
    headers: list[str]
    rows: list[dict[str, str]]
    repairs: list[str]
    review_status: Literal["pending", "approved", "rejected"]


class ChunkRecord(TypedDict):
    chunk_id: str
    document_id: str
    document_version: str
    plan_year: int | None
    pages: list[int]
    section: str
    content_type: Literal["text", "table_row"]
    text: str
    contextualized_text: str
    table_ids: list[str]
    source_sha256: str
    review_status: Literal["pending", "approved", "rejected"]


class QcReport(TypedDict):
    status: Literal["needs_visual_review", "passed", "failed"]
    source_sha256: str
    page_count: int
    chunk_count: int
    table_count: int
    structural_errors: list[dict[str, object]]
    structural_warnings: list[dict[str, object]]
    visual_verification: dict[str, object]

