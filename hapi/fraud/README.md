# Claims fraud investigation: agent + live trace

A LangGraph agent (Claude Opus 5.5) investigates the local HAPI claims data for billing
fraud, choosing among raw FHIR tools (via the langcare MCP server) and claims-analytics
tools. Every step streams to a React app: Claude's reasoning summary, the tool it picked
and its arguments, the result, timings, and the final findings scored against a planted
answer key. **Synthetic data only.**

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

`run_server.sh` uses `uv` to run the server with langgraph, langchain-anthropic,
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

**Results, one run per level (2026-09-30):**

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

## Running the agent on another model (`--model`)

The agent's model is a small registry in `agent.py` (`MODELS`), selectable in the app
(dropdown next to Run), in `ladder.py --model`, and in `POST /api/runs {"model": ...}`:

| Option | Model | Notes |
|---|---|---|
| `claude` (default) | Claude Opus 5.5 (Anthropic API) | summarized reasoning in the trace; tool results capped at 30,000 characters |
| `nous` | `Hermes-4-405B` on [Nous Portal](https://portal.nousresearch.com) (OpenAI-compatible, `https://inference-api.nousresearch.com/v1`) | needs `NOUS_API_KEY`; override the model id or URL with `NOUS_MODEL` / `NOUS_BASE_URL`; tool results capped at 8,000 characters for the smaller context window |

```bash
python ladder.py --model nous          # same five levels, labelled graph/Hermes-4-405B in the ladder table
```

Everything else is shared: graph, tools, MCP server, trace, scoring. The Nous option is
wired and unit-checked (client, endpoint, missing-key error) but **has not been run**:
no Nous key was available. Expect no reasoning summaries unless the API returns
`reasoning_content`, and check that the findings JSON parses before trusting a score
(the parser accepts a fenced or a bare `{"findings": ...}` object). Check the current
model ids at the portal.

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
