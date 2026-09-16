"""Deterministic billing-code parsing shared by policy search and evaluations."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


CODE_RE = re.compile(r"(?<![A-Za-z0-9])(?:[A-Za-z]\d{4}|\d{5})(?![A-Za-z0-9])", re.I)
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")
SEPARATOR_RE = re.compile(r":?-{3,}:?")
CODE_COLUMNS = ("HCPCS Code", "CPT/HCPCS Codes", "Code")


def code_tokens(value: str) -> list[str]:
    """Extract individual HCPCS/CPT codes from a code cell, preserving order."""
    return list(dict.fromkeys(match.group().upper() for match in CODE_RE.finditer(value)))


def requested_billing_codes(question: str) -> list[str]:
    """Route exact identifiers, avoiding unrelated five-digit clinical quantities."""
    tokens = code_tokens(question)
    numeric_context = bool(re.search(r"\b(?:billing|hcpcs|cpt|procedure|code)\b", question, re.I))
    if not numeric_context and not re.fullmatch(r"\s*\d{5}\s*", question):
        tokens = [token for token in tokens if not token.isdigit()]
    return tokens


def billing_table_name(headers: list[str], heading: str) -> str | None:
    """Identify code tables; preference and revision tables are not billing sources."""
    names = {header.casefold() for header in headers}
    if "preference" in names:
        return None
    if heading.casefold() == "applicable codes" and names.intersection(
        {"code", "cpt/hcpcs codes", "hcpcs code"}
    ):
        return "Applicable Codes"
    if "drug name" in names and "hcpcs code" in names:
        return "Billing codes"
    return None


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def docling_billing_rows(path: Path) -> list[dict[str, Any]]:
    """Read only billing/applicable-code Markdown tables from one Docling extract."""
    lines = path.read_text(encoding="utf-8").splitlines()
    heading = ""
    in_applicable_codes = False
    found: list[dict[str, Any]] = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        heading_match = HEADING_RE.match(line)
        if heading_match:
            heading = heading_match.group(1).strip().rstrip(":")
            if heading.casefold() == "applicable codes":
                in_applicable_codes = True
            elif heading.casefold().startswith(("scientific references", "policy history")):
                in_applicable_codes = False
            index += 1
            continue
        if not line.startswith("|") or index + 1 >= len(lines):
            index += 1
            continue
        headers = _cells(line)
        separator = _cells(lines[index + 1]) if lines[index + 1].strip().startswith("|") else []
        if len(headers) != len(separator) or not all(
            SEPARATOR_RE.fullmatch(cell) for cell in separator
        ):
            index += 1
            continue
        table_name = "Applicable Codes" if in_applicable_codes else billing_table_name(headers, heading)
        code_column = next((name for name in CODE_COLUMNS if name in headers), None)
        code_index = headers.index(code_column) if code_column else None
        # Docling repeats page-spanning tables with the first data row as a
        # pseudo-header. Preserve that row and the original Code column.
        continuation = in_applicable_codes and code_index is None and len(headers) >= 2
        if continuation:
            code_index = 1
        candidate_rows = [(index, headers)] if continuation else []
        index += 2
        while index < len(lines) and lines[index].strip().startswith("|"):
            candidate_rows.append((index, _cells(lines[index])))
            index += 1
        for row_index, cells in candidate_rows:
            if table_name and code_index is not None and len(cells) > code_index:
                for code in code_tokens(cells[code_index]):
                    found.append({
                        "code": code,
                        "raw_code_cell": cells[code_index],
                        "table_name": table_name,
                        "item_name": cells[0] if cells else "",
                        "line": row_index + 1,
                    })
    return found
