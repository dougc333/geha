"""Regenerate small, synthetic PDFs used by the HTML-table extraction tests.

Run with the bundled ReportLab Python when the binary fixtures need updating.
"""

from pathlib import Path

from reportlab.pdfgen import canvas


HERE = Path(__file__).resolve().parent
WIDTHS = (168, 112, 236)
ROW_HEIGHT = 38


def draw_table(page: canvas.Canvas, rows: list[tuple[str, str, str]]) -> None:
    x0, top = 48, 675
    x_edges = [x0]
    for width in WIDTHS:
        x_edges.append(x_edges[-1] + width)
    bottom = top - ROW_HEIGHT * len(rows)
    for x in x_edges:
        page.line(x, top, x, bottom)
    for index in range(len(rows) + 1):
        y = top - index * ROW_HEIGHT
        page.line(x0, y, x_edges[-1], y)
    page.setFont("Helvetica", 10)
    for index, row in enumerate(rows):
        y = top - index * ROW_HEIGHT - 24
        for column, value in enumerate(row):
            page.drawString(x_edges[column] + 6, y, value)


def new_page(page: canvas.Canvas, title: str) -> None:
    page.setFont("Helvetica-Bold", 18)
    page.drawString(48, 725, title)


def main() -> None:
    header = ("Drug Name", "HCPCS Code", "Description")

    numeric = canvas.Canvas(str(HERE / "table_numeric_header.pdf"), invariant=1)
    new_page(numeric, "Billing")
    draw_table(numeric, [
        header,
        ("Trodelvy", "J9317", "Injection, sacituzumab, 2.5 mg"),
        ("Datroway", "J9011", "Injection, datopotamab, 1 mg"),
    ])
    numeric.save()

    continuation = canvas.Canvas(str(HERE / "table_page_continuation.pdf"), invariant=1)
    new_page(continuation, "Billing")
    draw_table(continuation, [
        header,
        ("Avastin", "J9035", "Injection, bevacizumab, 10 mg"),
        ("Mvasi", "Q5107", "Injection, bevacizumab-awwb, 10 mg"),
    ])
    continuation.showPage()
    new_page(continuation, "Billing")
    draw_table(continuation, [
        ("Zirabev", "Q5118", "Injection, bevacizumab-bvzr, 10 mg"),
        ("Alymsys", "J9400", "Injection, bevacizumab-maly, 10 mg"),
    ])
    continuation.save()


if __name__ == "__main__":
    main()
