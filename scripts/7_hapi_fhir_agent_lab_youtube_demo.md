# YouTube Demo Script: Synthetic FHIR, MCP Agents, Fraud Workflows, and Held-Out Improvement

**Target length:** 18–22 minutes  
**Application:** `hapi` and its active subdirectories  
**Audience:** AI solution architects, healthcare data engineers, agent developers, and governance teams  
**Central message:** Healthcare agents need a controlled data and evaluation environment. This lab uses synthetic FHIR records to demonstrate read-only MCP access, deterministic analytics, inspectable agent traces, workflow compilation, and teacher-guided prompt and tool improvement without exposing real patient data.

## Recommended video title

**Building Governed Healthcare Agents with FHIR, MCP, and Evaluations**

## Thumbnail text

**FHIR + MCP + Agents**

## What this video should demonstrate

1. HAPI FHIR R4 and PostgreSQL provide a local standards-based data foundation populated only with synthetic Synthea records.
2. The language model never connects directly to PostgreSQL; it receives selected FHIR tools through a local MCP bridge.
3. Read-only tool filtering and permission middleware constrain what an agent can do.
4. The pharmacy example joins synthetic member medication records with public RxNorm and openFDA services through three MCP servers.
5. `claim_insights` performs deterministic, source-linked checks without an LLM.
6. The fraud application exposes every model step, tool call, result size, latency, citation source, score, and saved trace.
7. Graded agent runs can be compiled into a cheaper fixed workflow with escalation for cases the workflow cannot explain.
8. `self-improving-agents` changes prompts and proposed tools, not model weights; changes are accepted only when held-out evaluation improves.
9. Every result is a controlled synthetic experiment, not a clinical, fraud, coverage, payment, or production claim.

## Project map

| Path | Role in the demonstration |
| --- | --- |
| `hapi/docker-compose.yml` | Local HAPI FHIR R4 server and PostgreSQL |
| `hapi/synthea/` and `load_synthea.sh` | Deterministic synthetic-patient generation and loading |
| `hapi/bin/` and `langcare-config.yaml` | Local stdio MCP bridge to FHIR |
| `hapi/mcp_agent_demo.py` | Minimal Anthropic tool-use loop over read-only FHIR tools |
| `hapi/langgraph_agent.py` | LangChain agent with MCP adapters and permission middleware |
| `hapi/pharmacy_agent.py` | Multi-MCP join across FHIR, RxNorm, and openFDA |
| `hapi/claim_insights/` | Deterministic claimant/provider conflict and comorbidity checks |
| `hapi/fraud/` | React/FastAPI fraud investigation, evaluation ladder, and workflow compilation |
| `hapi/self-improving-agents/` | Held-out prompt lessons and human-reviewed learned-tool experiment |

The subprojects share the same synthetic FHIR foundation, but they are not one monolithic application. Run only the chapter being demonstrated.

## Before recording

### Start the synthetic FHIR stack

The ignored `.env` must contain the same database credentials that initialized the existing named volume:

```bash
cd /Users/dc/geha/hapi
docker compose up -d
docker compose ps
curl -fsS http://localhost:8080/fhir/metadata > /dev/null \
  && echo 'FHIR is ready'
```

Local endpoints:

```text
HAPI browser:     http://localhost:8080
FHIR R4 base:     http://localhost:8080/fhir
Capability:       http://localhost:8080/fhir/metadata
```

The Compose port binds to `127.0.0.1`. This is still a development server with no application login or TLS.

### Load deterministic synthetic records if needed

```bash
cd /Users/dc/geha/hapi
./load_synthea.sh 50 Missouri
```

This runs the bundled Synthea JAR in a Java 17 container with seed 42 and loads organization, practitioner, and patient bundles into HAPI. It adds records; it does not empty the database first.

Do not rerun this immediately before recording when the existing FHIR data already supports the saved fraud and claim-insight cases.

### Confirm the MCP bridge

The generated bridge binary should exist here:

