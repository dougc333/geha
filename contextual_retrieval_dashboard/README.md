# Contextual Retrieval Workbench

A React dashboard for running and inspecting contextual retrieval over the canonical GEHA document corpus.

The workbench preserves the original evidence chunk and asks Claude to add a short retrieval-oriented description derived from the whole document. The combined text can be indexed with BM25 or embeddings without replacing the source text used for citations and faithfulness checks.

It supports two artifact modes:

- **Canonical policy text:** Docling Markdown and chunks produced by `crawl_dir`.
- **Saved visual figures:** a page PDF paired with the latest rendered figure iteration from a completed ingestion run.

> **Demo scope:** this application processes public, curated documents. It is not production- or HIPAA-ready, and it does not promote generated candidates automatically.

## Why contextual retrieval

A short chunk can lose the names, dates, populations, plan options, or document section that make it retrievable. Contextual retrieval adds that missing document-level identity before indexing:

```text
whole document + target chunk
              |
              v
       Claude annotation
              |
              v
short retrieval context + original chunk text
              |
              +--> contextual BM25
              +--> contextual embeddings
```

The fields have intentionally different responsibilities:

| Field | Purpose |
|---|---|
| `text` | Preserved source evidence shown to users and used for grounding checks |
| `retrieval_context` | Short generated description that situates the chunk within the document |
| `contextual_retrieval_text` | `retrieval_context` followed by the original evidence text; intended for indexing |

The generated context is an indexing aid, not authoritative evidence.

## Application architecture

```text
React 19 + Vite UI
        |
        | JSON + Server-Sent Events
        v
aiohttp backend
        |
        +--> crawl_dir canonical ingestion
        |       Docling HybridChunker
        |       BAAI/bge-small-en-v1.5 tokenizer
        |       380-token chunk body
        |
        +--> Claude contextualization
        |       one request per text chunk or figure
        |       whole-document prompt caching
        |
        +--> durable JSONL and metadata under crawl_dir/runs
```

The backend serves the compiled React application, starts ingestion work in background threads, streams progress through SSE, and reconstructs run history from disk after restarts.

## Canonical policy-text mode

For each selected coverage-policy PDF, the backend:

1. verifies that a prior non-empty canonical `batch-*/candidate/document.md` exists;
2. invokes the canonical `crawl_dir.src.process_all` workflow for the requested batch;
3. verifies the newly created run's `candidate/document.md` before any model call;
4. reads `candidate/chunks.jsonl`;
5. sends the complete document and one target chunk to Claude;
6. checkpoints each result in `candidate/contextual-chunks.jsonl`; and
7. writes aggregate model, prompt, token-cache, and completion metadata.

The preflight check prevents spending money on contextualization when the source does not already have a viable canonical Markdown representation. Datroway and Elrexfio are identified in the UI as sources converted by the separate visual/ReAct workflow.

### Prompt and cache contract

Each text-chunk request contains:

1. the complete extracted document in a cached `<document>` system block;
2. the target canonical chunk in the changing user message; and
3. an instruction to produce only concise retrieval context.

The cache breakpoint is:

```json
{"cache_control": {"type": "ephemeral"}}
```

The **Prompt + cache** drawer shows the exact current prompt contract. Its live diagnostic makes two real Claude requests against the same document. It passes only when the second response reports `cache_read_input_tokens > 0`.

## Saved visual-figure mode

Visual mode reads a specific durable EY/LIMRA ingestion run configured in `backend.py`. It does not regenerate or repair figures.

For each `pages/page-NNN/segments/figure-NN` or `fig-NN` directory, it:

1. requires `page-NNN/source.pdf`;
2. selects the highest numbered `iteration-NN.png`;
3. optionally reads literal source text from `native-evidence.json`;
4. sends the page PDF and selected figure image to Claude; and
5. combines the generated context with the literal evidence text.

The chunk inspector then displays:

- **Panel 01:** the authoritative page PDF; and
- **Panel 02:** the latest figure image, its generated retrieval context, and the combined indexing text.

Visual records are reused only when the page hash, figure hash, model, and prompt version still match. Changing an artifact therefore invalidates only the affected record.

## Cost and resumability

Contextualization makes approximately one Claude request per canonical chunk or selected figure. The UI requires explicit cost acknowledgement before a run can start.

The health endpoint reports current document and call estimates from the files mounted into the application. Treat those values as estimates, not a fixed corpus size.

Both modes checkpoint after each completed item:

- interrupted runs retain already written results;
- matching results can be reused; and
- a failure in one policy document does not discard successful documents.

Only one in-memory dashboard run may be active at a time. Saved history is independent of that registry and survives backend or container restarts.

## Quick start with Docker Compose

Docker Compose is the recommended way to run the complete application. The image builds the React UI, installs the Python backend, and preloads the BGE tokenizer used by the canonical chunker.

```bash
cd /Users/dc/geha/contextual_retrieval_dashboard

# The container needs one of these credentials.
export ANTHROPIC_API_KEY=...
# or: export ANTHROPIC_AUTH_TOKEN=...

docker compose up --build
```

Open <http://127.0.0.1:8511>.

Run in the background and follow startup output:

```bash
docker compose up -d --build
docker compose logs -f
```

Override the host port without changing container port `8511`:

```bash
CONTEXTUAL_RETRIEVAL_PORT=8512 docker compose up --build
```

Then open <http://127.0.0.1:8512>.

Stop the service with:

```bash
docker compose down
```

Compose mounts:

