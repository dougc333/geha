# DSPy dental enrollment chatbot

This DSPy app has two deliberately separate assistants:

- **Enrollment chat** reuses the tested LangGraph policy engine in
  `../dental_enrollment_chatbot` and replaces its semantic input normalizer
  with a DSPy program.
- **Dental Policy Q&A** retrieves page-aware passages locally from
  `../downloads/dental/fedvip/2026-geha-dental-benefits-guide.pdf`, then uses a
  DSPy program to produce a concise answer with page citations.

DSPy may interpret a member's free text, but it cannot override the Python
guards for new-hire precedence, QLE policy, state/ZIP rate lookup, plan
recommendations, or premiums.

The policy assistant cannot modify enrollment state. Retrieval is local and
scoped to the benefits-guide PDF; only the retrieved passages are sent to the
configured language model. Every answer exposes those passages in the UI for
verification.

The Policy Q&A tab also includes six persona tests. Selecting **Run persona**
animates the persona's question character by character in the user chat bubble,
runs the currently selected retriever and DSPy answer program, then scores the
answer for the expected source page, inline citation, and required facts. The
personas cover retailer-specific glasses, hearing aids, Life Alert, combined
oral-care discounts, fitness access, a rambling multi-benefit question, and the
CDT codes D1110, D7140, and D3310. A retired federal employee persona asks
about adult orthodontic coverage, Standard in-network coinsurance, and the
lifetime maximum.
A middle-aged member persona compares the example cost of a porcelain crown
under High, Standard, and no insurance.
A parent-with-child persona compares High and Standard orthodontic costs and
lifetime maximums for a child's braces.
A rambling single-mom-in-Modesto persona tests whether the assistant can ignore
local and scheduling details and answer the underlying child-cleaning question.

**Docling auto** is the default evidence mode. It follows the existing corpus
router: exact `D####` questions use BM25 and search both the benefits guide and
the separate plan brochure with six returned pages; ordinary natural-language
questions use local BGE vector retrieval against the benefits guide. Code persona
evals require both source pages, both citations, and the expected facts.

The Policy Q&A tab can generate answers from four selectable evidence paths:
Docling hybrid (default), Docling vector, Docling BM25, or the earlier direct
PDF/BM25 index. All Docling choices reuse `agentic_search_corpus`; after local
retrieval, the selected Markdown pages are passed to the same DSPy answer
program. Retailer/glasses wording is expanded into vision, frames, lenses,
provider, participation, location, and network terms before retrieval.

Every evidence chunk carries `(document_id, plan_year, page, section)` source
identity. For supported CDT questions, the page-5 Markdown comparison table is
parsed into typed benefit records and the resolved Class A/B/C row is supplied
to the LLM as structured JSON. The model explains the selected record; it does
not align percentages across raw table columns.

The third **Retrieval comparison** tab reuses the existing implementation in
`../agentic_search_corpus/src/corpus_search.py`. It compares the current direct
PDF/BM25 path with Docling page Markdown retrieved by BM25, local BGE vectors,
or hybrid reciprocal-rank fusion. By default both sides search only the benefits
guide for a fair comparison; the UI can optionally add the separate plan brochure
to the existing corpus retriever.

For the question `is my Costco glasses covered`, the direct PDF/BM25 retriever
with vocabulary expansion and the Docling vector retriever both rank benefits
guide page 7 first. The existing plain BM25 and equal-weight hybrid fusion miss
page 7 in their top four for this wording. The UI therefore defaults the existing
RAG side to vector mode while retaining all three choices. The first vector query
may take several seconds while the local BGE model is loaded; later queries reuse
the cached resource.

## Install and run

```bash
cd /Users/dc/geha
source .venv/bin/activate
pip install -r dspy_dental_chatbot/requirements.txt
cp dspy_dental_chatbot/.env.example dspy_dental_chatbot/.env
```

Configure `DSPY_MODEL` and the provider credentials in `.env`, then:

```bash
cd /Users/dc/geha/dspy_dental_chatbot
streamlit run src/app.py --server.port 8506
```

