# YouTube Demo Script: Agentic Search with Bounded Corrective Retrieval

**Target length:** 9–11 minutes  
**Application:** `agentic_search`  
**Audience:** AI engineers, RAG engineers, and solution architects  
**Central message:** An agentic retrieval loop should earn its extra searches and model calls. This demo compares a single-search baseline with a bounded corrective workflow and shows where the additional search improves evidence, adds no value, or makes the answer worse.

## Recommended video title

**Does Agentic RAG Actually Help? A Measured Corrective-Search Experiment**

## Thumbnail text

**1 Search vs Agent Loop**

## What this video should demonstrate

1. `agentic_search` supports a fixed corrective-RAG workflow and a separate model-directed ReAct workflow.
2. The corrective workflow retrieves evidence, checks relevance and completeness, makes at most one follow-up search, generates an answer, and performs a bounded grounding check.
3. The AWS mode reuses the deployed `aws_rag` hybrid BM25/pgvector retrieval and Bedrock reranking service.
4. A controlled A/B test holds the question, corpus, retrieval service, and answer model constant while changing only the follow-up-search budget.
5. Follow-up retrieval can recover missing facts, but it can also repeat the first search, introduce confusion, reduce grounding, and add latency.
6. Agentic behavior should be enabled for query classes where evaluation shows a benefit, rather than applied to every question.

## Before recording

### Confirm the repository environment

```bash
cd /Users/dc/geha
UV_CACHE_DIR=/tmp/geha-uv-cache uv sync --locked

cd /Users/dc/geha/agentic_search
/Users/dc/geha/.venv/bin/python -m unittest discover \
  -s src -p 'test_*.py' -v
```

The offline test suite should complete without model, database, or AWS calls.

### Authenticate to AWS

```bash
aws login --profile geha-user --region us-west-2
aws sts get-caller-identity --profile geha-user
```

Do not display account IDs, API keys, database URLs, or shell history containing secrets in the recording.

### Prepare the recording tabs

1. Open `/Users/dc/geha/agentic_search/docs/agentic_rag.png`.
2. Open `/Users/dc/geha/agentic_search/README.md` at the recorded 22-question results.
3. Open `/Users/dc/geha/agentic_search/evals/aws_agentic_ab_results.md`.
4. Keep a terminal in `/Users/dc/geha/agentic_search`.
5. Increase the terminal font so the trace, citations, and metrics are readable.

### Use these live-demo questions

| Purpose | Question | Expected behavior |
|---|---|---|
| Follow-up helps | How is web or search-engine access used differently in CRAG and Search-R1? | The second search can recover the missing Search-R1 distinction. |
| First search is enough | What reflection tokens does Self-RAG use? | The initial retrieval can reach complete evidence without a follow-up. |
| Missing fact recovery | How large is Orca, and how many ChatGPT and GPT-4 responses were collected to train it? | The follow-up can recover the GPT-4 response count. |
| Known regression | What BLEU scores did the big Transformer achieve on WMT 2014 English-to-German and English-to-French? | The recorded follow-up confused the language pairs and reduced fact recall. |
| Abstention test | How many dollars did it cost to train Orca? | The corpus does not establish a dollar cost; the system should abstain. |

Use the web-access comparison for the live happy path. Replay the BLEU and Orca-cost questions from saved results rather than relying on a new live run to reproduce the same outcome.

## Main recording script

### 0:00–0:45 — Hook: more searches do not guarantee a better answer

**On screen**

- Show the recorded A/B summary.
- Highlight fact recall, grounding, follow-up rate, and latency.

**Narration**

> Agentic RAG sounds better than ordinary RAG because the system can inspect its evidence and search again. But another search can recover a missing fact, repeat the same evidence, or introduce a new error.
>
> This project compares one search with a bounded corrective loop over the same scientific-paper corpus. In one 22-question run, corrective retrieval improved fact recall by seven percentage points and evidence completeness by eighteen points. It also reduced the grounded-answer rate by nine points and added about 2.4 seconds of median latency.
>
> The point of this demo is not that agentic search always wins. The point is that we can measure when the extra loop earns its cost.

### 0:45–1:45 — Architecture: a bounded corrective loop

**On screen**

- Show `docs/agentic_rag.png`.
- Follow the arrows from retrieval through completeness, generation, and grounding.

**Narration**

> The fixed workflow begins with retrieval and reranking. It then assesses whether the accumulated evidence covers every part of the original question.
>
> If evidence is incomplete, the workflow may issue one focused follow-up query. Evidence from both rounds is accumulated and deduplicated. The answer model receives the original question and the retained evidence, not merely the rewritten query.
>
> After generation, a grounding check asks whether the answer is supported by the supplied passages. One regeneration is allowed when grounding fails. Search and generation budgets keep the graph from looping indefinitely.

**On-screen callout**

```text
retrieve → assess relevance and completeness
         ├── incomplete + budget → focused follow-up → retrieve
         └── complete or budget exhausted → generate
                                            ↓
                                      grounding check
                                            ↓
                                      finish or regenerate once
```

