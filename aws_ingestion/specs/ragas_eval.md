# Spec: RAGAS evaluation of ingestion

Review status: DRAFT. Not implemented.

## What RAGAS adds, and what it does not

RAGAS scores a RAG interaction (question, retrieved contexts, answer, reference answer) with LLM-judged metrics. It does not check extraction directly.

- **Per-page verification stays deterministic** (word diff, numeric check, table shape, vision diff in `react_loop.md`). RAGAS is too coarse and too costly to run inside the 5-iteration loop.
- **RAGAS is the end-to-end, task-level eval.** It answers: "does a RAG system built on this ingestion output answer real questions correctly and faithfully?" This catches errors that page diffs miss (broken table semantics, lost reading order, bad chunk boundaries).

## Experiment design

Hold everything constant except the ingestion variant.

```
questions + reference answers (fixed)
        |
   for each ingestion variant V in {pipeline 1, pipeline 2, Textract, Textract+agent, ...}
        |
   approved/candidate pages of V -> same chunker -> same embedder -> same index -> same retriever -> same generator
        |
   RAGAS metrics per question
```

Differences in scores are then attributable to ingestion. Each variant uses its own index version (see `search_sdk.md`).

## Metric mapping

| RAGAS metric | Ingestion question it answers |
|---|---|
| `context_recall` | Did the ingested text contain what is needed to support the reference answer? Low recall points to dropped text, tables or figure data. |
| `context_precision` | Are the relevant chunks ranked above noise? Points to chunk quality and duplicated or garbled text. |
| `faithfulness` | Is the answer supported by the retrieved context? Drops when OCR noise or garbled numbers mislead the generator. |
| `answer_relevancy` | Secondary sanity check on the generator. |

Report by page class (text, scan, form, table, figure) and by question type (lookup, numeric, table, multi-page). One average hides the failures that matter.

## Question and reference sets

- **Independence rule.** Reference answers MUST NOT be generated from the pipeline output under test. That would be circular and would reward the pipeline's own mistakes.
- Sources, in order of preference:
  1. Human-written questions and answers from the source PDFs (small gold set per benchmark document).
  2. RAGAS `TestsetGenerator` (as in `finetuning/generate_ragas_qa.py`) run on PyMuPDF text from text-layer pages only, then human-filtered.
  3. Vision-model questions generated from the page image for scanned pages, then human-filtered.
- Every item stores `doc_sha256`, `page_no` and `block_id` of its evidence, so a miss can be traced to a page and fed back to the review queue.
- Store sets as versioned JSONL under `evals/` (same shape as `advanced_rag/evals` output).

## Where it runs

- **Pipeline promotion gate.** A new `pipeline_version` or agent change is not promoted unless it matches or beats the current version on the gold set within a tolerance, with no per-class regression beyond a threshold.
- **Benchmark runs** (Phase 7): the benchmark set across all variants, reported with cost.
- **Scheduled sample** on approved production pages, so drift shows up.
- Never in the request path and never per page.

## Feeding results back

- Questions with low `context_recall` link to a page. Those pages get a raised risk score and appear at the top of the review queue.
- A systematic drop in one class (for example tables) is an input to the next spec change, not a per-page fix.

## Implementation

- Reuse `/Users/dc/geha/e2e_RAG/src/ragas_evaluator.py` (`RagasEvaluator`, `RagasSample`). It already accepts an injected `metric_runner`, so unit tests use a fake runner and need no model.
- Wrap it behind an `Evaluator` protocol in `search_sdk/eval.py` so `compare_pipelines` can report RAGAS metrics next to recall@k and MRR.
- Pin `ragas==0.4.3` as the existing projects do. Note its `instructor` dependency requires OpenAI < 2, so isolate it in an `eval` extra or its own environment, not in the worker image.

## Guardrails

- **Judge independence.** The judge model should differ from the model that extracts or repairs pages, to avoid correlated errors. Record judge model and version with every result.
- **Cost cap.** Cap judge calls and dollars per eval run. Metrics make several LLM calls per question; budget it.
- **Variance.** LLM judges are noisy. Report mean with confidence interval, and use paired comparison on identical questions across variants.
- **Data handling.** The demo uses only synthetic or public documents (see the AWS plan security section). The judge provider must be permitted for any real workload. Today the evaluator calls OpenAI directly; the AWS plan would move this to a Bedrock or approved provider behind Secrets Manager.
- No document text in logs.

## Acceptance

- The same question set runs against two ingestion variants and produces a paired, per-class report.
- A fake metric runner makes the whole eval path testable offline.
- Every low-scoring question resolves to a page in the review queue.
- Promotion is blocked on a seeded regression (for example, a variant that drops table text).

## Open questions

- Size of the gold set per benchmark document, and who writes it.
- Judge model choice, and whether to run a second judge for agreement.
- Whether table and figure questions need a custom numeric-exact metric alongside RAGAS.
