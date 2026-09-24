"""State and artifact schemas for the one-iteration cleaning graph."""

from __future__ import annotations

from typing import Literal, TypedDict


class TableArtifact(TypedDict):
    extractor: Literal["pdfplumber", "docling"]
    number: int
    page: int
    markdown: str
    columns: list[str]
    rows: list[list[str]]


class ChunkArtifact(TypedDict):
    number: int
    pages: list[int]
    headings: list[str]
    text: str


class ReviewIssue(TypedDict):
    artifact: str
    page: int
    kind: str
    pdf_evidence: str
    extracted_evidence: str
    explanation: str


class CleaningState(TypedDict, total=False):
    # Input and run control. This graph intentionally permits only iteration 1.
    pdf_path: str
    output_dir: str
    vision_model: str
    use_vision: bool
    iteration: int
    max_iterations: int

    # Source document and extraction outputs.
    source_sha256: str
    page_count: int
    pdfplumber_markdown: str
    pdfplumber_corrected_markdown: str
    pdfplumber_tables: list[TableArtifact]
    pdfplumber_corrected_tables: list[TableArtifact]
    docling_markdown: str
    docling_chunks_markdown: str
    docling_tables_markdown: str
    docling_tables: list[TableArtifact]
    docling_chunks: list[ChunkArtifact]
    page_images: list[str]

    # Review result. No node writes corrected data.
    issues: list[ReviewIssue]
    reviewed_units: int
    matched_units: int
    uncertain_units: int
    status: Literal["pending", "needs_human_review", "visually_matched"]
    error_report: str
