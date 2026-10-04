# Dental agentic search corpus

Copied Python implementation from `/Users/dc/geha/agentic_search/src`, with a new
page-aware corpus retriever in `src/corpus_search.py`. Original code remains available.

The default corpus loads only `page-*.md` from both directories:

- `/Users/dc/geha/downloads/dental/fedvip/2026-geha-dental-benefits-guide_pages`
- `/Users/dc/geha/downloads/dental/fedvip/2026-geha-dental-plan-brochure_pages`

PDF and HTML siblings are not indexed again. Page metadata distinguishes source PDF
page numbers from printed brochure pagination. Extracted document content is evidence,
not instructions for the agent.

## Run

### Streamlit chatbot

```bash
cd /Users/dc/geha/agentic_search_corpus
/Users/dc/geha/.venv/bin/python -m streamlit run src/corpus_app.py --server.port 8502
```

Open http://localhost:8502. Select BM25, vector, or hybrid retrieval, and agentic
answers, one-pass answers, or Non Agentic Search. One-pass answers retrieve once
and use the same gpt-4o answer prompt as the agent, with no relevance grading,
query rewriting, or grounding retries. The UI includes all 15 example questions,
page evidence, response timing, and a collapsed agent trace. Search resources and
BGE stay cached in the Streamlit process across turns. Questions are independent;
the displayed conversation history is not passed into the agent as context.
Set `OPENAI_API_KEY` in the launching shell or project `.env` for agentic answers.

```bash
cd /Users/dc/geha/agentic_search_corpus
/Users/dc/geha/.venv/bin/python src/corpus_search.py "How many adult cleanings does High cover compared with Standard?" --mode hybrid
/Users/dc/geha/.venv/bin/python evals/compare.py
```

Use `--mode bm25`, `--mode vector`, or `--mode hybrid`. For the copied corrective
LangGraph agent, append `--agentic`; this requires `OPENAI_API_KEY` and sends retrieved
public dental evidence and the question to OpenAI. BGE uses locally cached model files.

```bash
/Users/dc/geha/.venv/bin/python src/corpus_search.py "What do High and Standard pay for D3310, and what lifetime restriction applies?" --mode hybrid --agentic
```

## Streamlit workflow comparison

| Workflow | Retrieval | LLM answers | Grades evidence | Rewrites query | Checks grounding |
|---|---|---|---|---|---|
| Non Agentic Search | Once | No | No | No | No |
| One-pass answer | Once | Yes | No | No | No |
| Agentic answer | Once, with up to two additional searches | Yes | Yes | If no passages are relevant | Yes, with at most two generations |

The original question and retrieved page text are supplied to the answering LLM.
One-pass and agentic answers use the same gpt-4o model and answer prompt. The agent
filters pages through relevance grading before generation. Non Agentic Search shows
ranked snippets with expandable full pages and makes no LLM calls.

| Retrieval mode | Non Agentic Search | One-pass answer | Agentic answer |
|---|---|---|---|
| BM25 | BM25 search | BM25 + one LLM answer | BM25 + corrective loop |
| Vector | BGE vector search | Vector + one LLM answer | Vector + corrective loop |
| Hybrid | BM25/vector rank fusion | Hybrid + one LLM answer | Hybrid + corrective loop |

Agentic is a workflow using one of the three retrieval modes, not a fourth index.
The measured benchmark below covers only Non Agentic Search. One-pass and agentic
answer accuracy, end-to-end latency, and model cost have not yet been benchmarked.

## Index implementation

BM25 indexes page text with lowercase alphanumeric tokens, retaining CDT identifiers.
BGE large embeds overlapping 440-token windows with stride 360; page relevance is the
maximum window similarity. Window vectors are cached under `indexes/` with a content
hash; the index manifest preserves source/page IDs. This is a small NumPy vector index,
not a Chroma server. BM25 is rebuilt cheaply on startup. A production corpus would
need incremental ingestion and a scalable persistent search service.

Hybrid merges top-30 positive BM25 matches and top-30 vector pages using equal-weight
reciprocal rank fusion (constant 60). All modes return source pages, keeping table rows
and headings together. No per-query tuning is applied.

The optional agent reuses `AgenticRag`: relevance grading, at most two query rewrites,
generation, and at most two grounding-checked generations. It retains full cited
page evidence rather than truncating to the original client's first three passages.
It still checks relevance rather than completeness and does not accumulate evidence
across retries. Those are future changes, not claimed features.

