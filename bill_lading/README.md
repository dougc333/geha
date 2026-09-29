# Bill-of-lading OCR benchmark

## GPT-4o vs PaddleOCR-VL 1.6

Both OCR systems achieved complete recall on the eight-block, 79-field benchmark.
PaddleOCR-VL 1.6 completed the workload approximately **5.99× faster** than GPT-4o.

| Metric | GPT-4o | PaddleOCR-VL 1.6 |
|---|---:|---:|
| Matched benchmark fields | **79/79** | **79/79** |
| Field-recall accuracy | **100%** | **100%** |
| Perfect blocks | **8/8** | **8/8** |
| Successful API calls | 8/8 | 8/8 |
| Total latency | 14.908s | **2.491s** |
| Mean latency per block | 1.863s | **0.311s** |
| Relative speed | 1.00× | **5.99× faster** |

Each provider received the same complete block image once. GPT-4o used structured
cell-coverage output with a five-column layout hint for block 6. PaddleOCR used its
native `OCR:` or `Table Recognition:` task prompt. These results measure normalized
expected-field recall, not character-error rate or complete layout fidelity.

- [Detailed comparison](README_paddle_vs_gpt4o.md)
- [Machine-readable results](paddle_vs_gpt4o_run_20260927T192115Z/comparison_results.json)
- [LangGraph benchmark program](langgraph_paddle_vs_chat5.py)

## Field-level accuracy: Claude vs GPT-4o vs PaddleOCR-VL

All three engines score 79/79 on the recall metric above, which only checks that
each expected string appears somewhere in the block after removing case, spaces
and punctuation. Field-level accuracy is stricter: a field counts only if its
value appears **exactly** (case, punctuation, decimal points and signs kept) and
**as its own field**, not run together with the neighbouring text. Quote style
(`'` vs `"`) is treated as equal, because the ground truth has `'TO ORDER'` where
all three engines read `"TO ORDER"`.

| Block | Fields | Claude Opus 5.5 | GPT-4o | PaddleOCR-VL |
|---|---:|---:|---:|---:|
| 1. Header (carrier, B/L no.) | 7 | 7/7 (100%) | 7/7 (100%) | 7/7 (100%) |
| 2. Parties & references | 24 | 24/24 (100%) | 24/24 (100%) | **9/24 (38%)** |
| 3. Vessel & ports | 6 | 6/6 (100%) | 6/6 (100%) | **0/6 (0%)** |
| 4. Particulars notice | 1 | 1/1 (100%) | 1/1 (100%) | 1/1 (100%) |
| 5. Cargo headers | 5 | 5/5 (100%) | 5/5 (100%) | 5/5 (100%) |
| 6. Cargo table | 23 | 23/23 (100%) | 23/23 (100%) | 23/23 (100%) |
| 7. Charges & packages | 6 | 6/6 (100%) | 6/6 (100%) | 6/6 (100%) |
| 8. Issue & signature | 7 | 7/7 (100%) | 7/7 (100%) | **1/7 (14%)** |
| **Total** | **79** | **79/79 (100%)** | **79/79 (100%)** | **52/79 (65.8%)** |
| Latency, 8 blocks | | 35.2 s | 14.9 s | 2.5 s |

- **PaddleOCR-VL** reads every character correctly, but in `Table Recognition:`
  mode it joins a cell's lines without a space, so labels and values run together
  ("OCEAN VESSEL / VOYAGE**MERIDIAN** LABREA / 124N", "SHIPPER**FRUTAS** DEL SOL
  S.A.**Av.** de los Incas…") and can't be extracted as fields. This affects the
  label-over-value boxes in blocks 2, 3 and 8; blocks run in `OCR:` mode and the
  cargo table are unaffected. `OCR:` mode for those blocks, or parsing the table
  output with a break per line, may recover them (not tested).
- **Claude Opus 5.5 and GPT-4o** tie: no field errors on this page, and no
  decimal-point or sign errors from any engine; every value that occurs twice
  (one per container) is present twice. The remaining differences are layout:
  in block 6 GPT-4o used the value `MRDN4455667` as a heading and transcribed the
  printed underline; Claude returned five clean columns.
- One page, 79 fields, one run per engine: enough to show Paddle's field-boundary
  problem, too small to rank Claude against GPT-4o.

Sources: Claude from [`claude_run_20260929T220854Z`](claude_run_20260929T220854Z/README_claude.md)
([`claude_block_ocr.py`](claude_block_ocr.py): same eight block images and the same
instructions, cell counts and block-6 hint as GPT, Claude API, effort `medium`,
~$0.09); GPT-4o and PaddleOCR-VL from
[`paddle_vs_gpt4o_run_20260927T192115Z`](paddle_vs_gpt4o_run_20260927T192115Z/comparison_results.json).

# Reproduction notes

The full page was rendered at 144 DPI, producing a 2136×3584 PNG. Every block in `bill_of_lading_alt_1_ocr_iterations.json` is defined against that image using top-left `x, y, width, height` coordinates and half-open bounds.

Example ImageMagick reconstruction:

```sh
magick bill_of_lading_alt_1_page_1.png -crop WIDTHxHEIGHT+X+Y +repage recreated.png
```

The stored block PNG may be enlarged and contrast-normalized for OCR. The JSON coordinates always refer to the unmodified full-page PNG, so the source crop can be recreated without ambiguity.

## Schema-aware HTML reconstruction

`bill_of_lading_html_graph.py` uses the existing eight-block and named-cell
geometry as a versioned DOM schema. It first verifies literal cell data in
left-to-right, top-to-bottom order (maximum five passes), then renders and
visually verifies each HTML block (maximum ten passes). Every HTML version,
rendered PNG, issue, coordinate, and iteration count is retained in a fresh run
directory. Set `LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, and optionally
`LANGSMITH_PROJECT` to see the graph, model calls, and fidelity scores in
LangSmith.

Text fidelity is the hard gate. Visual review does not begin until every named
cell passes, and a visual repair is rejected if it changes, removes, duplicates,
or moves any verified cell text. Visual similarity is therefore an additional
review signal and can never compensate for incorrect extracted data.

During text review the command prints a start and completion line for every
schema cell. Each completed cell also becomes its own LangSmith child run with
the feedback keys `text_cell_match`, `text_cell_error`,
`text_cell_uncertain`, `text_cell_latency_seconds`, and
`text_cell_progress`. `text_cell_response_retries` counts empty or malformed
structured responses. Such responses are retried twice; if all three attempts
fail, the cell is recorded as uncertain and the graph finishes with
`needs_human_review` instead of crashing. Aggregate `data_error_count` and
`data_accuracy` feedback is still recorded after the full text-review iteration
finishes.

Build the HTML without making vision calls:

```sh
/Users/dc/geha/.venv/bin/python bill_of_lading_html_graph.py \
  --ocr-results gpt4o_only_run_20260927T183545Z/gpt4o_only_results.json \
  --no-vision
```

Run both correction stages with tracing:

```sh
export LANGSMITH_TRACING=true
export LANGSMITH_PROJECT=bill-of-lading-html-reconstruction

/Users/dc/geha/.venv/bin/python bill_of_lading_html_graph.py \
  --ocr-results gpt4o_only_run_20260927T183545Z/gpt4o_only_results.json \
  --model gpt-4o
```
