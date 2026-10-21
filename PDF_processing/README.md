# PDF Processing Experiments

Experiments for extracting dense forms by splitting a page into meaningful regions, applying literal OCR, validating typed fields, and reconstructing inspectable HTML.

The current reusable component is the versioned Bill of Lading schema in `bill_lading/bill_of_lading_html_graph.py`. The main `document_ingestion_workflow` imports that schema to segment the recognized form into eight blocks and named cells.

> **Scope:** this directory contains research code and saved benchmark artifacts. It is not a general-purpose PDF parser, a production document service, or a HIPAA-ready workflow.

## Why the page is segmented

Dense forms are difficult to process as one image. Small labels, values, column boundaries, and repeated table cells compete for the vision model's attention. The experiments use a narrower pipeline:

```text
PDF page
   |
   v
rendered page image
   |
   v
versioned block and cell geometry
   |
   +--> literal OCR of each named cell
   |
   +--> schema-aware field parsing and validation
   |
   +--> deterministic HTML reconstruction
   |
   +--> bounded visual/data review
   |
   v
validated fields + HTML + audit artifacts
```

Segmentation improves visibility, but it is not sufficient by itself. The schema and validation rules are what turn OCR text into usable document fields.

## Directory map

| Path | Status | Purpose |
|---|---|---|
| `bill_lading/` | Active specialist component | Bill of Lading geometry, OCR experiments, typed parsing, validation, reconstruction, tests, and saved results |
| `blocking_demo/` | Explanatory prototype | Shows why a dense page is divided into blocks before OCR |
| `logs/` | Saved artifacts | Historical workflow requests, results, reports, and process logs |

The directory name `bill_lading` is retained for compatibility even though “bill of lading” is the correct spelling.

## Current integration

`document_ingestion_workflow/bill_of_lading_workflow.py` loads `schema_manifest()` from:

```text
PDF_processing/bill_lading/bill_of_lading_html_graph.py
```

For the curated synthetic Bill of Lading, the integrated workflow:

1. recognizes the supported template;
2. scales its versioned 2136 × 3584 geometry to the rendered page;
3. creates eight block crops and individual named-cell crops;
4. performs literal OCR over those crops;
5. assembles semantic HTML deterministically;
6. reviews missing, incorrect, duplicated, extra, or reordered text; and
7. retries only the implicated cells, within a fixed iteration limit.

The integration deliberately does not treat CSS differences—fonts, spacing, borders, colors, wrapping, or logos—as OCR failures. Its acceptance boundary is structured text fidelity.

For the full application, source-document catalog, run format, and web interface, see [`../document_ingestion_workflow/README.md`](../document_ingestion_workflow/README.md).

## Bill of Lading components

### Versioned reconstruction schema

`bill_lading_html_graph.py` defines block geometry, named-cell geometry, reading order, deterministic HTML construction, exact cell-text checks, and bounded data/visual review routes.

It can reconstruct HTML directly from a compatible OCR-results JSON file:

```bash
cd /Users/dc/geha/PDF_processing/bill_lading
source ../../.venv/bin/activate

python bill_of_lading_html_graph.py \
  --ocr-results /absolute/path/to/gpt4o_only_results.json \
  --output-root /absolute/path/to/output \
  --no-vision
```

Remove `--no-vision` to enable model-based data and visual checks:

```bash
export OPENAI_API_KEY=...

python bill_of_lading_html_graph.py \
  --ocr-results /absolute/path/to/gpt4o_only_results.json \
  --output-root /absolute/path/to/output \
  --model gpt-4o
```

The review limits default to five data passes and ten visual passes. Override them with `--max-data-iterations` and `--max-visual-iterations`.

### Typed field parser

OCR returns strings. `bol_parser.py` converts compatible per-block text into typed, validated fields using:

- `bill_of_lading_spec.json` — template structure, labels, patterns, field types, required fields, groups, and cross-field rules;
- `bill_of_lading_gold_fields.json` — answer key used only for evaluation; and
- `bill_of_lading_ground_truth.json` — expected strings for the eight-block OCR benchmark.

The parser splits labels from values, validates strict patterns, groups cargo columns by reading order, checks column counts, and applies document-level rules such as package-total and issue-date validation. ISO 6346 checking is reported as a warning because the sample uses synthetic container identifiers.

Parse a directory containing `block_1.txt` through `block_8.txt`:

