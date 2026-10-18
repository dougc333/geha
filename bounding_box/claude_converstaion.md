# Conversation: bounding-box browser agent, specs, and vision models

Date: 2026-10-18. Repo: `/Users/dc/geha`.

---

## Q: Did Claude make its own bounding boxes for the EY PDFs, and were they checked by a prompt that described the chart and its bar values?

Partly. There are two separate paths.

**The prompt is real:** `bounding_box/annotations/research/ey-limra-workforce-benefits-study-final-2025/reconstruction-prompts/page-004/page-004-region-bcb07a18.md`.
It describes the Figure 1 stacked bars (Small 57/40/3 +7%, Midsize 64/35/1 +6%, Large 67/30/3 +5%). It tells the model to render at 868×884, compare the result with the crop, and treat the percentages as "locked evidence".

That prompt belongs to the **reconstruction path**, not the spec path:

| | Reconstruction path (`figure_bbox_app`) | Spec path (`figure_specs.py`) |
|---|---|---|
| Boxes | Drawn by hand in the React app → `figure-bounding-boxes.json` | Claude wrote `box_pt` in each spec from the PDF's text and drawing positions |
| Chart description | `generate_reconstruction_prompts.py`, from the hand-drawn boxes plus the PDF text | Claude-authored spec JSON |
| Checking | A model compares the rendered HTML with the crop (up to 6 passes) | Code checks every value against the native PDF text inside `box_pt` |
| Output | HTML written by the model | Fixed HTML from 9 renderers |

Both paths get the numbers right for the same reason: the EY PDF is native, so the values are real text in the PDF. The spec path won't carry over to scanned PDFs.

Related files in the same annotation folder: `reconstruction-prompts/`, `approved-reconstruction-prompts/`, `figure-reconstruction-prompts.json`, `figure-bounding-boxes.json`. The generator script is `generate_reconstruction_prompts.py`.

---

## Q: Build a browser-use agent that draws bounding boxes around figures and saves them to JSON. Run it on `medical_bill_en.pdf`.

Built: **`bounding_box/figure_bbox_app/browser_bbox_agent.py`**. You later moved the folder from `crawl_dir/figure_bbox_app/` to `bounding_box/figure_bbox_app/`; the code paths work from the new location.

How it works:
1. It starts the existing React bbox app for any PDF. `backend.py` now takes `--pdf` and `--out-dir`, and still opens the EY study when run without them.
2. It opens the app in Playwright Chromium and sends Claude (Opus 5.5) a screenshot of the page.
3. Claude has three tools: `draw_box` (a real mouse drag, then setting the type and label), `delete_box` and `finish`. After each action it gets a new screenshot showing its numbered boxes, so it can fix mistakes.
4. Boxes save through the app's normal autosave as `figure-bounding-boxes.json` (0–1000 scale). A sidecar file, `browser-agent-run.json`, adds the same boxes in PDF points, plus the model name, page summaries and token usage.

```bash
cd /Users/dc/geha
.venv/bin/python -m bounding_box.figure_bbox_app.browser_bbox_agent \
  --pdf /Users/dc/ocr-mini-bench/bench_documents/Invoices/medical_bill_en.pdf --headed
```

Needs `ANTHROPIC_API_KEY`. Output defaults to `bounding_box/annotations/other/<pdf stem>/`.

Result on the medical bill (a scanned image with no text layer and no charts). All 6 boxes were checked visually and are tight:

| # | kind | label | box (PDF pt) |
|---|---|---|---|
| 1 | image | Hospital logo | 53.8, 75.5 → 119.8, 140.6 |
| 2 | table | Patient information panel | 54.7, 306.6 → 434.0, 524.5 |
| 3 | table | Insurance & visit info panel | 466.0, 306.6 → 844.3, 503.8 |
| 4 | table | Provider and diagnosis panel | 54.7, 567.0 → 844.3, 666.0 |
| 5 | table | Itemized charges table | 54.7, 698.1 → 844.3, 920.8 |
| 6 | table | Account summary panel | 450.0, 964.2 → 844.3, 1311.3 |

---

## Q: Is this a spec file?

No. The agent is an agent, and its output records only *where* regions are on one document. A spec also describes *what's inside* each region (fields, patterns, rules) so code can check the values. These boxes could become the `box_px` input for a spec.

---

## Q: Is this an agent? Does it call the LLM? What's the cost?

Yes. It's a tool-use loop, and every turn is one Claude API call. Measured on the medical bill:

