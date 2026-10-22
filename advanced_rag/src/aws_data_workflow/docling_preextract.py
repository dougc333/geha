"""Pre-extract page Markdown with Docling and flag pages needing fallback OCR."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Callable


PageProgressCallback = Callable[[int, dict[str, Any], int, int], None]
PageStartCallback = Callable[[int, int, int], None]


def _tokens(value: str) -> set[str]:
    return {token.casefold() for token in re.findall(r"[A-Za-z0-9]{3,}", value)}


def assess_page(markdown: str, embedded_text: str, *, has_visual_content: bool) -> dict[str, Any]:
    """Return a conservative, explainable Docling quality decision."""
    markdown = markdown.strip()
    embedded_text = embedded_text.strip()
    reasons: list[str] = []
    source_tokens = _tokens(embedded_text)
    markdown_tokens = _tokens(markdown)
    token_recall = (
        len(source_tokens & markdown_tokens) / len(source_tokens)
        if source_tokens
        else None
    )
    if "\ufffd" in markdown:
        reasons.append("replacement_characters")
    if len(source_tokens) >= 8 and (token_recall or 0.0) < 0.70:
        reasons.append("low_embedded_text_recall")
    if len(embedded_text) >= 80 and len(markdown) < 40:
        reasons.append("suspiciously_short")
    if len(embedded_text) < 20 and has_visual_content and len(markdown) < 80:
        reasons.append("visual_or_scanned_page_without_sufficient_text")
    return {
        "accepted": not reasons,
        "fallback_required": bool(reasons),
        "reasons": reasons,
        "docling_characters": len(markdown),
        "embedded_text_characters": len(embedded_text),
        "embedded_token_recall": round(token_recall, 4) if token_recall is not None else None,
    }


def _cached_decision(page_dir: Path) -> dict[str, Any] | None:
    markdown_path = page_dir / "docling.md"
    quality_path = page_dir / "docling-quality.json"
    if not markdown_path.exists() or not quality_path.exists():
        return None
    try:
        decision = json.loads(quality_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(decision, dict):
        return None
    if not isinstance(decision.get("accepted"), bool):
        return None
    if not isinstance(decision.get("fallback_required"), bool):
        return None
    return decision


def _write_report(
    source: Path,
    pages_dir: Path,
    decisions: dict[str, dict[str, Any]],
    total_pages: int,
) -> dict[str, Any]:
    fallback_pages = [
        int(page) for page, item in decisions.items() if item["fallback_required"]
    ]
    completed_pages = len(decisions)
    report = {
        "schema_version": "1.1",
        "source": str(source),
        "status": "complete" if completed_pages == total_pages else "running",
        "page_count": total_pages,
        "completed_pages": completed_pages,
        "remaining_pages": total_pages - completed_pages,
        "accepted_pages": completed_pages - len(fallback_pages),
        "fallback_pages": fallback_pages,
        "pages": decisions,
    }
    (pages_dir / "docling-preflight.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def preextract_docling_pages(
    source: Path,
    pages_dir: Path,
    *,
    force: bool = False,
    on_page_start: PageStartCallback | None = None,
    on_page: PageProgressCallback | None = None,
) -> dict[str, Any]:
    """Extract each pre-split page independently and checkpoint after every page."""
    import pymupdf
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions()
    options.do_table_structure = True
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )

    page_sources = sorted(pages_dir.glob("page-*/source.pdf"))
    if not page_sources:
        raise FileNotFoundError(
            f"No pre-split page PDFs found under {pages_dir}; expected page-NNN/source.pdf"
        )

    total_pages = len(page_sources)
    decisions: dict[str, dict[str, Any]] = {}
    for processed, page_source in enumerate(page_sources, 1):
        match = re.fullmatch(r"page-(\d+)", page_source.parent.name)
        if match is None:
            continue
        page_number = int(match.group(1))
        page_dir = page_source.parent
        decision = None if force else _cached_decision(page_dir)
        if decision is None:
            if on_page_start is not None:
                on_page_start(page_number, processed, total_pages)
            try:
                document = converter.convert(page_source).document
                markdown = document.export_to_markdown(page_no=1).strip()
                with pymupdf.open(page_source) as pdf:
                    pdf_page = pdf[0]
                    embedded_text = pdf_page.get_text("text")
                    has_visual = bool(pdf_page.get_images(full=True)) or len(
                        pdf_page.get_drawings()
                    ) > 5
                decision = assess_page(
                    markdown,
                    embedded_text,
                    has_visual_content=has_visual,
                )
            except Exception as exc:  # Keep the remaining page jobs resumable.
                markdown = ""
                decision = {
                    "accepted": False,
                    "fallback_required": True,
                    "reasons": ["docling_extraction_failed"],
                    "docling_characters": 0,
                    "embedded_text_characters": None,
                    "embedded_token_recall": None,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            (page_dir / "docling.md").write_text(
                markdown + ("\n" if markdown else ""), encoding="utf-8"
            )
            (page_dir / "docling-quality.json").write_text(
                json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )

        decisions[str(page_number)] = decision
        report = _write_report(source, pages_dir, decisions, total_pages)
        if on_page is not None:
            on_page(page_number, decision, processed, total_pages)

    return _write_report(source, pages_dir, decisions, total_pages)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("pages_dir", type=Path)
    parser.add_argument("--force", action="store_true", help="Re-extract cached pages")
    args = parser.parse_args()

    def print_progress(
        page_number: int,
        decision: dict[str, Any],
        processed: int,
        total: int,
    ) -> None:
        route = "accepted" if decision["accepted"] else "fallback"
        print(f"[{processed}/{total}] page-{page_number:03d}: {route}", flush=True)

    result = preextract_docling_pages(
        args.source.resolve(),
        args.pages_dir.resolve(),
        force=args.force,
        on_page=print_progress,
    )
    print(json.dumps({key: value for key, value in result.items() if key != "pages"}, indent=2))


if __name__ == "__main__":
    main()
