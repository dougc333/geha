#!/usr/bin/env python3
"""Split a PDF into one-page PDFs and extract each page to Markdown with Docling.

By default, outputs are written to a sibling directory named
``<pdf-stem>_pages``. Each source page produces a matching pair:

    page-001.pdf
    page-001.md

The Markdown starts with a small metadata comment that preserves the original
file name and one-based source page number.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from pypdf import PdfReader, PdfWriter


DEFAULT_PDF = Path(
    "/Users/dc/geha/downloads/dental/fedvip/"
    "2026-geha-dental-plan-brochure.pdf"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "pdf",
        nargs="?",
        type=Path,
        default=DEFAULT_PDF,
        help=f"source PDF (default: {DEFAULT_PDF})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="output directory (default: <source directory>/<source stem>_pages)",
    )
    parser.add_argument(
        "--start-page",
        type=int,
        default=1,
        help="first one-based source page to process (default: 1)",
    )
    parser.add_argument(
        "--end-page",
        type=int,
        help="last one-based source page to process (default: final page)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace page PDF/Markdown pairs that already exist",
    )
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="enable OCR for scanned pages (slower; off by default)",
    )
    return parser.parse_args()


def build_converter(*, use_ocr: bool) -> DocumentConverter:
    options = PdfPipelineOptions(
        do_ocr=use_ocr,
        do_table_structure=True,
    )
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=options),
        }
    )


def write_single_page(reader: PdfReader, page_index: int, destination: Path) -> None:
    writer = PdfWriter()
    writer.add_page(reader.pages[page_index])
    temporary = destination.with_suffix(".pdf.tmp")
    with temporary.open("wb") as stream:
        writer.write(stream)
    temporary.replace(destination)


def markdown_for_page(converter: DocumentConverter, page_pdf: Path, source: Path, page: int) -> str:
    document = converter.convert(str(page_pdf)).document
    markdown = document.export_to_markdown().strip()
    metadata = f"<!-- source: {source.name}; source_page: {page} -->"
    return f"{metadata}\n\n{markdown}\n" if markdown else f"{metadata}\n"


def main() -> int:
    args = parse_args()
    source = args.pdf.expanduser().resolve()
    if not source.is_file():
        print(f"error: source PDF does not exist: {source}", file=sys.stderr)
        return 2
    if source.suffix.lower() != ".pdf":
        print(f"error: source is not a PDF: {source}", file=sys.stderr)
        return 2

    output_dir = (
        args.output_dir.expanduser().resolve()
        if args.output_dir
        else source.parent / f"{source.stem}_pages"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    reader = PdfReader(str(source))
    page_count = len(reader.pages)
    end_page = args.end_page or page_count
    if not 1 <= args.start_page <= end_page <= page_count:
        print(
            f"error: page range must satisfy 1 <= start <= end <= {page_count}",
            file=sys.stderr,
        )
        return 2

    width = max(3, len(str(page_count)))
    converter = build_converter(use_ocr=args.ocr)
    failures: list[tuple[int, str]] = []
    processed = skipped = 0

    for page_number in range(args.start_page, end_page + 1):
        stem = f"page-{page_number:0{width}d}"
        page_pdf = output_dir / f"{stem}.pdf"
        page_md = output_dir / f"{stem}.md"

        if page_pdf.exists() and page_md.exists() and not args.overwrite:
            print(f"skip {stem}: outputs already exist", flush=True)
            skipped += 1
            continue

        try:
            write_single_page(reader, page_number - 1, page_pdf)
            markdown = markdown_for_page(converter, page_pdf, source, page_number)
            temporary_md = page_md.with_suffix(".md.tmp")
            temporary_md.write_text(markdown, encoding="utf-8")
            temporary_md.replace(page_md)
            print(
                f"wrote {page_pdf.name} and {page_md.name} "
                f"({len(markdown):,} Markdown characters)",
                flush=True,
            )
            processed += 1
        except Exception as exc:  # keep successful page pairs and report all failures
            failures.append((page_number, str(exc)))
            page_pdf.unlink(missing_ok=True)
            page_md.unlink(missing_ok=True)
            print(f"failed page {page_number}: {exc}", file=sys.stderr, flush=True)

    print(
        f"complete: {processed} processed, {skipped} skipped, "
        f"{len(failures)} failed; output={output_dir}",
        flush=True,
    )
    if failures:
        for page_number, message in failures:
            print(f"page {page_number}: {message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