| Host path | Container access | Purpose |
|---|---|---|
| `crawl_dir/raw/coverage-policies` | Read-only | Canonical source PDFs |
| `crawl_dir/runs` | Read/write | Durable runs and contextual outputs |
| `crawl_dir/cache` | Read/write | Page-split and ingestion caches |

`docker compose down` does not remove these repository files.

## Local development

### Build the frontend

```bash
cd /Users/dc/geha/contextual_retrieval_dashboard/ui
npm ci
npm run build
```

### Start the backend

Use the GEHA Python environment with the dashboard requirements installed:

```bash
cd /Users/dc/geha
source .venv/bin/activate
uv pip install --python .venv/bin/python \
  -r contextual_retrieval_dashboard/requirements.txt

export ANTHROPIC_API_KEY=...
python -m contextual_retrieval_dashboard.backend
```

Open <http://127.0.0.1:8511>. The backend serves `ui/dist`; if it has not been built, the root route returns an instruction to build it.

For live frontend development, leave the backend on port `8511` and run:

```bash
cd /Users/dc/geha/contextual_retrieval_dashboard/ui
npm run dev
```

Open <http://127.0.0.1:5175>. Vite proxies `/api` to the backend.

Local authentication can use `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, or credentials available to the backend process through `ant auth login`. Docker Compose passes only the exported environment variables shown in `compose.yaml`.

## Using the workbench

1. Confirm that the status bar reports a ready Claude credential and the expected model.
2. Choose a policy marked **MD ready**, or select the saved visual run.
3. Review the estimated call count.
4. acknowledge the one-call-per-chunk or one-call-per-figure cost;
5. start the run and watch the canonical/contextual event stream;
6. select a completed or in-progress document to inspect chunks; and
7. use **Past contextual runs** to reopen durable output after a restart.

The batch ID accepts 3–80 letters, numbers, dots, underscores, or hyphens. Full-corpus execution is refused if any source lacks canonical batch Markdown.

## Durable artifacts

### Canonical policy run

```text
crawl_dir/runs/coverage-policies/<document-id>/<run-id>/
├── run-manifest.json
└── candidate/
    ├── document.md
    ├── chunks.jsonl
    ├── contextual-chunks.jsonl
    └── contextual-retrieval.json
```

### Saved visual run

```text
crawl_dir/runs/research/<document-id>/<run-id>/
├── pages/
│   └── page-NNN/
│       ├── source.pdf
│       └── segments/
│           └── figure-NN/
│               ├── native-evidence.json
│               └── iteration-NN.png
├── visual-contextual-chunks.jsonl
└── visual-contextual-retrieval.json
```

The cache diagnostic is saved at `crawl_dir/runs/contextual-prompt-cache-test.json`.

All contextual artifacts remain candidates. They still require the repository's normal review and promotion gates before use in a promoted corpus.

## Backend API

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/health` | Credential readiness, model, source inventory, Markdown readiness, and call estimates |
| `GET` | `/api/history` | Reconstruct saved textual and visual contextual runs from disk |
| `GET` | `/api/prompt` | Current text and visual prompt contracts |
| `GET` | `/api/prompt-cache-test` | Last saved cache diagnostic |
| `POST` | `/api/prompt-cache-test` | Execute the billable two-call cache diagnostic |
| `POST` | `/api/batches` | Start one-policy or full-corpus canonical/contextual processing |
| `POST` | `/api/visual-batches` | Contextualize figures in the configured saved visual run |
| `GET` | `/api/batches/{run_id}/events` | Stream live progress as Server-Sent Events |
| `GET` | `/api/chunks?run=...` | Return original/contextual chunk pairs for an allowed saved run |
| `GET` | `/api/artifact?run=...&path=...` | Serve an allowed PDF or image inside that run |

Run and artifact paths are resolved beneath `crawl_dir/runs`. Absolute artifact paths, directory traversal, unsupported file types, and nonexistent runs are rejected.

## Tests and build checks

Run the offline Python tests:

```bash
cd /Users/dc/geha
source .venv/bin/activate
python -m unittest contextual_retrieval_dashboard.test_visual_context -v
```

The tests verify figure discovery, highest-iteration selection, per-item checkpointing, and hash-based reuse without making Claude calls.

Build and type-check the frontend:

```bash
cd /Users/dc/geha/contextual_retrieval_dashboard/ui
npm ci
npm run build
```

## Project map

| Path | Responsibility |
|---|---|
| `backend.py` | aiohttp API, SSE registry, canonical batch orchestration, history, and safe artifact serving |
| `visual_context.py` | Figure discovery, Claude PDF/image contextualization, hashes, checkpointing, and reuse |
| `test_visual_context.py` | Offline visual-context unit tests |
| `ui/src/App.tsx` | React workbench, run controls, inspectors, history, and cache drawer |
| `ui/src/styles.css` | Workbench layout and visual styling |
| `compose.yaml` | Runtime environment, credentials, ports, and bind mounts |
| `Dockerfile` | Multi-stage React build and Python runtime image |
| `requirements.txt` | Backend runtime dependencies |

## Limitations

- The dashboard is coupled to the repository's `crawl_dir` artifact contracts.
- Visual mode currently targets the saved run configured by `VISUAL_RUN` in `backend.py`; it is not a general run picker.
- Generated context can still be wrong or incomplete and must not replace source evidence.
- Prompt caching reduces repeated input processing when the provider reports a cache hit, but it does not eliminate per-chunk model requests.
- The in-memory SSE registry does not resume a live stream after a backend restart; durable results remain recoverable from run history.
- The application has no user authentication or multi-tenant isolation.