```bash
cd /Users/dc/geha/PDF_processing/bill_lading
source ../../.venv/bin/activate

python bol_parser.py parse \
  --text-dir /absolute/path/to/block-text \
  --out /absolute/path/to/parsed.json
```

For Claude-style cell output, use `--claude-dir` instead of `--text-dir`.

`bol_parser.py evaluate` automatically evaluates compatible saved engine directories when those raw artifacts are present. Some benchmark summaries remain checked in without all original intermediate OCR directories, so an empty evaluation table means no compatible local engine artifacts were discovered—not that parsing succeeded.

### Eight-block OpenAI OCR

`gpt4o_only_8block_ocr.py` crops a rendered page into the predefined blocks and cells, calls the OpenAI Responses API with strict JSON output, and writes:

- block and cell images;
- one JSON transcription per block;
- normalized expected-string recall;
- a Markdown report; and
- an HTML inspection page.

```bash
cd /Users/dc/geha/PDF_processing/bill_lading
source ../../.venv/bin/activate
export OPENAI_API_KEY=...

python gpt4o_only_8block_ocr.py \
  --page-png /absolute/path/to/rendered-page.png \
  --output-root /absolute/path/to/output \
  --model gpt-4o
```

The input must be a page PNG matching the supported template. This script does not render the source PDF itself.

### OpenAI versus PaddleOCR-VL benchmark

`langgraph_paddle_vs_chat5.py` sends the same eight saved block images to an OpenAI model and a Fireworks-hosted PaddleOCR-VL deployment, then produces normalized recall and latency reports.

The script contains historical absolute defaults, so provide explicit paths:

```bash
cd /Users/dc/geha/PDF_processing/bill_lading
source ../../.venv/bin/activate
export OPENAI_API_KEY=...
export FIREWORKS_API_KEY=...

python langgraph_paddle_vs_chat5.py \
  --block-dir /absolute/path/to/eight-block-images \
  --gold bill_of_lading_ground_truth.json \
  --output-root /absolute/path/to/output \
  --openai-model gpt-5 \
  --fireworks-deployment accounts/.../deployments/...
```

This is a live, billable comparison. The deployment identifier must belong to the caller's Fireworks account.

## Understanding the saved benchmark

The detailed historical report is in [`bill_lading/README.md`](bill_lading/README.md). It reports two different measurements that should not be conflated:

| Measurement | What counts as correct | What it misses |
|---|---|---|
| Normalized expected-string recall | An expected string appears somewhere in the block after normalization | Field boundaries, neighboring text joined together, layout fidelity |
| Field-level accuracy | The exact value appears as its own field with punctuation and signs preserved | Broader visual similarity outside the typed field contract |

On the single saved 79-string page, normalized recall reached 79/79 for multiple engines. That result does **not** mean all engines produced equally usable fields. The saved report shows PaddleOCR-VL joining labels and values in several table-style regions, reducing its stricter field score.

Treat these numbers as a reproducible case study, not a general OCR leaderboard: they represent one synthetic page and one run per engine.

## Tests

Run the offline unit suite from the specialist directory:

```bash
cd /Users/dc/geha/PDF_processing/bill_lading
source ../../.venv/bin/activate
PYTHONPATH=. python -m unittest discover -p 'test_*.py' -v
```

The tests cover:

- schema block and cell reading order;
- HTML escaping and exact named-cell preservation;
- review routing and retry behavior;
- label/value splitting;
- pattern and type validation;
- cargo-group alignment and cross-field rules; and
- parsing of compatible saved OCR artifacts.

The unit tests mock model responses and do not make remote API calls.

## Secrets and generated artifacts

- `bill_lading/.env` is ignored by Git. Never add provider credentials to source files or saved reports.
- Model-backed scripts send image crops to the configured external provider and may incur cost.
- Write new runs to a fresh output directory rather than modifying checked-in benchmark artifacts.
- Keep source pixels, model output, normalized scores, and validated fields separate so each stage remains auditable.

## Limitations

- The geometry is template-specific and should not be applied to an unrelated form.
- The source sample is synthetic and does not establish accuracy on medical, insurance, or production shipping documents.
- Free-text fields remain harder to validate than identifiers, dates, counts, and constrained codes.
- A clean visual rendering cannot compensate for incorrect data; exact cell and field checks remain the hard gates.
- New layouts require a new versioned schema and new held-out evaluation documents.
