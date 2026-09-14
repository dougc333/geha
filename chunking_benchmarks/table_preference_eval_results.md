# Preferred and non-preferred table evaluation results

Generated: `2026-09-14T00:01:20.689456+00:00`

This report covers 34 queries across 17 policy preference tables. Answers are extracted deterministically from the top retrieved table, so these results isolate retrieval and table interpretation without an LLM grader.

## Summary

- Source recall@1: **91.2%**
- Source recall@3: **97.1%**
- Source recall@5: **100.0%**
- Exact table recall@1: **82.4%**
- Exact table recall@3: **94.1%**
- Exact table recall@5: **97.1%**
- Exact product-list match from top result: **82.4%**
- Mean product recall from top result: **82.4%**
- Embedding model: `BAAI/bge-small-en-v1.5`
- Candidate rows: `20`

## All query comparisons

### 1. `bendamustine_preferred`

- **Query:** Which bendamustine products are preferred?
- **Expected source:** `geha-coverage-policy-bendamustine.pdf`
- **Expected table:** `geha-coverage-policy-bendamustine.pdf` table 1
- **Top result:** `geha-coverage-policy-bendamustine.pdf` table 1 (Drug preference and prior authorization; similarity 0.7430)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Treanda, Bendamustine 505(b)(2) Dr Reddy's
- **Products from top result:** Treanda, Bendamustine 505(b)(2) Dr Reddy's
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-bendamustine.pdf` table 1 (Drug preference and prior authorization) — 0.7430 ← expected table
  2. `geha-coverage-policy-bendamustine.pdf` table 2 (Billing codes) — 0.6939
  3. `geha-coverage-policy-rytelo.pdf` table 1 (0 / 1 / 2 / 3 / 4) — 0.6522
  4. `geha-coverage-policy-bendamustine.pdf` table 3 (Revision history) — 0.6408
  5. `geha-coverage-policy-vectibix.pdf` table 1 (0 / 1 / 2 / 3 / 4) — 0.6271

### 2. `bendamustine_non_preferred`

- **Query:** Which bendamustine products are non-preferred?
- **Expected source:** `geha-coverage-policy-bendamustine.pdf`
- **Expected table:** `geha-coverage-policy-bendamustine.pdf` table 1
- **Top result:** `geha-coverage-policy-bendamustine.pdf` table 1 (Drug preference and prior authorization; similarity 0.7477)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Bendeka, Belrapzo, Vivimusta
- **Products from top result:** Bendeka, Belrapzo, Vivimusta
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-bendamustine.pdf` table 1 (Drug preference and prior authorization) — 0.7477 ← expected table
  2. `geha-coverage-policy-bendamustine.pdf` table 2 (Billing codes) — 0.6871
  3. `geha-coverage-policy-vectibix.pdf` table 1 (0 / 1 / 2 / 3 / 4) — 0.6581
  4. `geha-coverage-policy-rytelo.pdf` table 1 (0 / 1 / 2 / 3 / 4) — 0.6375
  5. `geha-coverage-policy-rituximab.pdf` table 1 (Preference / Requires Prior Drug / Name / HCPCS Code / Description) — 0.6256

### 3. `bevacizumab_preferred`

- **Query:** Which bevacizumab products are preferred?
- **Expected source:** `geha-coverage-policy-bevacizumab.pdf`
- **Expected table:** `geha-coverage-policy-bevacizumab.pdf` table 1
- **Top result:** `geha-coverage-policy-bevacizumab.pdf` table 1 (Drug preference and prior authorization; similarity 0.7836)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Bevacizumab-bvzr (Zirabev)
- **Products from top result:** Bevacizumab-bvzr (Zirabev)
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-bevacizumab.pdf` table 1 (Drug preference and prior authorization) — 0.7836 ← expected table
  2. `geha-coverage-policy-bevacizumab.pdf` table 3 (0 / 1 / 2) — 0.7594
  3. `geha-coverage-policy-vectibix.pdf` table 1 (0 / 1 / 2 / 3 / 4) — 0.7453
  4. `geha-coverage-policy-xgeva.pdf` table 1 (Drug preference and prior authorization) — 0.7300
  5. `geha-coverage-policy-bevacizumab.pdf` table 2 (Billing codes) — 0.7297

### 4. `bevacizumab_non_preferred`

- **Query:** Which bevacizumab products are non-preferred?
- **Expected source:** `geha-coverage-policy-bevacizumab.pdf`
- **Expected table:** `geha-coverage-policy-bevacizumab.pdf` table 1
- **Top result:** `geha-coverage-policy-bevacizumab.pdf` table 1 (Drug preference and prior authorization; similarity 0.7891)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Bevacizumab- awwb (Mvasi), Bevacizumab (Avastin), Bevacizumab-tnjn (Avzivi), Bevacizumab- maly (Alymsys), Bevacizumab- adcd (Vegzelma), Ziv-aflibercept (Zaltrap), Bevacizumab - nwgd (Jobevne)
- **Products from top result:** Bevacizumab- awwb (Mvasi), Bevacizumab (Avastin), Bevacizumab-tnjn (Avzivi), Bevacizumab- maly (Alymsys), Bevacizumab- adcd (Vegzelma), Ziv-aflibercept (Zaltrap), Bevacizumab - nwgd (Jobevne)
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-bevacizumab.pdf` table 1 (Drug preference and prior authorization) — 0.7891 ← expected table
  2. `geha-coverage-policy-vectibix.pdf` table 1 (0 / 1 / 2 / 3 / 4) — 0.7837
  3. `geha-coverage-policy-xgeva.pdf` table 1 (Drug preference and prior authorization) — 0.7503
  4. `geha-coverage-policy-bevacizumab.pdf` table 3 (0 / 1 / 2) — 0.7489

