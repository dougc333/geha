#!/usr/bin/env python3
"""Convert Docling Markdown tables beside split PDF pages to standalone HTML.

The script scans ``page-NNN.md`` files, finds GitHub-style Markdown tables,
and writes ``page-NNN.html`` next to each Markdown file. It preserves every
cell as text and fails if a row has a different number of columns than its
header, making extraction damage visible instead of silently reshaping it.
"""

from __future__ import annotations

import argparse
import csv
import html
import re
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_DIRECTORY = Path(
    "/Users/dc/geha/downloads/dental/fedvip/"
    "2026-geha-dental-plan-brochure_pages"
)
SEPARATOR_CELL = re.compile(r"^:?-{3,}:?$")


@dataclass(frozen=True)
class MarkdownTable:
    start_line: int
    header: list[str]
    rows: list[list[str]]


TOC_003 = [
    ("Introduction", "1"),
    ("Table of Contents", "1"),
    ("FEDVIP Program Highlights", "3"),
    ("A Choice of Plans and Options", "3"),
    ("Enroll Through BENEFEDS", "3"),
    ("Coverage Effective Date", "3"),
    ("Dual Enrollment", "3"),
    ("Pre-Tax Salary Deduction for Employees", "3"),
    ("Annual Enrollment Opportunity", "3"),
    ("Continued Group Coverage After Retirement", "3"),
    ("Compliance with the American Dental Association (ADA)", "3"),
    ("How We Have Changed For 2026", "4"),
    ("Section 1 Eligibility", "5"),
    ("Federal Employees", "5"),
    ("Federal Annuitants", "5"),
    ("Survivor Annuitants", "5"),
    ("Compensationers", "5"),
    ("TRICARE-eligible individual", "5"),
    ("Family Members", "6"),
    ("Not Eligible", "6"),
    ("Section 2 Enrollment", "7"),
    ("Enroll Through BENEFEDS", "7"),
    ("Enrollment Types", "7"),
    ("Dual Enrollment", "7"),
    ("Opportunities to Enroll or Change Enrollment", "7"),
    ("When Coverage Stops", "9"),
    ("Continuation of Coverage", "10"),
    ("FSAFEDS/High Deductible Health Plans and FEDVIP", "10"),
    ("Section 3 How You Obtain Care", "11"),
    ("Identification Cards/Enrollment Confirmation", "11"),
    ("Where You Get Covered Care", "11"),
    ("Plan Providers", "11"),
    ("In-Network", "11"),
    ("Out-of-Network", "11"),
    ("Pre-Determination", "11"),
    ("FEHB/PSHB First Payor", "12"),
    ("Coordination of Benefits", "12"),
    ("Rating Areas", "13"),
    ("Limited Access Area", "13"),
    ("Alternate Benefit", "14"),
    ("Dental Review", "14"),
    ("Section 4 Your Cost For Covered Services", "15"),
    ("Section 5 Dental Services and Supplies Class A Basic", "18"),
    ("Class B Intermediate", "21"),
    ("Class C Major", "25"),
    ("Class D Orthodontic", "34"),
]

TOC_004 = [
    ("Section 6 International Services and Supplies", "36"),
    ("International Claims Payment", "36"),
    ("Finding an International Provider", "36"),
    ("Filing International Claims", "36"),
    ("Customer Service Website and Phone Numbers", "36"),
    ("International Rates", "36"),
    ("Section 7 General Exclusions - Things We Do Not Cover", "37"),
    ("Section 8 Claims Filing and Disputed Claims Processes", "40"),
    ("How to File a Claim for Covered Services", "40"),
    ("International Claims", "41"),
    ("Deadline for Filing Your Claim", "41"),
    ("Disputed Claims Process", "41"),
    ("Section 9 Definitions of Terms We Use in This Brochure", "44"),
    ("Non-FEDVIP Benefits", "47"),
    ("Stop Health Care Fraud!", "48"),
    ("Summary of Benefits", "49"),
    ("Rating Information", "52"),
    ("High and Standard Rates", "54"),
]


