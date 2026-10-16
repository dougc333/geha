# Table-Aware Coverage Policy RAG

This project retrieves information from tables extracted from synthetic coverage-policy PDFs. It uses a parent-child retrieval design:

- Each table row is embedded as a searchable child record.
- The complete table is stored as its parent record.
- A matching row causes the entire table to be returned.
- The `search` command works locally without an LLM.
- The `ask` command sends the retrieved table to OpenAI and generates a cited answer.

![Table-aware parent-child RAG architecture](table_rag_architecture.svg)

```text
Question
   |
   v
Local embedding model (BAAI/bge-small-en-v1.5)
   |
   v
pgvector row similarity search
   |
   v
Complete parent table
   |
   +--> search: print locally
   |
   +--> ask: OpenAI answer with source and table citation
```

## Semantic search implementation

Semantic search is implemented locally with Sentence Transformers and PostgreSQL `pgvector`; it does not require an LLM. During ingestion, every normalized table row is converted into text containing its source filename, inferred table title, column names, and nonempty cell values. `BAAI/bge-small-en-v1.5` encodes that text as a normalized 384-dimensional vector, which is stored in `policy_table_vectors` and linked to the complete table in `policy_tables`.

At query time, the same model encodes and normalizes the user's question. PostgreSQL uses the `pgvector` cosine-distance operator to rank child rows:

```sql
1 - (embedding <=> query_embedding) AS similarity
```

An HNSW index using `vector_cosine_ops` accelerates this search. The nearest `--candidate-rows` are grouped by `table_id`; each parent table receives the maximum similarity of any matching child row. The highest-ranked `--top-tables` parent records are then returned with their complete CSV, structured rows, source filename, table number, and title.

```text
Table row + headers + source metadata
               |
               v
      normalized row embedding
               |
Question --> normalized query embedding
               |
               v
       cosine similarity search
               |
               v
 best child rows grouped by table_id
               |
               v
        complete parent tables
```

The current retriever is semantic-only: it does not yet combine vector similarity with PostgreSQL full-text search, BM25, exact procedure-code matching, or a separate reranker. The optional `ask` command runs only after retrieval and does not affect which tables are selected.

The vector-only retriever remains available as the ablation baseline. The
comparison chatbot adds in-memory BM25 over the same child-row corpus and fuses
BM25 and pgvector ranks with reciprocal-rank fusion before either returning flat
rows or expanding them to parent tables.

### Reranking status

There is currently no learned reranker. Reciprocal-rank fusion reorders results
by combining the BM25 and pgvector rankings, but it does not evaluate each
query-candidate pair like a cross-encoder or LLM reranker would.

A future reranking stage would sit after RRF and before final context selection:

```text
BM25 candidates + pgvector candidates
                  |
                  v
             RRF fusion
                  |
                  v
      cross-encoder or LLM reranker
                  |
                  v
       top chunks / parent tables
```

The reranker should score only a bounded candidate set, such as the top 20–50
RRF results, to control latency and token cost. The flat and table-aware paths
must use the same reranked child list so their comparison remains fair.

<!-- HYBRID_CONTEXT_RESULTS_START -->
### Hybrid retrieval context comparison

Both cases use the same BM25 + pgvector RRF child ranking.

| Question slice | Context strategy | Cases | Avg evidence coverage | Complete evidence | Expected table present | Avg estimated tokens | Evidence / 1k tokens |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Overall | Flat semantic chunks | 41 | 81.7% | 58.5% | 97.6% | 292 | 8.76 |
| Overall | Table-aware RAG | 41 | 100.0% | 100.0% | 100.0% | 431 | 7.92 |
| Preference | Flat semantic chunks | 34 | 81.4% | 58.8% | 97.1% | 285 | 7.22 |
| Preference | Table-aware RAG | 34 | 100.0% | 100.0% | 100.0% | 405 | 7.12 |
| Relation | Flat semantic chunks | 7 | 83.3% | 57.1% | 100.0% | 328 | 15.24 |
| Relation | Table-aware RAG | 7 | 100.0% | 100.0% | 100.0% | 558 | 10.76 |

Table-aware change versus flat chunks: average evidence coverage +18.3%, complete evidence +41.5%, and average context tokens +139.

This is a retrieval/context benchmark over labeled expected values. It does not use an LLM judge and does not measure generation quality.
<!-- HYBRID_CONTEXT_RESULTS_END -->

## Requirements