### 5. `datroway_preferred`

- **Query:** Which datroway products are preferred?
- **Expected source:** `geha-coverage-policy-datroway.pdf`
- **Expected table:** `geha-coverage-policy-datroway.pdf` table 1
- **Top result:** `geha-coverage-policy-datroway.pdf` table 1 (Drug preference and prior authorization; similarity 0.7514)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Trodelvy
- **Products from top result:** Trodelvy
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-datroway.pdf` table 1 (Drug preference and prior authorization) — 0.7514 ← expected table
  2. `geha-coverage-policy-datroway.pdf` table 2 (0 / 1 / 2) — 0.7349
  3. `geha-coverage-policy-datroway.pdf` table 3 (Date / !Updates) — 0.6756
  4. `geha-coverage-policy-rytelo.pdf` table 1 (0 / 1 / 2 / 3 / 4) — 0.6657
  5. `geha-coverage-policy-trastuzumab.pdf` table 1 (Drug preference and prior authorization) — 0.6540

### 6. `datroway_non_preferred`

- **Query:** Which datroway products are non-preferred?
- **Expected source:** `geha-coverage-policy-datroway.pdf`
- **Expected table:** `geha-coverage-policy-datroway.pdf` table 1
- **Top result:** `geha-coverage-policy-datroway.pdf` table 1 (Drug preference and prior authorization; similarity 0.7622)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Datroway
- **Products from top result:** Datroway
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-datroway.pdf` table 1 (Drug preference and prior authorization) — 0.7622 ← expected table
  2. `geha-coverage-policy-datroway.pdf` table 2 (0 / 1 / 2) — 0.7256
  3. `geha-coverage-policy-rytelo.pdf` table 1 (0 / 1 / 2 / 3 / 4) — 0.7223
  4. `geha-coverage-policy-vectibix.pdf` table 1 (0 / 1 / 2 / 3 / 4) — 0.6832
  5. `geha-coverage-policy-rituximab.pdf` table 1 (Preference / Requires Prior Drug / Name / HCPCS Code / Description) — 0.6748

### 7. `erythropoietin_stimulating_agents_preferred`

- **Query:** Which erythropoietin stimulating agents products are preferred?
- **Expected source:** `geha-coverage-policy-erythropoietin-stimulating-agents.pdf`
- **Expected table:** `geha-coverage-policy-erythropoietin-stimulating-agents.pdf` table 1
- **Top result:** `geha-coverage-policy-erythropoietin-stimulating-agents.pdf` table 1 (Drug preference and prior authorization; similarity 0.7911)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Retacrit, Aranesp
- **Products from top result:** Retacrit, Aranesp
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-erythropoietin-stimulating-agents.pdf` table 1 (Drug preference and prior authorization) — 0.7911 ← expected table
  2. `geha-coverage-policy-erythropoietin-stimulating-agents.pdf` table 2 (Billing codes) — 0.7350
  3. `geha-coverage-policy-erythropoietin-stimulating-agents.pdf` table 3 (Revision history) — 0.7288
  4. `geha-coverage-policy-long-acting-gcsfs.pdf` table 1 (Drug preference and prior authorization) — 0.6986
  5. `geha-coverage-policy-vectibix.pdf` table 1 (0 / 1 / 2 / 3 / 4) — 0.6923

### 8. `erythropoietin_stimulating_agents_non_preferred`

- **Query:** Which erythropoietin stimulating agents products are non-preferred?
- **Expected source:** `geha-coverage-policy-erythropoietin-stimulating-agents.pdf`
- **Expected table:** `geha-coverage-policy-erythropoietin-stimulating-agents.pdf` table 1
- **Top result:** `geha-coverage-policy-erythropoietin-stimulating-agents.pdf` table 1 (Drug preference and prior authorization; similarity 0.8110)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Epogen, Procrit
- **Products from top result:** Epogen, Procrit
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-erythropoietin-stimulating-agents.pdf` table 1 (Drug preference and prior authorization) — 0.8110 ← expected table
  2. `geha-coverage-policy-erythropoietin-stimulating-agents.pdf` table 2 (Billing codes) — 0.7446
  3. `geha-coverage-policy-erythropoietin-stimulating-agents.pdf` table 3 (Revision history) — 0.7230
  4. `geha-coverage-policy-vectibix.pdf` table 1 (0 / 1 / 2 / 3 / 4) — 0.7102
  5. `geha-coverage-policy-long-acting-gcsfs.pdf` table 1 (Drug preference and prior authorization) — 0.7099

### 9. `gemcitabine_preferred`

