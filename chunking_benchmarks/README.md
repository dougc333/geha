# Table-Aware Coverage Policy RAG

This project retrieves information from tables extracted from synthetic coverage-policy PDFs. It uses a parent-child retrieval design:

- Each table row is embedded as a searchable child record.
- The complete table is stored as its parent record.
- A matching row causes the entire table to be returned.
- The `search` command works locally without an LLM.
- The `ask` command sends the retrieved table to OpenAI and generates a cited answer.

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

[`tables.md`](tables.md) lists the qualifying PDFs and row counts. The current suite contains 34 cases across 17 policy documents. Its initial local retrieval baseline is 31/34 at top 1, 33/34 at top 3, and 34/34 at top 5.

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
- `tables.md`: qualifying policy inventory and retrieval baseline
- `*_table_openai.csv`: extracted table inputs in the coverage-policy directory
