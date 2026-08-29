# GEHA Garbled-Claim OCR → Vector → MySQL Pipeline

End-to-end pipeline that turns **real synthetic claim text** into **garbled form
images**, runs **OCR**, resolves the noisy text via a **vector database**, loads
the resolved values into **MySQL**, and flags **missing data** with SQL.

```
real text ──▶ CV garbling ──▶ image ──▶ OCR ──▶ .ocrtext ──▶ vector DB ──▶ MySQL ──▶ missing-data SQL
(claims)   (crop/blur/lines)   .png   (tesseract)          (faiss)   (claims_resolved)
```

## Pipeline stages

### 1. Generate garbled forms — `make_garbled_forms.py`
- Builds 10 synthetic CMS-1500 claim records (patient, member ID, diagnosis
  ICD-10, CPT, POS, DOS, charge, provider, NPI, facility, auth#). **Some fields
  are deliberately left blank** to simulate missing data.
- Renders each as a CMS-1500-style form with a **handwriting effect**
  (per-glyph jitter + Comic Sans/Chalkboard) so OCR misreads characters.
- Applies a **computer-vision garbling filter**: slight rotation/crop, gaussian
  blur, random lines/strokes, and speckle noise — tuned to be *challenging but
  recoverable*.
- Outputs `claim_forms_garbled/<claim_id>.png` + `ground_truth.json` (the true
  values + which fields were blanked, for evaluation).

### 2. OCR — `ocr_forms.py`
- Runs **tesseract** (psm 6) on each garbled PNG.
- Writes `<claim_id>.ocrtext` into `ocr_output/` (the requirement: store OCR
  text as `imagename.ocrtext`).

### 3. Vector DB to resolve garbled text — `build_vector_db.py`
- Builds a corpus of **canonical candidate values** per field (diagnosis codes,
  CPT codes, NPIs, provider/facility names, dates, amounts) from ground truth +
  a codebook.
- Embeds each candidate with a **position-invariant character n-gram hashing
  vectorizer** (robust to OCR misreads) and indexes it in **FAISS**.
- `resolve_all(ocr_text)` scans every token **and 2–3 word phrase**, runs FAISS
  nearest-neighbor search, and maps a garbled OCR token to the nearest canonical
  value **above a confidence threshold**. Low-confidence matches are dropped
  (→ NULL → flagged missing) rather than guessed wrong.
- Persists indexes to `vector_db/*.faiss` + `candidates.json`.

### 4. Load into MySQL — `load_mysql.py`
- Connects to the `geha_claims` MySQL 8 DB (Docker container `geha-mysql`).
- Creates table **`claims_resolved`** whose **schema matches the form fields**:
  `claim_id, source_image, patient_name, patient_dob, patient_sex, member_id,
  diagnosis, cpt, pos, dos, charge, auth_number, provider, npi, facility,
  ocr_text` (+ metadata columns).
- Inserts one row per form, using the vector-resolved values; unreadable fields
  become NULL.

### 5. Missing-data detection — `missing_data.sql`
- Computes a **comma-separated list of NULL/empty columns** per row via
  `CONCAT_WS`.
- Sets **`missing_data = 'Yes'`** when any required field is missing, `'No'`
  otherwise.
- Writes the missing column list into **`missing_fields`** (the CSV column
  list), then reports rows + a summary.

## Running the pipeline

```bash
# 1-3 (python; tesseract must be on PATH)
python make_garbled_forms.py
python ocr_forms.py
python build_vector_db.py --inspect

# 4-5 (MySQL 8 in Docker, port 3306)
docker run -d --name geha-mysql -e MYSQL_ROOT_PASSWORD=geha_root \
           -e MYSQL_DATABASE=geha_claims -p 3306:3306 mysql:8.0
python load_mysql.py
docker exec -i geha-mysql mysql -uroot -pgeha_root geha_claims < missing_data.sql
```

## Verification

`eval_fields.py` / `eval_resolver.py` compare resolved values against
`ground_truth.json`. Observed behavior on this seed:

- **0 wrong guesses** — unreadable fields are left NULL, never fabricated.
- **Recovered fields** (per-field accuracy): facility ~80%, NPI ~62%, dates
  ~56%, provider ~20%.
- **Unrecovered fields** are correctly routed to `missing_data=Yes` by SQL.
- Short codes (diagnosis/CPT/POS/charge) are heavily destroyed by the
  handwriting+noise garbling and largely land in missing-data — a realistic
  outcome that the missing-data detection is designed to catch.

## Files

| File | Purpose |
|------|---------|
| `make_garbled_forms.py` | real text → garbled form images |
| `claim_forms_garbled/` | 10 `.png` + `ground_truth.json` |
| `ocr_forms.py` | image → `<imagename>.ocrtext` |
| `ocr_output/` | the `.ocrtext` files |
| `build_vector_db.py` | vectorizer + FAISS index to resolve garbled text |
| `vector_db/` | `.faiss` indexes + `candidates.json` |
| `load_mysql.py` | load resolved values into MySQL `claims_resolved` |
| `missing_data.sql` | flag `missing_data=Yes/No` + `missing_fields` CSV list |
| `eval_fields.py`, `eval_resolver.py` | accuracy vs. ground truth |

## Notes & caveats

- **Dependencies:** `tesseract` (brew), Python `PIL`, `faiss-cpu`, `pymysql`;
  MySQL 8 via Docker. Runs in a Python 3.12 venv; **clear `PYTHONPATH`** when
  running (the Hermes agent venv leaks an incompatible py3.11 stack otherwise).
- All member, provider, and claim data is **fabricated**. Simulation for
  education/demo.
- The garbling severity is a dial: lowering it improves OCR recovery; raising it
  produces more "missing" fields. The current setting shows a realistic
  mix of recovered and missing.