```text
/Users/dc/geha/hapi/bin/langcare-mcp-fhir
```

Check it without exposing credentials:

```bash
test -x /Users/dc/geha/hapi/bin/langcare-mcp-fhir \
  && echo 'MCP bridge is available'
```

### Validate the local foundation

```bash
cd /Users/dc/geha/hapi
docker compose config --quiet
curl -fsS 'http://localhost:8080/fhir/Patient?_summary=count'
curl -fsS 'http://localhost:8080/fhir/ExplanationOfBenefit?_summary=count'
```

### Validate permission and workflow contracts

```bash
cd /Users/dc/geha
uv run --no-project --python 3.12 \
  --with 'langchain==1.4.2' \
  --with langchain-anthropic \
  --with langchain-openai \
  --with langchain-mcp-adapters \
  --with pyyaml \
  --with httpx \
  python -m unittest \
    agent_permissions.test_permissions \
    agent_permissions.test_agents_smoke -v
```

```bash
cd /Users/dc/geha/hapi/fraud
uv run --no-project --python 3.12 \
  --with 'langchain==1.4.2' \
  --with langchain-anthropic \
  --with langchain-openai \
  --with langchain-mcp-adapters \
  --with httpx \
  python -m unittest test_workflow -v
```

These tests do not establish production healthcare compliance. They verify the demo's declared permission and workflow behavior.

### Build both React applications

```bash
cd /Users/dc/geha/hapi/fraud/ui
npm install
npm run build

cd /Users/dc/geha/hapi/self-improving-agents/ui
npm install
npm run build
```

Both FastAPI applications use port 8765. Run only one at a time.

### Prepare the recording views

1. Open the HAPI browser at `http://localhost:8080`.
2. Keep a terminal in `/Users/dc/geha/hapi` for direct FHIR and MCP calls.
3. Open `/Users/dc/geha/hapi/README.md` at the architecture diagram.
4. Start the fraud UI first and open `http://127.0.0.1:8765`.
5. Keep `fraud/ladder_results.md` and the workflow comparison table ready.
6. Stop the fraud server before starting the self-improvement UI on the same port.
7. Keep `self-improving-agents/improve_results.md` and `lessons.md` ready.
8. Hide `.env`, API keys, local shell history, and unrelated browser tabs.

### Provider boundaries

- `ANTHROPIC_API_KEY` is required for new Claude agent runs.
- `NOUS_API_KEY` or `NOUS_KEY` is required for new DeepSeek runs through Nous.
- `OPENAI_API_KEY` is needed only for the selectable OpenAI model paths.
- RxNorm and openFDA use public network services through local stdio MCP processes.
- Replaying saved traces and inspecting recorded evaluation results does not require a new paid model call.

Use saved runs for the main recording. Live fraud ladder and improvement loops take minutes and can incur material model cost.

## Main recording script

### 0:00–0:45 — Hook: healthcare agents need a controlled laboratory

**On screen**

- Show HAPI, a FHIR JSON response, the fraud trace UI, and the self-improvement score panel in quick succession.

**Narration**

> A healthcare agent demo should not begin by giving a language model unrestricted access to a clinical database.
>
> This lab begins with fictional Synthea patients in a local FHIR server. It exposes a small read-only tool surface through MCP, applies permission policy before each call, preserves traces, grades known synthetic cases, and promotes an optimization only when it improves held-out performance.
>
> The goal is not autonomous healthcare decision making. The goal is to make data access, reasoning, evaluation, cost, and failure modes inspectable.

### 0:45–2:00 — HAPI FHIR and Synthea foundation

**On screen**

- Show the architecture section in `hapi/README.md`.
- Open the HAPI capability statement.
- Run a small count or patient search.

```bash
F=http://localhost:8080/fhir
curl -s "$F/Condition?code=http://snomed.info/sct%7C44054006&_summary=count"
curl -s "$F/Observation?code=http://loinc.org%7C4548-4&_sort=-date&_count=3"
```

