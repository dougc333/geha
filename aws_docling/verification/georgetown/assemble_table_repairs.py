"""Fan in independently verified table repairs without changing other document text."""

import csv
import json
import re
from pathlib import Path

from audit_extraction import TABLE_PAGES, audit, table_sections


ROOT = Path(__file__).parent
HEADING = re.compile(r"^Tab\s*le ([1-7])(?: \([^)]*\))?:")


def blocks(lines: list[str]) -> dict[int, list[tuple[int, int, list[str]]]]:
    found = {number: [] for number in range(1, 8)}
    for index, line in enumerate(lines):
        match = HEADING.match(line)
        if not match:
            continue
        start = index + 1
        while start < len(lines) and not lines[start].startswith("|"):
            if lines[start].strip():
                raise ValueError(f"Expected table body after line {index + 1}")
            start += 1
        end = start
        while end < len(lines) and lines[end].startswith("|"):
            end += 1
        if end == start:
            raise ValueError(f"No table body after line {index + 1}")
        found[int(match.group(1))].append((start, end, lines[start:end]))
    return found


def write_csvs(lines: list[str], status: dict[int, str]) -> dict[str, dict]:
    output = ROOT / "tables-corrected"
    output.mkdir(exist_ok=True)
    sections = table_sections(lines)
    exports = {}
    for number in range(1, 8):
        parts = [section for section in sections if section["number"] == number]
        path = output / f"table-{number}.csv"
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=[
                "part", "pdf_page", "markdown_line", "variable", "column", "value", "review_status"
            ], lineterminator="\n")
            writer.writeheader()
            count = 0
            for part_number, section in enumerate(parts, 1):
                rows = section["rows"]
                if number in (1, 2) and rows[0][1][0].lower() not in ("variable", "variables", "characteristic", "benefit"):
                    headers, data = ["variable", "value"], rows
                else:
                    headers, data = rows[0][1], rows[1:]
                pages = TABLE_PAGES[number]
                page = pages[min(part_number - 1, len(pages) - 1)]
                for line_number, cells in data:
                    for column_number, value in enumerate(cells[1:], 1):
                        if not value:
                            continue
                        writer.writerow({
                            "part": part_number, "pdf_page": page,
                            "markdown_line": line_number, "variable": cells[0],
                            "column": headers[column_number] if column_number < len(headers) else f"column {column_number}",
                            "value": value, "review_status": status[number],
                        })
                        count += 1
        exports[str(number)] = {"file": str(path.relative_to(ROOT)), "parts": len(parts),
                                "values": count, "review_status": status[number]}
    return exports


def main() -> None:
    source = ROOT / "aws-worker-rev2.md"
    source_lines = source.read_text(encoding="utf-8").splitlines()
    original_blocks = blocks(source_lines)
    replacements = []
    corrected_bodies = {}
    validations = {}
    statuses = {}
    for number in range(1, 8):
        stem = ROOT / "repairs" / f"table-{number}"
        validation = json.loads(stem.with_suffix(".validation.json").read_text())
        if validation["table"] != number or not 1 <= validation["iterations"] <= 4:
            raise ValueError(f"Table {number} has invalid validation metadata")
        if validation["status"] not in ("verified", "needs_review"):
            raise ValueError(f"Table {number} has invalid status")
        corrected_lines = stem.with_suffix(".corrected.md").read_text(encoding="utf-8").splitlines()
        corrected_blocks = blocks(corrected_lines)[number]
        if len(corrected_blocks) != len(original_blocks[number]):
            raise ValueError(f"Table {number} part count changed unexpectedly")
        applied = validation["status"] == "verified" and not validation["unresolved_issues"]
        validation.pop("corrected_markdown", None)
        validations[str(number)] = {**validation, "corrected_markdown": f"repairs/table-{number}.corrected.md", "applied": applied}
        statuses[number] = "source_verified" if applied else "review_required"
        corrected_bodies[number] = [part[2] for part in corrected_blocks]
        if applied:
            for old, new in zip(original_blocks[number], corrected_blocks):
                replacements.append((old[0], old[1], new[2]))

    for start, end, replacement in sorted(replacements, reverse=True):
        source_lines[start:end] = replacement
    final_blocks = blocks(source_lines)
    for number, parts in final_blocks.items():
        for _, _, body in parts:
            widths = {len(row.strip("|").split("|")) for row in body}
            if len(widths) != 1:
                raise ValueError(f"Table {number} has inconsistent Markdown cell counts")
    for number in (4, 5, 7):
        labels = [cells[0] for section in table_sections(source_lines) if section["number"] == number
                  for _, cells in section["rows"]]
        if any("Observations R-squared" in label for label in labels):
            raise ValueError(f"Table {number} still merges Observations and R-squared")
    output = ROOT / "document-corrected-tables.md"
    output.write_text("\n".join(source_lines) + "\n", encoding="utf-8")
    image_lines = (ROOT / "document-with-images.md").read_text(encoding="utf-8").splitlines()
    image_blocks = blocks(image_lines)
    image_replacements = []
    for number in range(1, 8):
        if not validations[str(number)]["applied"]:
            continue
        if len(image_blocks[number]) != len(corrected_bodies[number]):
            raise ValueError(f"Table {number} part count differs in image-embedded Markdown")
        for old, body in zip(image_blocks[number], corrected_bodies[number]):
            image_replacements.append((old[0], old[1], body))
    for start, end, replacement in sorted(image_replacements, reverse=True):
        image_lines[start:end] = replacement
    image_lines = [re.sub(r"^Tab\s+le ", "Table ", line) for line in image_lines]
    image_output = ROOT / "document-corrected-tables-with-images.md"
    image_output.write_text("\n".join(image_lines) + "\n", encoding="utf-8")
    exports = write_csvs(source_lines, statuses)
    before = json.loads((ROOT / "summary.json").read_text())
    after = audit(Path(before["source_pdf"]), output)
    image_after = audit(Path(before["source_pdf"]), image_output)
    table_codes = {"merged_table_variable_rows", "merged_table_statistic_rows",
                   "unlabeled_table_value_row", "missing_table_variable_rows", "broken_table_heading"}
    summary = {
        "source_markdown": source.name, "corrected_markdown": output.name,
        "image_embedded_markdown": image_output.name,
        "max_iterations_per_table": 4, "table_results": validations,
        "table_exports": exports,
        "known_table_issues_before": [issue for issue in before["issues"] if issue["code"] in {
            "merged_table_variable_rows", "merged_table_statistic_rows",
            "unlabeled_table_value_row", "missing_table_variable_rows",
        }],
        "remaining_table_issues": [issue for issue in after["issues"] if issue["code"] in table_codes],
        "remaining_table_issues_image_variant": [issue for issue in image_after["issues"] if issue["code"] in table_codes],
        "remaining_non_table_issue_codes_image_variant": [issue["code"] for issue in image_after["issues"] if issue["code"] not in table_codes],
        "scope": "Only numbered table bodies were replaced. The AWS variant retains its figure placeholders; the image variant retains its six embedded figure crops. Equation, prose, and references remain as in each source Markdown.",
    }
    (ROOT / "table-repair-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Applied {sum(item['applied'] for item in validations.values())} verified table repairs")


if __name__ == "__main__":
    main()