- **Query:** Which gemcitabine products are preferred?
- **Expected source:** `geha-coverage-policy-gemcitabine.pdf`
- **Expected table:** `geha-coverage-policy-gemcitabine.pdf` table 1
- **Top result:** `geha-coverage-policy-non-muscle-invasive-bladder-cancer.pdf` table 1 (Drug preference and prior authorization; similarity 0.7940)
- **Expected-source rank:** 2 — **FAIL at top 1**
- **Expected-table rank:** 2 — **FAIL at top 1**
- **Expected products:** Gemcitabine (Accord)
- **Products from top result:** Nadofaragene firadenovec-vncg (Adstiladrin), Pembrolizumab (Keytruda), Pembrolizumab and berahyaluronidas e alfa-pmph (Keytruda QLEX)
- **Product comparison:** **FAIL**; recall 0.0%, precision 0.0%
- **Top-five search results:**

  1. `geha-coverage-policy-non-muscle-invasive-bladder-cancer.pdf` table 1 (Drug preference and prior authorization) — 0.7940
  2. `geha-coverage-policy-gemcitabine.pdf` table 1 (Drug preference and prior authorization) — 0.7916 ← expected table
  3. `geha-coverage-policy-gemcitabine.pdf` table 3 (Revision history) — 0.7593
  4. `geha-coverage-policy-non-muscle-invasive-bladder-cancer.pdf` table 2 (Billing codes) — 0.7389
  5. `geha-coverage-policy-gemcitabine.pdf` table 2 (Billing codes) — 0.7345

### 10. `gemcitabine_non_preferred`

- **Query:** Which gemcitabine products are non-preferred?
- **Expected source:** `geha-coverage-policy-gemcitabine.pdf`
- **Expected table:** `geha-coverage-policy-gemcitabine.pdf` table 1
- **Top result:** `geha-coverage-policy-gemcitabine.pdf` table 1 (Drug preference and prior authorization; similarity 0.8103)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Gemzar, Avgemsi
- **Products from top result:** Gemzar, Avgemsi
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-gemcitabine.pdf` table 1 (Drug preference and prior authorization) — 0.8103 ← expected table
  2. `geha-coverage-policy-non-muscle-invasive-bladder-cancer.pdf` table 1 (Drug preference and prior authorization) — 0.8097
  3. `geha-coverage-policy-gemcitabine.pdf` table 3 (Revision history) — 0.7540
  4. `geha-coverage-policy-vectibix.pdf` table 1 (0 / 1 / 2 / 3 / 4) — 0.7533
  5. `geha-coverage-policy-non-muscle-invasive-bladder-cancer.pdf` table 2 (Billing codes) — 0.7469

### 11. `gnrh_analogues_in_prostate_cancer_preferred`

- **Query:** Which gnrh analogues in prostate cancer products are preferred?
- **Expected source:** `geha-coverage-policy-gnrh-analogues-in-prostate-cancer.pdf`
- **Expected table:** `geha-coverage-policy-gnrh-analogues-in-prostate-cancer.pdf` table 1
- **Top result:** `geha-coverage-policy-gnrh-analogues-in-prostate-cancer.pdf` table 3 (Revision history; similarity 0.8198)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 2 — **FAIL at top 1**
- **Expected products:** Firmagon (degarelix), Eligard(leuprolide acetate depot)
- **Products from top result:** _(none)_
- **Product comparison:** **FAIL**; recall 0.0%, precision 0.0%
- **Top-five search results:**

  1. `geha-coverage-policy-gnrh-analogues-in-prostate-cancer.pdf` table 3 (Revision history) — 0.8198
  2. `geha-coverage-policy-gnrh-analogues-in-prostate-cancer.pdf` table 1 (Drug preference and prior authorization) — 0.8095 ← expected table
  3. `geha-coverage-policy-gnrh-analogues-in-prostate-cancer.pdf` table 2 (Billing codes) — 0.7884

### 12. `gnrh_analogues_in_prostate_cancer_non_preferred`

- **Query:** Which gnrh analogues in prostate cancer products are non-preferred?
- **Expected source:** `geha-coverage-policy-gnrh-analogues-in-prostate-cancer.pdf`
- **Expected table:** `geha-coverage-policy-gnrh-analogues-in-prostate-cancer.pdf` table 1
- **Top result:** `geha-coverage-policy-gnrh-analogues-in-prostate-cancer.pdf` table 1 (Drug preference and prior authorization; similarity 0.8187)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Lupron Depot (leuprolide acetate depot), Camcevi (leuprolide mesylate), Lutrate Depot (leuprolide acetate depot), Trelstar (triptorelin), Camcevi ETM (leuprolide mesylate), Zoladex (goserelin), Orgovyx (relugolix)
- **Products from top result:** Lupron Depot (leuprolide acetate depot), Camcevi (leuprolide mesylate), Lutrate Depot (leuprolide acetate depot), Trelstar (triptorelin), Camcevi ETM (leuprolide mesylate), Zoladex (goserelin), Orgovyx (relugolix)
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-gnrh-analogues-in-prostate-cancer.pdf` table 1 (Drug preference and prior authorization) — 0.8187 ← expected table
  2. `geha-coverage-policy-gnrh-analogues-in-prostate-cancer.pdf` table 3 (Revision history) — 0.8157
  3. `geha-coverage-policy-gnrh-analogues-in-prostate-cancer.pdf` table 2 (Billing codes) — 0.7799

### 13. `long_acting_gcsfs_preferred`

- **Query:** Which long acting gcsfs products are preferred?
- **Expected source:** `geha-coverage-policy-long-acting-gcsfs.pdf`
- **Expected table:** `geha-coverage-policy-long-acting-gcsfs.pdf` table 1
- **Top result:** `geha-coverage-policy-long-acting-gcsfs.pdf` table 3 (0 / 1 / 2; similarity 0.7284)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 3 — **FAIL at top 1**
- **Expected products:** Nyvepria, Fylnetra
- **Products from top result:** _(none)_
- **Product comparison:** **FAIL**; recall 0.0%, precision 0.0%
- **Top-five search results:**

  1. `geha-coverage-policy-long-acting-gcsfs.pdf` table 3 (0 / 1 / 2) — 0.7284
  2. `geha-coverage-policy-long-acting-gcsfs.pdf` table 4 (Revision history) — 0.7088
  3. `geha-coverage-policy-long-acting-gcsfs.pdf` table 1 (Drug preference and prior authorization) — 0.6599 ← expected table
  4. `geha-coverage-policy-long-acting-gcsfs.pdf` table 2 (Billing codes) — 0.6491