**Narration**

> HAPI FHIR R4 runs locally with PostgreSQL. Synthea supplies deterministic fictional patients, encounters, conditions, observations, medications, and insurance claims represented as FHIR resources.
>
> A condition search uses standard terminology—SNOMED CT 44054006 for type 2 diabetes. An observation search uses LOINC 4548-4 for HbA1c.
>
> The database is implementation detail. Agents do not receive SQL access. They interact with the FHIR API through explicit tools, so every request remains resource- and parameter-shaped.

**On-screen callout**

```text
Synthea bundles → HAPI FHIR R4 → PostgreSQL
                         ↓
                   local MCP bridge
                         ↓
              selected read-only tools
```

### 2:00–3:20 — Minimal MCP agent and permission boundary

**On screen**

- Show `mcp_agent_demo.py` filtering the tool list.
- Run the minimal example only if a live provider call is acceptable.

```bash
cd /Users/dc/geha/hapi
uv run --no-project --python 3.12 --with anthropic \
  python mcp_agent_demo.py \
  'Find members with type 2 diabetes and their latest HbA1c.'
```

**Narration**

> The MCP bridge may support more operations, but this client offers the model only `fhir_search` and `fhir_read`. The terminal prints every call and its arguments before the result returns.
>
> The LangChain version adds shared permission middleware. Allowed FHIR reads proceed. Writes and unknown tools require approval; in an unattended command they are denied.
>
> Tool filtering limits what the model sees. Middleware checks what it tries to call. Those are defense-in-depth controls, not substitutes for server-side authentication and authorization.

### 3:20–4:35 — Multi-source pharmacy agent

**On screen**

- Show the three MCP servers in `pharmacy_agent.py`.
- Point out the allowed-tool subsets for each server.

**Narration**

> The pharmacy example uses one agent over three MCP servers. Local HAPI supplies synthetic member medications. RxNorm normalizes drug identifiers and ingredients. openFDA supplies public labels, shortages, NDC information, and recall searches.
>
> The model receives only a selected subset of each server's tools. Member data stays in the local FHIR path while drug-reference requests go to public NLM and FDA services.
>
> A recall result can identify a potentially relevant public notice. It cannot prove that a member received the recalled lot. The agent prompt requires that distinction.

**Optional live command**

```bash
cd /Users/dc/geha/hapi
uv run --no-project --python 3.12 \
  --with 'langchain==1.4.2' \
  --with langchain-anthropic \
  --with langchain-mcp-adapters \
  --with pyyaml \
  python pharmacy_agent.py
```

This requires Node.js, `npx`, network access, HAPI, and the external services.

### 4:35–5:45 — Deterministic claim insights without an LLM

**On screen**

- Show `claim_insights/find_insights.py`.
- Run the seeded check and show evidence resource references.

```bash
cd /Users/dc/geha/hapi/claim_insights
python3 seed_claimant.py
python3 find_insights.py --check
python3 find_insights.py --json
```

**Narration**

> Not every problem needs an agent. The claim-insight experiment is deterministic code over FHIR.
>
> It compares claimant-authored condition statements with provider records and identifies later active comorbidities. Every output names the relevant Condition and DocumentReference resources.
>
> The seeded statements create controlled conflict cases because Synthea does not generate claimant correspondence. The resulting text is templated research output, not a disability, coverage, clinical, or return-to-work determination.

### 5:45–6:55 — Why the fraud experiment is controlled

**On screen**

- Start or replay the fraud application.
- Show the planted-scheme table and the difficulty ladder.

```bash
cd /Users/dc/geha/hapi/fraud
python3 seed_fraud.py --level 1
./run_server.sh
```

Open `http://127.0.0.1:8765`.

**Narration**

> Synthea does not contain labeled fraud, so the experiment plants synthetic schemes and writes a separate answer key. The agent does not receive that key.
>
> Level one contains obvious upcoding, an impossible service day, claims after death, and exact duplicates. Later levels make pricing less extreme, spread anomalies across existing providers, introduce schemes no dedicated tool names, and finally plant nothing.
>
> The clean level is essential. A system that identifies every guilty provider but accuses innocent providers is not successful.

