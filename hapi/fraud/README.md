# Claims fraud investigation: agent + live trace

A LangGraph agent (Claude Opus 5.5) investigates the local HAPI claims data for billing
fraud, choosing among raw FHIR tools (via the langcare MCP server) and claims-analytics
tools. Every step streams to a React app: Claude's reasoning summary, the tool it picked
and its arguments, the result, timings, and the final findings scored against a planted
answer key. Graded runs can be compiled into a cheaper fixed workflow with a router in
front of it; see [Learn, then compile to a workflow](#learn-then-compile-to-a-workflow---mode-agent--workflow--routed).
**Synthetic data only.**

```
React UI (ui/)  ──SSE──►  server.py (FastAPI :8765)  ──►  agent.py (LangGraph)
                                                          ├─ fhir_search / fhir_read ──MCP──► langcare-mcp-fhir ──► HAPI
                                                          └─ analytics tools (tools.py) ─────────────────────────► HAPI
```

## Run

```bash
cd /Users/dc/geha/hapi && docker compose up -d        # HAPI with the Synthea data (see ../README.md)
cd fraud
python3 seed_fraud.py --level 1                       # plant level 1 (see the ladder below); writes answer_key.json
(cd ui && npm install && npm run build)               # React app -> ui/dist
./run_server.sh                                       # http://localhost:8765  (needs ANTHROPIC_API_KEY)
```

`run_server.sh` uses `uv` to run the server with langchain, langgraph, langchain-anthropic,
langchain-mcp-adapters, fastapi and uvicorn, and reads `ANTHROPIC_API_KEY` from the
environment (or `../../bill_lading/.env`). For UI development, `cd ui && npm run dev`
(port 5173, proxies `/api` to 8765). `python3 seed_fraud.py --reset` removes the planted
records.

## The planted fraud (`seed_fraud.py`)

Synthea's claims contain no fraud, so the script adds two made-up providers with 77
claims (ExplanationOfBenefit) built in the same shape as Synthea's. Nothing in the FHIR
data marks them; `answer_key.json` (git-ignored, ids differ per server) has the truth.

| Provider | Scheme | Planted |
|---|---|---|
| Dr. Vincent Grayle, Summit Ridge Wellness Clinic | upcoding | 45 "Consultation for treatment" claims paid ~5-7x the peer median ($102.58) |
| | impossible day | 26 one-hour visits between 07:00 and 20:00 on 2026-03-12 |
| Dr. Lena Moravec, Heartland Home Health | billing after death | 12 home visits for 3 deceased patients, 1-10 months after death |
| | duplicate billing | 10 visits each submitted twice (same patient, day, service, amount) |

**Why each level is harder.** The amount of data barely changes: every level searches the same
4,073 genuine Synthea claims plus whatever is planted. What changes is how small the fraud is
against that background, and how many kinds of fraud the agent has to think of.

| Level | Planted claims | Share of all claims |
|---|---:|---:|
| 1 Obvious | 77 | about 1.9% |
| 2 Subtle | 65 | about 1.6% |
| 3 Spread thin | 12 | about 0.3% |
| 4 Unnamed | 214 | about 5% |
| 5 Clean | 0 | 0% |

- **The signal weakens (level 2):** the fraud is still there in volume, but each claim is only
  slightly abnormal (1.6x instead of 6x pricing; one day apart instead of the same day, which
  the exact-date duplicate tool misses).
- **The needle shrinks (level 3):** 12 claims spread across six real providers, two or three
  each, inside genuine billing histories, with no new suspicious-looking providers.
- **The hypothesis space grows (level 4):** the most claims are planted, but no tool matches
  the schemes. At levels 1-3 the agent only has to run the right checks; at level 4 it must
  first imagine what unbundling or a phantom patient would look like, then build that check
  from raw searches.
- **The answer can be "nothing" (level 5):** the agent must search everything and still
  conclude there is no fraud, which tests restraint rather than detection.

So the search space of claims stays the same; what grows is the space of possible
explanations and the difficulty of telling fraud from normal variation. The levels are not
strictly harder for every model, because levels 4 and 5 test different skills.

## Difficulty ladder (`seed_fraud.py --level N`, `ladder.py`)

`seed_fraud.py --level 1-5` plants one level (removing any earlier planting);
`ladder.py` plants each level, runs the agent, scores it and saves the trace
(`ladder_results.json`/`.md`, and the app's **Difficulty ladder** tab).

| Level | What's planted |
|---|---|
| 1 Obvious | upcoding at ~6x peers, a 26-visit day, visits after death, exact duplicates (2 providers) |
| 2 Subtle | upcoding at 1.6x on half of one provider's claims, 14 visits in a 10-hour window, duplicates re-billed **one day later**, visits 2-3 weeks after death |
| 3 Spread thin | six **existing** Synthea providers: one exact duplicate each (3) or three claims at 2.5x their own price (3) |
| 4 Unnamed | schemes no tool covers: unbundling (one blood count billed as 4 tests), weekly therapy for 26 weeks, 12 **phantom patients** (no other history, one address) |
| 5 Clean | nothing |

For the ladder the agent describes schemes in its own words (the scheme names were
removed from its output format) and may report nothing. Scoring (`scoring.py`) is by
provider: guilty providers named, whether the description matches the scheme (keyword
check), and innocent providers accused.

**Opus Results, one run per level (2026-09-30):**

| Level | Guilty found | Schemes described | Innocent accused | Tool calls | Time |
|---|---:|---:|---:|---:|---:|
| 1 Obvious | 2/2 | 4/4 | 0 | 25 | 71 s |
| 2 Subtle | 2/2 | 3/4 | 0 | 21 | 80 s |
| 3 Spread thin | 5/6 | 5/6 | 0 | 24 | 77 s |
| 4 Unnamed | 2/3 | 2/3 | 0 | 31 | 86 s |
| 5 Clean | n/a | n/a | **0** | 33 | 70 s |

- **Level 2:** missed the next-day re-billing (the duplicate tool matches exact dates);
  it did find that provider's visits after death.
- **Level 3:** missed one provider's three 2.5x claims. It flagged the three single
  duplicates at low confidence ("isolated"). It caught one upcoding provider partly
  through a seeding artifact: a cloned claim of a patient who died in 2019, moved to
  2026, also became a claim after death.
- **Level 4:** found unbundling and the weekly therapy with no tool built for either;
  missed the phantom patients.
- **Level 5:** accused no one.

One run per level: treat these as indicative, not rates. Levels 1-3 still map onto the
analytics tools; levels 4-5 are the fairer tests.

The first ladder attempt was invalid: HAPI reuses search results for 60 seconds by
default, so the tools loaded the claims from before the planting and the agent (correctly)
found nothing at level 1. HAPI's search cache is now off (`docker-compose.yml`) and the
tools send `Cache-Control: no-cache`.

## Learn, then compile to a workflow (`--mode agent | workflow | routed`)

This follows Grep.ai's AgentRun idea. The full agent does the job the expensive way: about
$1, 20-30 tool calls and 70-90 s per run. Its graded runs are kept with a note per run. A
compiler turns those runs into a fixed workflow of typed steps, and a router sends each case
to the workflow first and to the full agent only when the workflow is unsure. Each step can
be checked on its own, and every decision is recorded so it can be replayed without a model.

```
ladder.py --learn ─► runs/traces.jsonl + runs/notes.jsonl ─► compile_workflow.py ─► workflow_spec.json
                                                                                         │
question ─► code steps ─► questions, p(yes) per provider ─► research (uncertain only) ─► router
                                                                                ├─ confident: workflow findings
                                                                                └─ unsure: full agent (agent.py)
```

| Step type | What runs | Model |
|---|---|---|
| `code` | the mechanical checks in `workflow_ops.py`: peer cost (upcoding), duplicates (same day, or an isolated re-bill one day later), claims after death (death certification excluded), busiest day of short visits, and a **profile** check (claims per patient-day, weekly repeat series, patients no other provider sees) | none |
| `question` | one typed yes/no question per provider a code step flags, e.g. *"Is this consistent with billing for services after the patient's death?"*, answered with a probability (`questions.py`) | `rules` (offline logistic on the step's score), `llm` (Claude Haiku 4.5, structured output), or `jev` (TypeSafe Jev `Choice`, called as in `dental_enrollment_chatbot/src/jev_router.py`) |
| `research` | a small `create_agent` sub-agent with only `fhir_search` / `fhir_read`, behind `PermissionMiddleware(fraud_policy())`, run only for provider-scheme pairs with p in [0.3, 0.7) | `--research-model`, default `haiku` |
| `escalate` | the router: hand the case to the full agent when the least certain decision is below 0.7, or when a provider is outside the profile limits and no question explains it | the full agent's model |

`make_classifier("auto")` picks `jev` when `typesafe-sdk` is installed and `TYPESAFE_API_KEY`
is set, then `llm` when `ANTHROPIC_API_KEY` is set, and otherwise `rules`. Neither condition
holds in this checkout, so every run below used `rules`.

### Files

| File | Role |
|---|---|
| `agent.py` | `investigate(..., learn=True)` adds one model call after the report: the agent's note on its own run (`note` event: `evidence_tools`, `wasted`, `wish_known_first`, `least_sure`). The event loop is now `stream_agent()`, which the research step reuses. |
| `runs.py` | appends graded runs to `runs/traces.jsonl` and notes to `runs/notes.jsonl` (git-ignored). It adds a model-free **derived** note per agent run: which tools' results named a guilty provider, repeated, failed or truncated calls, misses, and false accusations. `python runs.py backfill [DIR]` imports older graded traces. |
| `compile_workflow.py` | runs → `workflow_spec.json` (below). `--calibrate` fits each question's logistic prior on graded workflow runs. |
| `workflow_spec.json` | the compiled spec (committed). It lists the steps, each step's `why`, `uncovered_schemes`, `hints` for the research step, and the tool statistics behind the choices. |
| `workflow_ops.py`, `questions.py` | the code steps, and the classifiers behind one `ask(node, evidence)` interface |
| `workflow.py` | spec loader and validator, runner, router (`run_routed`), `decide()` (records → findings and route) and `replay()` |
| `compare.py` | agent vs workflow table per level from `runs/`, plus a leave-one-level-out calibration replayed without models |
| `test_workflow.py` | 27 unit tests: spec loader, code steps, the three classifiers, runner, research step (scripted model; a write is refused by the policy), router, replay, compiler, notes. They use synthetic claims and need no HAPI, MCP or LLM. |

**What the compiler took from the 16 graded runs in `traces/`** (Opus, DeepSeek V4 Pro and
MiMo; backfilled with derived notes):

- **Code steps:** the four analytics tools whose results named a guilty provider became
  code steps, in the agents' usual call order: duplicates, after-death, peer cost, daily
  load (named a guilty provider in 7, 10, 6 and 11 runs). `top_services` never did and was
  left out.
- **Parameters:**
  - The duplicate window became 1 day because the notes on missed runs mention re-billing
    "one day later".
  - Death certification is excluded from the after-death step because the agents' reports
    call those claims routine paperwork.
- **Not covered:** unbundling, excessive frequency and phantom patients were found only
  through raw FHIR searches. They are listed as `uncovered_schemes` and left to the full
  agent; the profile check is what routes such cases there.

### Run it

```bash
# shell with the agent's dependencies, as in run_server.sh
alias py='uv run -q --no-project --python 3.12 --with "langchain==1.4.2" --with langchain-anthropic --with langchain-openai --with langchain-mcp-adapters --with fastapi --with uvicorn python'

py ladder.py --learn                                  # learn: full agent + its note (~$1 per level); appends to runs/
py runs.py backfill                                   # or import graded runs already in traces/
py compile_workflow.py                                # compile: runs/ -> workflow_spec.json
py ladder.py --mode workflow --questions rules --no-research          # workflow only, no model calls
py ladder.py --mode routed --no-escalate --questions rules --no-research   # router decision recorded, agent not run
py ladder.py --mode routed                            # workflow, then the full agent when unsure (needs keys)
py compile_workflow.py --calibrate                    # fit question priors on the graded workflow runs
py workflow.py replay traces/<run id>.json            # decide a saved workflow run again, no model calls
py workflow.py replay traces/<run id>.json --spec other_spec.json --reclassify   # other thresholds / priors
py compare.py                                         # results table
py -m unittest test_workflow -v                       # tests
```

`POST /api/runs {"mode": "workflow" | "routed"}` runs the same modes from the server, and the
app replays those runs: they emit the same events as the agent, and their code steps show as
analytics calls. The UI has no mode selector yet. The server runs research only when
`ANTHROPIC_API_KEY` is set.

### Results (2026-10-14, offline, one run per level)

The agent columns are the saved Opus 5.5 ladder runs from 2026-09-30. The workflow columns are
`ladder.py --mode routed --no-escalate --questions rules --no-research`: no model calls, and
the router's decision is recorded but not acted on. Each cell shows guilty providers found,
then innocent providers accused.

| Level | Agent (Opus 5.5) | Agent effort | Workflow | Workflow effort | Router | Workflow, priors fitted on the other 4 levels |
|---|---|---|---|---|---|---|
| 1 Obvious | 2/2, 0 accused | 23 calls, 140k tokens, 75 s | 2/2, 0 accused | 5 code steps, 0 tokens, 7 s | workflow | 2/2, 0 accused |
| 2 Subtle | 2/2, 0 accused | 21 calls, 357k tokens, 80 s | 2/2, 0 accused | 5, 0, 7 s | workflow | 2/2, 0 accused |
| 3 Spread thin | 5/6, 0 accused | 24 calls, 231k tokens, 77 s | 6/6, 0 accused | 5, 0, 7 s | workflow | 3/6, 0 accused |
| 4 Unnamed | 2/3, 0 accused | 31 calls, 354k tokens, 86 s | 0/3, 0 accused | 5, 0, 7 s | **escalate**: the 3 guilty providers are outside the profile limits and unexplained | 0/3, 0 accused |
| 5 Clean | 0 accused | 33 calls, 284k tokens, 70 s | 0 accused | 5, 0, 7 s | workflow | 0 accused |

- **Workflow:** found all 10 guilty providers and all 14 planted schemes at levels 1-3,
  including the next-day re-billing the agent missed at level 2. It cannot find level 4's schemes, and it
  accused no one.
- **Router:** kept levels 1, 2, 3 and 5 in the workflow and sent only level 4 to the agent.
- **Routed (estimate):** the workflow's answers at levels 1-3 and 5, plus the agent's 2/3 at
  level 4, gives 12/13 guilty providers and 0 innocent ones accused, with one agent run
  instead of five. The agent alone found 11/13.
  - The level-4 figure is the saved agent run, not a routed run: routed mode hands the agent
    the workflow's leads, and that has not been run with a real model.
- **Cost:** a workflow run here is 0 tokens and about 7 s, against 140k-357k tokens and 70-86 s
  for the agent. With the `llm` classifier, add roughly 5-10 short Haiku calls per run, plus
  research calls for uncertain items. That has not been measured.
- **Leave-one-level-out:** fitting the priors on the other four levels drops level 3 to 3/6.
  No other level has single exact duplicates, so a fitted curve treats one duplicate as noise.
  The hand-set priors also do well on level 3 because they were written with the level types
  in mind (see below).

### Limitations

- **In-sample.** I set the question priors and profile limits by looking at the clean
  Synthea baseline, which all five levels share, and knowing which scheme types the levels
  plant. So the workflow's 0 accusations at level 5, and its level-3 result, are partly by
  construction. The leave-one-level-out column is the fairer number, and it is still
  in-domain.
- **The compiler selects and parameterizes steps from a hand-written library** (one per
  analytics tool). It does not write new code. `../self-improving-agents` (learned tools,
  approved by a person) is the path to new steps.
- **Untested against live models:**
  - The `llm` and `jev` classifiers, the research sub-agent, `--learn` notes and routed
    escalation were tested only with mocked or scripted models, not on the ladder. No
    Anthropic key is set in this checkout and `typesafe-sdk` is not installed.
  - Jev would send each provider's aggregates (synthetic) to TypeSafe's API.
  - The LLM classifier's probability is self-reported, not calibrated. `--calibrate` fits only
    the `rules` priors.
- **The backfilled runs have only derived notes**, so `hints` is empty. Agent-written notes
  appear after `ladder.py --learn` runs.
- **Routing is per run, not per claim.** The whole claims database is one case.
- **The router's margin is thin.** Its confidence is 0.731 on every level. The cause is one
  Synthea provider's single next-day repeat (p = 0.27), against a threshold of 0.7.
- **No mode selector in the UI;** `ladder_results.md` gained a Mode column.

## Running the agent on another model (`--model`)

The agent's model is a small registry in `agent.py` (`MODELS`), selectable in the app
(dropdown next to Run), in `ladder.py --model`, and in `POST /api/runs {"model": ...}`:

| Option | Model | Notes |
|---|---|---|
| `claude` (default) | Claude Opus 5.5 (Anthropic API) | summarized reasoning in the trace; tool results capped at 30,000 characters |
| `nous` | `deepseek/deepseek-v4-pro` on [Nous Portal](https://portal.nousresearch.com) (OpenAI-compatible gateway, `https://inference-api.nousresearch.com/v1`) | needs `NOUS_API_KEY` (or `NOUS_KEY`); pick any portal model with `NOUS_MODEL`; override the URL with `NOUS_BASE_URL` |
| `sonnet`, `haiku`, `gpt-4o`, `gpt-5` | Claude Sonnet 5.5, Claude Haiku 4.5, OpenAI | wired but not run on the ladder; the OpenAI options need `OPENAI_API_KEY` |

```bash
python ladder.py --model nous                                      # DeepSeek V4 Pro
NOUS_MODEL=<portal model id> python ladder.py --model nous       # any other portal model
```

Everything else is shared: graph, tools, MCP server, prompt, trace, scoring. The portal
listed no Hermes models on 2026-09-30, so the default is DeepSeek V4 Pro. If a model is
slow to answer, raise `LANGCHAIN_OPENAI_STREAM_CHUNK_TIMEOUT_S` (default 120 seconds).

### Model comparison (2026-09-30)

Same prompt, tools and planted data for every model; one run per level. Each cell is
guilty providers found, then innocent providers accused.

| Level | Claude Opus 5.5 | DeepSeek V4 Pro (Nous) |
|---|---|---|
| 1 Obvious | 2/2, 0 accused | 2/2, 0 accused |
| 2 Subtle | 2/2, 0 accused | 1/2, 6 accused |
| 3 Spread thin | 5/6, 0 accused | 4/6, 1 accused |
| 4 Unnamed | 2/3, 0 accused | 0/3, 6 accused |
| 5 Clean | 0 accused | 8 accused |
| Tool calls per level | 21-33 | 47-90 |
| Time per level | 70-86 s | 4.5-6.5 min |

- **Claude Opus 5.5** found 11 of 13 planted providers and accused no innocent one.
- **DeepSeek V4 Pro** found 7 of 13 and accused 21 innocent providers, 8 of them on the
  clean level, where the prompt says there may be no fraud at all.

One run per level, so single cells may be luck; the false-accusation gap is the consistent
difference.

HIPAA may prevent outside LLMs from accessing the data. Anonymizing the data may remove
the evidence signals needed for fraud analysis.

## Tools the agent chooses from

| Tool | Kind | What it returns |
|---|---|---|
| `fhir_search`, `fhir_read` | raw records (FHIR MCP) | any FHIR resource |
| `provider_billing_summary` | analytics | providers ranked by total/average paid or volume |
| `top_services` | analytics | most-billed services with median and 90th-percentile paid |
| `service_cost_by_provider` | analytics | each provider's pay for one service vs the median of the *other* providers |
| `find_duplicate_claims` | analytics | same patient + day + service + amount groups |
| `claims_after_patient_death` | analytics | claims dated after the patient's death |
| `provider_daily_load` | analytics | a provider's busiest days: claims, patients, billed minutes |

Nothing tells the agent which providers or schemes to look for. The peer comparison
excludes each provider's own claims: with them included, Grayle's 45 claims set the
median and he looked normal (1.15x instead of 6.08x).

## Results (2026-09-29)

**What the agent was and wasn't told.** It was not told which providers, services,
dates or amounts to look at; it found those itself and confirmed them in the raw
records. But the scheme *types* were given away by the design:

- the required findings format lists them: `"scheme": "upcoding | impossible_day | after_death | duplicates | other"`;
- the analytics tools map one-to-one onto the planted schemes (`find_duplicate_claims`,
  `claims_after_patient_death`, `provider_daily_load` for the impossible day,
  `service_cost_by_provider` for upcoding), and the system prompt describes them;
- `service_cost_by_provider` was changed to compare against *other* providers after
  a first version missed the upcoding, with the answer known.

So this shows the agent matching providers to a checklist of fraud types, with correct
amounts and evidence, not open-ended discovery. A fairer test would drop the scheme
names from the output format, replace the one-per-scheme tools with a generic
group-and-aggregate tool, and plant schemes nothing mentions (e.g. unbundling, a
referral ring, excessive units).


Planted vs found, latest run (`20260930T030348Z-c12551`; the other two completed runs match):

| Planted scheme | Planted | Agent found | Match |
|---|---|---|---|
| **Upcoding** · Dr. Grayle | 45 claims, $28,051.75 paid, ~6x peers | 45 claims at **6.08x** the peer median; **$23,435.55** at risk | ✓ Claim count exact; the dollar figure is the overpayment above the peer rate, not total paid |
| **Impossible day** · Dr. Grayle | 26 one-hour visits on 2026-03-12 | **27** claims, 1,620 minutes (27 hours) that day | ✓ 27 is correct: one randomly dated upcoded claim also fell on that day, so the answer key's 26 was off by one |
| **Billing after death** · Dr. Moravec | 12 home visits for 3 deceased patients, $1,381.53 | 12 claims, **$1,381.53** | ✓ Exact |
| **Duplicate billing** · Dr. Moravec | 10 pairs, $1,129.25 overpaid | 10 pairs, **$1,129.25** | ✓ Exact; the first run listed all 10 pairs by claim id |

It also avoided false positives: Synthea's own claims dated after death (6 death-certificate
claims from other providers) were treated as normal paperwork, and high-dollar providers
with one or two patients were checked and dismissed. The comparison is by provider, scheme,
counts and dollars; not every one of the 77 planted claim ids appears in each report.

Three runs, each 24-26 tool calls and 67-79 s, found all four schemes with the planted
dollar amounts: after-death $1,381.53 and duplicates $1,129.25 exactly; upcoding
45 claims at 6.08x peers ($23,435.55 above the peer rate). The agent reported 27 claims on
the impossible day, which is right: one randomly dated upcoded claim also fell on
2026-03-12 in this seeding (the script now avoids that day). About $0.70-$1.30 of Claude
usage per run.

The first two runs also took shortcuts through load artefacts: the planted providers
have adjacent resource ids, and one run searched `_lastUpdated` for "injected" records.
The system prompt now forbids using ids and storage metadata to find suspects; the third
run used none and still found all four. Synthea itself bills a few claims after death
(death certificates); the agent separated those from Moravec's pattern.

## The app

- **Investigation**: start a run or replay one; live timeline of steps (Claude's reasoning
  summary, the tools it called in parallel with arguments, timings and results), a
  per-step strip showing how many of the 8 tools it chose, and findings scored against
  the answer key.
- **Tool choices**: a step × tool grid (every tool is available at every step; filled
  cells are the ones chosen, with counts) next to the reasoning that led to each choice,
  plus the questions more than one tool can answer and which one the agent used.
- **Run history**: every saved run with status, score, steps, tool calls, time, tokens,
  and the error for failed runs; click one to replay it.

Tool results are capped at 30,000 characters before the model sees them, with a note to
narrow the call. Without the cap, one `fhir_search` for all 2026 claims returned 4.1 MB
and overflowed the 1M-token context (the failed run in the history); results cut this way
are marked "cut for model" in the timeline.

## Trace format

`agent.investigate()` emits `run_start` (tools on offer), `thinking` (Claude's summarized
reasoning), `text`, `tool_call`, `tool_result` (preview, size, ms, error and truncation flags), `final`
(report + parsed findings JSON) and `done` (tool calls, seconds, tokens). The server keeps
runs in memory, streams them as Server-Sent Events, and saves each to `traces/<id>.json`
for replay from the UI.

Workflow and routed runs (`workflow.py`) emit the same events. Their code steps appear as
`tool_call` / `tool_result` with source `analytics`, each question as a `text` line with its
probabilities, and research calls as FHIR calls. They add `workflow_node` events: the spec
and its hash, each code step's output, each question's evidence, probabilities, backend and
model, each research answer, and the route. `replay()` decides a run again from those
records alone. Learning-mode agent runs add a `note` event. `done` carries `mode`,
`escalated` and, with `--no-escalate`, `would_escalate`.