### 14. `long_acting_gcsfs_non_preferred`

- **Query:** Which long acting gcsfs products are non-preferred?
- **Expected source:** `geha-coverage-policy-long-acting-gcsfs.pdf`
- **Expected table:** `geha-coverage-policy-long-acting-gcsfs.pdf` table 1
- **Top result:** `geha-coverage-policy-long-acting-gcsfs.pdf` table 3 (0 / 1 / 2; similarity 0.7144)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 3 — **FAIL at top 1**
- **Expected products:** Neulasta, Rolvedon, Armlupeg, Ryzneuta, Fulphila, Udenyca, Ziextenzo, Stimufend
- **Products from top result:** _(none)_
- **Product comparison:** **FAIL**; recall 0.0%, precision 0.0%
- **Top-five search results:**

  1. `geha-coverage-policy-long-acting-gcsfs.pdf` table 3 (0 / 1 / 2) — 0.7144
  2. `geha-coverage-policy-long-acting-gcsfs.pdf` table 4 (Revision history) — 0.6901
  3. `geha-coverage-policy-long-acting-gcsfs.pdf` table 1 (Drug preference and prior authorization) — 0.6876 ← expected table
  4. `geha-coverage-policy-short-acting-gcsfs.pdf` table 1 (Drug preference and prior authorization) — 0.6645
  5. `geha-coverage-policy-long-acting-gcsfs.pdf` table 2 (Billing codes) — 0.6612

### 15. `non_muscle_invasive_bladder_cancer_preferred`

- **Query:** Which non muscle invasive bladder cancer products are preferred?
- **Expected source:** `geha-coverage-policy-non-muscle-invasive-bladder-cancer.pdf`
- **Expected table:** `geha-coverage-policy-non-muscle-invasive-bladder-cancer.pdf` table 1
- **Top result:** `geha-coverage-policy-non-muscle-invasive-bladder-cancer.pdf` table 1 (Drug preference and prior authorization; similarity 0.7500)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Nadofaragene firadenovec-vncg (Adstiladrin), Pembrolizumab (Keytruda), Pembrolizumab and berahyaluronidas e alfa-pmph (Keytruda QLEX)
- **Products from top result:** Nadofaragene firadenovec-vncg (Adstiladrin), Pembrolizumab (Keytruda), Pembrolizumab and berahyaluronidas e alfa-pmph (Keytruda QLEX)
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-non-muscle-invasive-bladder-cancer.pdf` table 1 (Drug preference and prior authorization) — 0.7500 ← expected table
  2. `geha-coverage-policy-non-muscle-invasive-bladder-cancer.pdf` table 2 (Billing codes) — 0.7229
  3. `geha-coverage-policy-non-muscle-invasive-bladder-cancer.pdf` table 3 (Revision history) — 0.7130
  4. `geha-coverage-policy-gnrh-analogues-in-prostate-cancer.pdf` table 1 (Drug preference and prior authorization) — 0.6730
  5. `geha-coverage-policy-vectibix.pdf` table 1 (0 / 1 / 2 / 3 / 4) — 0.6663

### 16. `non_muscle_invasive_bladder_cancer_non_preferred`

- **Query:** Which non muscle invasive bladder cancer products are non-preferred?
- **Expected source:** `geha-coverage-policy-non-muscle-invasive-bladder-cancer.pdf`
- **Expected table:** `geha-coverage-policy-non-muscle-invasive-bladder-cancer.pdf` table 1
- **Top result:** `geha-coverage-policy-non-muscle-invasive-bladder-cancer.pdf` table 1 (Drug preference and prior authorization; similarity 0.7554)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Nogapendekin alfa inbakicept- pmln (Anktiva), Gemcitabine (Inlexzo)
- **Products from top result:** Nogapendekin alfa inbakicept- pmln (Anktiva), Gemcitabine (Inlexzo)
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-non-muscle-invasive-bladder-cancer.pdf` table 1 (Drug preference and prior authorization) — 0.7554 ← expected table
  2. `geha-coverage-policy-non-muscle-invasive-bladder-cancer.pdf` table 2 (Billing codes) — 0.7177
  3. `geha-coverage-policy-non-muscle-invasive-bladder-cancer.pdf` table 3 (Revision history) — 0.7023
  4. `geha-coverage-policy-vectibix.pdf` table 1 (0 / 1 / 2 / 3 / 4) — 0.6959
  5. `geha-coverage-policy-gnrh-analogues-in-prostate-cancer.pdf` table 1 (Drug preference and prior authorization) — 0.6791

### 17. `paclitaxel_protein_bound_preferred`

