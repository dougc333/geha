"""Export raw page-local pdfplumber tables to standalone HTML files."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .raw_table_html import save_raw_tables


def extract_pdfplumber_tables_html(
    pdf_path: Path, output_dir: Path | None = None,
) -> list[Path]:
    """Keep default 0/1/2 columns and separate tables on separate pages."""
    import pandas as pd
    import pdfplumber

    pdf_path = pdf_path.expanduser().resolve()
    if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    output_dir = (output_dir or pdf_path.parent).expanduser().resolve()
    tables: list[tuple[int, Any]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, 1):
            for rows in page.extract_tables():
                if rows:
                    tables.append((page_number, pd.DataFrame(rows)))
    return save_raw_tables(pdf_path, output_dir, "pdfplumber", tables)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="Source PDF")
    parser.add_argument("--output-dir", type=Path, help="Defaults to the PDF directory")
    args = parser.parse_args()
    for path in extract_pdfplumber_tables_html(args.pdf, args.output_dir):
        print(path)


if __name__ == "__main__":
    main()
