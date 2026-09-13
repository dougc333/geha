# GEHA LangGraph review demo

## Local Langfuse tracing

`langfuse_app.py` runs the existing synthetic claim-review graph with Langfuse tracing. Each run records the graph and node inputs, outputs, durations, errors, tags, and metadata in the self-hosted Langfuse instance at `http://localhost:3000`. A stable trace ID derived from the LangGraph thread ID connects the initial run and its later human-review resume.

Create API keys in the local Langfuse project settings, then configure the application:

```bash
cd /Users/dc/geha/langgraph_demo
cp .env.example .env
```

Edit `.env` and replace both placeholder values with that project's `pk-lf-...` and `sk-lf-...` keys. Keep `.env` local; it is excluded from Git. Install the locked environment and verify authentication:

```bash
uv sync --locked
uv run langfuse_app.py check
```

Start a traced review:

```bash
uv run langfuse_app.py start
```

The command prints a LangGraph `thread_id` and Langfuse trace ID. The graph pauses at `next: ["review"]`. Resume the same thread with:

```bash
uv run langfuse_app.py review YOUR_THREAD_ID \
  --action approve \
  --reason 'Checked the recorded reason and cited guidance'
```

Open `http://localhost:3000` and select **Tracing** in the project. Search for trace name **GEHA synthetic claim review** or the printed trace ID. The example contains synthetic data only; do not send real member or claim data into this development deployment.

## All 20 claims: new versus saved reviews

All 20 synthetic claims are available in the Streamlit dropdown with their recorded insurance status. The default `demo_operator` fixture can start explanation reviews for all of them. `member` remains restricted to the original fixed member and `outsider` remains denied. This is an operator demo, not production authorization.

**Start new review** creates a fresh UUID every time. **Reopen a case** restores an existing thread; labels show claim ID, explanation-review status, and a short thread ID. Insurance claim status and explanation approval are independent: even a PAID or DENIED synthetic claim can have an explanation awaiting review. Approval never changes its claim status.

`uv run prepare_cases.py` prepares one saved review per claim, paused for human input. It uses stable IDs, so rerunning it skips existing prepared threads, including completed ones. It does not overwrite any other threads or modify source JSON. Run it with no other process writing reviews. The CLI also accepts `--actor demo_operator` when starting a case.

## Streamlit application

```bash
cd /Users/dc/geha/langgraph_demo
uv sync --locked
uv run streamlit run app.py --server.address 127.0.0.1 --server.port 8503
```

Open http://127.0.0.1:8503. **Start new review** automatically generates a thread ID and selects the new case. Read or edit the draft, choose approve or reject, and supply a reason. **Saved cases** reopens earlier cases after a browser/server restart, including CLI-created cases. Normal page refreshes do not create threads. Checkpoint history and JSON export are available below each case.

The UI shares `data/checkpoints.sqlite` with the CLI. A process-wide lock serializes UI operations across sessions, but does not coordinate other server processes or the CLI; avoid concurrent updates to the same thread outside this process. All saved cases are visible to the local operator: this is not a secure member portal. Keep the server bound to localhost and use only synthetic data. `GEHA_DEMO_DB` and `GEHA_DEMO_BASE` optionally override the database and inputs for isolated testing.

A separate, local command-line demo: authorize a synthetic member, look up a claim's recorded simulation outcome, retrieve curated guidance, draft an explanation, pause for a human, and resume after review. No source records are modified. No payment, claim approval, denial, or external submission occurs.

## Run

```bash
cd /Users/dc/geha/langgraph_demo
uv sync --locked
uv run demo.py example
uv run demo.py start
```

`start` selects an existing pending claim and prints a new `thread_id`, its draft, and `next: ["review"]`. Copy that actual thread ID into these commands:

```bash
uv run demo.py show YOUR_THREAD_ID
uv run demo.py review YOUR_THREAD_ID --action approve --reason 'Checked the recorded reason and cited guidance'
uv run demo.py history YOUR_THREAD_ID
```

You can close the terminal between start and review: SQLite checkpoints persist under `data/checkpoints.sqlite`. Each CLI command opens a fresh graph and database connection. Review must use the same thread ID and database. Start a new thread to repeat the demo.

To reject or edit the explanation:

```bash
uv run demo.py review YOUR_THREAD_ID --action reject --reason 'Insufficient supporting evidence'
uv run demo.py review YOUR_THREAD_ID --action approve --reason 'Clarified wording' --edit 'Your reviewed explanation'
```

These are alternatives, not sequential commands on a completed thread. Rejection ends that thread without releasing its draft. Approving approves only the explanation, not the claim. The CLI records reviewer identity, action, reason, and any edited text. The original draft remains in checkpoint history.

Test unauthorized access with `uv run demo.py start --actor outsider`. It ends before claim details, retrieval, or drafting. Use `--claim CLM-...` for a specific claim; the fixed demo member can only view records with the default example's member ID.

## Nodes and files

| Node | Behavior |
| --- | --- |
| authorize | Fixed synthetic member-scope check; unauthorized requests end early. |
| lookup | Reads recorded status and blocking notes from simulation audit trails. |
| retrieve | Topic-filters existing public reference snippets. |
| draft | Creates a deterministic explanation with cited guidance. |
| review | Calls LangGraph `interrupt()` and awaits reviewer input. |
| release | Returns approved or edited text, or a rejection notice. |

`demo.py` contains the graph and CLI. `test_demo.py` covers persistence after reopening, access denial, approval, rejection, editing, review permissions, and repeated-resume rejection. Run `uv run python -m unittest -v`.

## Read-only dependencies

- `../agentic_simulation/claims/claims.json`: synthetic member/claim identifiers and plan labels.
- `../agentic_simulation/claims/audit_trails.json`: recorded status and reasons (authoritative within this simulation).
- `../agentic_reference/data/public_reference.json`: curated, summarized guidance with source URLs.

No dependency on the deleted `vector_db` or `fuzzy_search` directories. No imports from the reference agent are required. `--base /path/to/geha` selects another input root; `--db /path/to/checkpoints.sqlite` selects another checkpoint store. Put these options before the subcommand.

## Deliberate limits

Both CLI and Streamlit interfaces are available. Drafting uses templates, not an LLM. Retrieval uses the curated JSON snippets, not all downloaded PDFs or semantic embeddings. The snippets are general administrative references: no plan/year-specific coverage conclusion is inferred. Missing-document requirements are not invented when the audit trail does not record them. Existing synthetic data and rules may contain inconsistencies.

The fixed personas are fixtures, not authentication. Anyone with local CLI/database access can act as reviewer and inspect checkpoints. Do not expose this demo as a public service or use real patient data. Production needs verified identity, thread-level authorization, reviewer validation, privacy controls, concurrency control, and a protected audit store. Run one operation at a time on a thread. SQLite history is mutable, unencrypted local state—not an immutable compliance audit. Reviewer-edited explanations are not automatically fact-checked.

Potential next steps: add a local review UI, plan/year-filtered PDF retrieval with evaluation cases, then an optional LLM drafting adapter. Preserve deterministic claim facts and human approval when adding those features.

LangGraph references: [interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) and [persistence](https://docs.langchain.com/oss/python/langgraph/persistence).