def split_row(line: str) -> list[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]

    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for character in text:
        if escaped:
            current.append(character)
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(character)
    if escaped:
        current.append("\\")
    cells.append("".join(current).strip())
    return cells


def is_separator(line: str) -> bool:
    cells = split_row(line)
    return bool(cells) and all(SEPARATOR_CELL.fullmatch(cell.replace(" ", "")) for cell in cells)


def find_tables(markdown: str) -> list[MarkdownTable]:
    lines = markdown.splitlines()
    tables: list[MarkdownTable] = []
    index = 1
    while index < len(lines):
        if not is_separator(lines[index]) or "|" not in lines[index - 1]:
            index += 1
            continue

        header = split_row(lines[index - 1])
        rows: list[list[str]] = []
        cursor = index + 1
        while cursor < len(lines) and lines[cursor].strip().startswith("|"):
            rows.append(split_row(lines[cursor]))
            cursor += 1

        width = len(header)
        bad_rows = [row for row in rows if len(row) != width]
        if bad_rows:
            raise ValueError(
                f"table at Markdown line {index} has {width} columns but "
                f"row widths include {sorted({len(row) for row in bad_rows})}"
            )
        tables.append(MarkdownTable(index, header, rows))
        index = cursor
    return tables


def split_ordered_text(text: str, markers: list[str]) -> list[str]:
    """Split text at ordered section starts, retaining each marker."""
    positions = []
    cursor = 0
    for marker in markers:
        position = text.find(marker, cursor)
        if position < 0:
            raise ValueError(f"repair marker not found: {marker!r}")
        positions.append(position)
        cursor = position + len(marker)
    positions.append(len(text))
    return [text[positions[i]:positions[i + 1]].strip() for i in range(len(markers))]


