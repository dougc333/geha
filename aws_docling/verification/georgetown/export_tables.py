"""Export the seven Markdown tables as traceable, long-form CSV files."""

import argparse
import csv
import json
from pathlib import Path

from audit_extraction import TABLE_PAGES, table_sections


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--markdown", type=Path, default=Path(__file__).with_name("document-with-figure-links.md"))
    parser.add_argument("--summary", type=Path, default=Path(__file__).with_name("summary.json"))
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("tables"))
    args = parser.parse_args()
    lines = args.markdown.read_text(encoding="utf-8").splitlines()
    sections = table_sections(lines)
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    bad_lines = {line for issue in summary["issues"] for line in issue["markdown_lines"]
                 if issue["code"].startswith(("merged_table", "unlabeled_table", "missing_table"))}
    args.output.mkdir(parents=True, exist_ok=True)
    counts = {}
    for number in range(1, 8):
        parts = [section for section in sections if section["number"] == number]
        if not parts:
            raise ValueError(f"Table {number} is absent from {args.markdown}")
        path = args.output / f"table-{number}.csv"
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=["part", "pdf_page", "markdown_line",
                                                    "variable", "column", "value", "review_status"])
            writer.writeheader()
            count = 0
            for part_no, section in enumerate(parts, 1):
                rows = section["rows"]
                if not rows:
                    continue
                if number in (1, 2):
                    headers = ["variable", "value"]
                    data_rows = rows
                else:
                    headers = rows[0][1]
                    data_rows = rows[1:]
                source_pages = TABLE_PAGES[number]
                page = source_pages[min(part_no - 1, len(source_pages) - 1)]
                for line_no, cells in data_rows:
                    variable = cells[0]
                    for index, value in enumerate(cells[1:], 1):
                        if not value:
                            continue
                        writer.writerow({
                            "part": part_no, "pdf_page": page, "markdown_line": line_no,
                            "variable": variable, "column": headers[index] if index < len(headers) else f"column {index}",
                            "value": value,
                            "review_status": "review_required" if number == 4 or line_no in bad_lines else "unverified",
                        })
                        count += 1
        counts[str(number)] = {"file": str(path.relative_to(args.markdown.parent)),
                               "parts": len(parts), "values": count,
                               "review_status": "review_required" if number in (4, 5, 7) else "unverified"}
    summary["table_exports"] = counts
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(counts)} CSV files to {args.output}")


if __name__ == "__main__":
    main()