- **Query:** Which paclitaxel protein bound products are preferred?
- **Expected source:** `geha-coverage-policy-paclitaxel-protein-bound.pdf`
- **Expected table:** `geha-coverage-policy-paclitaxel-protein-bound.pdf` table 1
- **Top result:** `geha-coverage-policy-paclitaxel-protein-bound.pdf` table 1 (Drug preference and prior authorization; similarity 0.8289)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Docetaxel (Taxotere), Docetaxel (Hospira 505(b)(2)), Paclitaxel (Taxol)
- **Products from top result:** Docetaxel (Taxotere), Docetaxel (Hospira 505(b)(2)), Paclitaxel (Taxol)
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-paclitaxel-protein-bound.pdf` table 1 (Drug preference and prior authorization) — 0.8289 ← expected table
  2. `geha-coverage-policy-paclitaxel-protein-bound.pdf` table 3 (Revision history) — 0.8049
  3. `geha-coverage-policy-paclitaxel-protein-bound.pdf` table 2 (Billing codes) — 0.7862

### 18. `paclitaxel_protein_bound_non_preferred`

- **Query:** Which paclitaxel protein bound products are non-preferred?
- **Expected source:** `geha-coverage-policy-paclitaxel-protein-bound.pdf`
- **Expected table:** `geha-coverage-policy-paclitaxel-protein-bound.pdf` table 1
- **Top result:** `geha-coverage-policy-paclitaxel-protein-bound.pdf` table 1 (Drug preference and prior authorization; similarity 0.8325)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Paclitaxel Protein- Bound (Abraxane)
- **Products from top result:** Paclitaxel Protein- Bound (Abraxane)
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-paclitaxel-protein-bound.pdf` table 1 (Drug preference and prior authorization) — 0.8325 ← expected table
  2. `geha-coverage-policy-paclitaxel-protein-bound.pdf` table 3 (Revision history) — 0.8151
  3. `geha-coverage-policy-paclitaxel-protein-bound.pdf` table 2 (Billing codes) — 0.7793

### 19. `pemetrexed_preferred`

- **Query:** Which pemetrexed products are preferred?
- **Expected source:** `geha-coverage-policy-pemetrexed.pdf`
- **Expected table:** `geha-coverage-policy-pemetrexed.pdf` table 1
- **Top result:** `geha-coverage-policy-pemetrexed.pdf` table 1 (Drug preference and prior authorization; similarity 0.7553)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Pemetrexed (Axtle), Pemetrexed (Accord), Pemetrexed (Bluepoint)
- **Products from top result:** Pemetrexed (Axtle), Pemetrexed (Accord), Pemetrexed (Bluepoint)
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-pemetrexed.pdf` table 1 (Drug preference and prior authorization) — 0.7553 ← expected table
  2. `geha-coverage-policy-erythropoietin-stimulating-agents.pdf` table 1 (Drug preference and prior authorization) — 0.7277
  3. `geha-coverage-policy-pemetrexed.pdf` table 3 (Billing codes) — 0.7107
  4. `geha-coverage-policy-pemetrexed.pdf` table 4 (Revision history) — 0.7049
  5. `geha-coverage-policy-rytelo.pdf` table 1 (0 / 1 / 2 / 3 / 4) — 0.6992

### 20. `pemetrexed_non_preferred`

- **Query:** Which pemetrexed products are non-preferred?
- **Expected source:** `geha-coverage-policy-pemetrexed.pdf`
- **Expected table:** `geha-coverage-policy-pemetrexed.pdf` table 1
- **Top result:** `geha-coverage-policy-pemetrexed.pdf` table 1 (Drug preference and prior authorization; similarity 0.7641)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Pemetrexed (Hospira), Pemetrexed (Sandoz), Pemetrexed (Alimta ), Pemetrexed (Teva), Pemetrexed ditromethamine (Hospira), Pemfexy, Pemrydi RTU
- **Products from top result:** Pemetrexed (Hospira), Pemetrexed (Sandoz), Pemetrexed (Alimta ), Pemetrexed (Teva), Pemetrexed ditromethamine (Hospira), Pemfexy, Pemrydi RTU
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-pemetrexed.pdf` table 1 (Drug preference and prior authorization) — 0.7641 ← expected table
  2. `geha-coverage-policy-pemetrexed.pdf` table 3 (Billing codes) — 0.7126
  3. `geha-coverage-policy-erythropoietin-stimulating-agents.pdf` table 1 (Drug preference and prior authorization) — 0.7109
  4. `geha-coverage-policy-pemetrexed.pdf` table 4 (Revision history) — 0.7008
  5. `geha-coverage-policy-vectibix.pdf` table 1 (0 / 1 / 2 / 3 / 4) — 0.6991

### 21. `rituximab_preferred`