### 1:45–2:35 — The retrieval service remains constant

**On screen**

- Show `src/aws_retriever.py` and the AWS retrieval response fields.
- Point out chunk text, source, page, rank, and rerank score.

**Narration**

> The agent does not own a second search index. AWS mode calls the existing `aws_rag` retrieval API, which combines BM25 and pgvector with reciprocal-rank fusion and Bedrock reranking.
>
> That separation matters for the experiment. Both conditions use the same corpus, retriever, reranker, and answer model. The A/B test changes only `max_rewrites`: zero for the single-search baseline and one for the corrective condition.
>
> The returned evidence keeps paper, page, chunk, table, and figure provenance so the final answer can be inspected against its sources.

### 2:35–4:00 — Run one corrective search

**On screen**

- Run the web-access comparison.
- Pause on the initial query, completeness decision, follow-up query, citations, and final metrics.

```bash
cd /Users/dc/geha/agentic_search

./run_aws_agentic.sh \
  "How is web or search-engine access used differently in CRAG and Search-R1?"
```

**Narration**

> The first retrieval may cover CRAG but miss the specific Search-R1 mechanism. The completeness check identifies the uncovered requirement and proposes a narrower follow-up rather than simply repeating the original question.
>
> The second retrieval is accumulated with the first. The final answer should distinguish CRAG's corrective web search, triggered when retrieved evidence is poor or uncertain, from Search-R1's learned multi-turn search during reasoning.
>
> I am checking four things in the trace: whether the follow-up targeted the missing requirement, whether it returned new evidence, whether the answer cited the right sources, and whether the grounding check passed.

### 4:00–5:05 — Compare against the single-search baseline

**On screen**

- Run three A/B cases or display the saved complete result.
- Show that both conditions use the same question fixture.

```bash
cd /Users/dc/geha/agentic_search

./run_aws_agentic_ab.sh --limit 3
```

**Narration**

> The A/B runner evaluates every question twice. The baseline has no follow-up-search budget. The corrective condition has one. Both can use the grounding regeneration step, so this comparison isolates corrective retrieval rather than comparing an LLM answer with no verification against an agent with verification.
>
> The fixture contains single-paper questions, multi-paper comparisons, and deliberately unanswerable questions. Fact recall measures required answer facts. Source recall checks whether the expected papers appear in the selected evidence. Completeness, grounding, retrieval rounds, generation attempts, and latency expose the operational tradeoff.

### 5:05–6:05 — Cases where the follow-up helped

**On screen**

- Show the saved records for Orca, DeepSeek-V3 versus Kimi K3, and CRAG versus Search-R1.

**Narration**

> The corrective search helped when the first retrieval covered one part of a compound question but missed another.
>
> For Orca, fact recall increased from 67 to 100 percent after a follow-up recovered the GPT-4 response count. For the DeepSeek-V3 and Kimi K3 comparison, fact recall increased from 50 to 100 percent, although the grounding check still failed. For CRAG and Search-R1, the second search recovered the missing web-search distinction and produced a grounded answer.
>
> These are the cases agentic search is designed for: the evidence gap is identifiable, the follow-up is specific, and the second retrieval returns a missing source or fact.

### 6:05–7:15 — Cases where the loop added no value or caused harm

**On screen**

- Show the Transformer heads, CRAG actions, and Transformer BLEU records.
- Put the initial and follow-up queries side by side.

**Narration**

> The loop also searched when the first evidence was already sufficient. The Transformer-head question remained at 100 percent fact recall while latency increased from about 3.3 to 5.7 seconds. The CRAG-actions question also remained complete; the narrower query added no measured value.
>
> More importantly, one follow-up was harmful. The Transformer BLEU question initially had both language-pair scores. The generated follow-up mixed English-to-German and English-to-French, and fact recall fell from 100 to 50 percent.
>
> A production policy should avoid a second search when evidence is already complete and should reject follow-ups that change entities, datasets, dates, or comparison sides from the original question.

### 7:15–8:10 — Abstention is a separate capability

**On screen**

- Show the two unanswerable examples and the known HNSW fixture defect.

**Narration**

> Corrective retrieval does not automatically create reliable abstention. The corpus does not state the dollar cost to train Orca, and it does not contain a WMT 2019 English-to-Chinese result for the original Transformer. Searching again cannot manufacture absent evidence.
>
> In the recorded run, correct abstention remained zero in both conditions. One fixture also incorrectly labeled the HNSW `M` question as unanswerable even though the source contains the value range. That is an evaluation-data defect, not a retrieval result.
>
> Before using abstention metrics, the gold labels must be source reviewed and the answer policy must distinguish “not found after this search” from “the corpus does not establish this fact.”

### 8:10–9:15 — Read the aggregate result honestly

**On screen**

- Show the recorded 22-question table.
- Highlight both improvements and regressions.

