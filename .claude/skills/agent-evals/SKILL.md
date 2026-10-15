---
name: agent-evals
description: Run evals on this repo's agents, RAG pipelines and classifiers, and hill-climb them (change one thing, re-measure, keep it only if it wins) without fooling yourself. Use this whenever the user wants to evaluate, benchmark, score, compare or A/B two agents, models, prompts, retrievers, scorers or workflows; asks "is X better than Y", "how good is this", "did that change help"; wants to tune, improve or optimise a metric, threshold or prompt; or asks for an eval set, a held-out test, a leaderboard or a results table. This applies even if they don't say "eval": for example "make the fraud agent find more schemes", "which chunker is best" or "try Haiku instead of Sonnet".
---

# Agent evals and hill-climbing

An eval is only useful if a result you report would still hold on cases you have never
looked at. Most mistakes come from tuning on the same cases you report on. PR #69 in this
repo is an example: it set its thresholds while looking at the test levels, so its
results were partly true by construction. The workflow below exists to prevent that, and
to make every claim come with its cost and its noise.

## Workflow

### 1. Find or define the eval
Check whether the repo already has an eval for this component (see the map below) and
reuse its data, metric and runner before writing anything new. If you need a new one,
define first:
- **the unit:** one question, provider, trajectory or task
- **the metric(s):** at least one quality metric, plus **cost** (tokens or $) and **latency**.
  A quality gain that costs 10x more is a different decision from a free one.
- **a guardrail metric** that must not get worse: false accusations, unsafe answers,
  facts missing from the context. Climbing one number while this one degrades is the
  usual way hill-climbing goes wrong.

Write these down in the eval's README or results file before running anything.

### 2. Split before you look
Freeze a **test** split that the climbing loop never sees:
```bash
python .claude/skills/agent-evals/scripts/split.py cases.jsonl --id-field id --test-frac 0.3
```
This writes `cases.dev.jsonl` and `cases.test.jsonl`, assigning each case by a hash of its
id, so the split is stable when cases are added. Many of this repo's eval files have no
`id` field. Use whichever field is unique, for example `--id-field query` for
`agentic_search/evals/retrieval_questions.jsonl`. Climb only on dev. If the eval is small
(under ~30 cases), say so: differences of one or two cases are noise.

Also keep a **shift set** if you can: cases unlike the training data, such as a new
scheme, a new document type or a new model. The `learn_then_compile` demo shows why:
a compiled workflow can look perfect on familiar cases and fail quietly on new ones.

### 3. Baseline first
Run the current system unchanged on dev and log it. Every later number is a delta
against this.

### 4. Hill-climb on dev
Change **one** thing per experiment (a prompt, threshold, model, scorer or tool), run dev,
and log it:
```bash
python .claude/skills/agent-evals/scripts/ledger.py add EXPERIMENTS.jsonl \
    --name "haiku scorer" --split dev --metric recall=0.91 --metric cost_usd=0.42 \
    --note "swapped rules scorer for Haiku" --seed 1
python .claude/skills/agent-evals/scripts/ledger.py best EXPERIMENTS.jsonl --metric recall --split dev
```
Keep a change only if it beats the current best by more than the noise. Estimate the
noise by re-running the baseline with 2–3 seeds or repeats, since LLM runs vary. A change
that wins on one seed and loses on another hasn't won. Log losing experiments too: they
show what was tried, and they stop the same idea being tried twice.

### 5. Test once
When climbing is done, run the chosen configuration **and the baseline** on the test split
(and the shift set), once each. Report those numbers. If you then change anything because of
the test result, the test split has been used for tuning: say so, or make a fresh test split.

### 6. Report
Use this shape so results can be compared across PRs:

```markdown
## Results: <component>, <date>
**Question:** <what was being decided>
**Data:** <N> dev / <M> test cases (+ <K> shift), split by `split.py` (seed/hash), never tuned on test
| config | <quality> | <guardrail> | cost $ | latency | seeds |
|---|---|---|---|---|---|
| baseline | | | | | |
| best | | | | | |
**Verdict:** <keep/drop, and by how much over the noise>
**Caveats:** <in-sample risks, small N, mocked models, assumed prices>
```

Say plainly what wasn't measured: mocked models, offline scorers, assumed prices. This
repo's PRs already do that ("Not run against a real model"); keep doing it.

## Cost and safety
- **Estimate before running anything paid**, track a running total from each run's token
  usage, and stop and ask before going over budget. Default cap: **$5** per eval session
  unless the user sets another.
- Prefer free runs first: scripted models, replays of saved traces, rule-based scorers.
  Then Haiku or Sonnet on a small slice, and Opus only if the budget clearly allows.
- Don't send member or PHI-like data to a new external API (Jev/TypeSafe, DeepSeek and so
  on) without checking with the user. The repo's data is mostly synthetic, but say what
  leaves the machine.

## Existing evals in this repo

| Component | Runner | Data / results |
|---|---|---|
| Agentic search retrieval | `agentic_search/evals/retrieval_benchmark.py`, `check_retrieval_thresholds.py` | `retrieval_questions.jsonl`, `multipaper_retrieval_questions.jsonl`, `retrieval_results.md` |
| Agentic search corpus answers | `agentic_search_corpus/evals/{compare,gemma_answer_benchmark,mimo_answer_benchmark,retrieval_benchmark}.py` | `queries.jsonl`, `*_results.md` |
| AWS RAG | `aws_rag/evals/run_eval.py`; guard: `run_guard_eval.py` | see `aws_rag/tests/test_eval_runner.py` |
| Chunking | `chunking_benchmarks_RAG/benchmark_chunkers.py`, `evaluate_*.py` | billing codes, policy sections, conditions |
| Table RAG | `avoid_failed_rag/table_RAG/evaluate.py`, `evaluate_preference_rows.py` | |
| Dental chatbot | `dspy_dental_chatbot/src/{compare_jev_dspy,compare_trajectories,evaluate_policy_qa}.py`, `dental_enrollment_chatbot/src/compare_parsers.py` | `dspy_dental_chatbot/runs/` |
| Fraud agent | `hapi/fraud/ladder.py` (levels 1–5), `compare.py` (PR #69) | `ladder_results.md` |
| Context compiler | `context_compiler/demo.py --episodes N` | recall + cost per call |
| Learn-then-compile | `learn_then_compile/demo.py --seed N` | held-out + shift sets |

Read a runner before reusing it. Check its metric definitions and whether its thresholds
were set on the same data it reports on.

## Pitfalls seen in this repo
- **Tuning on the test set** (#69's priors and profile limits). Use the split.
- **One seed:** the `learn_then_compile` routed cost ranged from 5% to 33% of the agent's
  across seeds 1–3. Report a range, not one number.
- **Ignoring the KV cache in cost:** v1 of the context compiler sent 72% fewer tokens but
  saved only 3% at first, because changing the prompt prefix broke the cache. Cost
  includes cache reads and writes, not just token counts.
- **Proxies treated as success:** "facts present in context" (recall) is not "task solved".
  Label proxies as proxies.
- **Mocked or offline models:** results from scripted models show the plumbing works,
  not that the agent is good.
