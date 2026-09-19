# GEHA plain-chunk Chroma search

This is a simple retrieval baseline for the PDFs in `../downloads/coverage-policies`. It extracts embedded PDF text with `pdfplumber`, splits each page into 180-word chunks with 30 words of overlap, and stores the chunks in a local Chroma collection. It uses no Tesseract or other OCR. It does not detect tables, create row embeddings, or generate answers. Pages without embedded text are skipped rather than converted from images.

# Background

Chroma uses as a default L2 distance for a similarity metric. The search results compare the query embedding vs. chunk embedding. 

$$
d_{\mathrm{L2}}^2 = \sum_{i=1}^{n}(a_i-b_i)^2
$$

Postgres uses cosine similarity

They can be equivalent using: squared L2 distance = 2 - 2 × cosine similarity


## Run

```bash
cd /Users/dc/geha/naive_chroma
uv sync
uv run python index.py
uv run streamlit run app.py --server.address 127.0.0.1 --server.port 8502
```

Latest no-OCR rebuild: **32/32 PDFs**, **108/113 pages**, and **240 chunks** indexed. The five skipped pages are listed below.

## PDFs with pages that have no embedded text

On the evaluated PDF set, no entire PDF is textless. These two PDFs have pages with no text extractable by `pdfplumber`; the indexer skips those pages because it does not use Tesseract or another OCR tool:

| Source PDF | Pages without embedded text | Pages still indexed |
|---|---|---|
| `geha-coverage-policy-datroway.pdf` | 1, 2, 3 | 4 |
| `geha-coverage-policy-elrexfio.pdf` | 1, 2 | 3 |

The preference table in Datroway is on skipped page 1, so its two row questions have no retrievable gold chunk. Elrexfio has no qualifying preferred/non-preferred table rows in this evaluation.

Open the local URL printed by Streamlit. The index is stored in `.chroma/`. You can also build or refresh it from the app sidebar. Rebuilding replaces the existing plain-chunk collection; it does not change the source PDFs.

The first index build may download Chroma's default embedding model. Later runs use the local model cache. The search UI returns source PDF, page, excerpt, and Chroma distance for each hit. Distance is a ranking measure, not answer confidence.

To index a different PDF folder, run `uv run python index.py --pdf-dir /path/to/pdfs`. The app uses the default GEHA folder shown above.

## Verified table-aware comparison

The same 10 preference-row queries were run live against:

- `naive_chroma`: 180-word PDF chunks with 30-word overlap.
- `chunking_benchmarks_RAG`: parsed table rows linked to complete parent tables.

| Query target | Naive rank | Table-aware rank | Expected result |
|---|---:|---:|---|
| Avgemsi | 2 | **1** | Non-preferred, J9184, PA Yes |
| Camcevi | 2 | **1** | Non-preferred, J1952, PA Yes |
| Lupron Depot 7.5 mg | 4 | **1** | Non-preferred, J9217, PA No |
| Orgovyx | 4 | **1** | Non-preferred, J8999, PA Yes |
| Armlupeg | 2 | **1** | Non-preferred, J3590, PA Yes |
| Ryzneuta | 2 | **1** | Non-preferred, J9361, PA Yes |
| Nyvepria | 2 | **1** | Preferred, Q5122, PA Yes |
| Pemetrexed ditromethamine | 5 | **1** | Non-preferred, J9323, PA Yes |
| Pemfexy | 15 | **1** | Non-preferred, J9304, PA Yes |
| Pemrydi RTU | 5 | **1** | Non-preferred, J9324, PA Yes |

### Metrics for these 10 selected examples

| Metric | Naive | Table aware |
|---|---:|---:|
| Exact evidence at rank 1 | **0/10** | **10/10** |
| Exact evidence within top 4 | **7/10** | **10/10** |
| Mean reciprocal rank | **0.347** | **1.000** |

These cases were deliberately selected from naive top-one failures to demonstrate specific improvements. They are not an unbiased estimate of overall accuracy.

### Example queries

1. In the gemcitabine policy, is Avgemsi preferred? What is its HCPCS code and prior authorization requirement?
2. In the GnRH analogues policy, is Camcevi preferred? What is its HCPCS code and prior authorization requirement?
3. In the GnRH analogues policy, is Lupron Depot at the 7.5 mg dose preferred? What is its HCPCS code and prior authorization requirement?
4. In the GnRH analogues policy, is Orgovyx preferred? What is its HCPCS code and prior authorization requirement?
5. In the long-acting G-CSF policy, is Armlupeg preferred? What is its HCPCS code and prior authorization requirement?
6. In the long-acting G-CSF policy, is Ryzneuta preferred? What is its HCPCS code and prior authorization requirement?
7. In the long-acting G-CSF policy, is Nyvepria preferred? What is its HCPCS code and prior authorization requirement?
8. In the pemetrexed policy, is Pemetrexed ditromethamine preferred? What is its HCPCS code and prior authorization requirement?
9. In the pemetrexed policy, is Pemfexy preferred? What is its HCPCS code and prior authorization requirement?
10. In the pemetrexed policy, is Pemrydi RTU preferred? What is its HCPCS code and prior authorization requirement?

### Why table-aware retrieval improves these queries

- **Split table rows:** Fixed 180-word chunks divide long tables. The Lupron and later pemetrexed rows fall into a different chunk from the beginning of the table.
- **Revision-history distraction:** For Avgemsi and Camcevi, ordinary prose mentioning the product outranks the preference table.
- **Similar-policy confusion:** Short-acting G-CSF chunks outrank long-acting G-CSF rows for Armlupeg, Ryzneuta, and Nyvepria.
- **Complete parent tables:** The table-aware implementation links searchable child rows to their complete parent table, preserving the drug, preference, HCPCS code, and authorization fields in one result.

These queries explicitly name the policy, so `chunking_benchmarks_RAG` also benefits from its policy-name routing before returning the structured parent table. This comparison therefore measures the behavior of the two complete applications, rather than isolating row embeddings alone.


## Re-run the preference-row evaluation

```bash
cd /Users/dc/geha/naive_chroma
uv run python evaluate_preference_rows.py
```

