# Local Synthetic FHIR and Agent Lab

This directory is a local development environment for experimenting with FHIR,
MCP tools, and healthcare-oriented agents without using real patient data. It
combines a Dockerized HAPI FHIR R4 server, deterministic Synthea records, a
read-only MCP bridge, and several agent demonstrations.

This is a research sandbox, not a deployable clinical system. The HAPI endpoint
has no application authentication or TLS and every included workflow assumes
synthetic data.

## What is here

| Component | Purpose | Entry point |
|---|---|---|
| HAPI FHIR + PostgreSQL | Persistent local FHIR R4 data store | [`docker-compose.yml`](docker-compose.yml) |
| Synthea loader | Generate and load repeatable synthetic records | [`load_synthea.sh`](load_synthea.sh) |
| MCP bridge | Expose the local FHIR server as MCP tools | [`langcare-config.yaml`](langcare-config.yaml) |
| Direct MCP agent | Minimal Anthropic tool-use loop | [`mcp_agent_demo.py`](mcp_agent_demo.py) |
| LangChain FHIR agent | `create_agent` with read-only FHIR tools and permission middleware | [`langgraph_agent.py`](langgraph_agent.py) |
| Pharmacy agent | Join FHIR medication data with RxNorm and openFDA | [`pharmacy_agent.py`](pharmacy_agent.py) |
| Fraud investigation app | React/FastAPI comparison of agent, compiled workflow, and routed modes | [`fraud/README.md`](fraud/README.md) |
| Self-improving agent app | Teacher-guided prompt and tool optimization experiment | [`self-improving-agents/README.md`](self-improving-agents/README.md) |
| Claim insights | Detect planted claimant/provider conflicts and later comorbidities | [`claim_insights/`](claim_insights/) |

The repository root is not one monolithic application. Start the FHIR stack,
then run only the agent or UI needed for the experiment.

## Architecture

```text
Synthea JAR
    |
    | FHIR transaction bundles
    v
HAPI FHIR R4 (localhost:8080) <----> PostgreSQL
    |
    | local stdio MCP bridge
    v
langcare-mcp-fhir
    |
    +--> direct MCP demo
    +--> LangChain FHIR agent
    +--> pharmacy agent (+ RxNorm and openFDA)
    +--> fraud and self-improving agent applications
```

The agents receive ordinary FHIR JSON from tool calls. The language model does
not connect directly to PostgreSQL.

## Quick start

### Prerequisites

- Docker Desktop with Docker Compose
- `curl`
- `uv` for the Python agent commands
- the Synthea release JAR at
  `synthea/synthea-with-dependencies.jar`
- Go only if the MCP bridge binary must be built
- Node.js and `npx` for the React UIs and public drug-data MCP servers

The Synthea JAR, generated output, MCP binary, environment file, and runtime
traces are intentionally not committed.

### 1. Configure the database once

```bash
cd /Users/dc/geha/hapi
printf 'HAPI_DB_USER=hapi\nHAPI_DB_PASSWORD=replace-with-a-long-random-password\n' > .env
```

The password initializes PostgreSQL when its Docker volume is first created.
Do not replace the password in `.env` while reusing that volume; HAPI will then
fail database authentication because PostgreSQL retains the original password.

### 2. Start HAPI FHIR

```bash
docker compose up -d
docker compose ps
curl -fsS http://localhost:8080/fhir/metadata > /dev/null && echo 'FHIR is ready'
```

Local endpoints:

- HAPI browser: <http://localhost:8080>
- FHIR R4 base: <http://localhost:8080/fhir>
- Capability statement: <http://localhost:8080/fhir/metadata>

The Compose file binds HAPI to `127.0.0.1`; it is not exposed to other hosts.

### 3. Generate and load synthetic records

```bash
./load_synthea.sh 50 Missouri
```

The arguments are patient count and state. The script:

1. waits for HAPI to become ready;
2. clears the previous local Synthea output directory;
3. runs the bundled JAR in a Java 17 container with seed `42`;
4. loads hospital and practitioner bundles before patient bundles; and
5. prints resource counts from HAPI.

No local Java installation is needed. Override the destination with `FHIR_BASE`
when necessary:

```bash
FHIR_BASE=http://localhost:8080/fhir ./load_synthea.sh 10 California
```

The loader adds data; it does not empty the HAPI database first.

## Service lifecycle