- macOS or Linux
- Docker with Compose
- [`uv`](https://docs.astral.sh/uv/)
- An OpenAI API key for the optional `ask` command
- Extracted table files named `*_table_openai.csv`

The CSV extractor places multiple tables in one file and separates them with two blank rows.

## Setup

Run commands from the repository root:

```bash
cd /Users/dc/geha
uv sync
```

Create the local configuration:

```bash
cp chunking_benchmarks/.env.example chunking_benchmarks/.env
```

Edit `chunking_benchmarks/.env`:

```dotenv
GEHA_RAG_DATABASE_URL=postgresql://geha:geha-local@127.0.0.1:5433/geha_rag
OPENAI_API_KEY=sk-your-key
OPENAI_MODEL=gpt-3.5-turbo
```

The program loads this project file with `override=True`, so its values replace stale variables exported by an earlier shell session. The `.env` file is ignored by Git. Never put a real key in `.env.example`.

## Start PostgreSQL and pgvector

```bash
docker compose -f chunking_benchmarks/docker-compose.pgvector.yml up -d pgvector
```

Check its status:

```bash
docker compose -f chunking_benchmarks/docker-compose.pgvector.yml ps
```

The database listens on `127.0.0.1:5433` and stores its data in the `geha_pgvector_data` Docker volume.

## Initialize the schema

```bash
uv run python chunking_benchmarks/table_rag.py init-db
```

This creates:

- `policy_tables`: complete parent tables and source metadata
- `policy_table_vectors`: embedded child rows
- An HNSW cosine-similarity index over the 384-dimensional embeddings

## Ingest extracted tables

```bash
uv run python chunking_benchmarks/table_rag.py ingest \
  /Users/dc/geha/downloads/coverage-policies
```

Ingestion is repeatable. Existing tables with the same source filename and table number are updated, and their child vectors are rebuilt.

The 32 extracted CSV files in `/Users/dc/geha/downloads/coverage-policies` produce 84 parent tables and 463 searchable child rows.

## Retrieve a complete table locally

```bash
uv run python chunking_benchmarks/table_rag.py search \
  "Which bendamustine products are non-preferred?"
```

Useful retrieval controls:

```bash
uv run python chunking_benchmarks/table_rag.py search \
  "Which bendamustine products are non-preferred?" \
  --top-tables 3 \
  --candidate-rows 30
```

`--candidate-rows` controls how many row matches are considered before grouping them by parent table. `--top-tables` controls how many complete tables are returned.

## Streamlit parent-child retrieval UI

The Streamlit UI makes both retrieval levels visible: it shows the child rows
that produced each similarity score and the complete parent table returned through
their `table_id` relationship. Its query picker is populated from the preference
and row-to-column evaluation suites.

After starting PostgreSQL, initializing the schema, and ingesting the CSV files,
run:

```bash
uv run streamlit run chunking_benchmarks/streamlit_app.py
```

Useful evaluation-backed queries include:

- `Which bendamustine products are non-preferred?`
- `For bendamustine HCPCS J9036, what drug, preference, and prior authorization are listed?`
- `Which long-acting G-CSF drugs are preferred, and what HCPCS code and prior authorization does each have?`
- `Which gemcitabine products do not require prior authorization? Give each drug, HCPCS code, and preference.`
- `Which pemetrexed products are preferred, and what is each HCPCS code?`
- `In the Taxotere and Docivyx policy, list each drug with its HCPCS code, preference, and prior authorization requirement.`
- `For Xgeva policy code Q5157, which denosumab drug names are listed and what are their preference and prior authorization status?`

## Chatbot comparison: flat hybrid chunks versus table-aware RAG

The comparison chat holds the query, BM25 corpus, embedding model, pgvector
index, and reciprocal-rank-fused child ranking constant. Flat mode returns the
top fused row chunks. Table-aware mode expands the same fused child matches to
their complete parent tables. This isolates context assembly rather than
confounding it with a different retriever or generator.

```text
query ─┬─ BM25 rank ─────┐
       └─ pgvector rank ─┴─ RRF child ranking
                              ├─ flat: top row chunks
                              │     └─ answer LLM ── response to user
                              │                         └─ blind LLM judge
                              └─ table-aware: complete parent tables
                                    └─ answer LLM ── response to user
                                                        └─ blind LLM judge
```

Answer generation and judging are optional. Each branch uses a separate answer
call. The judge is blind to which retrieval strategy produced the answer. For
labeled questions it checks the response against both that branch's evidence
and the verified structured reference; custom questions remain context-only.

The demo opens with a saved 41-question evaluation panel showing where parent
expansion added evidence. Results are broken out by multi-row preference lookup
and row-to-column relationship questions. A second table labels proposed future
evaluation types—single-row lookup, qualifier/exception lists, cross-table
synthesis, and hard negatives—separately from the types measured today. Select
an evaluation type and use **Run selected example** to execute either a saved
case or a custom chat question through both context paths.

```bash
cd /Users/dc/Documents/ChatGPT/aggents/geha_cloud_reliability
uv run streamlit run chunking_benchmarks/comparison_chat_app.py
```

Ask an evaluation-backed question to compare:

- the exact retrieved row chunks;
- complete parent tables;
- estimated context tokens;
- expected evidence coverage; and
- the rank of the expected parent table.

When `OPENAI_API_KEY` is configured, the chatbot also generates one answer from
each context and evaluates each independently with the same strategy-blind LLM
judge. For the 41 labeled questions, `YES` requires the response to include the
complete verified reference, contain no extraneous claims, and ground every
claim in that side's retrieved context. A deterministic generation check also
reports expected-value coverage and rejects unexpected HCPCS codes. The UI
reports those generation metrics alongside grounding, missing information, and
answer-plus-judge token usage. Configure answer and judge models independently
with `OPENAI_MODEL` and `OPENAI_JUDGE_MODEL`.

The UI always displays raw evidence next to generated responses so a fluent
answer cannot conceal a retrieval or context-assembly failure. LLM judgments
are evaluation signals rather than ground truth and should be calibrated
against labeled, human-reviewed cases before becoming a promotion gate.

Run every suggested query with resumable per-query checkpoints:

```bash
zsh -lic 'cd /Users/dc/Documents/ChatGPT/aggents/geha_cloud_reliability && \
  .venv/bin/python chunking_benchmarks/evaluate_chunking_judge.py --resume'
```

The batch writes `chunking_judge_results.json` with full answers, verified
references, judge reasons, missing information, deterministic generation
metrics, ranks, coverage and token usage, plus a concise
`chunking_judge_results.md` table. The Streamlit comparison automatically shows
the completed table when the JSON report exists. It also replaces the generated
results block below, leaving the rest of this README unchanged. Version 2
checkpoints invalidate older context-only judge records when `--resume` is used.

<!-- CHUNKING_JUDGE_RESULTS_START -->
### Recorded generation-evaluation results

Results pending. The reference-aware external model evaluation has not been run yet.
<!-- CHUNKING_JUDGE_RESULTS_END -->

For these table questions, “flat semantic chunks” means independently returned
semantic row chunks; it does not mean that a semantic-boundary splitter created
the underlying source tables.

When an evaluation query is selected, the UI also displays its expected parent
table and expected values, then reports the rank at which that parent was retrieved.

## Generate an answer

The policy documents in this demo are synthetic. The `ask` command transmits the retrieved table content to the configured OpenAI model:

```bash
uv run python chunking_benchmarks/table_rag.py ask \
  "Which bendamustine products are non-preferred?"
```

Expected answer:

```text
The non-preferred bendamustine products are Bendeka, Belrapzo, and Vivimusta.
(Source: geha-coverage-policy-bendamustine.pdf,
Table: Drug preference and prior authorization)
```

Override the configured model for one request:

```bash
uv run python chunking_benchmarks/table_rag.py ask \
  "Which bendamustine products are non-preferred?" \
  --model gpt-3.5-turbo
```

## Run tests

```bash
uv run python -m unittest -v chunking_benchmarks/test_table_rag.py
uv run python -m py_compile chunking_benchmarks/table_rag.py
```

The unit tests cover table separation, uneven-row normalization, and inferred table titles.

## Preference evaluation set

[`table_preference_evals.json`](table_preference_evals.json) contains one preferred query and one non-preferred query for every qualifying policy. Each case records the expected source, table title, preference class, and all expected drug-name phrases.

[`tables.md`](tables.md) lists the qualifying PDFs and row counts. The current suite contains 34 cases across 17 policy documents. Detailed per-query rankings and product comparisons are in [`table_preference_eval_results.md`](table_preference_eval_results.md).

| Measurement | Correct | Accuracy | Error rate |
| --- | ---: | ---: | ---: |
| Expected source at top 1 | 31/34 | 91.2% | 8.8% |
| Expected source within top 3 | 33/34 | 97.1% | 2.9% |
| Expected source within top 5 | 34/34 | 100.0% | 0.0% |
| Exact table at top 1 | 28/34 | 82.4% | 17.6% |
| Exact table within top 3 | 32/34 | 94.1% | 5.9% |
| Exact table within top 5 | 33/34 | 97.1% | 2.9% |
| Exact product-list match from the top table | 28/34 | 82.4% | 17.6% |

## Row versus whole-table retrieval ablation

[`evaluate_table_ablation.py`](evaluate_table_ablation.py) compares the existing row-vector retriever with a baseline that embeds each complete table once. Both methods use the same ingested parent tables, embedding model, questions, and deterministic answer extraction. The full-table vectors live in a separate `policy_table_full_vectors` table; the existing row index is unchanged.

Start PostgreSQL and ingest the extracted CSVs as above, then run:

```bash
uv run python chunking_benchmarks/evaluate_table_ablation.py all
```

To rebuild only the full-table index or repeat the evaluation:

```bash
uv run python chunking_benchmarks/evaluate_table_ablation.py index
uv run python chunking_benchmarks/evaluate_table_ablation.py compare
```

The report is written to `chunking_benchmarks/table_ablation_results.json`. It scores exact-table Hit@1, Hit@3, Hit@5, and exact answer match. The 34 existing preference questions are joined by seven [`row-to-column questions`](table_relation_evals.json) with verified drug, HCPCS, preference, and prior-authorization cells. A correct answer must come from the top retrieved table and match the complete expected set of rows. This isolates retrieval representation; it does not measure PDF extraction quality or LLM answer quality. Long whole-table strings may be truncated by the embedding model, which is part of this baseline's behavior.

On the 32 extracted CSV files available locally on September 18, 2026 (84 tables and 463 row vectors), the [`ablation report`](table_ablation_results.json) found:

| Questions | Retriever | Exact table Hit@1 | Hit@3 | Hit@5 | Exact answer |
| --- | --- | ---: | ---: | ---: | ---: |
| Preference (34) | Row vectors | 28/34 | 32/34 | 33/34 | 28/34 |
| Preference (34) | Full-table vectors | 31/34 | 34/34 | 34/34 | 31/34 |
| Row-to-column (7) | Row vectors | 7/7 | 7/7 | 7/7 | 7/7 |
| Row-to-column (7) | Full-table vectors | 4/7 | 6/7 | 6/7 | 4/7 |

The answer step reads the complete top table in both methods. The row-to-column exact-answer score therefore tracks top-table retrieval in this run; it does not independently test an LLM's ability to interpret cells. Seven targeted relation questions are too few to establish a general performance advantage.

For a repeatable run on an existing Docker volume, use a new database so older ingestions cannot add extra tables to the search corpus:

```bash
docker exec geha-pgvector psql -U geha -d postgres -c 'CREATE DATABASE geha_ablation'
uv run python chunking_benchmarks/table_rag.py --database-url postgresql://geha:geha-local@127.0.0.1:5433/geha_ablation init-db
uv run python chunking_benchmarks/table_rag.py --database-url postgresql://geha:geha-local@127.0.0.1:5433/geha_ablation ingest /Users/dc/geha/downloads/coverage-policies
uv run python chunking_benchmarks/evaluate_table_ablation.py all --database-url postgresql://geha:geha-local@127.0.0.1:5433/geha_ablation
```

If `geha_ablation` already exists, choose another unused database name throughout these commands to ensure a clean corpus.

Error rate is `1 - accuracy`. Product answers are extracted deterministically from the top retrieved table, without an LLM, so the table reports retrieval and table-interpretation errors rather than generation or hallucination errors.

Run the complete local comparison:

```bash
cd /Users/dc/geha/chunking_benchmarks
uv run python evaluate_table_preferences.py
```

The evaluator records the top-five tables and similarity scores for every query, compares the expected and retrieved table, and extracts the requested products from the top result without calling an LLM. It writes:

- `table_preference_eval_results.md`: readable comparison of all 34 cases
- `table_preference_eval_results.json`: complete machine-readable results

## Stop the database

```bash
docker compose -f chunking_benchmarks/docker-compose.pgvector.yml down
```

This keeps the database volume. To delete the stored database as well, explicitly remove the `geha_pgvector_data` Docker volume.

## Files

- `table_rag.py`: schema creation, ingestion, retrieval, and answer generation
- `test_table_rag.py`: local unit tests
- `docker-compose.pgvector.yml`: PostgreSQL 17 with pgvector
- `.env.example`: safe configuration template
- `table_preference_evals.json`: preferred and non-preferred retrieval/answer cases
- `evaluate_table_preferences.py`: repeatable local evaluation runner
- `table_preference_eval_results.md`: complete readable evaluation report
- `table_preference_eval_results.json`: machine-readable evaluation report
- `tables.md`: qualifying policy inventory and retrieval baseline
- `table_rag_architecture.svg`: editable architecture figure
- `table_rag_architecture.png`: rendered architecture figure
- `*_table_openai.csv`: extracted table inputs in the coverage-policy directory
