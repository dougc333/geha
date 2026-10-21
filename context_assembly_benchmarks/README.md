# Context Assembly Benchmarks

This project measures a specific RAG failure mode: the retriever finds a useful
row, but the evidence assembled for the language model omits the table context,
qualifier, exception, or note needed to answer correctly.

The benchmark holds retrieval constant and compares three ways to assemble the
LLM context:

1. **Flat row chunks** — return the highest-ranked table rows.
2. **Table-aware** — use the same ranked rows to identify and return their full
   parent tables.
3. **Table-aware + attached notes** — return each parent table together with its
   nearby explanatory paragraph and notes.

All three strategies begin with the same child-row ranking: BM25 and pgvector
cosine similarity are combined with reciprocal-rank fusion (RRF). There is no
learned or cross-encoder reranker in this project.

![Table-aware parent-child RAG architecture](table_rag_architecture.svg)

## What the benchmark isolates

```text
question
   |
   v
BM25 + dense row retrieval
   |
   v
RRF-ranked child rows             <- retrieval
   |
   +-- flat: top rows
   +-- table-aware: parent tables  <- context assembly
   +-- table-aware + notes
   |
   v
LLM answer                         <- generation
```

The retrieval ranking is shared so that differences can be attributed to
context assembly rather than to different retrievers.

The project tracks required facts through both the assembled context and the
generated answer:

| Fact in context? | Fact in answer? | Outcome |
|---|---|---|
| Yes | Yes | Correct |
| Yes | No | Generation drop |
| No | No | Retrieval/context-assembly failure |
| No | Yes | Unsupported claim |

**Context completeness** asks whether every required fact is present in the
evidence sent to the model. **Answer completeness** asks whether every required
fact appears in the final response. These are different metrics and should not
be collapsed into one judge score.

## Quick start with Docker Compose

From this directory:

```bash
cd /Users/dc/geha/context_assembly_benchmarks

# Required by the PostgreSQL service. Keep the same value while reusing the
# existing Docker volume.
export GEHA_POSTGRES_PASSWORD="$(openssl rand -hex 24)"

# Optional. Retrieval and the saved-results dashboard work without it.
# export OPENAI_API_KEY="..."

docker compose up --build
```

Open:

- **Interactive Streamlit comparison:** <http://127.0.0.1:8507>
- **React results dashboard:** <http://127.0.0.1:5174>

The first service restores the checked-in benchmark snapshot into PostgreSQL:
102 parent tables and 675 searchable child-row vectors. The React service is a
static viewer for the checked-in evaluation export; it does not query the live
database.

Stop the stack without deleting the database:

```bash
docker compose down
```

### PostgreSQL password and volume behavior

PostgreSQL records its password when the data volume is first initialized. If
you later change `GEHA_POSTGRES_PASSWORD` while reusing that volume, the app can
fail with `password authentication failed for user "geha"`. Re-export the
original password, or recreate the local benchmark volume:

```bash
# Deletes only this Compose project's local database volume. The benchmark can
# be restored again from postgres-init/geha_rag.dump.
docker compose down -v
export GEHA_POSTGRES_PASSWORD="$(openssl rand -hex 24)"
docker compose up --build
```

## Interfaces

| Interface | Purpose | Live dependencies |
|---|---|---|
| `comparison_chat_app.py` | Run one query through flat and table-aware assembly and inspect retrieved evidence | PostgreSQL; OpenAI only when generation/judging is enabled |
| `dashboard/` | Explore the saved 59-question evaluation by strategy and question type | None after the static data is built |
| `streamlit_app.py` | Older parent-child table retrieval demonstration | PostgreSQL and optional OpenAI |
| `table_rag.py` | CLI for schema setup, ingestion, search, and cited answers | PostgreSQL; OpenAI only for `ask` |

The live comparison app currently exposes flat rows and table-aware parent
tables. The third, attached-notes strategy is implemented in the evaluation
pipeline and shown in the React dashboard.

## Retrieval and storage design

`table_rag.py` stores two levels:

- `policy_tables`: complete parent tables, structured rows, source metadata,
  title, and serialized table content.
- `policy_table_vectors`: searchable child rows linked to their parent table.

Each row is serialized with its source, inferred table title, headers, and
nonempty cell values. `BAAI/bge-small-en-v1.5` produces a normalized
384-dimensional embedding. PostgreSQL stores the vectors with pgvector and uses
an HNSW cosine index.