- **Query:** Which rituximab products are preferred?
- **Expected source:** `geha-coverage-policy-rituximab.pdf`
- **Expected table:** `geha-coverage-policy-rituximab.pdf` table 1
- **Top result:** `geha-coverage-policy-rituximab.pdf` table 1 (Preference / Requires Prior Drug / Name / HCPCS Code / Description; similarity 0.7848)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Ruxience
- **Products from top result:** Ruxience
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-rituximab.pdf` table 1 (Preference / Requires Prior Drug / Name / HCPCS Code / Description) — 0.7848 ← expected table
  2. `geha-coverage-policy-vectibix.pdf` table 1 (0 / 1 / 2 / 3 / 4) — 0.7783
  3. `geha-coverage-policy-xgeva.pdf` table 1 (Drug preference and prior authorization) — 0.7238
  4. `geha-coverage-policy-rituximab.pdf` table 2 (Billing codes) — 0.7236
  5. `geha-coverage-policy-trastuzumab.pdf` table 1 (Drug preference and prior authorization) — 0.7216

### 22. `rituximab_non_preferred`

- **Query:** Which rituximab products are non-preferred?
- **Expected source:** `geha-coverage-policy-rituximab.pdf`
- **Expected table:** `geha-coverage-policy-rituximab.pdf` table 1
- **Top result:** `geha-coverage-policy-rituximab.pdf` table 1 (Preference / Requires Prior Drug / Name / HCPCS Code / Description; similarity 0.7935)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Truxima, Rituxan Hycela, Rituxan, Riabni
- **Products from top result:** Truxima, Rituxan Hycela, Rituxan, Riabni
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-rituximab.pdf` table 1 (Preference / Requires Prior Drug / Name / HCPCS Code / Description) — 0.7935 ← expected table
  2. `geha-coverage-policy-vectibix.pdf` table 1 (0 / 1 / 2 / 3 / 4) — 0.7830
  3. `geha-coverage-policy-trastuzumab.pdf` table 1 (Drug preference and prior authorization) — 0.7386
  4. `geha-coverage-policy-xgeva.pdf` table 1 (Drug preference and prior authorization) — 0.7355
  5. `geha-coverage-policy-bevacizumab.pdf` table 1 (Drug preference and prior authorization) — 0.7190

### 23. `rytelo_preferred`

- **Query:** Which rytelo products are preferred?
- **Expected source:** `geha-coverage-policy-rytelo.pdf`
- **Expected table:** `geha-coverage-policy-rytelo.pdf` table 1
- **Top result:** `geha-coverage-policy-rytelo.pdf` table 1 (0 / 1 / 2 / 3 / 4; similarity 0.6805)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Reblozyl (luspatercept)
- **Products from top result:** Reblozyl (luspatercept)
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-rytelo.pdf` table 1 (0 / 1 / 2 / 3 / 4) — 0.6805 ← expected table
  2. `geha-coverage-policy-rytelo.pdf` table 2 (Billing codes) — 0.6532
  3. `geha-coverage-policy-long-acting-gcsfs.pdf` table 1 (Drug preference and prior authorization) — 0.5898
  4. `geha-coverage-policy-rytelo.pdf` table 3 (Revision history) — 0.5877
  5. `geha-coverage-policy-trastuzumab.pdf` table 1 (Drug preference and prior authorization) — 0.5823

### 24. `rytelo_non_preferred`

- **Query:** Which rytelo products are non-preferred?
- **Expected source:** `geha-coverage-policy-rytelo.pdf`
- **Expected table:** `geha-coverage-policy-rytelo.pdf` table 1
- **Top result:** `geha-coverage-policy-rytelo.pdf` table 1 (0 / 1 / 2 / 3 / 4; similarity 0.7191)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Rytelo (imetelstat)
- **Products from top result:** Rytelo (imetelstat)
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-rytelo.pdf` table 1 (0 / 1 / 2 / 3 / 4) — 0.7191 ← expected table
  2. `geha-coverage-policy-rytelo.pdf` table 2 (Billing codes) — 0.6361
  3. `geha-coverage-policy-vectibix.pdf` table 1 (0 / 1 / 2 / 3 / 4) — 0.6202
  4. `geha-coverage-policy-long-acting-gcsfs.pdf` table 1 (Drug preference and prior authorization) — 0.6040
  5. `geha-coverage-policy-rituximab.pdf` table 1 (Preference / Requires Prior Drug / Name / HCPCS Code / Description) — 0.5962

### 25. `short_acting_gcsfs_preferred`

- **Query:** Which short acting gcsfs products are preferred?
- **Expected source:** `geha-coverage-policy-short-acting-gcsfs.pdf`
- **Expected table:** `geha-coverage-policy-short-acting-gcsfs.pdf` table 1
- **Top result:** `geha-coverage-policy-long-acting-gcsfs.pdf` table 3 (0 / 1 / 2; similarity 0.6987)
- **Expected-source rank:** 3 — **FAIL at top 1**
- **Expected-table rank:** not in top 5 — **FAIL at top 1**
- **Expected products:** Nivestym (filgrastim- aafi)
- **Products from top result:** _(none)_
- **Product comparison:** **FAIL**; recall 0.0%, precision 0.0%
- **Top-five search results:**

  1. `geha-coverage-policy-long-acting-gcsfs.pdf` table 3 (0 / 1 / 2) — 0.6987
  2. `geha-coverage-policy-long-acting-gcsfs.pdf` table 4 (Revision history) — 0.6749
  3. `geha-coverage-policy-short-acting-gcsfs.pdf` table 2 (Billing codes) — 0.6362
  4. `geha-coverage-policy-short-acting-gcsfs.pdf` table 3 (Revision history) — 0.6357
  5. `geha-coverage-policy-long-acting-gcsfs.pdf` table 1 (Drug preference and prior authorization) — 0.6352

### 26. `short_acting_gcsfs_non_preferred`