The fixed `gold_preference_rows.json` records every question, expected row values, source PDF, page, and accepted index chunk IDs. The runner searches all indexed PDFs with the same pure Chroma vector query as the app. It updates the statistics and full per-row results below and writes `preference_row_results.json` for further analysis. If you rebuild the index with a different chunking scheme, review the gold chunk IDs before comparing scores.

<!-- PREFERENCE_ROW_EVAL_START -->
## Plain-chunk Chroma: preferred-row retrieval evaluation

Each question asks for one row's preference, HCPCS code, and prior authorization. The gold result is a page-1 chunk containing the row's preference evidence; a billing or revision mention is not counted. Searches use the app's unfiltered Chroma vector query across 32 policy PDFs. No Tesseract or other OCR is used, so pages without embedded text contribute no chunks. The other 15 PDFs have no qualifying preference rows but remain searchable distractors where text exists. No answer model was evaluated.

- Gold rows: **99** across **17** preference-table PDFs.
- Rows without an indexed source table: **2**; retrievable row gold: **97**.
- Strict row hit@1: **72/99** (72.7%); hit@4: **91/99** (91.9%); hit@10: **95/99** (96.0%).
- Correct PDF at rank 1: **88/99** (88.9%); MRR: **0.823**.
- Other-policy top-1 misses: 9; same-policy other-page misses: 6; same-page wrong-chunk misses: 10; source-page-not-indexed misses: 2.

### Breakdown

| Preference | Rows | Hit@1 | Hit@4 |
|---|---:|---:|---:|
| preferred | 29 | 24 | 28 |
| non-preferred | 70 | 48 | 63 |

| Policy PDF | Rows | Hit@1 | Hit@4 |
|---|---:|---:|---:|
| geha-coverage-policy-bendamustine.pdf | 5 | 5 | 5 |
| geha-coverage-policy-bevacizumab.pdf | 8 | 8 | 8 |
| geha-coverage-policy-datroway.pdf | 2 | 0 | 0 |
| geha-coverage-policy-erythropoietin-stimulating-agents.pdf | 4 | 4 | 4 |
| geha-coverage-policy-gemcitabine.pdf | 3 | 2 | 3 |
| geha-coverage-policy-gnrh-analogues-in-prostate-cancer.pdf | 10 | 6 | 10 |
| geha-coverage-policy-long-acting-gcsfs.pdf | 10 | 2 | 10 |
| geha-coverage-policy-non-muscle-invasive-bladder-cancer.pdf | 5 | 1 | 5 |
| geha-coverage-policy-paclitaxel-protein-bound.pdf | 4 | 4 | 4 |
| geha-coverage-policy-pemetrexed.pdf | 10 | 7 | 7 |
| geha-coverage-policy-rituximab.pdf | 5 | 4 | 5 |
| geha-coverage-policy-rytelo.pdf | 2 | 2 | 2 |
| geha-coverage-policy-short-acting-gcsfs.pdf | 5 | 5 | 5 |
| geha-coverage-policy-taxotere-docivyx.pdf | 3 | 3 | 3 |
| geha-coverage-policy-trastuzumab.pdf | 8 | 8 | 8 |
| geha-coverage-policy-vectibix.pdf | 2 | 2 | 2 |
| geha-coverage-policy-xgeva.pdf | 13 | 9 | 10 |

### Per-row questions and results

#### geha-coverage-policy-bendamustine.pdf

| ID | Query | Gold answer | Gold page/chunk | Top 1? | Gold rank | Actual first hit and diagnosis |
|---|---|---|---|---|---:|---|
| bendamustine_01 | In the bendamustine policy, is Treanda preferred? What is its HCPCS code and prior authorization requirement? | Treanda: preferred; HCPCS J9033; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-bendamustine.pdf p1 c1. Correct row. |
| bendamustine_02 | In the bendamustine policy, is Bendamustine 505(b)(2) Dr Reddy's preferred? What is its HCPCS code and prior authorization requirement? | Bendamustine 505(b)(2) Dr Reddy's: preferred; HCPCS J9999; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-bendamustine.pdf p1 c1. Correct row. |
| bendamustine_03 | In the bendamustine policy, is Bendeka preferred? What is its HCPCS code and prior authorization requirement? | Bendeka: non-preferred; HCPCS J9034; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-bendamustine.pdf p1 c1. Correct row. |
| bendamustine_04 | In the bendamustine policy, is Belrapzo preferred? What is its HCPCS code and prior authorization requirement? | Belrapzo: non-preferred; HCPCS J9036; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-bendamustine.pdf p1 c1. Correct row. |
| bendamustine_05 | In the bendamustine policy, is Vivimusta preferred? What is its HCPCS code and prior authorization requirement? | Vivimusta: non-preferred; HCPCS J9056; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-bendamustine.pdf p1 c1. Correct row. |

#### geha-coverage-policy-bevacizumab.pdf