The comparison and evaluation paths add in-memory BM25 over the same child-row
corpus and combine BM25 and dense ranks with RRF. A matching row can then remain
a flat chunk or expand to its complete parent table. `context_attachments.py`
adds nearby prose and notes for the third strategy.

RRF is rank fusion, not a semantic reranker. It combines two ranked lists but
does not jointly score a query-document pair like a cross-encoder.

## Evaluation sets and metrics

The checked-in evaluation contains 59 questions:

| Question type | Cases | What it tests |
|---|---:|---|
| Preference lookup | 34 | Values found in individual table rows |
| Row-to-column relationship | 7 | Relationships that require the table structure |
| Qualifier | 18 | Footnotes, exceptions, authorization periods, and nearby prose |

The main measurements are:

- required-fact coverage and complete-context rate;
- complete-answer rate, groundedness, and judge verdict;
- assembly errors, generation drops, and unsupported facts;
- estimated context tokens, rows sent, and sibling-row noise.

`evaluate_hybrid_contexts.py` is deterministic and does not call an LLM.
`evaluate_chunking_judge.py` generates answers and uses an LLM judge plus
fact-level checks, so it requires `OPENAI_API_KEY` and incurs API cost.

## Checked-in result snapshot

These results are from the saved 59-question run dated 2026-10-16. They are
configuration-bound evidence, not a general claim about all RAG systems. Rerun
the benchmark after changing data, retrieval settings, prompts, or models.

| Strategy | Context complete | Answer complete | Assembly-error cases | Generation-drop cases | Avg. context tokens |
|---|---:|---:|---:|---:|---:|
| Flat row chunks | 40.7% | 40.7% | 59.3% | 5.1% | 299 |
| Table-aware | 69.5% | 69.5% | 27.1% | 6.8% | 476 |
| Table-aware + attached notes | 100.0% | 93.2% | 0.0% | 6.8% | 896 |

Across 188 required facts, the saved run recorded:

| Strategy | Correct | Generation drop | Assembly error | Unsupported |
|---|---:|---:|---:|---:|
| Flat row chunks | 128 | 3 | 57 | 0 |
| Table-aware | 164 | 6 | 16 | 2 |
| Table-aware + attached notes | 182 | 6 | 0 | 0 |

The attached-notes strategy reaches 100% context completeness partly by
construction: its qualifier cases are defined from those notes. The answer
evaluation is still necessary to test whether the model uses the available
facts. Qualifiers located on other pages are not yet covered.

## Reproduce the evaluation

Run from the repository root so package imports and paths resolve consistently:

```bash
cd /Users/dc/geha
source .venv/bin/activate
```

The main Compose database is intentionally private to its Docker network. To
run the evaluation scripts directly from the host, start the development
pgvector service under a separate Compose project, then initialize and ingest
it:

```bash
docker compose \
  -p geha-rag-dev \
  -f context_assembly_benchmarks/docker-compose.pgvector.yml \
  up -d pgvector

python -m context_assembly_benchmarks.table_rag init-db
python -m context_assembly_benchmarks.table_rag ingest \
  crawl_dir/verified/coverage-policies
```

The host-side CLI and evaluation scripts default to
`postgresql://geha:geha-local@127.0.0.1:5433/geha_rag`. Use
`GEHA_RAG_DATABASE_URL` to target another compatible PostgreSQL/pgvector
instance.

### 1. Build or refresh qualifier cases

```bash
python -m context_assembly_benchmarks.make_qualifier_cases
```

### 2. Measure context completeness without an LLM

```bash
python -m context_assembly_benchmarks.evaluate_hybrid_contexts
```

Defaults:

- top 5 flat chunks;
- top 3 parent tables;
- 30 fused candidate rows;
- 100 vector candidates.

This writes `hybrid_context_results.json` and
`hybrid_context_results.md`. It also replaces the generated block below.

<!-- HYBRID_CONTEXT_RESULTS_START -->
The generated deterministic context-completeness table is stored in
[`hybrid_context_results.md`](hybrid_context_results.md). Run
`evaluate_hybrid_contexts.py` to refresh this block and the saved artifacts.
<!-- HYBRID_CONTEXT_RESULTS_END -->

### 3. Generate and judge answers

```bash
export OPENAI_API_KEY="..."
export OPENAI_MODEL="gpt-4o-mini"
export OPENAI_JUDGE_MODEL="gpt-4o-mini"

python -m context_assembly_benchmarks.evaluate_chunking_judge --resume
```