```bash
docker compose logs -f hapi   # follow server logs
docker compose stop           # stop containers, preserve data
docker compose down           # remove containers, preserve the named volume
docker compose down -v        # delete the database volume and all local FHIR data
```

Use `down -v` only when a complete reset is intended. After deleting the volume,
the credentials currently in `.env` become the credentials for the new database.

## Query FHIR directly

```bash
F=http://localhost:8080/fhir

# Missouri patients
curl -s "$F/Patient?address-state=MO&_count=5"

# Count type 2 diabetes conditions (SNOMED CT 44054006)
curl -s "$F/Condition?code=http://snomed.info/sct%7C44054006&_summary=count"

# Latest HbA1c observations (LOINC 4548-4)
curl -s "$F/Observation?code=http://loinc.org%7C4548-4&_sort=-date&_count=5"

# ExplanationOfBenefit resources for one patient
curl -s "$F/ExplanationOfBenefit?patient=Patient/<id>&_sort=-created"
```

These commands return FHIR Bundles. Use `jq` when a compact terminal view is
helpful.

## Build and run the FHIR MCP bridge

[`langcare-config.yaml`](langcare-config.yaml) points the bridge at the local
FHIR base URL, uses stdio transport, and enables scrubbed JSON logs. The compiled
binary belongs at `bin/langcare-mcp-fhir` and is git-ignored.

```bash
git clone --depth 1 --branch v2.5.0 \
  https://github.com/langcare/langcare-mcp-fhir.git /tmp/langcare-mcp-fhir

(cd /tmp/langcare-mcp-fhir && \
  go build -o /Users/dc/geha/hapi/bin/langcare-mcp-fhir ./cmd/server)

/Users/dc/geha/hapi/bin/langcare-mcp-fhir \
  -config /Users/dc/geha/hapi/langcare-config.yaml
```

The upstream MCP server may expose write tools, but the agents in this directory
bind only `fhir_search` and `fhir_read`. They also apply the shared policy in
[`../agent_permissions/README.md`](../agent_permissions/README.md). Tool filtering
and middleware are defense-in-depth for the demos; they do not replace server-side
FHIR authorization.

## Agent examples

Export the relevant provider key before starting an agent:

```bash
export ANTHROPIC_API_KEY=...
```

### Minimal MCP tool-use loop

[`mcp_agent_demo.py`](mcp_agent_demo.py) starts the MCP bridge over stdio, gives
Anthropic only the two read tools, prints each FHIR call, and returns the final
answer.

```bash
cd /Users/dc/geha/hapi
uv run --no-project --python 3.12 --with anthropic \
  python mcp_agent_demo.py

uv run --no-project --python 3.12 --with anthropic \
  python mcp_agent_demo.py 'Find members with type 2 diabetes and their latest HbA1c.'
```

### LangChain FHIR agent

[`langgraph_agent.py`](langgraph_agent.py) uses LangChain `create_agent`, MCP
adapters, and `PermissionMiddleware`. Despite the historical filename, it is not
a hand-written `StateGraph`.

```bash
uv run --no-project --python 3.12 \
  --with 'langchain==1.4.2' \
  --with langchain-anthropic \
  --with langchain-mcp-adapters \
  --with pyyaml \
  python langgraph_agent.py
```

### Pharmacy agent

[`pharmacy_agent.py`](pharmacy_agent.py) combines three stdio MCP servers:

| Source | Use | Credentials |
|---|---|---|
| Local HAPI FHIR | Synthetic patient medication records | none |
| RxNorm | Drug names, identifiers, properties, and relationships | public API |
| openFDA | Labels, NDC data, recalls, and shortages | public API |

```bash
uv run --no-project --python 3.12 \
  --with 'langchain==1.4.2' \
  --with langchain-anthropic \
  --with langchain-mcp-adapters \
  --with pyyaml \
  python pharmacy_agent.py
```

This command requires Node.js, `npx`, and network access for RxNorm and openFDA.
The public drug information can identify a potentially relevant recall; it cannot
establish that a patient received a particular recalled lot.

## React agent applications

Both applications serve a built React UI through FastAPI at
<http://127.0.0.1:8765>. They use the same port, so run only one at a time.

### Fraud investigation

```bash
cd /Users/dc/geha/hapi/fraud
(cd ui && npm install && npm run build)
python3 seed_fraud.py --level 1
./run_server.sh
```

The app compares:

- an exploratory tool-using agent;
- a fixed workflow compiled from prior graded runs; and
- a router that chooses the workflow or escalates to the full agent.