## Comparison

### Current limit: two search turns total

Going forward, multiturn uses at most **two retrieval rounds**: initial search
plus one follow-up. This shared budget includes no-relevant-evidence rewrites.
It is not a limit of two LLM calls: passage grading, completeness assessment,
answer generation and grounding checks still make separate calls. Explicit
benchmark overrides can differ, so verify settings before running old scripts.

The October 4 GPT-4o marriage comparison below used the previous three-round
budget, not this new limit:

| Metric | Vector single-turn | Vector multiturn |
|---|---:|---:|
| Wall time, excluding model setup | 9.7 s | 32.1 s |
| LLM calls | 1 | 35 |
| Retrieval rounds | 1 | 3 |
| Follow-up searches | 0 | 2 |

One run per workflow; no statistical quality conclusion. Multiturn ended with
incomplete evidence and near-repetitive follow-up queries. Both answers cited
page 10 for timing rules on page 11 and lacked an explicit BENEFEDS submission
instruction. Multiturn added effective-date guidance but also contradicted its
permission assertion with an unresolved-evidence warning. No clear improvement
was observed. [Answers and traces](evals/marriage_workflow_comparison.jsonl).

### Current Streamlit sidebar

The sidebar now has exactly two agent options, replacing the retrieval/workflow
selectors described in older experiments:

| Option | Backend |
|---|---|
| Vector search single-turn agent (default) | Vector retrieval once, then one answer-generation call. |
| Multiturn agent | Vector retrieval, relevance grading, accumulated evidence, completeness assessment, up to two targeted follow-up searches, answer generation and bounded grounding checks. |

Both use the existing OpenAI answer client and require `OPENAI_API_KEY`.
Multiturn means multiple internal search/reasoning steps for the current question,
not memory or state shared across user messages. Source evidence and traces remain
available. BM25/hybrid remain in the CLI and benchmark code, but there is no
automatic CDT/BM25 routing in this revised UI. Backend dispatch lives in
`src/answer_workflows.py`; the Streamlit widget selects that dispatch directly.

### Completeness-driven agentic mode — implemented October 4, 2026

The Streamlit **Agentic answer** workflow now uses this bounded flow:

```text
retrieve → grade relevance and accumulate evidence → assess completeness
  incomplete + new targeted query + search budget → retrieve again
  complete or budget exhausted → generate → grounding check → finish
```

The LLM compares all parts of the original question against accumulated evidence
and returns `complete`, `missing`, and `next_query`. Missing requirements override
a contradictory complete flag. Code permits at most two additional searches,
sharing the budget with no-relevant-evidence rewrites. Repeated queries stop;
identical passages are deduplicated, and previously useful evidence is retained.
If the evidence remains incomplete, the response and UI explicitly display this
limitation. Grounding and completeness are separate checks; neither constitutes
a validated eligibility decision. Grounding regeneration remains bounded at two.

**One-pass is unchanged** and remains the UI default. No benchmark is automatically
started by these changes. Existing Gemma/MiMo results describe the old loop and
must not be presented as measurements of this new implementation. The historical
benchmark adapters inject graders without an LLM and therefore retain their old
relevance-only behavior unless a completeness callback is explicitly supplied.
`AgenticRag` creates the structured completeness assessor for clients with an LLM;
tests can inject a callback without network calls.

Fake tests cover missing-evidence searches, accumulation/deduplication, complete
first retrieval, repeated queries, and budget exhaustion. Live answer-quality
improvement has not yet been measured. The model can still misjudge sufficiency;
complex eligibility rules require source review or deterministic validation.

### Experimental UI baseline: automatic retrieval + one-pass

The Streamlit defaults are now **Auto retrieval** and **One-pass answer**.
Natural-language questions use vector retrieval. A standalone CDT identifier
matching `D` plus four digits (case-insensitive, e.g. D1110) selects BM25.
Dates, ages, and arbitrary numbers do not trigger BM25. Manual BM25, vector,
hybrid, agentic, and retrieval-only settings remain available. This is a simple
local rule, not JEV or an LLM router. No completeness-driven loop or synonym
tuning has been added. UI answer generation still uses its existing OpenAI
client; the comparison benchmark below uses Google Gemma.