### 6:55–8:35 — Replay an inspectable fraud trace

**On screen**

- Open a saved run in **Run history**.
- Walk through reasoning summaries, tool calls, arguments, result latency and size.
- Show the final scored findings.

**Narration**

> The React application streams events from FastAPI with Server-Sent Events. Each model step shows the reasoning summary, selected tools, arguments, latency, preview, error status, and whether a large result was truncated before reaching the model.
>
> The agent has raw FHIR search and read plus purpose-built claims analytics: provider summaries, service cost versus peers, duplicates, claims after death, and daily workload.
>
> The final report is parsed into findings and scored against the planted answer key. The trace is saved as JSON and can be replayed without rerunning the model.
>
> This supports error analysis. A miss can be assigned to a tool gap, a tool-selection failure, a misleading tool result, an evidence interpretation error, or a final-report omission.

### 8:35–9:40 — Tool choices and bounded context

**On screen**

- Open **Tool choices**.
- Show the step-by-tool matrix and overlapping tool capabilities.
- Point to a truncated result marker in a saved trace if available.

**Narration**

> The tool-choice view distinguishes tools that were available from tools the model actually selected. It also reveals overlapping paths to the same question.
>
> Raw FHIR search is flexible but can return entire records. One unrestricted search returned 4.1 megabytes and overflowed the model context. Tool results are now capped at 30,000 characters and marked `cut for model`, prompting a narrower query.
>
> Context-window management is part of agent reliability. A correct tool with an unbounded response can still make the system fail.

### 9:40–10:55 — Difficulty ladder and model comparison

**On screen**

- Open **Difficulty ladder**.
- Show the saved Opus results across levels 1–5.
- Then show the documented Opus versus DeepSeek comparison.

**Narration**

> The ladder varies more than anomaly size. Level three hides a small signal inside existing providers. Level four introduces unbundling, long repetitive treatment, and phantom patients without matching dedicated tools. Level five tests whether the agent can conclude that no fraud was planted.
>
> In one saved five-level run, Opus found 11 of 13 planted providers and accused no innocent provider. In the documented comparison, DeepSeek found 7 of 13 and accused 21 innocent providers. These are single runs, not statistical rates, but the false-accusation gap motivated the improvement experiment.

### 10:55–12:45 — Learn from traces, then compile a workflow

**On screen**

- Show the `Learn, then compile to a workflow` diagram in `fraud/README.md`.
- Show `workflow_spec.json` and the offline result table.

**Narration**

> Repetitive investigations do not need to remain expensive open-ended agents forever.
>
> Graded agent traces and notes identify mechanical checks that can become typed workflow steps. Code performs duplicates, after-death, peer-cost, daily-load, and profile checks. Typed questions classify flagged provider-scheme pairs. A small research agent is reserved for uncertain evidence. The full agent is the final escalation path.
>
> In the saved offline comparison, the workflow used five code steps, zero model tokens, and about seven seconds per level. It found all ten guilty providers in levels one through three and accused no one, but it could not detect level four's new schemes. The router therefore kept levels one, two, three, and five in the workflow and marked level four for escalation.
>
> The reported routed result is partly an estimate using a saved agent result for level four. The complete routed path with live model escalation has not been measured and should not be presented as if it has.

**On-screen callout**

```text
graded agent traces
        ↓
compile typed steps
        ↓
workflow → confident result
        └→ uncertain or unexplained → research → full-agent escalation
```

### 12:45–13:35 — Workflow limitations matter

**On screen**

- Highlight the limitations directly below the comparison table.

**Narration**