| ID | Query | Gold answer | Gold page/chunk | Top 1? | Gold rank | Actual first hit and diagnosis |
|---|---|---|---|---|---:|---|
| bevacizumab_01 | In the bevacizumab policy, is Bevacizumab-awwb (Mvasi) preferred? What is its HCPCS code and prior authorization requirement? | Bevacizumab- awwb (Mvasi): non-preferred; HCPCS Q5107; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-bevacizumab.pdf p1 c1. Correct row. |
| bevacizumab_02 | In the bevacizumab policy, is Bevacizumab-bvzr (Zirabev) preferred? What is its HCPCS code and prior authorization requirement? | Bevacizumab-bvzr (Zirabev): preferred; HCPCS Q5118; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-bevacizumab.pdf p1 c1. Correct row. |
| bevacizumab_03 | In the bevacizumab policy, is Bevacizumab (Avastin) preferred? What is its HCPCS code and prior authorization requirement? | Bevacizumab (Avastin): non-preferred; HCPCS J9035; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-bevacizumab.pdf p1 c1. Correct row. |
| bevacizumab_04 | In the bevacizumab policy, is Bevacizumab-tnjn (Avzivi) preferred? What is its HCPCS code and prior authorization requirement? | Bevacizumab-tnjn (Avzivi): non-preferred; HCPCS J9999; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-bevacizumab.pdf p1 c1. Correct row. |
| bevacizumab_05 | In the bevacizumab policy, is Bevacizumab-maly (Alymsys) preferred? What is its HCPCS code and prior authorization requirement? | Bevacizumab- maly (Alymsys): non-preferred; HCPCS Q5126; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-bevacizumab.pdf p1 c1. Correct row. |
| bevacizumab_06 | In the bevacizumab policy, is Bevacizumab-adcd (Vegzelma) preferred? What is its HCPCS code and prior authorization requirement? | Bevacizumab- adcd (Vegzelma): non-preferred; HCPCS Q5129; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-bevacizumab.pdf p1 c1. Correct row. |
| bevacizumab_07 | In the bevacizumab policy, is Ziv-aflibercept (Zaltrap) preferred? What is its HCPCS code and prior authorization requirement? | Ziv-aflibercept (Zaltrap): non-preferred; HCPCS J9400; prior authorization Yes. | p1 c1, p1 c2 | Yes | 1 | geha-coverage-policy-bevacizumab.pdf p1 c1. Correct row. |
| bevacizumab_08 | In the bevacizumab policy, is Bevacizumab - nwgd (Jobevne) preferred? What is its HCPCS code and prior authorization requirement? | Bevacizumab - nwgd (Jobevne): non-preferred; HCPCS Q5160; prior authorization Yes. | p1 c1, p1 c2 | Yes | 1 | geha-coverage-policy-bevacizumab.pdf p1 c1. Correct row. |

#### geha-coverage-policy-datroway.pdf

| ID | Query | Gold answer | Gold page/chunk | Top 1? | Gold rank | Actual first hit and diagnosis |
|---|---|---|---|---|---:|---|
| datroway_01 | In the datroway policy, is Trodelvy preferred? What is its HCPCS code and prior authorization requirement? | Trodelvy: preferred; HCPCS J9317; prior authorization Yes. | No chunk (page 1 lacks embedded text) | No | — | geha-coverage-policy-imdelltra.pdf p3 c1. Source preference table is on page 1, which has no embedded text; OCR is disabled. |
| datroway_02 | In the datroway policy, is Datroway preferred? What is its HCPCS code and prior authorization requirement? | Datroway: non-preferred; HCPCS J9011; prior authorization Yes. | No chunk (page 1 lacks embedded text) | No | — | geha-coverage-policy-bendamustine.pdf p3 c2. Source preference table is on page 1, which has no embedded text; OCR is disabled. |

#### geha-coverage-policy-erythropoietin-stimulating-agents.pdf

| ID | Query | Gold answer | Gold page/chunk | Top 1? | Gold rank | Actual first hit and diagnosis |
|---|---|---|---|---|---:|---|
| erythropoietin-stimulating-agents_01 | In the erythropoietin stimulating agents policy, is Retacrit preferred? What is its HCPCS code and prior authorization requirement? | Retacrit: preferred; HCPCS Q5106; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-erythropoietin-stimulating-agents.pdf p1 c1. Correct row. |
| erythropoietin-stimulating-agents_02 | In the erythropoietin stimulating agents policy, is Aranesp preferred? What is its HCPCS code and prior authorization requirement? | Aranesp: preferred; HCPCS J0881; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-erythropoietin-stimulating-agents.pdf p1 c1. Correct row. |
| erythropoietin-stimulating-agents_03 | In the erythropoietin stimulating agents policy, is Epogen preferred? What is its HCPCS code and prior authorization requirement? | Epogen: non-preferred; HCPCS J0885; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-erythropoietin-stimulating-agents.pdf p1 c1. Correct row. |
| erythropoietin-stimulating-agents_04 | In the erythropoietin stimulating agents policy, is Procrit preferred? What is its HCPCS code and prior authorization requirement? | Procrit: non-preferred; HCPCS J0885; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-erythropoietin-stimulating-agents.pdf p1 c1. Correct row. |

#### geha-coverage-policy-gemcitabine.pdf

| ID | Query | Gold answer | Gold page/chunk | Top 1? | Gold rank | Actual first hit and diagnosis |
|---|---|---|---|---|---:|---|
| gemcitabine_01 | In the gemcitabine policy, is Gemzar preferred? What is its HCPCS code and prior authorization requirement? | Gemzar: non-preferred; HCPCS J9201; prior authorization No. | p1 c1 | Yes | 1 | geha-coverage-policy-gemcitabine.pdf p1 c1. Correct row. |
| gemcitabine_02 | In the gemcitabine policy, is Gemcitabine (Accord) preferred? What is its HCPCS code and prior authorization requirement? | Gemcitabine (Accord): preferred; HCPCS J9196; prior authorization No. | p1 c1 | Yes | 1 | geha-coverage-policy-gemcitabine.pdf p1 c1. Correct row. |
| gemcitabine_03 | In the gemcitabine policy, is Avgemsi preferred? What is its HCPCS code and prior authorization requirement? | Avgemsi: non-preferred; HCPCS J9184; prior authorization Yes. | p1 c1 | No | 2 | geha-coverage-policy-gemcitabine.pdf p3 c2. Another mention of the drug or code elsewhere in the right PDF outranked its preference table. |

#### geha-coverage-policy-gnrh-analogues-in-prostate-cancer.pdf

