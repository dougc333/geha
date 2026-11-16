"""Audit the saved Georgetown extraction against its text-backed source PDF.

This reports structural errors that can be detected without guessing corrected cells.
It does not edit the extracted Markdown.
"""

import argparse
import json
import re
from pathlib import Path

import cv2
import numpy as np
import pymupdf


TABLE_PAGES = {1: [7], 2: [8], 3: [8], 4: [19, 20], 5: [21, 22],
               6: [23, 24], 7: [26, 27]}
FIGURE_PAGES = {1: 10, 2: 11, 3: 12, 4: 13, 5: 13, 6: 14}
BENEFIT_ROWS = (
    "Paid Vacation or Sick Leave", "Health insurance", "Retirement plans",
    "Life insurance", "Disability insurance", "Ability to Work from Home",
)


def table_sections(lines: list[str]) -> list[dict]:
    sections = []
    for i, line in enumerate(lines):
        match = re.match(r"^Tab\s*le ([1-7])(?: \([^)]*\))?:", line)
        if not match:
            continue
        rows = []
        for j in range(i + 1, len(lines)):
            if lines[j].startswith("|"):
                cells = [cell.strip() for cell in lines[j].strip("|").split("|")]
                if not all(re.fullmatch(r"[-: ]+", cell) for cell in cells):
                    rows.append((j + 1, cells))
            elif rows and not lines[j].strip():
                break
        sections.append({"number": int(match.group(1)), "line": i + 1,
                         "heading": line, "rows": rows})
    return sections


