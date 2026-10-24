# Chunk noise report

Runs: `/Users/dc/geha/crawl_dir/runs` (batch `batch-20261009-all`)

Flags are text heuristics: `toc` = 3+ dot-leader or page-number lines; `form` = 2+ blank fields or checkboxes; `tiny` = under 25 words; `boilerplate` = half or more of the chunk's lines appear in at least 5.4 documents.

| group | documents | pages | chunks | chunks_per_page | toc_pct | form_pct | tiny_pct | boilerplate_pct |
|---|---|---|---|---|---|---|---|---|
| all | 54 | 1093 | 3197 | 2.92 | 6.9 | 0.0 | 9.8 | 14.4 |
| coverage-policies | 35 | 181 | 449 | 2.48 | 0.4 | 0.0 | 4.5 | 24.5 |
| dental | 2 | 68 | 211 | 3.1 | 9.5 | 0.0 | 19.0 | 15.6 |
| medical | 17 | 844 | 2537 | 3.01 | 7.8 | 0.0 | 9.9 | 12.5 |
| 3-5 pages | 33 | 116 | 297 | 2.56 | 0.0 | 0.0 | 5.4 | 36.7 |
| 6-15 pages | 10 | 83 | 290 | 3.49 | 0.3 | 0.0 | 5.2 | 20.3 |
| 16-40 pages | 4 | 68 | 164 | 2.41 | 0.0 | 0.0 | 17.7 | 0.0 |
| 41- pages | 7 | 826 | 2446 | 2.96 | 9.0 | 0.0 | 10.3 | 12.0 |

## Concentration

- top 1 documents chunk share pct: 14.6%
- top 3 documents chunk share pct: 41.8%
- top 5 documents chunk share pct: 67.6%
- top 10 documents chunk share pct: 80.7%
- chunks grow as pages^1.05
- repeated-line rank-frequency slope: -0.44 (Zipf is about -1)

## Most repeated lines

- 33 documents: `medical necessity`
- 31 documents: `#/#/#`
- 31 documents: `universal approval criteria:`
- 31 documents: `for internal use only`
- 31 documents: `policy type:`
- 31 documents: `disclaimer`
- 30 documents: `review date:`
- 30 documents: `- o clinical pharmacology (strong for); or`
- 30 documents: `references`
- 30 documents: `- o wolters kluwer lexi-drugs® (level a); or`
- 29 documents: `- o meeting abstracts and case reports are excluded from consideration;`
- 27 documents: `revision date(s):`
- 25 documents: `original effective date:`
- 25 documents: `line of business:`
- 23 documents: `- non-standard protocols may be approved based on unique clinical circumstances;`
