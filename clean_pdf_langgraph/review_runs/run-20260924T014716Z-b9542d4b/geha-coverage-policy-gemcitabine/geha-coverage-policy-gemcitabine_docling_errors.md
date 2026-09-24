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
- Table 1 (PDF page 1): mismatch (1 initial issue(s))
- Table 2 (PDF page 2): mismatch (1 initial issue(s))
- Table 3 (PDF page 3): match (0 initial issue(s))

Raw extraction is preserved. Corrected HTML, when produced, is derived from the PDF source of truth.

- Table 1 (PDF page 1): match
- Table 2 (PDF page 2): mismatch
- Table 3 (PDF page 3): match

## Issue 1: docling table 2 — missing_row

- PDF page: 2
- PDF evidence: Gemcitabine J9201 Injection, gemcitabine hydrochloride, not otherwise specified, 200 mg
- HTML evidence: MISSING
- Explanation: The PDF contains an additional row with 'Gemcitabine J9201' which is missing from the HTML.

## Issue 2: docling table 2 — wrong_cell

- PDF page: 2
- PDF evidence: Gemcitabine (Accord) J9196 Injection, gemcitabine hydrochloride (accord), therapeutically equivalent to J9201, 200 mg
- HTML evidence: Gemcitabine (Accord) J9196 Injection, gemcitabine hydrochloride (accord), not therapeutically equivalent to J9201, 200 mg
- Explanation: The description for 'Gemcitabine (Accord) J9196' in the PDF indicates it's equivalent to J9201, whereas the HTML states 'not equivalent'.
