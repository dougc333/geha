# Block routing: decide when to use bounding boxes, one schema per block

Research code, offline by default. Nothing here calls a model or Jev unless you inject one.

## What it does
```
single pass --> quality score (no ground truth) --> decide: blocks or not --> [blocks: boxes --> per-block schema --> merge]
                                                       rules -> LLM -> Jev -> deterministic fallback
```
- **Accuracy-driven:** a single pass is tried first. `quality.py` scores it with deterministic checks (required fields,
  date validity, totals that must add up, line math, items summing to the pre-tax amount, email/BIC/currency formats;
  for the Bill of Lading, the spec's value patterns). Poor score -> blocks.
- **The decision chain** (`decide.py`; every stage is recorded in `Decision.trace`):
  1. **rules** (deterministic): first-pass quality >= 0.97 -> single pass; < 0.90 -> blocks; or, with no first pass, the number
     of expected fields (>= 30 blocks, <= 12 single). A versioned template geometry always means blocks.
  2. **LLM** (`make_llm_decider`, Anthropic, temperature 0): asked only when the rules are inconclusive; counts only with
     confidence >= 0.7.
  3. **Jev** (TypeSafe, `jev.py`): when the LLM cannot decide. A `Choice` over `blocks | single_pass | unsure`; the winner is
     taken from the probabilities (ties by name) if it is clear of the runner-up (margin >= 0.15) and not "unsure".
  4. **deterministic fallback**: used when Jev is unsure, unavailable or fails. With nothing known it uses blocks.
- **Bounding boxes** (`blocks.py`): Python finds candidate horizontal cuts (blank gaps, ruling lines); a prompt lets a model
  *choose* among them by id and name the blocks; the reply is validated (no unknown ids, no overlap); on any problem a
  deterministic split at the strongest cuts is used. The model never writes coordinates.
- **Per-block schemas** (`schemas.py`, files in `schemas/`): invoices -> `header`, `parties`, `line_items`, `totals`, `extras`
  (field names follow the ocr-mini-bench ground truth, so merged output can be scored with it); Bill of Lading -> its 8 blocks,
  generated from `bill_lading/bill_of_lading_spec.json`. All strict (`additionalProperties: false`).
- `pipeline.extract_document(...)` wires it together with injected `single_pass` and `block_extract` callables and keeps
  whichever of the two records scores higher.

## Run
```bash
cd /Users/dc/geha/PDF_processing/block_routing
/Users/dc/geha/.venv/bin/python -W error::ResourceWarning -m unittest discover -s tests   # 33 tests, no network
/Users/dc/geha/.venv/bin/python demo.py --overlay cuts.png                                 # 12 invoices, offline
/Users/dc/geha/.venv/bin/python -m block_router.schemas                                    # rewrite schemas/
```
`decide(features, jev=False)` never touches the Jev service. With `jev=None` (the default) it creates a real client when
`typesafe_sdk` and `TYPESAFE_API_KEY` are present, which is a real service call.

## What was measured (and what was not)
- **Validators on the benchmark's ground truth:** 12 invoices score 1.000 (0 false alarms). Two records first failed
  (a medical bill whose total is the balance after insurance; a table with discounted lines and `DD/MM/YYYY` dates); the checks
  were fixed to allow credits, net prices and dates as printed.
- **Detection of injected errors** (20 random seeds over the 12 invoices): wrong digit in total / pre-tax / tax / one line
  total 95%, wrong quantity 92%, missing invoice number, garbled date, dropped line item, broken email 100%.
- **Not detected: errors inside strings** (a wrong VAT digit, an address typo): 0%. A high quality score means the numbers and
  structure are consistent, not that every string is right.
- **Not run:** any real model extraction, the LLM stage, or a successful Jev call. The thresholds above are untuned defaults.
  Tuning them needs a labeled set: run single pass and blocks on documents with ground truth (ocr-mini-bench: 12 invoices, 13
  receipts, 17 logistics; the Bill of Lading gold fields), record which route scored higher, and tune on held-out templates.
  No training set is needed to use rules, an LLM or Jev; the labeled set is for evaluation and for setting thresholds.

## Known limits / next steps
- Horizontal bands only; vertical splits inside a band are not implemented (see ocr-mini-bench `blocking/`).
- For the Meridian Bill of Lading the versioned geometry in the spec should be used instead of proposed boxes.
- `block_extract` and `single_pass` are injected; wire them to the existing OCR code (`bill_lading/gpt4o_only_8block_ocr.py`)
  or any model.