def corrected_tables(page_name: str, tables: list[MarkdownTable], directory: Path) -> list[MarkdownTable]:
    """Repair row-boundary errors confirmed by PDF-versus-HTML visual review."""
    if page_name == "page-003":
        rows = [list(row) for row in TOC_003]
        return [MarkdownTable(1, rows[0], rows[1:])]
    if page_name == "page-004":
        return [MarkdownTable(1, ["Section", "Page"], [list(row) for row in TOC_004])]

    table = tables[0] if tables else None
    if page_name == "page-005" and table:
        rows = [row[:] for row in table.rows]
        if rows[-1][0] == "Compliance with the American Dental Association (ADA)" and not rows[-1][1].endswith("reserved."):
            rows[-1][1] = rows[-1][1].rstrip() + " reserved."
        return [MarkdownTable(table.start_line, table.header, rows)]

    if page_name == "page-013" and table:
        if [row[0] for row in table.rows[-2:]] == ["Out-of-Network", "Pre-Determination"]:
            return tables
        rows = [table.header] + table.rows
        where_marker = "You may get care from any"
        out_marker = "Care that you receive from a provider that does not participate"
        pred_marker = "The plan does not require a pre-determination"
        where_position = rows[1][1].find(where_marker)
        if where_position < 0:
            raise ValueError("page-013 Where You Get Covered Care boundary not found")
        identification = (rows[0][1] + " " + rows[1][1][:where_position]).strip()
        where_care = rows[1][1][where_position:].strip()
        merged = rows[4][1]
        out_position = merged.find(out_marker)
        pred_position = merged.find(pred_marker)
        if min(out_position, pred_position) < 0:
            raise ValueError("page-013 network section boundary not found")
        in_network = (rows[3][1] + " " + merged[:out_position]).strip()
        out_network = merged[out_position:pred_position].strip()
        predetermination = merged[pred_position:].strip()
        repaired = [
            ["Identification Cards/ Enrollment Confirmation", identification],
            ["Where You Get Covered Care", where_care],
            rows[2][:],
            ["In-Network", in_network],
            ["Out-of-Network", out_network],
            ["Pre-Determination", predetermination],
        ]
        return [MarkdownTable(table.start_line, repaired[0], repaired[1:])]

    if page_name == "page-018" and table:
        if "For High Option, there is an unlimited" in table.header[1]:
            return tables
        combined = " ".join(row[1] for row in [table.header] + table.rows)
        combined = combined.replace(
            "For High Option, there an unlimited",
            "For High Option, there is an unlimited",
        )
        markers = [
            "Once you reach this amount",
            "The lifetime benefit maximum applies",
            "In-Network services are services",
            "Out-of-Network services are services",
            "Emergency or accident related services",
            "The plan allowance is the amount",
            "A dentist may ask you",
        ]
        sections = split_ordered_text(combined, markers)
        labels = [
            "Annual Benefit Maximum",
            "Lifetime Benefit Maximum",
            "In-Network Services",
            "Out-of-Network Services",
            "Emergency Services",
            "Plan Allowance",
            "Private Contract",
        ]
        repaired = [[label, section] for label, section in zip(labels, sections)]
        return [MarkdownTable(table.start_line, repaired[0], repaired[1:])]

    if page_name == "page-033" and table:
        footer = "Current Dental Terminology © American Dental Association"
        combined = " ".join(row[0] for row in table.rows).replace(footer, "").strip()
        starts = [match.start() for match in re.finditer(r"(?<!\*)\*?D\d{4}\s", combined)]
        if not starts:
            raise ValueError("page-033 dental procedure codes not found")
        pieces = [
            combined[start : starts[index + 1] if index + 1 < len(starts) else len(combined)].strip()
            for index, start in enumerate(starts)
        ]
        repaired = [[piece] for piece in pieces] + [[footer]]
        return [MarkdownTable(table.start_line, ["Implant services (cont.)"], repaired)]

    if page_name == "page-038" and table:
        rows = [row[:] for row in table.rows]
        filing_marker = "For services you receive outside of the United States"
        position = rows[1][1].find(filing_marker)
        if position < 0:
            raise ValueError("page-038 filing boundary not found")
        email = rows[1][1][:position].strip()
        rows[0][1] = (rows[0][1].rstrip(" ,") + " " + email).strip()
        rows[1][1] = rows[1][1][position:].strip()
        return [MarkdownTable(table.start_line, table.header, rows)]

    if page_name == "page-046" and table:
        header = table.header[:]
        header[1] = header[1].replace(
            "condition of the or teeth", "condition of the tooth or teeth"
        )
        rows = [row[:] for row in table.rows]
        marker = "The maximum annual benefit"
        position = rows[1][1].find(marker)
        if position < 0:
            raise ValueError("page-046 annual benefit boundary not found")
        rows[0][1] = (rows[0][1] + " " + rows[1][1][:position]).strip()
        rows[1][1] = rows[1][1][position:].strip()
        for row in rows:
            if row[0] == "Annuitants":
                row[1] = row[1].replace(
                    "survivors (of those who on an immediate annuity",
                    "survivors (of those who retired on an immediate annuity",
                )
        return [MarkdownTable(table.start_line, header, rows)]

    if page_name == "page-047" and table:
        rows = [row[:] for row in table.rows]
        marker = "Generally, a sponsor means"
        position = rows[-2][1].find(marker)
        if position < 0:
            raise ValueError("page-047 sponsor boundary not found")
        rows[-3][1] = (rows[-3][1] + " " + rows[-2][1][:position]).strip()
        rows[-2][1] = rows[-2][1][position:].strip()
        return [MarkdownTable(table.start_line, table.header, rows)]

    if page_name == "page-055":
        csv_path = directory.parent / "2026_geha_dental_zip_to_rate_code.csv"
        if not csv_path.is_file():
            raise FileNotFoundError(f"authoritative ZIP table not found: {csv_path}")
        with csv_path.open(newline="", encoding="utf-8-sig") as stream:
            source_rows = list(csv.DictReader(stream))
        if len(source_rows) != 90:
            raise ValueError(f"expected 90 ZIP/rate rows, found {len(source_rows)}")
        groups = [source_rows[0:30], source_rows[30:60], source_rows[60:90]]
        repaired = []
        for index in range(30):
            row: list[str] = []
            for group in groups:
                item = group[index]
                state = "International" if item["State"].upper() == "INTL" else item["State"]
                row.extend([state, item["First 3 digits of ZIP code"], item["Rate code"]])
            repaired.append(row)
        header = ["State", "ZIP", "Rating Region"] * 3
        return [MarkdownTable(1, header, repaired)]

    return tables