| ID | Query | Gold answer | Gold page/chunk | Top 1? | Gold rank | Actual first hit and diagnosis |
|---|---|---|---|---|---:|---|
| gnrh-analogues-in-prostate-cancer_01 | In the gnrh analogues in prostate cancer policy, is Firmagon (degarelix) preferred? What is its HCPCS code and prior authorization requirement? | Firmagon (degarelix): preferred; HCPCS J9155; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-gnrh-analogues-in-prostate-cancer.pdf p1 c1. Correct row. |
| gnrh-analogues-in-prostate-cancer_02 | In the gnrh analogues in prostate cancer policy, is Eligard (leuprolide acetate depot) preferred? What is its HCPCS code and prior authorization requirement? | Eligard(leuprolide acetate depot): preferred; HCPCS J9217; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-gnrh-analogues-in-prostate-cancer.pdf p1 c1. Correct row. |
| gnrh-analogues-in-prostate-cancer_03 | In the gnrh analogues in prostate cancer policy, is Lupron Depot (leuprolide acetate depot) at the 3.75 mg dose preferred? What is its HCPCS code and prior authorization requirement? | Lupron Depot (leuprolide acetate depot): non-preferred; HCPCS J1950; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-gnrh-analogues-in-prostate-cancer.pdf p1 c1. Correct row. |
| gnrh-analogues-in-prostate-cancer_04 | In the gnrh analogues in prostate cancer policy, is Camcevi (leuprolide mesylate) preferred? What is its HCPCS code and prior authorization requirement? | Camcevi (leuprolide mesylate): non-preferred; HCPCS J1952; prior authorization Yes. | p1 c1 | No | 2 | geha-coverage-policy-gnrh-analogues-in-prostate-cancer.pdf p5 c1. General prose in the right PDF outranked the preference table. |
| gnrh-analogues-in-prostate-cancer_05 | In the gnrh analogues in prostate cancer policy, is Lutrate Depot (leuprolide acetate depot) preferred? What is its HCPCS code and prior authorization requirement? | Lutrate Depot (leuprolide acetate depot): non-preferred; HCPCS J1954; prior authorization No. | p1 c1 | Yes | 1 | geha-coverage-policy-gnrh-analogues-in-prostate-cancer.pdf p1 c1. Correct row. |
| gnrh-analogues-in-prostate-cancer_06 | In the gnrh analogues in prostate cancer policy, is Trelstar (triptorelin) preferred? What is its HCPCS code and prior authorization requirement? | Trelstar (triptorelin): non-preferred; HCPCS J3315; prior authorization No. | p1 c1, p1 c2 | Yes | 1 | geha-coverage-policy-gnrh-analogues-in-prostate-cancer.pdf p1 c2. Correct row. |
| gnrh-analogues-in-prostate-cancer_07 | In the gnrh analogues in prostate cancer policy, is Camcevi ETM (leuprolide mesylate) preferred? What is its HCPCS code and prior authorization requirement? | Camcevi ETM (leuprolide mesylate): non-preferred; HCPCS J9003; prior authorization No. | p1 c1, p1 c2 | No | 2 | geha-coverage-policy-gnrh-analogues-in-prostate-cancer.pdf p5 c1. Another mention of the drug or code elsewhere in the right PDF outranked its preference table. |
| gnrh-analogues-in-prostate-cancer_08 | In the gnrh analogues in prostate cancer policy, is Zoladex (goserelin) preferred? What is its HCPCS code and prior authorization requirement? | Zoladex (goserelin): non-preferred; HCPCS J9202; prior authorization No. | p1 c1, p1 c2 | Yes | 1 | geha-coverage-policy-gnrh-analogues-in-prostate-cancer.pdf p1 c1. Correct row. |
| gnrh-analogues-in-prostate-cancer_09 | In the gnrh analogues in prostate cancer policy, is Lupron Depot (leuprolide acetate depot) at the 7.5 mg dose preferred? What is its HCPCS code and prior authorization requirement? | Lupron Depot (leuprolide acetate depot): non-preferred; HCPCS J9217; prior authorization No. | p1 c2 | No | 4 | geha-coverage-policy-gnrh-analogues-in-prostate-cancer.pdf p1 c1. An adjacent fixed-size chunk from the same table page outranked the chunk containing this row. |
| gnrh-analogues-in-prostate-cancer_10 | In the gnrh analogues in prostate cancer policy, is Orgovyx (relugolix) preferred? What is its HCPCS code and prior authorization requirement? | Orgovyx (relugolix): non-preferred; HCPCS J8999; prior authorization Yes. | p1 c2 | No | 4 | geha-coverage-policy-gnrh-analogues-in-prostate-cancer.pdf p1 c1. An adjacent fixed-size chunk from the same table page outranked the chunk containing this row. |

#### geha-coverage-policy-long-acting-gcsfs.pdf

| ID | Query | Gold answer | Gold page/chunk | Top 1? | Gold rank | Actual first hit and diagnosis |
|---|---|---|---|---|---:|---|
| long-acting-gcsfs_01 | In the long acting gcsfs policy, is Neulasta preferred? What is its HCPCS code and prior authorization requirement? | Neulasta: non-preferred; HCPCS J2506; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-long-acting-gcsfs.pdf p1 c1. Correct row. |
| long-acting-gcsfs_02 | In the long acting gcsfs policy, is Rolvedon preferred? What is its HCPCS code and prior authorization requirement? | Rolvedon: non-preferred; HCPCS J1449; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-long-acting-gcsfs.pdf p1 c1. Correct row. |
| long-acting-gcsfs_03 | In the long acting gcsfs policy, is Armlupeg preferred? What is its HCPCS code and prior authorization requirement? | Armlupeg: non-preferred; HCPCS J3590; prior authorization Yes. | p1 c1 | No | 2 | geha-coverage-policy-short-acting-gcsfs.pdf p1 c1. The short-acting G-CSF table's similar preference language outranked the long-acting drug row. |
| long-acting-gcsfs_04 | In the long acting gcsfs policy, is Ryzneuta preferred? What is its HCPCS code and prior authorization requirement? | Ryzneuta: non-preferred; HCPCS J9361; prior authorization Yes. | p1 c1 | No | 2 | geha-coverage-policy-short-acting-gcsfs.pdf p1 c1. The short-acting G-CSF table's similar preference language outranked the long-acting drug row. |
| long-acting-gcsfs_05 | In the long acting gcsfs policy, is Fulphila preferred? What is its HCPCS code and prior authorization requirement? | Fulphila: non-preferred; HCPCS Q5108; prior authorization Yes. | p1 c1 | No | 2 | geha-coverage-policy-short-acting-gcsfs.pdf p1 c1. The short-acting G-CSF table's similar preference language outranked the long-acting drug row. |
| long-acting-gcsfs_06 | In the long acting gcsfs policy, is Udenyca preferred? What is its HCPCS code and prior authorization requirement? | Udenyca: non-preferred; HCPCS Q5111; prior authorization Yes. | p1 c1 | No | 2 | geha-coverage-policy-short-acting-gcsfs.pdf p1 c1. The short-acting G-CSF table's similar preference language outranked the long-acting drug row. |
| long-acting-gcsfs_07 | In the long acting gcsfs policy, is Ziextenzo preferred? What is its HCPCS code and prior authorization requirement? | Ziextenzo: non-preferred; HCPCS Q5120; prior authorization Yes. | p1 c1 | No | 2 | geha-coverage-policy-short-acting-gcsfs.pdf p1 c1. The short-acting G-CSF table's similar preference language outranked the long-acting drug row. |
| long-acting-gcsfs_08 | In the long acting gcsfs policy, is Nyvepria preferred? What is its HCPCS code and prior authorization requirement? | Nyvepria: preferred; HCPCS Q5122; prior authorization Yes. | p1 c1, p1 c2 | No | 2 | geha-coverage-policy-short-acting-gcsfs.pdf p1 c1. The short-acting G-CSF table's similar preference language outranked the long-acting drug row. |
| long-acting-gcsfs_09 | In the long acting gcsfs policy, is Stimufend preferred? What is its HCPCS code and prior authorization requirement? | Stimufend: non-preferred; HCPCS Q5127; prior authorization Yes. | p1 c1, p1 c2 | No | 2 | geha-coverage-policy-short-acting-gcsfs.pdf p1 c1. The short-acting G-CSF table's similar preference language outranked the long-acting drug row. |
| long-acting-gcsfs_10 | In the long acting gcsfs policy, is Fylnetra preferred? What is its HCPCS code and prior authorization requirement? | Fylnetra: preferred; HCPCS Q5130; prior authorization Yes. | p1 c1, p1 c2 | No | 2 | geha-coverage-policy-short-acting-gcsfs.pdf p1 c1. The short-acting G-CSF table's similar preference language outranked the long-acting drug row. |

