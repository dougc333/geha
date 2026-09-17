# pdfplumber extraction review: geha-coverage-policy-ziihera.pdf

- Source SHA-256: `addb184326c16a940eeb8618808d120321f72d77a913ef7f2c2d497399a742ab`
- Extracted Markdown: `geha-coverage-policy-ziihera_pdfplumber.md`
- Combined HTML: `geha-coverage-policy-ziihera_pdfplumber_tables.html`
- Review status: needs_human_review
- Tables: 2
- Vision matches: 1
- Vision mismatches: 1
- Unverified: 0
- Reported issues: 3

No extraction content has been corrected. The PDF is the source of truth.

- Table 1 (PDF page 2): mismatch
- Table 2 (PDF page 3): match

## Issue 1: pdfplumber table 1 — missing_header

- PDF page: 2
- PDF evidence: Drug Name, HCPCS Code, Description
- HTML evidence: 0, 1, 2, 3, 4
- Explanation: The HTML table uses numeric placeholders as headers instead of the relevant headers present in the PDF.

## Issue 2: pdfplumber table 1 — missing_row

- PDF page: 2
- PDF evidence: Ziihera (zanidatamab-hrii), J9276, Injection, zanidatamab-hrii, 2 mg
- HTML evidence: Only one row with drug details is shown in HTML, but there seems to be an omission from the expected format.
- Explanation: The HTML table is missing the second row which should contain the headers for HCPCS and Description.

## Issue 3: pdfplumber table 1 — wrong_cell

- PDF page: 2
- PDF evidence: Column values in PDF match assigned headers
- HTML evidence: Some cell values are empty in the extracted HTML table where they should contain relevant information.
- Explanation: Cells for HCPCS and Description in the second row are missing values in HTML.
