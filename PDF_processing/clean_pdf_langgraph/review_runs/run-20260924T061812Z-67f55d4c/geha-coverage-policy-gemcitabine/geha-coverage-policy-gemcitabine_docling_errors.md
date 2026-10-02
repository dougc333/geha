# docling extraction review: geha-coverage-policy-gemcitabine.pdf

- Source SHA-256: `465656dedc7d2c5d40de1344e68f03105ed1c2504b73e91d1863ec510cb027d6`
- Extracted Markdown: `geha-coverage-policy-gemcitabine.docling.md`
- Combined HTML: `geha-coverage-policy-gemcitabine_docling_tables.html`
- Corrected HTML: `geha-coverage-policy-gemcitabine_docling_tables_corrected.html`
- Review status: needs_human_review
- Tables: 3
- Vision matches: 2
- Vision mismatches: 1
- Unverified: 0
- Reported issues: 2

Initial table results:
- Table 1 (PDF page 1): mismatch (1 initial issue(s), 1 correction attempt(s))
- Table 2 (PDF page 2): match (0 initial issue(s), 0 correction attempt(s))
- Table 3 (PDF page 3): match (0 initial issue(s), 0 correction attempt(s))

Raw extraction is preserved. Corrected HTML, when produced, is derived from the PDF source of truth.

- Table 1 (PDF page 1): mismatch
- Table 2 (PDF page 2): match
- Table 3 (PDF page 3): match

## Issue 1: docling table 1 — missing_row

- PDF page: 1
- PDF evidence: No blank row in PDF table
- HTML evidence: <tr>
      <td></td>
      <td></td>
      <td>Gemcitabine</td>
      <td>J9201</td>
      <td>Injection, gemcitabine hydrochloride, not otherwise specified, 200 mg</td>
    </tr>
- Explanation: The extracted HTML table has an extra, empty row with only one cell filled.

## Issue 2: docling table 1 — wrong_heading

- PDF page: 1
- PDF evidence: PDF Header: Requires Auth
- HTML evidence: HTML Header: Requires Prior Auth
- Explanation: The header 'Requires Auth' in the PDF was altered to 'Requires Prior Auth' in the HTML.