#### geha-coverage-policy-non-muscle-invasive-bladder-cancer.pdf

| ID | Query | Gold answer | Gold page/chunk | Top 1? | Gold rank | Actual first hit and diagnosis |
|---|---|---|---|---|---:|---|
| non-muscle-invasive-bladder-cancer_01 | In the non muscle invasive bladder cancer policy, is Nadofaragene firadenovec-vncg (Adstiladrin) preferred? What is its HCPCS code and prior authorization requirement? | Nadofaragene firadenovec-vncg (Adstiladrin): preferred; HCPCS J9029; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-non-muscle-invasive-bladder-cancer.pdf p1 c1. Correct row. |
| non-muscle-invasive-bladder-cancer_02 | In the non muscle invasive bladder cancer policy, is Pembrolizumab (Keytruda) preferred? What is its HCPCS code and prior authorization requirement? | Pembrolizumab (Keytruda): preferred; HCPCS J9271; prior authorization Yes. | p1 c1 | No | 2 | geha-coverage-policy-non-muscle-invasive-bladder-cancer.pdf p5 c2. General prose in the right PDF outranked the preference table. |
| non-muscle-invasive-bladder-cancer_03 | In the non muscle invasive bladder cancer policy, is Pembrolizumab and berahyaluronidase alfa-pmph (Keytruda QLEX) preferred? What is its HCPCS code and prior authorization requirement? | Pembrolizumab and berahyaluronidas e alfa-pmph (Keytruda QLEX): preferred; HCPCS J9277; prior authorization Yes. | p1 c1 | No | 2 | geha-coverage-policy-non-muscle-invasive-bladder-cancer.pdf p5 c2. Another mention of the drug or code elsewhere in the right PDF outranked its preference table. |
| non-muscle-invasive-bladder-cancer_04 | In the non muscle invasive bladder cancer policy, is Nogapendekin alfa inbakicept-pmln (Anktiva) preferred? What is its HCPCS code and prior authorization requirement? | Nogapendekin alfa inbakicept- pmln (Anktiva): non-preferred; HCPCS J9028; prior authorization Yes. | p1 c1 | No | 2 | geha-coverage-policy-non-muscle-invasive-bladder-cancer.pdf p1 c2. An adjacent fixed-size chunk from the same table page outranked the chunk containing this row. |
| non-muscle-invasive-bladder-cancer_05 | In the non muscle invasive bladder cancer policy, is Gemcitabine (Inlexzo) preferred? What is its HCPCS code and prior authorization requirement? | Gemcitabine (Inlexzo): non-preferred; HCPCS J9183; prior authorization Yes. | p1 c1 | No | 2 | geha-coverage-policy-non-muscle-invasive-bladder-cancer.pdf p5 c2. Another mention of the drug or code elsewhere in the right PDF outranked its preference table. |

#### geha-coverage-policy-paclitaxel-protein-bound.pdf

| ID | Query | Gold answer | Gold page/chunk | Top 1? | Gold rank | Actual first hit and diagnosis |
|---|---|---|---|---|---:|---|
| paclitaxel-protein-bound_01 | In the paclitaxel protein bound policy, is Docetaxel (Taxotere) preferred? What is its HCPCS code and prior authorization requirement? | Docetaxel (Taxotere): preferred; HCPCS J9171; prior authorization No. | p1 c1 | Yes | 1 | geha-coverage-policy-paclitaxel-protein-bound.pdf p1 c1. Correct row. |
| paclitaxel-protein-bound_02 | In the paclitaxel protein bound policy, is Docetaxel (Hospira 505(b)(2)) preferred? What is its HCPCS code and prior authorization requirement? | Docetaxel (Hospira 505(b)(2)): preferred; HCPCS J9232; prior authorization No. | p1 c1 | Yes | 1 | geha-coverage-policy-paclitaxel-protein-bound.pdf p1 c1. Correct row. |
| paclitaxel-protein-bound_03 | In the paclitaxel protein bound policy, is Paclitaxel (Taxol) preferred? What is its HCPCS code and prior authorization requirement? | Paclitaxel (Taxol): preferred; HCPCS J9267; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-paclitaxel-protein-bound.pdf p1 c1. Correct row. |
| paclitaxel-protein-bound_04 | In the paclitaxel protein bound policy, is Paclitaxel Protein-Bound (Abraxane) preferred? What is its HCPCS code and prior authorization requirement? | Paclitaxel Protein- Bound (Abraxane): non-preferred; HCPCS J9264; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-paclitaxel-protein-bound.pdf p1 c1. Correct row. |