- **Query:** Which short acting gcsfs products are non-preferred?
- **Expected source:** `geha-coverage-policy-short-acting-gcsfs.pdf`
- **Expected table:** `geha-coverage-policy-short-acting-gcsfs.pdf` table 1
- **Top result:** `geha-coverage-policy-long-acting-gcsfs.pdf` table 3 (0 / 1 / 2; similarity 0.6889)
- **Expected-source rank:** 4 — **FAIL at top 1**
- **Expected-table rank:** 4 — **FAIL at top 1**
- **Expected products:** Zarxio (filgrastim-sndz), Neupogen (filgrastim), Granix (tbo-filgrastim), Nypozi (filgrastim-txid)
- **Products from top result:** _(none)_
- **Product comparison:** **FAIL**; recall 0.0%, precision 0.0%
- **Top-five search results:**

  1. `geha-coverage-policy-long-acting-gcsfs.pdf` table 3 (0 / 1 / 2) — 0.6889
  2. `geha-coverage-policy-long-acting-gcsfs.pdf` table 1 (Drug preference and prior authorization) — 0.6606
  3. `geha-coverage-policy-long-acting-gcsfs.pdf` table 4 (Revision history) — 0.6593
  4. `geha-coverage-policy-short-acting-gcsfs.pdf` table 1 (Drug preference and prior authorization) — 0.6592 ← expected table
  5. `geha-coverage-policy-short-acting-gcsfs.pdf` table 2 (Billing codes) — 0.6519

### 27. `taxotere_docivyx_preferred`

- **Query:** Which taxotere docivyx products are preferred?
- **Expected source:** `geha-coverage-policy-taxotere-docivyx.pdf`
- **Expected table:** `geha-coverage-policy-taxotere-docivyx.pdf` table 1
- **Top result:** `geha-coverage-policy-taxotere-docivyx.pdf` table 1 (Drug preference and prior authorization; similarity 0.7574)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Taxotere (docetaxel), Docetaxel (Hospira 505(b)(2))
- **Products from top result:** Taxotere (docetaxel), Docetaxel (Hospira 505(b)(2))
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-taxotere-docivyx.pdf` table 1 (Drug preference and prior authorization) — 0.7574 ← expected table
  2. `geha-coverage-policy-taxotere-docivyx.pdf` table 2 (Drug Name / HCPC S Code / Description) — 0.7331
  3. `geha-coverage-policy-paclitaxel-protein-bound.pdf` table 1 (Drug preference and prior authorization) — 0.7134
  4. `geha-coverage-policy-paclitaxel-protein-bound.pdf` table 3 (Revision history) — 0.7016
  5. `geha-coverage-policy-paclitaxel-protein-bound.pdf` table 2 (Billing codes) — 0.6988

### 28. `taxotere_docivyx_non_preferred`

- **Query:** Which taxotere docivyx products are non-preferred?
- **Expected source:** `geha-coverage-policy-taxotere-docivyx.pdf`
- **Expected table:** `geha-coverage-policy-taxotere-docivyx.pdf` table 1
- **Top result:** `geha-coverage-policy-taxotere-docivyx.pdf` table 1 (Drug preference and prior authorization; similarity 0.7378)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Docetaxel (Docivyx)
- **Products from top result:** Docetaxel (Docivyx)
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-taxotere-docivyx.pdf` table 1 (Drug preference and prior authorization) — 0.7378 ← expected table
  2. `geha-coverage-policy-paclitaxel-protein-bound.pdf` table 3 (Revision history) — 0.7215
  3. `geha-coverage-policy-taxotere-docivyx.pdf` table 2 (Drug Name / HCPC S Code / Description) — 0.7044
  4. `geha-coverage-policy-paclitaxel-protein-bound.pdf` table 1 (Drug preference and prior authorization) — 0.6990
  5. `geha-coverage-policy-paclitaxel-protein-bound.pdf` table 2 (Billing codes) — 0.6763

### 29. `trastuzumab_preferred`

- **Query:** Which trastuzumab products are preferred?
- **Expected source:** `geha-coverage-policy-trastuzumab.pdf`
- **Expected table:** `geha-coverage-policy-trastuzumab.pdf` table 1
- **Top result:** `geha-coverage-policy-trastuzumab.pdf` table 1 (Drug preference and prior authorization; similarity 0.8029)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Trazimera, Kanjinti
- **Products from top result:** Trazimera, Kanjinti
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-trastuzumab.pdf` table 1 (Drug preference and prior authorization) — 0.8029 ← expected table
  2. `geha-coverage-policy-trastuzumab.pdf` table 2 (Billing codes) — 0.7545
  3. `geha-coverage-policy-trastuzumab.pdf` table 3 (Revision history) — 0.7444
  4. `geha-coverage-policy-rituximab.pdf` table 1 (Preference / Requires Prior Drug / Name / HCPCS Code / Description) — 0.7289

### 30. `trastuzumab_non_preferred`

- **Query:** Which trastuzumab products are non-preferred?
- **Expected source:** `geha-coverage-policy-trastuzumab.pdf`
- **Expected table:** `geha-coverage-policy-trastuzumab.pdf` table 1
- **Top result:** `geha-coverage-policy-trastuzumab.pdf` table 1 (Drug preference and prior authorization; similarity 0.7997)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Herceptin, Herceptin Hylecta, Hercessi, Ontruzant, Herzuma, Ogivri
- **Products from top result:** Herceptin, Herceptin Hylecta, Hercessi, Ontruzant, Herzuma, Ogivri
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-trastuzumab.pdf` table 1 (Drug preference and prior authorization) — 0.7997 ← expected table
  2. `geha-coverage-policy-vectibix.pdf` table 1 (0 / 1 / 2 / 3 / 4) — 0.7520
  3. `geha-coverage-policy-trastuzumab.pdf` table 2 (Billing codes) — 0.7487
  4. `geha-coverage-policy-rituximab.pdf` table 1 (Preference / Requires Prior Drug / Name / HCPCS Code / Description) — 0.7432
  5. `geha-coverage-policy-xgeva.pdf` table 1 (Drug preference and prior authorization) — 0.7380

