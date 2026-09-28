# Vercel selectable RAG demo

This deployable version preserves the original demo's experiment controls while
moving persistent retrieval state out of Streamlit and the local filesystem.

## Features

- true Okapi BM25 over the selected document's chunks
- OpenAI embeddings with pgvector cosine search
- hybrid retrieval using reciprocal-rank fusion
- optional LLM reranking
- optional grounded answer generation with chunk citations
- per-stage latency and raw retrieved evidence

The first deployment intentionally uses pre-indexed documents. That makes each
experiment fast and keeps document ingestion separate from interactive search.

## Database

Create a PostgreSQL database with pgvector, then run:

```bash
psql "$DATABASE_URL" -f schema.sql
```

Index one or more demo PDFs:

```bash
export DATABASE_URL='postgresql://...'
export OPENAI_API_KEY='...'
python scripts/ingest.py ../data/2306.02707.pdf ../data/1706.03762v7.pdf
```

## Local development

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
vercel dev
```

Run the dependency-free retrieval tests with:

```bash
python -m unittest test_rag_core.py
```

## Deploy

Create a Vercel project whose Root Directory is `e2e_RAG/vercel_app`. Add these
environment variables:

- `DATABASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_EMBEDDING_MODEL` (optional; defaults to `text-embedding-3-small`)
- `OPENAI_RERANK_MODEL` (optional; defaults to `gpt-4o-mini`)
- `OPENAI_GENERATION_MODEL` (optional; defaults to `gpt-4o-mini`)
- `ALLOWED_ORIGINS` (optional; defaults to `*`)

The included `vercel.json` pins the function to Vercel's `iad1` region to keep
it close to the Neon database provisioned in the Washington, D.C. region.

Then deploy from the project directory:

```bash
vercel
vercel --prod
```

Do not place API keys in `.env` files committed to Git. For healthcare claims or
other sensitive documents, confirm contractual and data-residency requirements
before enabling uploads; this portfolio configuration is intended for public,
non-PHI documents.