> This workflow is still a research result. Its step library is hand written. Priors and profile limits were chosen with knowledge of the synthetic schemes. Leave-one-level-out calibration weakens the level-three result. The live Jev classifier, LLM classifier, research sub-agent, and routed escalation were tested with mocks rather than measured across the ladder.
>
> Compilation reduces cost only for recurring, well-understood patterns. New or unexplained cases still need escalation.

### 13:35–14:05 — Switch applications safely

**On screen**

- Stop the fraud server.
- Start the self-improvement server.

```bash
# Stop fraud/run_server.sh with Ctrl-C first.
cd /Users/dc/geha/hapi/self-improving-agents
./run_server.sh
```

Open `http://127.0.0.1:8765` again.

**Narration**

> The fraud and self-improvement applications are separate builds that share port 8765. I stop one before starting the other. The self-improvement interface reads saved experiment artifacts; it does not invent progress in the browser.

### 14:05–15:35 — What self-improving means—and does not mean

**On screen**

- Open **Self-improvement**.
- Follow the five phases: baseline, train and grade, teacher reflection, held-out test, acceptance gate.

**Narration**

> DeepSeek's weights do not change. A stronger teacher analyzes graded errors and proposes reusable prompt lessons or a candidate analytics tool.
>
> The loop measures a baseline on held-out variants, trains on different cases, reflects on misses and false accusations, reruns the held-out cases, and keeps the change only when the held-out score improves.
>
> The system prompt remains unchanged. Accepted lessons are appended from `lessons.md`. Candidate Python tools remain unavailable until validation and human approval. The precise description is teacher-guided prompt and tool optimization with held-out evaluation—not recursive self-improvement, fine-tuning, or model-weight training.

### 15:35–17:05 — Read the held-out result and effort tradeoff

**On screen**

- Compare **Baseline without lessons** against **Held-out test with learned lessons**.
- Show net score, guilty providers found, false accusations, tool calls, tokens, and accepted lessons.

**Narration**

> The score is guilty providers found minus innocent providers accused. A false accusation costs a point so that accusing every provider cannot win.
>
> On the saved five held-out cases, DeepSeek improved from 3 of 13 guilty providers found with 14 innocent accusations—a net score of minus 11—to 11 of 13 found with zero innocent accusations, a score of 11.
>
> The improvement was not free. Input increased from 2.1 million to 20.8 million tokens, and tool calls rose to 82 through 173 per case. Recorded cost increased from about eight cents to about 62 cents per case. The lessons improved accuracy by making the model check far more evidence.
>
> Opus already had a perfect held-out baseline in that experiment, so its proposed lessons were rejected. The acceptance gate is model- and baseline-specific.

### 17:05–18:20 — Learned tools: passing a unit check is not enough

**On screen**

- Show the learned-tools review table.
- Compare the revoked next-day-rebill tool with the approved isolated version.

**Narration**

> The toolsmith path demonstrates a second acceptance problem. A first next-day-rebilling tool technically found the missed provider, but ranked it behind legitimate daily-care patterns. DeepSeek then used the noisy result to dismiss the real fraud. The tool was revoked.
>
> The acceptance check was tightened from appearing anywhere to ranking the missed provider in the top three. A revised isolated-next-day-rebilling tool excluded recurring daily series. On the test case it listed only the actual rebiller and recovered the targeted scheme.
>
> Even then, the complete case did not improve because the agent missed another provider. A tool can fix its target metric while redirecting attention and harming the overall task. Promotion therefore needs held-out end-to-end evaluation, noise measurement, and human review—not only a unit test.

### 18:20–19:20 — Error analysis across the lab

**On screen**

- Show the trace, answer key, workflow comparison, and accepted/rejected lesson panel.

**Narration**

> This lab supports four levels of error analysis.
>
> First, data errors: stale FHIR search caching once made a valid seeded case appear empty, so search-result reuse was disabled. Second, tool errors: a peer median originally included the suspect provider and hid its own upcoding. Third, agent errors: the model may skip a tool, stop early, or misread noisy evidence. Fourth, evaluation errors: an answer key can be wrong, a seed can create an artifact, and one run per case can exaggerate luck.
>
> The first failing stage should be fixed before changing models or adding more autonomy.