| Metric | Single search | Corrective | Change |
| --- | ---: | ---: | ---: |
| Fact recall | 56.1% | 63.2% | +7.0 pp |
| Source recall | 57.9% | 57.9% | 0.0 pp |
| Evidence-complete rate | 4.5% | 22.7% | +18.2 pp |
| Grounded-answer rate | 63.6% | 54.5% | -9.1 pp |
| Follow-up-search rate | 0.0% | 95.5% | +95.5 pp |
| Median latency | 4,458 ms | 6,887 ms | +2,429 ms |

**Narration**

> Corrective retrieval improved fact recall on four questions, regressed on one, and tied on seventeen. Source recall did not change, while grounding became worse.
>
> The most important diagnostic is the 95.5 percent follow-up rate. Twenty-one of twenty-two questions triggered another search. A useful agent should be selective. This evaluator behaved more like an automatic second-search switch.
>
> The next experiment should calibrate the completeness threshold, measure whether the second round adds novel evidence, and route only compound or incomplete questions into the corrective workflow. Simple fact questions should usually stay on the faster single-search path.

### 9:15–10:05 — Corrective RAG versus ReAct

**On screen**

- Show `src/agentic_rag.py` and `src/react_rag.py` side by side.

**Narration**

> This repository contains two different meanings of agentic search.
>
> Corrective RAG follows a fixed LangGraph state machine. The transitions and budgets are explicit, which makes the workflow easier to test and compare. ReAct lets the model decide when to search and when to answer through tool calls. It is more flexible, but the trajectory is less predictable and needs its own evaluation for tool selection, termination, latency, and answer quality.
>
> The 22-question result shown here evaluates the bounded corrective workflow. It should not be presented as evidence that the ReAct implementation performs better.

### 10:05–10:40 — Close: use agentic search selectively

**On screen**

- Return to the corrective-loop diagram.
- Display the repository path `agentic_search/`.

**Narration**

> Agentic search is valuable when the first retrieval is measurably incomplete and the system can formulate a focused second query. It is wasteful when the first evidence is already sufficient, and dangerous when the rewrite changes the meaning of the question.
>
> The engineering pattern is simple: start with a strong single-search baseline, add one bounded corrective step, record the full trace, and keep the loop only for the query classes where held-out evaluation shows a quality gain worth the latency and model cost.

## Optional 90-second version

> This project tests whether a bounded agentic search loop improves RAG answers over scientific papers.
>
> Both conditions use the same AWS hybrid BM25 and pgvector retriever, reciprocal-rank fusion, Bedrock reranking, and answer model. The baseline searches once. The corrective workflow checks evidence completeness, may issue one focused follow-up, accumulates the evidence, generates an answer, and performs a bounded grounding check.
>
> In one 22-question run, corrective retrieval improved fact recall from 56.1 to 63.2 percent and evidence completeness from 4.5 to 22.7 percent. But source recall did not change, the grounded-answer rate fell from 63.6 to 54.5 percent, and median latency increased by about 2.4 seconds.
>
> The loop helped compound questions where the first search missed one required fact. It added no value to already-complete questions and hurt one Transformer BLEU comparison when the follow-up mixed the language pairs.
>
> The conclusion is not “always use an agent.” Start with one strong search, add a bounded correction step, inspect the trace, and route only the question types where evaluation shows that the extra search improves the answer.

## Suggested YouTube chapters

```text
00:00 Does another search improve the answer?
00:45 Bounded corrective-RAG architecture
01:45 Reusing AWS hybrid retrieval
02:35 Live corrective-search trace
04:00 Single-search versus corrective A/B
05:05 Cases where follow-up retrieval helped
06:05 Unnecessary and harmful follow-ups
07:15 Abstention and evaluation-data defects
08:10 Recorded quality and latency tradeoff
09:15 Corrective RAG versus ReAct
10:05 When to use agentic search
```

## Accuracy and recording notes

- The recorded metrics come from one sequential 22-question run on October 22, 2026. They are not statistical guarantees.
- Nova supplies fact, completeness, and grounding judgments. These are automated rubric results, not independent human adjudication.
- The HNSW `M` fixture is mislabeled as unanswerable in the recorded run. Correct it before publishing a new abstention metric.
- The corrective condition issued a follow-up for 21 of 22 questions. Describe this as an overactive completeness gate, not evidence of optimal routing.
- Corrective retrieval and ReAct are separate workflows. Do not attribute the corrective A/B result to ReAct.
- AWS mode uses the deployed `aws_rag` retrieval API. It does not open the local Chroma index.
- Local-PDF mode and AWS mode use different retrieval backends and completeness implementations. State which one is on screen.
- A grounding score does not prove policy or scientific correctness. Verify claims against the cited source pages.
- Do not display AWS account IDs, API keys, database URLs, or shell history containing secrets.

## Suggested links for the video description

```text
Agentic-search implementation:
agentic_search/

Corrective workflow:
agentic_search/src/agentic_rag.py

ReAct workflow:
agentic_search/src/react_rag.py

AWS retrieval adapter:
agentic_search/src/aws_retriever.py

Recorded A/B evaluation:
agentic_search/evals/aws_agentic_ab_results.md
```