def audit(pdf_path: Path, markdown_path: Path) -> dict:
    lines = markdown_path.read_text(encoding="utf-8").splitlines()
    pdf = pymupdf.open(pdf_path)
    sections = table_sections(lines)
    issues = []
    figure_verification = []

    def add(code: str, severity: str, pages: list[int], md_lines: list[int],
            detail: str, evidence: str) -> None:
        issues.append({"code": code, "severity": severity, "pdf_pages": pages,
                       "markdown_lines": md_lines, "detail": detail,
                       "evidence": evidence})

    for section in sections:
        number = section["number"]
        pages = TABLE_PAGES[number]
        page_text = "\n".join(pdf[p - 1].get_text() for p in pages)
        for line_no, cells in section["rows"]:
            label = cells[0]
            merged_benefits = [name for name in BENEFIT_ROWS if name.lower() in label.lower()]
            if len(merged_benefits) > 1 and all(name.lower() in page_text.lower() for name in merged_benefits):
                add("merged_table_variable_rows", "high", pages, [line_no],
                    f"Table {number} combines {len(merged_benefits)} PDF variable rows into one Markdown row; values and columns are no longer reliable.",
                    label)
            if "Observations" in label and "R-squared" in label and re.search(r"\bObservations\b", page_text) and "R-squared" in page_text:
                add("merged_table_statistic_rows", "high", pages, [line_no],
                    f"Table {number} combines the separate Observations and R-squared rows.",
                    " | ".join(cells)[:240])
            if len(cells) > 1 and label == "" and any(re.fullmatch(r"[\d,.]+", c) for c in cells[1:]):
                add("unlabeled_table_value_row", "high", pages, [line_no],
                    f"Table {number} has numeric values with no row label.",
                    " | ".join(cells)[:240])

        if number == 4 and "(cont" not in section["heading"].lower():
            labels = [cells[0] for _, cells in section["rows"]]
            expected = (*BENEFIT_ROWS, "Constant", "Includes Covariates?",
                        "Includes Year FEs?", "Observations", "R-squared")
            absent = [label for label in expected if label.lower() not in {x.lower() for x in labels}]
            if absent:
                add("missing_table_variable_rows", "high", [19], [section["line"]],
                    "Table 4 PDF rows are absent as separate Markdown rows: " + ", ".join(absent),
                    "PDF page 19 lists each variable and statistic on its own line.")
    formula_lines = [i for i, line in enumerate(lines, 1) if "<!-- formula-not-decoded -->" in line]
    if formula_lines and "(Equation 1)" in pdf[15].get_text():
        add("undecoded_equation", "high", [16], formula_lines,
            "Equation 1 is present in the PDF but the Markdown contains a placeholder.",
            "<!-- formula-not-decoded -->")

    for number, pages in TABLE_PAGES.items():
        for i, line in enumerate(lines, 1):
            if re.match(rf"^Tab\s+le {number}\b", line) and any(
                f"Table {number}" in pdf[page - 1].get_text() for page in pages
            ):
                add("broken_table_heading", "medium", pages, [i],
                    f"The Table {number} heading is split as 'Tab le' in the Markdown.", line)

    # The figure crops are saved inline. They are not numeric chart transcriptions.
    figure_lines = {int(m.group(1)): i for i, line in enumerate(lines, 1)
                    if (m := re.match(r"^Figure ([1-6]):", line))}
    for number, line_no in sorted(figure_lines.items()):
        next_caption = min((v for v in figure_lines.values() if v > line_no), default=len(lines) + 1)
        block = lines[line_no:next_caption - 1]
        if not any("data:image/png;base64," in line for line in block):
            add("missing_figure_image", "high", [FIGURE_PAGES[number]], [line_no],
                f"Figure {number} has no embedded image in the Markdown.", lines[line_no - 1])

    figure_manifest = json.loads(markdown_path.with_name("figures.json").read_text())
    linked_markdown_path = markdown_path.with_name("document-with-figure-links.md")
    linked_markdown = linked_markdown_path.read_text(encoding="utf-8")
    for figure in figure_manifest["figures"]:
        number, page_no = figure["index"], figure["page"]
        image_path = markdown_path.parent / figure["file"]
        image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        page = pdf[page_no - 1]
        pix = page.get_pixmap(colorspace=pymupdf.csGRAY, alpha=False)
        page_image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
        if image is None or image.shape[0] > pix.height or image.shape[1] > pix.width:
            add("unreadable_figure_png", "high", [page_no], [],
                f"Figure {number} PNG is missing or invalid.", figure["file"])
            continue
        _, score, _, location = cv2.minMaxLoc(
            cv2.matchTemplate(page_image, image, cv2.TM_CCOEFF_NORMED)
        )
        x0, _, _, y1 = figure["bbox"]
        expected = (round(x0), round(page.rect.height - y1))
        linked = f"![Figure]({figure['file']})" in linked_markdown
        passed = score >= 0.98 and all(abs(a - b) <= 2 for a, b in zip(location, expected)) and linked
        figure_verification.append({
            "figure": number, "pdf_page": page_no, "png": figure["file"],
            "markdown_link_found": linked, "template_match_score": round(score, 6),
            "render_match_top_left": list(location), "expected_top_left": list(expected),
            "crop_matches_source_pdf": passed,
        })
        if not passed:
            add("figure_verification_failed", "high", [page_no], [],
                f"Figure {number} PNG or Markdown link did not match the recorded PDF location.",
                figure["file"])

    conclusion = next((i for i, line in enumerate(lines) if line.startswith("## VII. Conclusion")), None)
    if conclusion is not None:
        first = next((i for i in range(conclusion + 1, len(lines)) if lines[i].startswith("Employers are uniquely")), None)
        displaced = next((i for i in range(conclusion + 1, len(lines)) if lines[i].startswith("emergencies. There are gains")), None)
        if first is not None and displaced is not None and displaced > first + 1:
            add("out_of_order_conclusion_text", "high", [28], [first + 1, displaced + 1],
                "The first PDF conclusion paragraph is split and part of it appears after the next paragraph.",
                "PDF: 'financial emergencies. There are gains'; Markdown separates 'financial' from 'emergencies.'")

    return {
        "source_pdf": str(pdf_path),
        "markdown": str(markdown_path),
        "pdf_page_count": len(pdf),
        "markdown_line_count": len(lines),
        "numbered_tables": sorted({s["number"] for s in sections}),
        "numbered_figures": sorted(figure_lines),
        "table_sections": [{"table": s["number"], "pdf_pages": TABLE_PAGES[s["number"]],
                            "markdown_line": s["line"], "heading": s["heading"]}
                           for s in sections],
        "linked_markdown": str(linked_markdown_path),
        "figure_verification": figure_verification,
        "issues": issues,
        "issue_count": len(issues),
        "scope": "Full Markdown scanned for numbered tables, figures, formula placeholders, and a confirmed conclusion ordering error. Table findings are structural; cells and prose have not been exhaustively checked for transcription accuracy."
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--markdown", type=Path, default=Path(__file__).with_name("document-with-images.md"))
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("summary.json"))
    args = parser.parse_args()
    result = audit(args.pdf.resolve(), args.markdown.resolve())
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(result['issues'])} findings to {args.output}")


if __name__ == "__main__":
    main()