### 19:20–20:05 — Close

**On screen**

- Return to the HAPI architecture and then the held-out acceptance gate.

**Narration**

> The value of this project is not a claim that an agent can autonomously investigate healthcare data.
>
> It is a layered engineering pattern: synthetic standards-based data, narrow MCP tools, explicit permissions, deterministic analytics where possible, visible traces, answer keys, difficulty ladders, workflow compilation, held-out evaluation, and human approval for new capabilities.
>
> That is how an agent experiment becomes measurable before anyone considers production healthcare use.

## Optional command appendix for the recording

### Direct LangChain FHIR agent

```bash
cd /Users/dc/geha/hapi
uv run --no-project --python 3.12 \
  --with 'langchain==1.4.2' \
  --with langchain-anthropic \
  --with langchain-mcp-adapters \
  --with pyyaml \
  python langgraph_agent.py
```

### Replay the deterministic claim-insight check

```bash
cd /Users/dc/geha/hapi/claim_insights
python3 find_insights.py --check
```

### Run workflow mode without model calls

Use the dependency shell documented in `hapi/fraud/README.md`, then:

```bash
cd /Users/dc/geha/hapi/fraud
python ladder.py --mode workflow --questions rules --no-research
python compare.py
```

### Replay a saved workflow trace

```bash
cd /Users/dc/geha/hapi/fraud
python workflow.py replay traces/<run-id>.json
```

### Run the complete improvement experiment

This is expensive and slow; do not start it casually during a recording:

```bash
cd /Users/dc/geha/hapi/self-improving-agents
python improve.py --model nous
```

## Error-analysis checklist

| Symptom | First stage to inspect | Evidence |
| --- | --- | --- |
| No FHIR records after seeding | Data loading or stale search | HAPI counts, loader output, cache settings |
| Tool is unexpectedly available | MCP filtering or permission policy | `tools/list`, bound tool names, middleware decision |
| Correct resource exists but agent misses it | Query construction or tool selection | Tool arguments, FHIR Bundle, trace sequence |
| Model context overflows | Tool-result scope | Result size, truncation flag, `_count`, `_elements` |
| Fraud provider is missed | Analytics gap or interpretation | Tool matrix, raw records, planted key, final findings |
| Innocent provider is accused | Evidence quality or stopping rule | Competing explanations, peer baseline, clean level |
| Workflow succeeds only in-domain | Overfitting | Uncovered schemes, leave-one-level-out result, escalation |
| Lesson helps training but not test | Prompt overfitting | Baseline, train, held-out variants, acceptance decision |
| Learned tool finds target but hurts task | Ranking/noise/attention shift | Clean-data noise, top rank, complete held-out score |

## Claims to avoid

- Do not describe any data in this repository as real patient or production claims data.
- Do not call the local HAPI deployment HIPAA-ready or production-secure.
- Do not say MCP tool filtering replaces server-side authorization.
- Do not claim a public FDA recall proves a member received a recalled lot.
- Do not call a planted fraud experiment a validated real-world fraud detector.
- Do not present one run per level as an accuracy rate.
- Do not claim the compiled workflow discovers novel schemes it has never represented.
- Do not call `self-improving-agents` model training, fine-tuning, distillation, or autonomous RSI.
- Do not claim an LLM or workflow should autonomously deny claims, accuse providers, or make clinical decisions.
- Do not expose API keys, FHIR identifiers from any non-synthetic source, or unreviewed private data in a recording.

## Post-recording cleanup

Stop the active React/FastAPI application with `Ctrl-C`, then preserve or stop the FHIR stack:

```bash
cd /Users/dc/geha/hapi
docker compose stop
```

This preserves the named PostgreSQL volume. Use `docker compose down` to remove the containers while retaining the volume.

Do **not** run `docker compose down -v` unless you intentionally want to delete all local FHIR data and recreate the experiment from scratch.
