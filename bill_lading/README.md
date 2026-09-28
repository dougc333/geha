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