`--resume` reuses completed records in `chunking_judge_partial.jsonl`. Without
it, the command refuses to overwrite an existing partial checkpoint. Use
`--limit N` for a smaller pilot before paying for the full run.

Outputs:

- `chunking_judge_partial.jsonl`: resumable per-question checkpoint;
- `chunking_judge_results.json`: machine-readable final report;
- `chunking_judge_results.md`: human-readable summary.

### 4. Refresh the React dashboard data

```bash
python -m context_assembly_benchmarks.build_dashboard_data

cd /Users/dc/geha/context_assembly_benchmarks/dashboard
npm install
npm run dev
```

Open <http://127.0.0.1:5174>. `npm run data` is a shortcut that invokes the
same Python export through the repository's `.venv`.

## Run the retrieval CLI manually

The separate `docker-compose.pgvector.yml` exposes a development PostgreSQL
instance at `127.0.0.1:5433` using the CLI's default credentials. Unlike the
main Compose stack, it does not restore the benchmark dump automatically.

```bash
cd /Users/dc/geha
docker compose \
  -p geha-rag-dev \
  -f context_assembly_benchmarks/docker-compose.pgvector.yml \
  up -d pgvector

source .venv/bin/activate
python -m context_assembly_benchmarks.table_rag init-db
python -m context_assembly_benchmarks.table_rag ingest \
  crawl_dir/verified/coverage-policies

python -m context_assembly_benchmarks.table_rag search \
  "Does Q5157 require prior authorization?" \
  --top-tables 3 \
  --candidate-rows 30
```

To generate a cited answer after retrieval:

```bash
export OPENAI_API_KEY="..."
python -m context_assembly_benchmarks.table_rag ask \
  "Does Q5157 require prior authorization?" \
  --top-tables 3
```

## Visualizations

The context-window comparison illustrates the size/structure tradeoff between
flat rows and complete parent tables:

![Flat chunks versus table-aware context](context_window_flat_vs_table.svg)

The four flat chunks in this illustration were selected by hand; the image is
an explanation of context shape, not a retrieval benchmark result. Regenerate
it with:

```bash
cd /Users/dc/geha
.venv/bin/python context_assembly_benchmarks/draw_context_window.py
```

## Tests

```bash
cd /Users/dc/geha
source .venv/bin/activate

python -m unittest -v \
  context_assembly_benchmarks.test_table_rag \
  context_assembly_benchmarks.test_generation_eval \
  context_assembly_benchmarks.test_dashboard_data
```

Build the React app as a separate frontend check:

```bash
cd /Users/dc/geha/context_assembly_benchmarks/dashboard
npm run build
```

## Important files

| Path | Role |
|---|---|
| `comparison_chat_app.py` | Live flat-versus-table-aware Streamlit app |
| `table_rag.py` | PostgreSQL schema, ingestion, dense retrieval, and CLI |
| `chunking_compare.py` | BM25 + dense RRF and context formatting |
| `context_attachments.py` | Finds and attaches nearby explanatory text |
| `eval_queries.py` | Loads and normalizes the evaluation cases |
| `evaluate_hybrid_contexts.py` | Deterministic context-completeness evaluation |
| `evaluate_chunking_judge.py` | Answer generation, judging, and fact-level evaluation |
| `generation_eval.py` | Joins context and answer evidence into outcome cells |
| `build_dashboard_data.py` | Exports saved evaluation data for React |
| `dashboard/` | Static React/Vite results explorer |
| `postgres-init/geha_rag.dump` | Reproducible database snapshot for Compose |

## Scope and limitations

- This is a research benchmark, not a production or HIPAA-ready application.
- The corpus is a curated extraction of coverage-policy tables and nearby text;
  results do not establish performance on arbitrary PDFs or domains.
- The benchmark focuses on evidence presence and answer use. It does not yet
  report standard retrieval metrics such as Recall@k, MRR, or nDCG.
- Retrieval uses a fixed embedding model and RRF configuration. There is no
  learned reranker, query rewriting, or cross-encoder stage.
- Token counts are estimates in parts of the evaluation.
- LLM judge results are model- and prompt-dependent; inspect fact-level outputs
  and deterministic context coverage before drawing conclusions.

Do not commit API keys or local passwords. Keep secrets in environment
variables or an ignored local `.env`, and never put real member or claims data
into this demonstration corpus.