Run only the remaining Gemma vector/one-pass questions, preserving completed
checkpoints and leaving the other benchmark modes stopped:

```bash
cd /Users/dc/geha/agentic_search_corpus
zsh -ic 'env HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/dc/geha/.venv/bin/python -u evals/remaining_vector_baseline.py'
```

Validation: 21 unit tests passed, including exact-code routing and rejecting
non-code numbers. The policy answer source review is recorded separately below;
automated rubric scores must not be treated as policy correctness guarantees.

#### Source review of vector one-pass answers

As of October 4, five of six Gemma vector/one-pass cases have scores (automated
mean 92%); root-canal/crown timed out and is being retried once. This is not
92% independently verified policy accuracy. Direct comparison against the
supplied source Markdown found the following:

| Question | Source comparison |
|---|---|
| Marriage | Window matches brochure page 11, but the answer should distinguish coverage tier from High/Standard option changes, explain the pre-event new-enrollment exception, and explicitly hand off to BENEFEDS. |
| Implants and braces | $2,500 annual implant and $3,500 lifetime orthodontic caps match guide page 5. The answer omits High's 30% orthodontic share even though the automated evaluator awarded all five rubric criteria. |
| Disabled child | Conditional continuation for a disabled child 22+ matches brochure page 8; it should clarify federal versus TRICARE eligibility instead of treating their rules as interchangeable. |
| VA cancellation | Pre/post-tax distinctions and notification/documentation deadlines match brochure page 11. It omits the source's cancellation-effective-date guidance; do not infer immediate cancellation. |
| Discounts | Vision, hearing and fitness are correctly distinguished from insured dental benefits (guide pages 7/9, brochure page 49). Gym fees are omitted, although the rubric includes fees and the evaluator awarded full credit. The sources describe different fitness offerings/counts; don't silently equate them. |

This review is a limited source-text inspection, not professional eligibility
adjudication or PDF extraction certification. It demonstrates why automated
self-judging overstates completeness in some cases. The baseline remains
experimental; the agentic completeness-loop changes are not implemented.

### Gemma 4 one-pass versus agentic benchmark

### MiMo via Nous

#### Incomplete results — stopped October 4, 2026

The user stopped the MiMo-V2.5 run after **10 of 36 scored configurations**.
One additional configuration (limits, vector, one-pass) timed out; the remaining
25 configurations have no completed score. Saved checkpoints are preserved.

| Retrieval | Answer workflow | Completed | Rubric completeness | Supported citations | Median seconds |
|---|---|---:|---:|---:|---:|
| BM25 | One-pass | 2/6 | 60.0% | 2/2 | 40.4 |
| BM25 | Agentic | 2/6 | 60.0% | 2/2 | 57.5 |
| Vector | One-pass | 1/6 | 80.0% | 1/1 | 48.9 |
| Vector | Agentic | 2/6 | 80.0% | 2/2 | 64.8 |
| Hybrid | One-pass | 2/6 | 80.0% | 1/2 | 34.7 |
| Hybrid | Agentic | 1/6 | 60.0% | 0/1 | 50.2 |

These uneven, partial samples do not establish a winner or an agentic advantage.
MiMo evaluates its own answers; scores are automated rubric judgments, not
human-validated accuracy. Latency includes retrieval and workflow API calls,
but excludes the separate evaluator. The marriage query exposed a BM25 wording
mismatch: pages 10–11 were absent from its top ten, and the current relevance-only
loop did not recover them. Vector retrieved those pages, but answers still had
interpretation and verbosity issues. Different API pacing and self-evaluators
prevent a controlled quality or speed comparison against the stopped Gemma run.

The same 36 configurations can run with `xiaomi/mimo-v2.5` through the paid
Nous API. Reads `NOUS_API_KEY` or `NOUS_KEY` from the environment:

```bash
cd /Users/dc/geha/agentic_search_corpus
zsh -ic 'env HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/dc/geha/.venv/bin/python -u evals/mimo_answer_benchmark.py'
```

Separate [MiMo results](evals/mimo_nous_results.md) and
[checkpoints](evals/mimo_nous_answers.jsonl) preserve the stopped Gemma run.
Nous requests are sequential with backoff on transient errors, without Google's
14-second quota delay. Each model judges its own answers, so cross-model scores
are exploratory, not an independent quality ranking. JSON objects are validated
locally; the Google response-schema setting is not sent to Nous.

