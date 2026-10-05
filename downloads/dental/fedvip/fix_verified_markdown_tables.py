#!/usr/bin/env python3
"""Apply PDF-verified table repairs to selected Docling Markdown pages."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from markdown_tables_to_html import MarkdownTable, corrected_tables, find_tables, is_separator


TARGETS = {"page-003", "page-005", "page-013", "page-018", "page-033", "page-038", "page-046", "page-047", "page-055"}


def escape_cell(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").strip()


def serialize_table(table: MarkdownTable) -> list[str]:
    width = len(table.header)
    if any(len(row) != width for row in table.rows):
        raise ValueError("cannot serialize inconsistent table width")
    lines = ["| " + " | ".join(escape_cell(cell) for cell in table.header) + " |"]
    lines.append("| " + " | ".join("---" for _ in range(width)) + " |")
    lines.extend("| " + " | ".join(escape_cell(cell) for cell in row) + " |" for row in table.rows)
    return lines


def table_span(lines: list[str]) -> tuple[int, int]:
    for separator_index in range(1, len(lines)):
        if is_separator(lines[separator_index]) and "|" in lines[separator_index - 1]:
            start = separator_index - 1
            end = separator_index + 1
            while end < len(lines) and lines[end].strip().startswith("|"):
                end += 1
            return start, end
    raise ValueError("Markdown table not found")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--backup-directory", type=Path, required=True)
    args = parser.parse_args()
    directory = args.directory.expanduser().resolve()
    backup = args.backup_directory.expanduser().resolve()
    backup.mkdir(parents=True, exist_ok=True)

    for stem in sorted(TARGETS):
        path = directory / f"{stem}.md"
        original = path.read_text(encoding="utf-8")
        tables = find_tables(original)
        if len(tables) != 1:
            raise ValueError(f"{path.name}: expected one table, found {len(tables)}")
        repaired = corrected_tables(stem, tables, directory)
        if len(repaired) != 1:
            raise ValueError(f"{path.name}: expected one repaired table")
        lines = original.splitlines()
        start, end = table_span(lines)
        prefix = lines[:start]
        if stem == "page-055" and not any("Premium Rating Areas by State/Zip Code" in line for line in prefix):
            prefix = prefix + ["", "## Premium Rating Areas by State/Zip Code (first three digits)", ""]
        updated_lines = prefix + serialize_table(repaired[0]) + lines[end:]
        updated = "\n".join(updated_lines).rstrip() + "\n"
        shutil.copy2(path, backup / path.name)
        temporary = path.with_suffix(".md.tmp")
        temporary.write_text(updated, encoding="utf-8")
        temporary.replace(path)
        print(f"fixed {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
