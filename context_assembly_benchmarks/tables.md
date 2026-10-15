# Coverage policies with preferred and non-preferred tables

17 policy PDFs contain at least one preferred row and at least one non-preferred row in the extracted table data.

| Policy PDF | Extracted table CSV | Preferred | Non-preferred |
|---|---|---:|---:|
| `geha-coverage-policy-bendamustine.pdf` | `geha-coverage-policy-bendamustine_table_openai.csv` | 2 | 3 |
| `geha-coverage-policy-bevacizumab.pdf` | `geha-coverage-policy-bevacizumab_table_openai.csv` | 1 | 7 |
| `geha-coverage-policy-datroway.pdf` | `geha-coverage-policy-datroway_table_openai.csv` | 1 | 1 |
| `geha-coverage-policy-erythropoietin-stimulating-agents.pdf` | `geha-coverage-policy-erythropoietin-stimulating-agents_table_openai.csv` | 2 | 2 |
| `geha-coverage-policy-gemcitabine.pdf` | `geha-coverage-policy-gemcitabine_table_openai.csv` | 1 | 2 |
| `geha-coverage-policy-gnrh-analogues-in-prostate-cancer.pdf` | `geha-coverage-policy-gnrh-analogues-in-prostate-cancer_table_openai.csv` | 2 | 8 |
| `geha-coverage-policy-long-acting-gcsfs.pdf` | `geha-coverage-policy-long-acting-gcsfs_table_openai.csv` | 2 | 8 |
| `geha-coverage-policy-non-muscle-invasive-bladder-cancer.pdf` | `geha-coverage-policy-non-muscle-invasive-bladder-cancer_table_openai.csv` | 3 | 2 |
| `geha-coverage-policy-paclitaxel-protein-bound.pdf` | `geha-coverage-policy-paclitaxel-protein-bound_table_openai.csv` | 3 | 1 |
| `geha-coverage-policy-pemetrexed.pdf` | `geha-coverage-policy-pemetrexed_table_openai.csv` | 3 | 7 |
| `geha-coverage-policy-rituximab.pdf` | `geha-coverage-policy-rituximab_table_openai.csv` | 1 | 4 |
| `geha-coverage-policy-rytelo.pdf` | `geha-coverage-policy-rytelo_table_openai.csv` | 1 | 1 |
| `geha-coverage-policy-short-acting-gcsfs.pdf` | `geha-coverage-policy-short-acting-gcsfs_table_openai.csv` | 1 | 4 |
| `geha-coverage-policy-taxotere-docivyx.pdf` | `geha-coverage-policy-taxotere-docivyx_table_openai.csv` | 2 | 1 |
| `geha-coverage-policy-trastuzumab.pdf` | `geha-coverage-policy-trastuzumab_table_openai.csv` | 2 | 6 |
| `geha-coverage-policy-vectibix.pdf` | `geha-coverage-policy-vectibix_table_openai.csv` | 1 | 1 |
| `geha-coverage-policy-xgeva.pdf` | `geha-coverage-policy-xgeva_table_openai.csv` | 1 | 12 |

## Evaluation coverage

The companion `table_preference_evals.json` contains 34 cases: one preferred query and one non-preferred query for each policy above.

Preference labels were normalized for matching. For example, `Non-Preferred`, `Non- Preferred`, `Non - Preferred`, uppercase labels, and footnote markers are treated as the same category. Expected drug names preserve the extracted table text.

## Initial retrieval baseline

Using `BAAI/bge-small-en-v1.5`, cosine similarity, and the configured 20 candidate rows, the existing database retrieved the expected policy source for:

- Top 1: 31 of 34 cases (91.2%)
- Top 3: 33 of 34 cases (97.1%)
- Top 5: 34 of 34 cases (100%)

These are retrieval-source results. They do not score whether a generated answer includes every expected drug name.

The top-1 misses are `gemcitabine_preferred`, `short_acting_gcsfs_preferred`, and `short_acting_gcsfs_non_preferred`. The short-acting G-CSF non-preferred case is also the sole top-3 miss. These failures are retained in the suite so improvements to retrieval can be measured rather than hidden by rewriting the expected results.