For an OpenAI-compatible Nous endpoint, set `DSPY_MODEL`, `DSPY_API_BASE`, and
either `DSPY_API_KEY` or the existing `NOUS_KEY`. For OpenRouter, use a LiteLLM
model identifier beginning with `openrouter/` and set `OPENROUTER_API_KEY`.

## Test

The tests inject fake DSPy programs and do not call a remote model:

```bash
PYTHONPATH=src /Users/dc/geha/.venv/bin/python -m unittest -v \
  src/test_dspy_router.py src/test_policy_qa.py
```

## Policy Q&A evals

`data/policy_qa_eval_cases.json` contains grounded cases for the page 9 member
discounts: teeth whitening, electric toothbrushes, hearing aids, medical alert
systems, and fitness memberships. The default evaluation is local: it checks
that retrieval finds page 9 and that the retrieved source contains every
required fact.

```bash
PYTHONPATH=src python src/evaluate_policy_qa.py
```

To additionally score answers from the configured DSPy model for required facts
and the `[p. 9]` citation, explicitly enable the live evaluation:

```bash
PYTHONPATH=src python src/evaluate_policy_qa.py --live
```

Each run is saved under `runs/policy-qa-eval-<timestamp>/results.json`.

## Optimize

`data/router_examples.json` contains initial labeled examples. Add examples from
failed Langfuse trajectories, keep a held-out validation set, and compile:

```bash
PYTHONPATH=src python src/optimize_router.py --output compiled_router.json
```

Then set `DSPY_PROGRAM_PATH=compiled_router.json` before starting Streamlit.

## Compare with JEV

On October 8, 2026, DSPy and JEV were run without DSPy response caching on the
same held-out routing answers and the same four scripted, guarded trajectories.
The LangGraph policy rules were identical for both classifiers.

### Held-out routing cases

| Metric | JEV | DSPy |
|---|---:|---:|
| Correct | 23/26 | 23/26 |
| Clarifications | 0 | 2 |
| No match | 1 | 3 |
| Median latency | **0.10 seconds** | 0.78 seconds |
| Maximum latency | **0.28 seconds** | 2.15 seconds |
| Tokens | Not exposed | 15,345 |
| Cost | Not exposed | $0.0026 |

### End-to-end guarded trajectories

| Metric | JEV | DSPy |
|---|---:|---:|
| Personas passed | **4/4** | **4/4** |
| Total turns | 25 | 25 |
| Clarifications | 1 | 1 |
| Reprompts | 1 | 1 |
| Model calls | 22 | 22 |
| Median persona latency | **0.74 seconds** | 4.76 seconds |
| Tokens | Not exposed | 11,788 |
| Cost | Not exposed | $0.0021 |

Both implementations passed the routine-retiree, widow-QLE, new-baby-QLE, and
rambling braces/new-hire personas. DSPy correctly requested clarification for
“we got married and had a baby,” where JEV selected marriage. DSPy returned no
match when two states were stated, while JEV selected California. Conversely,
JEV recognized “we're expecting twins” as acquiring a family member, while
DSPy returned no match.

The measured accuracy is tied, so this run does not establish DSPy as more
accurate. DSPy was more conservative on some multi-intent inputs; JEV was about
6–8 times faster. The DSPy router can now be optimized on its observed failures
and rerun against the unchanged held-out set.

Saved results:

- [Held-out routing results](runs/jev-vs-dspy-20261009T020616Z/results.json)
- [End-to-end trajectory results](runs/trajectory-jev-vs-dspy-20261009T020640Z/results.json)
- [Routing comparison runner](src/compare_jev_dspy.py)
- [Trajectory comparison runner](src/compare_trajectories.py)

### Rerun the comparisons

Run both classifiers on identical held-out answers and save the raw result:

```bash
PYTHONPATH=src python src/compare_jev_dspy.py
```

Results are written under `runs/jev-vs-dspy-<timestamp>/results.json`.

For the four identical scripted end-to-end personas:

```bash
PYTHONPATH=src python src/compare_trajectories.py
```