The seeder modifies only the local synthetic dataset. Results and event traces
are stored under `fraud/traces/`. Reset and ladder commands, API routes, scoring,
and experiment caveats are documented in [`fraud/README.md`](fraud/README.md).

### Teacher-guided improvement

```bash
cd /Users/dc/geha/hapi/self-improving-agents
(cd ui && npm install && npm run build)
python3 seed_fraud.py --level 1
./run_server.sh
```

This experiment uses graded runs to propose prompt or tool changes and records
their approval state. It does not train model weights and should not be described
as autonomous recursive self-improvement. See
[`self-improving-agents/README.md`](self-improving-agents/README.md) for its
workflow and controls.

The servers require `ANTHROPIC_API_KEY`; `OPENAI_API_KEY` and `NOUS_API_KEY` are
needed only when selecting those providers. A blank page or 404 at port `8765`
usually means the corresponding `ui/dist` bundle has not been built.

## Claim-insight experiment

Synthea provides the provider record but not claimant-authored correspondence.
[`claim_insights/seed_claimant.py`](claim_insights/seed_claimant.py) therefore
plants tagged claimant statements for controlled conflict cases. The analyzer
finds claimant/provider disagreements and active comorbidities whose onset follows
a chosen primary condition.

```bash
cd /Users/dc/geha/hapi/claim_insights
python3 seed_claimant.py
python3 find_insights.py --check
python3 find_insights.py --json
python3 find_insights.py --patient Patient/<id>
python3 find_insights.py --since 2020-01-01
python3 seed_claimant.py --reset
```

Seeded resources are tagged `urn:geha:claim-insights|seed`, allowing reset to
remove the experiment without deleting unrelated synthetic records. Generated
insight language is templated research output, not a clinical, coverage,
disability, or return-to-work determination.

## Permissions and data boundaries

The agents use two layers of tool control:

1. only selected read tools are bound to the model; and
2. `PermissionMiddleware` evaluates calls against the healthcare policy in
   `agent_permissions`.

Allowed reads proceed. Writes and unknown tools require approval and are denied
when an unattended run cannot obtain it. Permission decisions can be audited,
but this does not make the local HAPI server production-ready.

Before using any external model, remember that tool results become model context.
Use only the synthetic records produced for this lab.

## Validation

Validate the Compose configuration without starting containers:

```bash
cd /Users/dc/geha/hapi
HAPI_DB_USER=hapi HAPI_DB_PASSWORD=readme-validation \
  docker compose config --quiet
```

Run the agent-permission integration suite from the GEHA repository root:

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

Run the fraud workflow tests without calling HAPI or an LLM:

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

Build either React client with `npm run build` in its `ui` directory.

## Troubleshooting

### HAPI never becomes ready

```bash
docker compose ps
docker compose logs --tail=200 hapi db
```

The database health check must pass before HAPI starts. Initial startup can take
longer while the schema is created.

### `password authentication failed for user "hapi"`

The password in `.env` differs from the password stored in the existing database
volume. Restore the original value. If the data can be discarded, run
`docker compose down -v` and recreate the stack with the current `.env`.

### Synthea JAR not found

Place an official Synthea release artifact at:

```text
/Users/dc/geha/hapi/synthea/synthea-with-dependencies.jar
```

It is intentionally excluded from Git because of its size.

### MCP binary not found

Build `bin/langcare-mcp-fhir` using the commands above. Run agent commands from
`/Users/dc/geha/hapi` so relative configuration paths resolve correctly.

### Port already in use

- `8080`: another service is using the HAPI port.
- `8765`: the other React/FastAPI demo is probably still running.
- `5173`: a Vite development server is already active; production-style
  `run_server.sh` serves the built UI on `8765` and does not need Vite.

## Limitations

- The Compose stack is local development infrastructure: no TLS, user login,
  production authorization, or production audit controls.
- `hapiproject/hapi:latest` can change behavior between pulls; pin an image digest
  before using reproducible benchmark results.
- Synthea data is fictional but not guaranteed to be clinically realistic.
- Agent output is probabilistic and may omit evidence or make incorrect claims.
- Fraud seeds, scoring keys, and compiled workflows are controlled demonstrations,
  not evidence of real-world fraud-detection performance.
- RxNorm and openFDA are external public services whose availability and response
  formats can change.
- None of these tools should make autonomous clinical, benefits, coverage, fraud,
  or payment decisions.
