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
