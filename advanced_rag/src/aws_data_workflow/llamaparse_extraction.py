"""LlamaParse adapter returning one Markdown string per PDF page."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


PageStatusCallback = Callable[[int, str, str | None, str | None], None]


def extract_llamaparse_pages(
    source: Path,
    *,
    api_key: str,
    tier: str = "agentic",
    client_factory: Callable[..., Any] | None = None,
) -> dict[int, str]:
    """Upload and parse a PDF, returning 1-based page Markdown."""
    if not api_key:
        raise ValueError("LLAMA_CLOUD_API_KEY is required for LlamaParse")
    if not source.is_file():
        raise FileNotFoundError(source)
    if client_factory is None:
        try:
            from llama_cloud import LlamaCloud
        except ImportError as error:
            raise RuntimeError(
                "llama-cloud is required for LlamaParse; install requirements.txt"
            ) from error
        client_factory = LlamaCloud
    client = client_factory(api_key=api_key)
    uploaded = client.files.create(file=str(source), purpose="parse")
    result = client.parsing.parse(
        file_id=uploaded.id,
        tier=tier,
        version="latest",
        expand=["markdown"],
    )
    pages = getattr(getattr(result, "markdown", None), "pages", None) or []
    output: dict[int, str] = {}
    for fallback_number, page in enumerate(pages, start=1):
        page_number = int(getattr(page, "page_number", fallback_number))
        markdown = str(getattr(page, "markdown", "")).strip()
        if markdown:
            output[page_number] = markdown + "\n"
    if not output:
        raise ValueError("LlamaParse returned no page Markdown")
    return output


def extract_llamaparse_split_pages(
    pages_dir: Path,
    *,
    api_key: str,
    tier: str = "agentic",
    client_factory: Callable[..., Any] | None = None,
    on_status: PageStatusCallback | None = None,
    include_pages: set[int] | None = None,
) -> dict[int, str]:
    """Parse split single-page PDFs and checkpoint each completed page."""
    if not api_key:
        raise ValueError("LLAMA_CLOUD_API_KEY is required for LlamaParse")
    if client_factory is None:
        try:
            from llama_cloud import LlamaCloud
        except ImportError as error:
            raise RuntimeError(
                "llama-cloud is required for LlamaParse; install requirements.txt"
            ) from error
        client_factory = LlamaCloud
    client = client_factory(api_key=api_key)
    output: dict[int, str] = {}
    page_sources = sorted(pages_dir.glob("page-[0-9][0-9][0-9]/source.pdf"))
    if not page_sources:
        raise ValueError(f"No split PDF pages found under {pages_dir}")

    for source in page_sources:
        page_number = int(source.parent.name.removeprefix("page-"))
        if include_pages is not None and page_number not in include_pages:
            continue
        checkpoint = source.parent / "llamaparse.md"
        if checkpoint.is_file():
            markdown = checkpoint.read_text(encoding="utf-8").strip()
            if markdown:
                output[page_number] = markdown + "\n"
                if on_status:
                    on_status(page_number, "completed", None, "reused checkpoint")
                continue
        job_id: str | None = None
        try:
            uploaded = client.files.create(file=str(source), purpose="parse")
            job = client.parsing.create(
                file_id=uploaded.id,
                tier=tier,
                version="latest",
            )
            job_id = str(job.id)
            if on_status:
                on_status(page_number, "submitted", job_id, None)
            client.parsing.wait_for_completion(job_id)
            result = client.parsing.get(job_id, expand=["markdown"])
            pages = getattr(getattr(result, "markdown", None), "pages", None) or []
            markdown = "\n\n".join(
                str(getattr(page, "markdown", "")).strip()
                for page in pages
                if str(getattr(page, "markdown", "")).strip()
            )
            if not markdown:
                raise ValueError("LlamaParse returned no page Markdown")
            checkpoint.write_text(markdown + "\n", encoding="utf-8")
            output[page_number] = markdown + "\n"
            if on_status:
                on_status(page_number, "completed", job_id, None)
        except Exception as error:
            if on_status:
                on_status(page_number, "failed", job_id, f"{type(error).__name__}: {error}")

    if not output:
        raise ValueError("LlamaParse returned no page Markdown")
    return output

