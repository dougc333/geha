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
docker compose -f chunking_benchmarks/docker-compose.pgvector.yml up -d
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

The current sample corpus produces 103 parent tables and 691 searchable child rows from 35 extracted CSV files.

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
