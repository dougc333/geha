# GEHA simulation MCP server

A real, local **stdio MCP server** wrapping the nine fabricated insurance
simulations under `../highlevel_simulation/`. Uses the official Python MCP SDK (v1 maintenance line, pinned below
v2). No LLM, API key, network listener, real insurance transaction, or database is
required. The server does not certify medical necessity or regulatory compliance.

## Setup and run

```bash
cd /Users/dc/geha/MCP_server
uv sync --locked
uv run --locked server.py
```

`server.py` waits for MCP messages on stdin; it is not an interactive terminal
menu. An MCP host normally starts this process. It writes only protocol messages
to stdout; SDK diagnostics go to stderr and simulator logs stay in run folders.

To exercise it through an actual MCP client:

```bash
uv run --locked demo_client.py            # discover tools and list flows (read-only)
uv run --locked demo_client.py --run-all  # create a new isolated simulation run
```

`mcp_config.example.json` provides a conventional `mcpServers` configuration for
clients accepting that format. It uses the project's installed `.venv` and an
absolute script path, so no working-directory assumption is needed. Adapt the
configuration to your client's schema. No client settings are changed automatically.

## Tools

| Tool | Arguments | Behavior |
|---|---|---|
| `list_flows` | none | Lists all nine flows, dependencies, and output filenames. |
| `run_flow` | `flow_id` | Runs one flow and prerequisites in a fresh workspace. |
| `run_all_flows` | none | Runs all nine sequentially in a fresh workspace. |
| `get_flow_results` | `flow_id`, `run_id` | Reads an actual completed summary. |
| `get_flow_records` | `flow_id`, `run_id`, `offset=0`, `limit=50` | Pages through detailed records. |
| `get_flow_events` | same | Pages through event logs. |
| `get_run_status` | `run_id` | Reads status, provenance, warnings, and failure information. |

Flow IDs are the strings `"01"` through `"09"`, not paths or script names.
Pagination is capped at 100 records per request. `next_offset: null` means the
last page. Reads require a specific `run_id`; there is no ambiguous global
"latest" result or fallback to example files. A failed, cancelled, or unfinished
run cannot be read as a successful result, even if some prerequisite flows finished.

Example tool arguments:

```json
{"flow_id": "04"}
```

The resulting run executes `01` then `04`. Use the returned `run_id` with
`get_flow_results` or `get_flow_events`. `08` depends on `01` and `03`; `09`
depends on all preceding flows. Prerequisites are rerun, not read from stale
source-directory outputs. Member Services' premium responses remain placeholders.

## Run outputs and safeguards

```text
runs/run_<32-hex-uuid>/
  run.json
  claims/audit_trails.json       # when claims input exists and is needed
  01_membership_benefits/
    simulate_membership.py       # allowlisted source snapshot
    members.json
    membership_events.json
    mcp_response.json
    stdout.log
    stderr.log
  ...
```

- Only fixed, allowlisted scripts execute. No shell, caller-supplied code,
  filesystem paths, environment variables, or commands are exposed as tools.
- Each run gets a unique private directory. Original simulator datasets and
  example responses are not overwritten by MCP calls.
- Two active runs per server process maximum; further calls receive a busy error.
  Flows within a run execute sequentially. Separate server instances also use
  unique run IDs, but their concurrency limits are independent.
- Each simulator has a 30-second timeout. Timeout/cancellation kills its process
  group. Output streams are captured and bounded to 256 KiB each.
- JSON reads are limited to 2 MiB per file. Responses and output lists are checked
  before marking a flow successful. A nonzero exit or missing response fails the run.
- Manifests are atomically replaced. They record timestamps, script hashes, claims
  snapshot provenance, completed flows, and overall status. These are local records,
  not tamper-proof audit evidence.
- The server refuses new runs after 100 run directories are present. Archive runs
  manually with the server stopped; no automatic deletion is performed. This is a
  directory-count guard, not a hard filesystem byte quota.
- Child processes receive a minimal environment, not inherited API keys.

## Claims path correction

The two dependent simulators now default to:

`/Users/dc/geha/demo_data/audit_trails.json`

The MCP runner snapshots that existing file into the isolated run and supplies
`GEHA_CLAIMS_PATH` to the child processes. It does **not** rerun the claims
adjudication engine. Missing input is reported as a warning; compliance evidence
counts reflect the absence. Malformed input fails the run.

Operator-only environment overrides (not tool arguments):

- `GEHA_CLAIMS_PATH`: trusted claims audit JSON input.
- `GEHA_RUNS_DIR`: output root, default `MCP_server/runs`.

Direct `bash ../highlevel_simulation/run_all_flows.sh` still runs in the source folders and overwrites
their JSON outputs. Use the MCP tools for isolation.

## Scope and remaining limitations

This is a local demo for a trusted user and trusted scripts, **not a sandbox for
malicious Python**. It runs with the OS permissions of its launching user. No
multi-user authentication or authorization is implemented, and no HTTP transport
is exposed. Do not add real patient data or make it publicly accessible without
appropriate privacy, security, and authorization work.

Simulation caveats are unchanged: HIPAA checks include an always-pass placeholder;
Member Services may report a `NOT_FOUND` lookup as resolved; identity checks use
fabricated flags; billing, referrals, and ID-card operations are simulated. A
successful subprocess exit is not a business or compliance approval. The server
preserves warnings and `simulation_only: true`, and compliance summaries retain
`compliance_verified: false`.

## Tests

```bash
uv run --locked python -B -m unittest discover -s . -p 'test_server.py'
uv run --locked python -B -m unittest discover -s ../highlevel_simulation -p 'test_responses.py'
```

Tests use temporary copies and include all nine response counters, dependency
execution, claims lookup, isolation, traversal rejection, stale-result rejection,
exit failures, timeouts, cancellation, log limits, quotas, pagination, and a real
stdio MCP session with discovery, tool calls, structured results, and error cases.