#### geha-coverage-policy-pemetrexed.pdf

| ID | Query | Gold answer | Gold page/chunk | Top 1? | Gold rank | Actual first hit and diagnosis |
|---|---|---|---|---|---:|---|
| pemetrexed_01 | In the pemetrexed policy, is Pemetrexed (Axtle) preferred? What is its HCPCS code and prior authorization requirement? | Pemetrexed (Axtle): preferred; HCPCS J9292; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-pemetrexed.pdf p1 c1. Correct row. |
| pemetrexed_02 | In the pemetrexed policy, is Pemetrexed (Hospira) preferred? What is its HCPCS code and prior authorization requirement? | Pemetrexed (Hospira): non-preferred; HCPCS J9294; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-pemetrexed.pdf p1 c1. Correct row. |
| pemetrexed_03 | In the pemetrexed policy, is Pemetrexed (Accord) preferred? What is its HCPCS code and prior authorization requirement? | Pemetrexed (Accord): preferred; HCPCS J9296; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-pemetrexed.pdf p1 c1. Correct row. |
| pemetrexed_04 | In the pemetrexed policy, is Pemetrexed (Sandoz) preferred? What is its HCPCS code and prior authorization requirement? | Pemetrexed (Sandoz): non-preferred; HCPCS J9297; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-pemetrexed.pdf p1 c1. Correct row. |
| pemetrexed_05 | In the pemetrexed policy, is Pemetrexed (Alimta ) preferred? What is its HCPCS code and prior authorization requirement? | Pemetrexed (Alimta ): non-preferred; HCPCS J9305; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-pemetrexed.pdf p1 c1. Correct row. |
| pemetrexed_06 | In the pemetrexed policy, is Pemetrexed (Teva) preferred? What is its HCPCS code and prior authorization requirement? | Pemetrexed (Teva): non-preferred; HCPCS J9314; prior authorization Yes. | p1 c1, p1 c2 | Yes | 1 | geha-coverage-policy-pemetrexed.pdf p1 c1. Correct row. |
| pemetrexed_07 | In the pemetrexed policy, is Pemetrexed (Bluepoint) preferred? What is its HCPCS code and prior authorization requirement? | Pemetrexed (Bluepoint): preferred; HCPCS J9322; prior authorization Yes. | p1 c1, p1 c2 | Yes | 1 | geha-coverage-policy-pemetrexed.pdf p1 c1. Correct row. |
| pemetrexed_08 | In the pemetrexed policy, is Pemetrexed ditromethamine (Hospira) preferred? What is its HCPCS code and prior authorization requirement? | Pemetrexed ditromethamine (Hospira): non-preferred; HCPCS J9323; prior authorization Yes. | p1 c2 | No | 5 | geha-coverage-policy-pemetrexed.pdf p1 c1. An adjacent fixed-size chunk from the same table page outranked the chunk containing this row. |
| pemetrexed_09 | In the pemetrexed policy, is Pemfexy preferred? What is its HCPCS code and prior authorization requirement? | Pemfexy: non-preferred; HCPCS J9304; prior authorization Yes. | p1 c2 | No | 15 | geha-coverage-policy-pemetrexed.pdf p1 c1. An adjacent fixed-size chunk from the same table page outranked the chunk containing this row. |
| pemetrexed_10 | In the pemetrexed policy, is Pemrydi RTU preferred? What is its HCPCS code and prior authorization requirement? | Pemrydi RTU: non-preferred; HCPCS J9324; prior authorization Yes. | p1 c2 | No | 5 | geha-coverage-policy-pemetrexed.pdf p1 c1. An adjacent fixed-size chunk from the same table page outranked the chunk containing this row. |

#### geha-coverage-policy-rituximab.pdf

| ID | Query | Gold answer | Gold page/chunk | Top 1? | Gold rank | Actual first hit and diagnosis |
|---|---|---|---|---|---:|---|
| rituximab_01 | In the rituximab policy, is Ruxience preferred? What is its HCPCS code and prior authorization requirement? | Ruxience: preferred; HCPCS Q5119; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-rituximab.pdf p1 c1. Correct row. |
| rituximab_02 | In the rituximab policy, is Truxima preferred? What is its HCPCS code and prior authorization requirement? | Truxima: non-preferred; HCPCS Q5115; prior authorization Yes. | p1 c1 | No | 2 | geha-coverage-policy-trastuzumab.pdf p1 c1. An unrelated policy chunk outranked the source table row; semantic similarity favored broad policy wording. |
| rituximab_03 | In the rituximab policy, is Rituxan Hycela preferred? What is its HCPCS code and prior authorization requirement? | Rituxan Hycela: non-preferred; HCPCS J9311; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-rituximab.pdf p1 c1. Correct row. |
| rituximab_04 | In the rituximab policy, is Rituxan preferred? What is its HCPCS code and prior authorization requirement? | Rituxan: non-preferred; HCPCS J9312; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-rituximab.pdf p1 c1. Correct row. |
| rituximab_05 | In the rituximab policy, is Riabni preferred? What is its HCPCS code and prior authorization requirement? | Riabni: non-preferred; HCPCS Q5123; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-rituximab.pdf p1 c1. Correct row. |

#### geha-coverage-policy-rytelo.pdf

| ID | Query | Gold answer | Gold page/chunk | Top 1? | Gold rank | Actual first hit and diagnosis |
|---|---|---|---|---|---:|---|
| rytelo_01 | In the rytelo policy, is Reblozyl (luspatercept) preferred? What is its HCPCS code and prior authorization requirement? | Reblozyl (luspatercept): preferred; HCPCS J0896; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-rytelo.pdf p1 c1. Correct row. |
| rytelo_02 | In the rytelo policy, is Rytelo (imetelstat) preferred? What is its HCPCS code and prior authorization requirement? | Rytelo (imetelstat): non-preferred; HCPCS J0870; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-rytelo.pdf p1 c1. Correct row. |

