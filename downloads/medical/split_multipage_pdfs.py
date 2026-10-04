#!/usr/bin/env python3
"""Split FEHB and PSHB multipage PDFs into one-page PDFs.

By default, this processes:

    /Users/dc/geha/downloads/medical/fehb
    /Users/dc/geha/downloads/medical/pshb

Each source gets its own output directory so page files keep the complete source
name without colliding with pages from another document. For example:

    fehb/example.pdf
      -> fehb/single_pages/example/example--page-0001.pdf
      -> fehb/single_pages/example/example--page-0002.pdf

Existing outputs are left untouched unless --overwrite is supplied.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader, PdfWriter


DEFAULT_INPUTS = (
    Path("/Users/dc/geha/downloads/medical/fehb"),
    Path("/Users/dc/geha/downloads/medical/pshb"),
)
OUTPUT_DIRECTORY = "single_pages"


@dataclass(frozen=True)
class SplitResult:
    source: Path
    output_directory: Path
    page_count: int
    written_count: int
    skipped_count: int


def page_output_path(source: Path, page_number: int) -> Path:
    """Return the one-page output path for a one-based page number."""
    return (
        source.parent
        / OUTPUT_DIRECTORY
        / source.stem
        / f"{source.stem}--page-{page_number:04d}.pdf"
    )


def source_pdfs(directory: Path) -> list[Path]:
    """List only top-level source PDFs, excluding generated output."""
    if not directory.is_dir():
        raise FileNotFoundError(f"Input directory does not exist: {directory}")
    return sorted(path for path in directory.glob("*.pdf") if path.is_file())


def write_single_page(page, destination: Path) -> None:
    """Write one page atomically so an interrupted run cannot leave a partial PDF."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    writer.add_page(page)
    with tempfile.NamedTemporaryFile(
        mode="wb", suffix=".pdf", prefix=".split-", dir=destination.parent, delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
        writer.write(temporary)
    temporary_path.replace(destination)


def split_pdf(source: Path, *, overwrite: bool, dry_run: bool) -> SplitResult:
    reader = PdfReader(source)
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as error:
            raise ValueError(f"Cannot open encrypted PDF: {source}") from error

    written = 0
    skipped = 0
    for page_number, page in enumerate(reader.pages, start=1):
        destination = page_output_path(source, page_number)
        if destination.exists() and not overwrite:
            skipped += 1
            continue
        if not dry_run:
            write_single_page(page, destination)
        written += 1

    output_directory = source.parent / OUTPUT_DIRECTORY / source.stem
    return SplitResult(source, output_directory, len(reader.pages), written, skipped)


def verify_result(result: SplitResult) -> None:
    """Verify the output count and confirm every generated PDF contains one page."""
    expected = {
        page_output_path(result.source, page_number)
        for page_number in range(1, result.page_count + 1)
    }
    actual = set(result.output_directory.glob("*.pdf"))
    missing = expected - actual
    unexpected = actual - expected
    if missing or unexpected:
        raise RuntimeError(
            f"Output mismatch for {result.source.name}: "
            f"missing={len(missing)}, unexpected={len(unexpected)}"
        )
    for page_pdf in sorted(actual):
        if len(PdfReader(page_pdf).pages) != 1:
            raise RuntimeError(f"Output is not a single-page PDF: {page_pdf}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "directories",
        nargs="*",
        type=Path,
        default=list(DEFAULT_INPUTS),
        help="Directories containing source PDFs (defaults to the FEHB and PSHB directories).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing one-page PDFs. Without this flag they are skipped.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read the source PDFs and report planned outputs without writing files.",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip the post-write one-page and output-count verification.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    failures: list[str] = []
    source_count = 0
    page_count = 0

    for directory in args.directories:
        try:
            pdfs = source_pdfs(directory.expanduser().resolve())
        except Exception as error:
            failures.append(str(error))
            continue

        print(f"\n{directory}: {len(pdfs)} source PDF(s)")
        for source in pdfs:
            source_count += 1
            try:
                result = split_pdf(source, overwrite=args.overwrite, dry_run=args.dry_run)
                page_count += result.page_count
                action = "would write" if args.dry_run else "wrote"
                print(
                    f"  {source.name}: {result.page_count} page(s); "
                    f"{action} {result.written_count}, skipped {result.skipped_count}; "
                    f"output {result.output_directory}"
                )
                if not args.dry_run and not args.no_verify:
                    verify_result(result)
            except Exception as error:
                failures.append(f"{source}: {error}")

    print(f"\nProcessed {source_count} source PDF(s), representing {page_count} page(s).")
    if failures:
        print("Failures:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
