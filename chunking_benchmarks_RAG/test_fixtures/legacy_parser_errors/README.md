# Archived pre-fix PDF table extracts

These HTML files are byte-for-byte snapshots of the old outputs in
`downloads/coverage-policies/html_tables/`. Do not regenerate or edit them:
they are the **before** side of a future LangGraph parsing-repair demo.

The original source PDFs are already tracked elsewhere in this repository, so
the PDFs are referenced in `manifest.json` rather than copied here.

| Case | Source page | Archived HTML | Observable error |
| --- | ---: | --- | --- |
| Datroway billing | 3 | `geha-coverage-policy-datroway_billing.html` | `0, 1, 2` columns; `Drug Name / HCPCS Code / Description` appears as a data row |
| Bevacizumab billing, first fragment | 2 | `geha-coverage-policy-bevacizumab_billing.html` | Correct header, saved as context for the continuation |
| Bevacizumab billing, continuation | 3 | `geha-coverage-policy-bevacizumab_billing_2.html` | Same PDF table continues with rows but `0, 1, 2` columns instead of inherited labels |

A repair demo should read the source PDF and these archived outputs, write its
corrected output to a *different* directory, and compare against the PDF. It
must never use an archived file as a replacement for the source PDF.

Run `python -m unittest -v chunking_benchmarks_RAG.test_legacy_parser_errors`
from the GEHA repository root to verify the archive has not changed.