#### geha-coverage-policy-short-acting-gcsfs.pdf

| ID | Query | Gold answer | Gold page/chunk | Top 1? | Gold rank | Actual first hit and diagnosis |
|---|---|---|---|---|---:|---|
| short-acting-gcsfs_01 | In the short acting gcsfs policy, is Zarxio (filgrastim-sndz) preferred? What is its HCPCS code and prior authorization requirement? | Zarxio (filgrastim-sndz): non-preferred; HCPCS Q5101; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-short-acting-gcsfs.pdf p1 c1. Correct row. |
| short-acting-gcsfs_02 | In the short acting gcsfs policy, is Nivestym (filgrastim-aafi) preferred? What is its HCPCS code and prior authorization requirement? | Nivestym (filgrastim- aafi): preferred; HCPCS Q5110; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-short-acting-gcsfs.pdf p1 c1. Correct row. |
| short-acting-gcsfs_03 | In the short acting gcsfs policy, is Neupogen (filgrastim) preferred? What is its HCPCS code and prior authorization requirement? | Neupogen (filgrastim): non-preferred; HCPCS J1442; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-short-acting-gcsfs.pdf p1 c1. Correct row. |
| short-acting-gcsfs_04 | In the short acting gcsfs policy, is Granix (tbo-filgrastim) preferred? What is its HCPCS code and prior authorization requirement? | Granix (tbo-filgrastim): non-preferred; HCPCS J1447; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-short-acting-gcsfs.pdf p1 c1. Correct row. |
| short-acting-gcsfs_05 | In the short acting gcsfs policy, is Nypozi (filgrastim-txid) preferred? What is its HCPCS code and prior authorization requirement? | Nypozi (filgrastim-txid): non-preferred; HCPCS Q5148; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-short-acting-gcsfs.pdf p1 c1. Correct row. |

#### geha-coverage-policy-taxotere-docivyx.pdf

| ID | Query | Gold answer | Gold page/chunk | Top 1? | Gold rank | Actual first hit and diagnosis |
|---|---|---|---|---|---:|---|
| taxotere-docivyx_01 | In the taxotere docivyx policy, is Taxotere (docetaxel) preferred? What is its HCPCS code and prior authorization requirement? | Taxotere (docetaxel): preferred; HCPCS J9171; prior authorization No. | p1 c1 | Yes | 1 | geha-coverage-policy-taxotere-docivyx.pdf p1 c1. Correct row. |
| taxotere-docivyx_02 | In the taxotere docivyx policy, is Docetaxel (Hospira 505(b)(2)) preferred? What is its HCPCS code and prior authorization requirement? | Docetaxel (Hospira 505(b)(2)): preferred; HCPCS J9232; prior authorization No. | p1 c1 | Yes | 1 | geha-coverage-policy-taxotere-docivyx.pdf p1 c1. Correct row. |
| taxotere-docivyx_03 | In the taxotere docivyx policy, is Docetaxel (Docivyx) preferred? What is its HCPCS code and prior authorization requirement? | Docetaxel (Docivyx): non-preferred; HCPCS J9172; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-taxotere-docivyx.pdf p1 c1. Correct row. |

#### geha-coverage-policy-trastuzumab.pdf

| ID | Query | Gold answer | Gold page/chunk | Top 1? | Gold rank | Actual first hit and diagnosis |
|---|---|---|---|---|---:|---|
| trastuzumab_01 | In the trastuzumab policy, is Trazimera preferred? What is its HCPCS code and prior authorization requirement? | Trazimera: preferred; HCPCS Q5116; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-trastuzumab.pdf p1 c1. Correct row. |
| trastuzumab_02 | In the trastuzumab policy, is Kanjinti preferred? What is its HCPCS code and prior authorization requirement? | Kanjinti: preferred; HCPCS Q5117; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-trastuzumab.pdf p1 c1. Correct row. |
| trastuzumab_03 | In the trastuzumab policy, is Herceptin preferred? What is its HCPCS code and prior authorization requirement? | Herceptin: non-preferred; HCPCS J9355; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-trastuzumab.pdf p1 c1. Correct row. |
| trastuzumab_04 | In the trastuzumab policy, is Herceptin Hylecta preferred? What is its HCPCS code and prior authorization requirement? | Herceptin Hylecta: non-preferred; HCPCS J9356; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-trastuzumab.pdf p1 c1. Correct row. |
| trastuzumab_05 | In the trastuzumab policy, is Hercessi preferred? What is its HCPCS code and prior authorization requirement? | Hercessi: non-preferred; HCPCS Q5416; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-trastuzumab.pdf p1 c1. Correct row. |
| trastuzumab_06 | In the trastuzumab policy, is Ontruzant preferred? What is its HCPCS code and prior authorization requirement? | Ontruzant: non-preferred; HCPCS Q5112; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-trastuzumab.pdf p1 c1. Correct row. |
| trastuzumab_07 | In the trastuzumab policy, is Herzuma preferred? What is its HCPCS code and prior authorization requirement? | Herzuma: non-preferred; HCPCS Q5113; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-trastuzumab.pdf p1 c1. Correct row. |
| trastuzumab_08 | In the trastuzumab policy, is Ogivri preferred? What is its HCPCS code and prior authorization requirement? | Ogivri: non-preferred; HCPCS Q5114; prior authorization Yes. | p1 c1, p1 c2 | Yes | 1 | geha-coverage-policy-trastuzumab.pdf p1 c1. Correct row. |

#### geha-coverage-policy-vectibix.pdf

| ID | Query | Gold answer | Gold page/chunk | Top 1? | Gold rank | Actual first hit and diagnosis |
|---|---|---|---|---|---:|---|
| vectibix_01 | In the vectibix policy, is Cetuximab (Erbitux) preferred? What is its HCPCS code and prior authorization requirement? | Cetuximab (Erbitux): preferred; HCPCS J9055; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-vectibix.pdf p1 c1. Correct row. |
| vectibix_02 | In the vectibix policy, is Panitumumab (Vectibix) preferred? What is its HCPCS code and prior authorization requirement? | Panitumumab (Vectibix): non-preferred; HCPCS J9303; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-vectibix.pdf p1 c1. Correct row. |

