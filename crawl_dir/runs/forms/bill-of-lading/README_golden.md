# Bill-of-lading golden runs

These two complete saved runs use the same synthetic source PDF (SHA-256
`bb69da6f9072e0c2c16a675bc38e535adff1cbdc2c33c2042eb2d1d7021f16ef`).
They preserve page images, named-cell crops, OCR snapshots, correction iterations,
rendered HTML, Markdown, and QC records for comparing workflow changes.

- `agent-demo-20261016T032408Z-da8bdb_golden/` is the earlier reference run.
- `agent-demo-20261118T201304Z-c816f0_latestgolden/` is the newer Opus OCR run. Its
  `candidate/bill_of_lading_fields.json` contains two cargo rows, and
  `candidate/bill_of_lading_verification.json` records the structural checks.

Both QC reports retain `needs_visual_review`; these artifacts are saved baselines,
not an automatic promotion or an independently established ground truth.
