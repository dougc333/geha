# GEHA catalog classification review

This is a review taxonomy for the 141 assets in the live catalog snapshot. It is intentionally separate from the future S3 object-key schema.

Source:

- Root page: https://www.geha.com/en/resource-center/forms-and-documents
- Snapshot: `/Users/dc/geha/collections/inventory-snapshot.json`
- Snapshot time: 2026-11-06

Generated files:

- `geha-document-classification.csv` — easiest to sort/filter in Numbers or Excel.
- `geha-document-classification.json` — complete structured rows plus summary.
- `geha-document-classification-summary.json` — counts only.

## Current counts

| Document type | Count |
|---|---:|
| Coverage policy | 38 |
| Member form (UMF/general) | 41 |
| Medical plan brochure | 16 |
| Medical Summary of Benefits (SBC) | 15 |
| Medical benefits guide | 8 |
| Dental plan brochure | 4 |
| Dental form | 5 |
| Dental benefits guide | 2 |
| Claims form | 4 |
| Prescription form | 2 |
| Appeals or notice | 2 |
| Member resource | 2 |
| Vision plan brochure | 1 |
| Enrollment form | 1 |
| **Total** | **141** |

## Year buckets

- 2025: 7 explicit plan-year documents
- 2026: 19 explicit plan-year documents
- 2027: 18 explicit plan-year documents
- Not applicable or not explicit in catalog metadata: 97

Coverage policies are not assigned a plan year from the catalog. Two have an explicit `2026-12-31` URL suffix; the other 36 need revision/effective-date extraction from the PDF itself.

Spanish forms remain in the inventory: 18 assets are marked `language=Spanish`.

`review_flags` identify rows that still need human/PDF review. In particular, `extract_revision_from_pdf` means the catalog URL does not reliably carry the policy revision, so the PDF's title block/effective date/revision date should be extracted before designing revision keys.
