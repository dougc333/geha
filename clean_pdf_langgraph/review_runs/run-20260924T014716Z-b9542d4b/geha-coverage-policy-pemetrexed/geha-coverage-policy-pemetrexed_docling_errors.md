# docling extraction review: geha-coverage-policy-pemetrexed.pdf

- Source SHA-256: `c876c51d54bc3e5bc800787cce3686383dbd189f9dc09267c12be198315db3dc`
- Extracted Markdown: `geha-coverage-policy-pemetrexed.docling.md`
- Combined HTML: `geha-coverage-policy-pemetrexed_docling_tables.html`
- Corrected HTML: `geha-coverage-policy-pemetrexed_docling_tables_corrected.html`
- Review status: needs_human_review
- Tables: 4
- Vision matches: 3
- Vision mismatches: 1
- Unverified: 0
- Reported issues: 2

Initial table results:
- Table 1 (PDF page 1): match (0 initial issue(s))
- Table 2 (PDF page 2): mismatch (7 initial issue(s))
- Table 3 (PDF page 3): mismatch (3 initial issue(s))
- Table 4 (PDF page 4): match (0 initial issue(s))

Raw extraction is preserved. Corrected HTML, when produced, is derived from the PDF source of truth.

- Table 1 (PDF page 1): match
- Table 2 (PDF page 2): mismatch
- Table 3 (PDF page 3): match
- Table 4 (PDF page 4): match

## Issue 1: docling table 2 — missing_row

- PDF page: 2
- PDF evidence: Drug Name: Pemetrexed (Alimta)
HCPCS Code: J9305
Description: Injection, pemetrexed, not otherwise specified, 10 mg
- HTML evidence: Missing in HTML extraction
- Explanation: The HTML table is missing the row for 'Pemetrexed (Alimta)', HCPCS Code: J9305.

## Issue 2: docling table 2 — wrong_cell

- PDF page: 1
- PDF evidence: J9297 Injection, pemetrexed (sandoz), not therapeutically equivalent to J9305, 10 mg
- HTML evidence: J9297 Injection, pemetrexed sandoz, not therapeutically equivalent to J9305, 10 mg
- Explanation: The HTML extraction has removed the parentheses around 'sandoz' that are present in the PDF.