### 31. `vectibix_preferred`

- **Query:** Which vectibix products are preferred?
- **Expected source:** `geha-coverage-policy-vectibix.pdf`
- **Expected table:** `geha-coverage-policy-vectibix.pdf` table 1
- **Top result:** `geha-coverage-policy-vectibix.pdf` table 1 (0 / 1 / 2 / 3 / 4; similarity 0.7829)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Cetuximab (Erbitux)
- **Products from top result:** Cetuximab (Erbitux)
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-vectibix.pdf` table 1 (0 / 1 / 2 / 3 / 4) — 0.7829 ← expected table
  2. `geha-coverage-policy-vectibix.pdf` table 2 (Billing codes) — 0.7140
  3. `geha-coverage-policy-bevacizumab.pdf` table 1 (Drug preference and prior authorization) — 0.6709
  4. `geha-coverage-policy-rytelo.pdf` table 1 (0 / 1 / 2 / 3 / 4) — 0.6664
  5. `geha-coverage-policy-erythropoietin-stimulating-agents.pdf` table 1 (Drug preference and prior authorization) — 0.6629

### 32. `vectibix_non_preferred`

- **Query:** Which vectibix products are non-preferred?
- **Expected source:** `geha-coverage-policy-vectibix.pdf`
- **Expected table:** `geha-coverage-policy-vectibix.pdf` table 1
- **Top result:** `geha-coverage-policy-vectibix.pdf` table 1 (0 / 1 / 2 / 3 / 4; similarity 0.7937)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Panitumumab (Vectibix)
- **Products from top result:** Panitumumab (Vectibix)
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-vectibix.pdf` table 1 (0 / 1 / 2 / 3 / 4) — 0.7937 ← expected table
  2. `geha-coverage-policy-vectibix.pdf` table 2 (Billing codes) — 0.6966
  3. `geha-coverage-policy-bevacizumab.pdf` table 1 (Drug preference and prior authorization) — 0.6768
  4. `geha-coverage-policy-long-acting-gcsfs.pdf` table 1 (Drug preference and prior authorization) — 0.6747
  5. `geha-coverage-policy-rituximab.pdf` table 1 (Preference / Requires Prior Drug / Name / HCPCS Code / Description) — 0.6690

### 33. `xgeva_preferred`

- **Query:** Which xgeva products are preferred?
- **Expected source:** `geha-coverage-policy-xgeva.pdf`
- **Expected table:** `geha-coverage-policy-xgeva.pdf` table 1
- **Top result:** `geha-coverage-policy-xgeva.pdf` table 1 (Drug preference and prior authorization; similarity 0.6950)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Zoledronic Acid (Zometa)
- **Products from top result:** Zoledronic Acid (Zometa)
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-xgeva.pdf` table 1 (Drug preference and prior authorization) — 0.6950 ← expected table
  2. `geha-coverage-policy-xgeva.pdf` table 3 (Revision history) — 0.6677
  3. `geha-coverage-policy-xgeva.pdf` table 2 (Billing codes) — 0.6568

### 34. `xgeva_non_preferred`

- **Query:** Which xgeva products are non-preferred?
- **Expected source:** `geha-coverage-policy-xgeva.pdf`
- **Expected table:** `geha-coverage-policy-xgeva.pdf` table 1
- **Top result:** `geha-coverage-policy-xgeva.pdf` table 1 (Drug preference and prior authorization; similarity 0.7117)
- **Expected-source rank:** 1 — **PASS at top 1**
- **Expected-table rank:** 1 — **PASS at top 1**
- **Expected products:** Denosumab (Xgeva), Denosumab-desu (Jubereq), Denosumab-qbde (Xtrenbo), Denosumab-bbdz (Wyost), Denosumab-bmwo (Osenvelt), Denosumab-bmwo (Denosumab-Celtrion), Denosumab-bnht (Bomyntra), Denosumab-bnht (denosumab Frensenius), Denosumab-dssb (Xbryk), Denosumab-dssb (Denosumab Samsung Bioepis), Denosumab-kyqq (Aukelso), Denosumab-nxxp (Bilprevda)
- **Products from top result:** Denosumab (Xgeva), Denosumab-desu (Jubereq), Denosumab-qbde (Xtrenbo), Denosumab-bbdz (Wyost), Denosumab-bmwo (Osenvelt), Denosumab-bmwo (Denosumab-Celtrion), Denosumab-bnht (Bomyntra), Denosumab-bnht (denosumab Frensenius), Denosumab-dssb (Xbryk), Denosumab-dssb (Denosumab Samsung Bioepis), Denosumab-kyqq (Aukelso), Denosumab-nxxp (Bilprevda)
- **Product comparison:** **PASS**; recall 100.0%, precision 100.0%
- **Top-five search results:**

  1. `geha-coverage-policy-xgeva.pdf` table 1 (Drug preference and prior authorization) — 0.7117 ← expected table
  2. `geha-coverage-policy-vectibix.pdf` table 1 (0 / 1 / 2 / 3 / 4) — 0.6646
  3. `geha-coverage-policy-xgeva.pdf` table 2 (Billing codes) — 0.6581
  4. `geha-coverage-policy-xgeva.pdf` table 3 (Revision history) — 0.6516
  5. `geha-coverage-policy-rytelo.pdf` table 1 (0 / 1 / 2 / 3 / 4) — 0.6482