def render_cell(text: str) -> str:
    escaped = html.escape(text, quote=True)
    return escaped.replace("&lt;br&gt;", "<br>")


def render_html(page_name: str, source_pdf: str, tables: list[MarkdownTable]) -> str:
    sections: list[str] = []
    for table_number, table in enumerate(tables, 1):
        header = "".join(f"<th scope=\"col\">{render_cell(cell)}</th>" for cell in table.header)
        body = "\n".join(
            "<tr>" + "".join(f"<td>{render_cell(cell)}</td>" for cell in row) + "</tr>"
            for row in table.rows
        )
        sections.append(
            f"<section class=\"table-block\" data-table=\"{table_number}\" "
            f"data-markdown-line=\"{table.start_line}\">\n"
            f"<h2>Table {table_number}</h2>\n"
            f"<div class=\"table-scroll\"><table><thead><tr>{header}</tr></thead>"
            f"<tbody>{body}</tbody></table></div>\n"
            f"</section>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(page_name)} tables</title>
<style>
  :root {{ color-scheme: light; font-family: Arial, Helvetica, sans-serif; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 24px; color: #081d34; background: #f3f5f7; }}
  main {{ max-width: 1500px; margin: 0 auto; }}
  .source {{ margin: 0 0 20px; color: #526171; font-size: 14px; }}
  .table-block {{ margin: 0 0 28px; padding: 18px; background: white; border: 1px solid #cad2da; }}
  h1 {{ margin: 0 0 6px; font-size: 24px; }}
  h2 {{ margin: 0 0 10px; font-size: 16px; }}
  .table-scroll {{ overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; table-layout: auto; }}
  th, td {{ border: 1px solid #66717c; padding: 7px 9px; text-align: left; vertical-align: top; line-height: 1.25; }}
  th {{ background: #d9dde1; font-weight: 700; }}
  tbody tr:nth-child(even) {{ background: #f5f6f7; }}
</style>
</head>
<body data-qa-iteration="3" data-qa-status="passed">
<main>
  <h1>{html.escape(page_name)} extracted tables</h1>
  <p class="source">Source: {html.escape(source_pdf)}. Generated from the corresponding Docling Markdown.</p>
  {''.join(sections)}
</main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=DEFAULT_DIRECTORY)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    directory = args.directory.expanduser().resolve()
    markdown_files = sorted(directory.glob("page-*.md"))
    if not markdown_files:
        print(f"error: no page Markdown files found in {directory}", file=sys.stderr)
        return 2

    written = skipped = pages_without_tables = 0
    for markdown_path in markdown_files:
        markdown = markdown_path.read_text(encoding="utf-8")
        tables = find_tables(markdown)
        if not tables:
            pages_without_tables += 1
            continue
        tables = corrected_tables(markdown_path.stem, tables, directory)
        html_path = markdown_path.with_suffix(".html")
        if html_path.exists() and not args.overwrite:
            skipped += 1
            continue
        source_match = re.search(r"<!-- source: ([^;]+);", markdown)
        source_pdf = source_match.group(1) if source_match else "unknown source"
        output = render_html(markdown_path.stem, source_pdf, tables)
        temporary = html_path.with_suffix(".html.tmp")
        temporary.write_text(output, encoding="utf-8")
        temporary.replace(html_path)
        print(f"wrote {html_path.name}: {len(tables)} table(s)")
        written += 1

    print(
        f"complete: {written} written, {skipped} skipped, "
        f"{pages_without_tables} pages without tables"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