### Google Gemma run

Run the six multi-rule questions with all three retrievers and both answering
workflows (36 configurations), using Google-hosted `gemma-4-26b-a4b-it`:

```bash
cd /Users/dc/geha/agentic_search_corpus
zsh -ic 'env HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 /Users/dc/geha/.venv/bin/python -u evals/gemma_answer_benchmark.py'
```

The runner reads `GEMINI_API_KEY` or `GOOGLE_API_KEY` from the shell. It does not
call OpenAI or Nous. Free-tier eligibility and quotas depend on the Google project.
Completed configurations are checkpointed and skipped on resume. Generation and
evaluation calls are paced to reduce free-tier rate errors.

[Live/finished results](evals/gemma4_results.md),
[saved answers and usage](evals/gemma4_answers.jsonl), and
[questions with rubrics](evals/gemma4_cases.json) are written during the run.
Until the report says 36/36 completed, its table is partial.

#### Stopped run — October 4, 2026

Stopped at the user's request. The checkpoint contains **15 of 36 scored
configurations**, with no current configuration errors. The last report was
written at 14/36; the table below includes the final saved vector one-pass answer.
The remaining 21 configurations were not completed. No winner can be established
from this incomplete, uneven sample.

| Retrieval | Answer workflow | Completed | Rubric completeness | Supported citations |
|---|---|---:|---:|---:|
| BM25 | One-pass | 3/6 | 60.0% | 3/3 |
| BM25 | Agentic | 3/6 | 53.3% | 3/3 |
| Vector | One-pass | 3/6 | 86.7% | 3/3 |
| Vector | Agentic | 2/6 | 90.0% | 2/2 |
| Hybrid | One-pass | 2/6 | 80.0% | 2/2 |
| Hybrid | Agentic | 2/6 | 50.0% | 1/2 |

These are same-model automated rubric judgments, not human-validated accuracy.
No unsupported claims were flagged in the scored answers, but that does not
guarantee correctness. The agent made zero query rewrites and one extra answer
generation in this partial run. It checks passage relevance and grounding, not
whether all required policy rules were retrieved. The loop has not demonstrated
an answer-quality improvement here. Google requests were deliberately spaced
at least 14 seconds apart to avoid quota errors, so recorded workflow latency
includes throttling and should not be treated as model-only inference speed.
Saved answers, traces, and token usage remain in `evals/gemma4_answers.jsonl`;
the command above can resume successful checkpoints without rerunning them.

Gemma judges rubric completeness, unsupported claims, and citation support; these
are automated scores, not human-validated accuracy. Relevance grading is batched
per round with validated JSON arrays; the copied LangGraph decisions remain the
same. One-pass and agentic runs use the same answer prompt. Query/answer text and
public documents are the only data sent. Evidence completeness is not a routing
condition in the current agent, so a missing rule need not cause a rewrite.

[Example queries](evals/queries.jsonl) contain manually selected evidence pages.
[Measured results](evals/results.md) and [per-query rankings](evals/results.json)
compare BM25-only, vector-only, and hybrid over identical corpus pages.
These scores measure retrieval; they do not prove the agentic loop improves answers.
The labels are curated and alternative relevant pages may be omitted.

Measured local results (2026-10-04), 15 questions over 68 pages:

| Mode | Evidence Recall@5 | All evidence@5 | MRR@10 | Median query ms |
|---|---:|---:|---:|---:|
| BM25 | 0.933 | 0.867 | 0.850 | 0.3 |
| Vector | 0.700 | 0.600 | 0.651 | 30.0 |
| Hybrid | 0.900 | 0.867 | 0.761 | 29.6 |

BM25 leads on this small, terminology-heavy fixture. There is no measured reason
to prefer hybrid here yet. Broader paraphrase and absent-answer tests are needed.
Initial model loading and indexing took 21.6 seconds and are excluded above.

Validation: 17 copied unit tests and 2 corpus tests passed. A live BM25-backed
agent question about TruHearing retrieved two relevant pages out of ten and passed
the model's grounding check. It returned the 30%-60% discount with a guide-page
citation. The generated answer also called eligibility/process information missing,
although the brochure page contains some such information: the grounding check is
not an answer-completeness guarantee. No live answer comparison across all modes
has been fully completed; the retrieval table above is strictly a retrieval
comparison. The stopped Gemma answer benchmark is documented separately above.