#### geha-coverage-policy-xgeva.pdf

| ID | Query | Gold answer | Gold page/chunk | Top 1? | Gold rank | Actual first hit and diagnosis |
|---|---|---|---|---|---:|---|
| xgeva_01 | In the xgeva policy, is Zoledronic Acid (Zometa) preferred? What is its HCPCS code and prior authorization requirement? | Zoledronic Acid (Zometa): preferred; HCPCS J3489; prior authorization No. | p1 c1 | Yes | 1 | geha-coverage-policy-xgeva.pdf p1 c1. Correct row. |
| xgeva_02 | In the xgeva policy, is Denosumab (Xgeva) preferred? What is its HCPCS code and prior authorization requirement? | Denosumab (Xgeva): non-preferred; HCPCS J0897; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-xgeva.pdf p1 c1. Correct row. |
| xgeva_03 | In the xgeva policy, is Denosumab-desu (Jubereq) preferred? What is its HCPCS code and prior authorization requirement? | Denosumab-desu (Jubereq): non-preferred; HCPCS J3590; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-xgeva.pdf p1 c1. Correct row. |
| xgeva_04 | In the xgeva policy, is Denosumab-qbde (Xtrenbo) preferred? What is its HCPCS code and prior authorization requirement? | Denosumab-qbde (Xtrenbo): non-preferred; HCPCS J3590; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-xgeva.pdf p1 c1. Correct row. |
| xgeva_05 | In the xgeva policy, is Denosumab-bbdz (Wyost) preferred? What is its HCPCS code and prior authorization requirement? | Denosumab-bbdz (Wyost): non-preferred; HCPCS Q5136; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-xgeva.pdf p1 c1. Correct row. |
| xgeva_06 | In the xgeva policy, is Denosumab-bmwo (Osenvelt) preferred? What is its HCPCS code and prior authorization requirement? | Denosumab-bmwo (Osenvelt): non-preferred; HCPCS Q5157; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-xgeva.pdf p1 c1. Correct row. |
| xgeva_07 | In the xgeva policy, is Denosumab-bmwo (Denosumab-Celtrion) preferred? What is its HCPCS code and prior authorization requirement? | Denosumab-bmwo (Denosumab-Celtrion): non-preferred; HCPCS Q5157; prior authorization Yes. | p1 c1 | Yes | 1 | geha-coverage-policy-xgeva.pdf p1 c1. Correct row. |
| xgeva_08 | In the xgeva policy, is Denosumab-bnht (Bomyntra) preferred? What is its HCPCS code and prior authorization requirement? | Denosumab-bnht (Bomyntra): non-preferred; HCPCS Q5158; prior authorization Yes. | p1 c1, p1 c2 | Yes | 1 | geha-coverage-policy-xgeva.pdf p1 c1. Correct row. |
| xgeva_09 | In the xgeva policy, is Denosumab-bnht (denosumab Frensenius) preferred? What is its HCPCS code and prior authorization requirement? | Denosumab-bnht (denosumab Frensenius): non-preferred; HCPCS Q5158; prior authorization Yes. | p1 c1, p1 c2 | Yes | 1 | geha-coverage-policy-xgeva.pdf p1 c1. Correct row. |
| xgeva_10 | In the xgeva policy, is Denosumab-dssb (Xbryk) preferred? What is its HCPCS code and prior authorization requirement? | Denosumab-dssb (Xbryk): non-preferred; HCPCS Q5159; prior authorization Yes. | p1 c2 | No | 4 | geha-coverage-policy-xgeva.pdf p1 c1. An adjacent fixed-size chunk from the same table page outranked the chunk containing this row. |
| xgeva_11 | In the xgeva policy, is Denosumab-dssb (Denosumab Samsung Bioepis) preferred? What is its HCPCS code and prior authorization requirement? | Denosumab-dssb (Denosumab Samsung Bioepis): non-preferred; HCPCS Q5159; prior authorization Yes. | p1 c2 | No | 8 | geha-coverage-policy-xgeva.pdf p1 c1. An adjacent fixed-size chunk from the same table page outranked the chunk containing this row. |
| xgeva_12 | In the xgeva policy, is Denosumab-kyqq (Aukelso) preferred? What is its HCPCS code and prior authorization requirement? | Denosumab-kyqq (Aukelso): non-preferred; HCPCS Q5161; prior authorization Yes. | p1 c2 | No | 10 | geha-coverage-policy-xgeva.pdf p1 c1. An adjacent fixed-size chunk from the same table page outranked the chunk containing this row. |
| xgeva_13 | In the xgeva policy, is Denosumab-nxxp (Bilprevda) preferred? What is its HCPCS code and prior authorization requirement? | Denosumab-nxxp (Bilprevda): non-preferred; HCPCS Q5162; prior authorization Yes. | p1 c2 | No | 70 | geha-coverage-policy-xgeva.pdf p1 c1. An adjacent fixed-size chunk from the same table page outranked the chunk containing this row. |

### Interpretation

A top-1 miss measures retrieval only. The answer text above is the source-table gold label, not a claim that the search UI generated a correct answer. Fixed word chunks can put multiple preference rows together, split a row near a boundary, or rank a billing mention ahead of its preference table. Miss reasons describe the observed first hit and the likely ranking failure; they cannot establish the embedding model's internal cause. The gold file records every accepted chunk ID.

The questions explicitly name a policy. Scores apply to these exact questions: the shorter `Is Treanda preferred?` query, for example, previously placed its table chunk fifth.

Gold labels were seeded from the existing `_table_openai.csv` preference tables and cross-checked against the plain index's page-1 drug and code text where available. Datroway's two gold rows have no indexed page-1 text. Retain the source PDFs as the authority if a PDF is later revised.

<!-- PREFERENCE_ROW_EVAL_END -->
