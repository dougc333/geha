# RAG Teaching Lab (Vercel)

A small, self-contained RAG app for teaching how retrieval works. Ask one
question about one paper and see **BM25, vector search and hybrid (RRF)
fusion side by side**, optionally followed by an LLM reranker and a grounded
answer. Chunks keep the same colour in every column, so it's easy to see which
method found what. A "What to notice" box summarises the differences, and each
pipeline stage (chunk → BM25 / vector → fuse → rerank → generate) has a
one-click explanation.

The corpus is deliberately small: two arXiv papers, *Attention Is All You
Need* (27 chunks) and *Orca* (105 chunks). Each has suggested questions chosen
to show where keyword search wins (numbers, names), where semantic search wins
(paraphrases, concepts), and where they agree.

This app uses OpenAI (`text-embedding-3-small`, `gpt-4o-mini`) and is
independent of the AWS stack in [`../../aws_rag`](../../aws_rag), which uses
Amazon Bedrock models. Both share one Neon database but keep their tables in
different Postgres schemas, because their vectors aren't compatible:

| Schema | Used by | Embeddings |
|---|---|---|
| `teaching` | this app | OpenAI, 1536-d |
| `public` | `aws_rag` | Amazon Titan v2, 1024-d |

## API

- `GET /api/documents`: indexed papers and chunk counts
- `POST /api/compare`: `{document_id, query, top_k, use_reranker, generate_answer}`
  returns the `bm25`, `vector`, `hybrid` and (if requested) `reranked` top-k
  lists, the answer, per-stage timings and stats (chunks searched, BM25 matches,
  query terms). One embedding call serves all columns.
- `POST /api/search`: the original single-mode search, kept for compatibility.

## Database

Create the `teaching` schema and tables (safe to re-run; it doesn't touch
`public`):

```bash
psql "$DATABASE_URL" -f schema.sql
```

Index the two demo papers with readable titles. With `DATABASE_URL` and
`OPENAI_API_KEY` exported, from this directory:

```bash
python scripts/ingest.py ../data/1706.03762v7.pdf --title "Attention Is All You Need (1706.03762)"
python scripts/ingest.py ../data/2306.02707.pdf --title "Orca (2306.02707)"
```

Keep the arXiv ID in the title: the page matches suggested questions on it.
The tables' schema comes from `RAG_SCHEMA` (default `teaching`) in both the
ingest script and the API.

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

- `DATABASE_URL` (the Neon integration sets it)
- `OPENAI_API_KEY` (for Production, and Preview if you use preview deployments)
- `RAG_SCHEMA` (optional; defaults to `teaching`)
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