| | |
|---|---|
| API calls | 2 (all 6 boxes drawn in one turn, then one turn to check and finish) |
| Input tokens | 9,040 |
| Output tokens | 1,059 |
| Cost | about $0.07 per page, assuming Opus pricing of $5/M input and $25/M output (check current rates) |

How it scales:
- A page screenshot is roughly 3–4k tokens, and every turn resends the whole conversation.
- A busy page that needs corrections runs about 5–8 calls, roughly $0.25–0.50.
- 29 EY pages would cost about $2–5.
- Cheaper options: `--model claude-sonnet-5-5`, or keep only the latest screenshot in the history.

---

## Q: Does this generalize to Invoices, Logistics and Receipts in `ocr-mini-bench`? Does the ground truth imply a spec approach?

What's in the folders:

| | Files | Pages | Text layer | Distinct ground-truth field sets |
|---|---|---|---|---|
| Invoices | 12 | all 1 | none (image only) | 12 / 12 |
| Logistics | 17 | all 1 | none | 14 / 17 |
| Receipts | 13 | all 1 | none | 13 / 13 |

Each ground-truth field looks like `{value, critical, type}`.

**The bbox agent:** it works on all three folders as is (about $3 for all 42 files). Two caveats: the prompt targets figures, so it boxes panels and tables rather than individual fields, and with no text layer the values still have to be read by a vision model or OCR.

**Specs:** the ground truth is an answer key that includes the schema. It doesn't say where fields sit on the page.

| Kind of spec | Works here? |
|---|---|
| Layout spec (label anchors and box positions, like `bill_of_lading_spec.json`) | Only for repeated templates, possibly the `bill_of_lading_alt_*` and `transport_order_*` files |
| Schema and rules spec (types, patterns, arithmetic) | Yes, one per document type |
| Ground truth as the evaluation set | Yes, with critical fields weighted more |

Arithmetic checked against the ground truth:
- Invoices, `pretax + tax == total`: 9 pass, 1 is missing a field, 2 fail for real reasons.
  - `medical_bill_en`: the total is the balance after insurance.
  - `ecommerce_retail_en`: off by 6.00, probably shipping.
  - So the rules must allow adjustment lines.
- Receipts: 10 of 13 lack the tax or pretax fields, so a rule that items sum to the total fits better.
- One receipt ground-truth file has a malformed key, `item_id”: `.

Proposed pipeline: vision model → JSON in the ground-truth field names → schema-and-rules spec → score against ground truth. With no text layer, a spec can only catch values that are impossible or inconsistent; it can't confirm them against the PDF.

---

## Q: What does "the bbox agent is optional" mean?

The pipeline works without boxes. Each file is one page, so a vision model can read the entire page and return all the fields:

```
whole page image → vision model → JSON → spec checks → score
```

Boxes help in four situations:
- Dense pages with small text: a crop keeps the text readable after the API shrinks large images.
- Showing where a value came from: a review UI can highlight the region behind a value.
- Repeated templates: boxes become `box_px` in a layout spec.
- Retrying: re-read only the region that failed a check.

Their costs are an extra model call and the risk of a bad box cutting off a field. Suggestion: start without boxes, score against the ground truth, and add boxes only where scores are poor.

---

## Q: Are vision models interchangeable? Paddle, Meta, any VLM? Which work best?

Mostly yes, if each engine is plugged in as "page image in, JSON in the ground-truth field names out". The spec checks and scoring don't care which model produced the JSON. There are two groups:

1. **OCR and document parsers** (PaddleOCR-VL, Tesseract, Docling, olmOCR, Mistral OCR) output text or markdown and need a second step to map it to fields. In repo results, PaddleOCR-VL read every character correctly but ran labels into values. Tesseract got 13/46 on the bill of lading.
2. **General VLMs** (Claude, GPT, Gemini, Qwen-VL, Meta's Llama vision models, InternVL) return schema JSON directly. On the bill of lading, Claude Opus 5.5 got 46/46, and Claude and GPT-4o tied with zero field errors.

What to expect (from general knowledge; test before relying on it):

| Option | Fit |
|---|---|
| Claude / GPT / Gemini | Most accurate, especially for receipt photos and dense tables. Gemini is usually cheapest. |
| Qwen2.5-VL / Qwen3-VL | The strongest open option for documents. Use larger sizes for dense invoices. |
| PaddleOCR-VL + spec parser | Fast and local. Suits repeated templates. |
| Meta Llama vision | Usable, but weaker than Qwen-VL on dense documents. |
| Tesseract | Baseline only. |

Recommendation: use `ocr-mini-bench` itself as the benchmark. Run 3–4 engines through the same pipeline and compare accuracy, cost and speed per folder.
