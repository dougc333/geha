"""Shared document-processing primitives for the GEHA repository.

Application directories own orchestration and artifact layouts.  Reusable
processing behavior belongs here so extraction, repair, and evaluation paths
do not silently diverge.
"""

from .contextual import (
    CLAUDE_MODEL,
    FALLBACK_BETA,
    PROMPT_VERSION,
    ClaudeContextResult,
    ContextGenerator,
    contextual_retrieval_prompt,
    make_claude_context_generator,
)
from .io import (
    atomic_json,
    atomic_jsonl,
    read_jsonl,
    sha256_file,
    sha256_text,
    write_jsonl,
)
from .pdf import native_text_converter, ocr_table_converter, require_embedded_text, split_pdf_pages
from .tables import (
    KNOWN_COLUMN_HEADERS,
    choose_replacement_headers,
    inherit_continuation_header,
    normalized,
    promote_embedded_header,
    table_headers_are_default,
)

__all__ = [
    "CLAUDE_MODEL",
    "FALLBACK_BETA",
    "PROMPT_VERSION",
    "ClaudeContextResult",
    "ContextGenerator",
    "KNOWN_COLUMN_HEADERS",
    "atomic_json",
    "atomic_jsonl",
    "choose_replacement_headers",
    "contextual_retrieval_prompt",
    "inherit_continuation_header",
    "make_claude_context_generator",
    "native_text_converter",
    "normalized",
    "ocr_table_converter",
    "promote_embedded_header",
    "read_jsonl",
    "require_embedded_text",
    "sha256_file",
    "sha256_text",
    "split_pdf_pages",
    "table_headers_are_default",
    "write_jsonl",
]
