# aws_rag: project log

A condensed, chronological history of how `aws_rag` was built, from the first
question ("how do I build a chunker on AWS for PDFs in S3?") to now. It records
what was asked, what was decided and why, what broke and how it was fixed,
the measurements, and the commits and pull requests. Secrets (keys, passwords,
connection strings) are deliberately left out.

Dates: 2026-09-28 to 2026-09-29. Account/region: AWS `669059827483`, stack
`sam-app` in `us-west-2`. Repo: `dougc333/geha`.

---

## 1. Starting point

Before `aws_rag`, the RAG demo lived in `e2e_RAG/vercel_app`: a Vercel app with
a FastAPI search API (BM25 in Python, OpenAI embeddings in pgvector, hybrid
RRF, an LLM reranker and grounded answers) over a few pre-indexed PDFs in a
Neon Postgres database. An architecture figure was drawn for it
(`vercel_app/rag_architecture.svg`).

## 2. The chunker (S3 → SQS → Lambda)

**Question:** how to build a chunker on AWS for PDFs in S3.

**Design:** S3 `ObjectCreated` → SQS queue (with a dead-letter queue) →
Chunker Lambda (Python + PyMuPDF, 350-word chunks, 50-word overlap, reusing
`rag_core.chunk_text`) → one `chunks/<sha256 of PDF>.jsonl` per paper in a
second bucket. SQS gives retries, a DLQ and concurrency control; keying output
by the PDF's SHA-256 makes reprocessing idempotent.

**Built:** `/Users/dc/geha/aws_rag` with `template.yaml` (both buckets, queue +
DLQ, queue policy, S3 notification, Lambda), `chunker/handler.py`, README.

**First deploy failed:** every invocation raised `No module named 'pymupdf'`
because `sam deploy` ran without `sam build`. Fixed by building first; the
README now warns about it. The Attention paper produced 27 chunks, pages 1–15.

## 3. The embedder

**Decisions (asked):** write to the existing Neon database the Vercel app used
(no VPC needed), with OpenAI `text-embedding-3-small`.

**Built:** chunk-file notification → embed queue + DLQ → Embedder Lambda →
`rag_documents` / `rag_chunks` in one transaction per paper. Secrets in
Secrets Manager.

**Database confusion resolved:** there was no `DATABASE_URL` anywhere at first.
It turned out to be a Neon database created through Vercel's Neon integration;
its connection string was copied from Vercel. `psql` wasn't installed
(`brew install libpq`), and an unquoted `&` in the URL broke the `export`.
The tables already existed. Credentials were pasted into the chat at points;
rotation was recommended and declined.

**Result:** 27 Attention chunks embedded into Neon in ~5 s.

## 4. Query API and UI on Lambda

The Vercel app's FastAPI code was moved into a `QueryApi` Lambda (Mangum
adapter) behind a public **Function URL**, which also serves the page at `/`.
A hybrid + rerank + answer query took ~8.7 s.

## 5. Leaving OpenAI: Amazon Bedrock

**Goal:** remove the OpenAI dependency.

- The first plan was Cohere Embed v4 + Cohere Rerank 3.5 + a Bedrock model.
  Alternatives to Claude were listed; **Nova Lite** was chosen for answers on
  cost ($0.06 / $0.24 per million tokens; Nova 2 Lite is ~7× more).
- **Cohere was blocked:** Bedrock sells third-party models through AWS
  Marketplace, which rejected the account's payment method
  (`INVALID_PAYMENT_INSTRUMENT`).
- **All-Amazon stack chosen:** Titan Text Embeddings v2 (1024-d), Amazon Rerank
  1.0, Nova Lite. The Neon column changed to `vector(1024)` and everything was
  re-embedded.
- `DATABASE_URL` moved from Secrets Manager ($0.40/month) to a free SSM
  Parameter Store SecureString. Names starting with `aws` are reserved, so it's
  `/rag-demo/database-url`.
- Cost at demo scale: well under $1/month. Lambda, SQS and logs are in the free
  tier. No AWS SQL service is free for this account (RDS's 12-month free tier
  doesn't apply; Aurora DSQL has no pgvector), so Neon stayed.
- **Fix:** hybrid fusion pushed the "what is Orca" definition just past the top
  20 sent to the reranker; the rerank pool became 50 (same cost per 100 docs).

## 6. Retiring Vercel; the chatbot

- The Vercel deployment was retired as the main UI (the Neon database it
  created is kept). `aws_rag` became self-contained (own `schema.sql`, README).
- **Chatbot** (`/chat`, `chat.py`): multi-turn chat across all papers with
  follow-up rewriting, hybrid retrieval, rerank and cited answers, plus
  **"Add an arXiv paper"** (`/api/arxiv`). The first version answered "what is
  orca?" about killer whales; the answer prompt was tightened to stay within
  the sources. `chatbot/add_arxiv.py` is a CLI loader.
- MCP was discussed: not needed for our own chatbot; only for exposing the
  papers to Claude Desktop/Code etc.

## 7. Observability: Langfuse

Every chat message and lab search is traced (route/rewrite, retrieve, rerank,
answer; prompts, chunks, token usage, timings), with one session per chat page
load and 👍/👎 scores. Keys live in SSM; traces are flushed at the end of each
request because Lambda freezes. Langfuse doesn't know Bedrock prices: a Nova
Lite price definition was added through the Langfuse API, and the code reports
embedding and rerank costs itself (a follow-up message ≈ $0.0012, mostly rerank).

## 8. Paper metadata and the library catalog

- `rag_documents` gained arXiv metadata: authors, dates, abstract, categories,
  comment, journal ref, DOI. The metadata travels as a **sidecar JSON next to
  each PDF in S3**; the chunker carries it and the embedder stores it.
  `backfill_arxiv_metadata.py` fixed the four papers titled by file name.
- The chatbot got a catalog of all papers in its prompt, so "list the papers" and
  "who wrote X" worked.

## 9. Scaling to ~100 papers

- `chatbot/download_top_cited.py` downloaded the **300 most-cited ML/AI arXiv
  papers**, ranked by Semantic Scholar citation counts. OpenAlex was rejected
  for mismatched titles and duplicates. Each PDF has a metadata sidecar; 1.3 GB
  locally, git-ignored.
- The top 100 were uploaded (`scripts/upload_papers.py`). **29 papers failed:**
  their text contained NUL characters that Postgres rejects; stripped in the
  chunker and embedder. One paper (2203.00667) is image-only and can't be indexed.
- The chatbot's BM25 loaded every chunk into Python per turn. It moved to
  **Postgres full-text search** (generated `tsvector` + GIN), ~150 ms at 5,300 chunks.

## 10. Weaviate comparison

- Pinecone and Weaviate were explained; Weaviate was chosen to "get a feel"
  because its native BM25 + hybrid replaces the code that didn't scale.
- A free **Weaviate Cloud sandbox** (us-east-1) was set up; its key was read from
  `.zshrc` into SSM. The sandbox only allows the **HFresh** index (not HNSW).
- `scripts/load_weaviate.py` copies chunks with their existing Titan vectors
  (no re-embedding). `/backends` compares Postgres and Weaviate side by side,
  and the chat has a search-engine selector.

## 11. Routing, REST and fixes

- **"Show me all 100 titles"** listed only 10 of 103: the answer model can't
  reproduce long lists. A **router** (one Nova Lite call returning JSON) now
  sends list/count/author/topic questions to **SQL** (`library.py`) for
  complete, exact answers; content questions go to RAG as before. The router
  also writes the standalone search query (replacing the rewrite step) and runs
  as a function inside the QueryApi Lambda, not a separate Lambda (README
  explains when that would change). `/api/documents` gained filters (`author`,
  `year_from`, `year_to`, `category`, `q`).
- **Swagger** is at `/docs` (OpenAPI 3.1, generated by FastAPI).
- **Bug found via Swagger:** since the Langfuse change, `/api/search` rejected
  every request (422) and `/openapi.json` returned 500. The tracing decorator
  hid the request type from FastAPI. Fixed by tracing an inner function.
- **Postgres connection reuse:** a new TLS connection per request cost ~1 s.
  One connection per Lambda container, pinged after 60 s idle, took Postgres
  retrieval from ~1.5 s to ~0.31 s and chat from ~4.9 s to ~3–3.8 s.
- A PR merge (#13) happened before three later commits were pushed; they
  reached `main` via #14.

## 12. The retrieval eval

- `evals/generate_questions.py`: 40 questions (20 facts, 20 paraphrases), each
  kept only if its evidence quote appears verbatim on its page. Reference-list
  trivia and non-standalone questions are filtered out; 9 weak ones were
  regenerated with `--replace`.
- `evals/run_eval.py` scores setups on page hit@1/5/10, MRR@10 and paper hit@5.

**Key finding:** Postgres `ts_rank_cd` was the weak link (hit@5 0.50–0.55 vs
Weaviate BM25 0.85); Postgres hybrid was no better than vector alone.
Weighting fusion toward vector didn't help.

## 13. Real BM25 in Postgres

- Neon has **deprecated `pg_search`** (ParadeDB BM25), so BM25 was written in SQL.
- The first version was correct but took **~8.5 s** (it unpacked every
  candidate's `tsvector`), and the eval recomputed it per setup; an in-script
  cache fixed the eval's slowness.
- **`rag_terms`**: an inverted index (word, chunk, count) filled by a trigger,
  656k rows / 70 MB at 5,300 chunks. The planner still scanned the whole table
  until a `LATERAL … OFFSET 0` fence forced per-word index lookups:
  **9–38 ms** in the database.
- **Result:** BM25 + vector + rerank in Postgres matched Weaviate + rerank
  exactly (hit@1 0.82, hit@5 0.95, MRR 0.88 vs 0.75 / 0.85 / 0.79 before).
  The chatbot switched to it (`KEYWORD_SEARCH=bm25`), removing the dependency
  on the expiring sandbox.

## 14. Access key

The Function URL was public. Every `/api/*` call except `/api/health` now
needs `X-API-Key` matching `/rag-demo/api-key` in SSM (constant-time compare;
the Lambda fails closed if the parameter is missing). Pages ask for the key
once and keep it in localStorage; Swagger has an Authorize button; the CLI
reads it from SSM. The key was pasted into the chat later; rotation declined.

## 15. Scaling to 202 papers

- 99 more papers loaded: **202 papers, 10,167 chunks, 319 MB** (Neon free tier
  is 0.5 GB). `load_weaviate.py` now deletes stale copies (it found 35).
- Eval, 103 → 202 papers: chatbot 0.82/0.95/0.88 → **0.78/0.93/0.84**;
  Weaviate + rerank 0.82/0.95/0.88 → 0.78/0.95/0.85. Vector search lost most at
  hit@1 (0.55 → 0.47); BM25 slowed ~184 → ~294 ms (from a laptop).
- The auto-mode permission check was down for a while, so the eval was run in
  the user's terminal. Langfuse "401 Unauthorized" noise came from stale keys in
  `.zshrc`; the eval now disables tracing.
- Streaming answers were considered and deferred: Python Lambdas need the
  Lambda Web Adapter for response streaming.

## 16. Table-aware parsing with Docling

- **Test** (`e2e_RAG/pymupdf_docling_test/`): on the Attention paper, Docling
  found all 4 tables with captions and correct structure. PyMuPDF
  `find_tables` found 2 of 4 (none of the booktabs tables), scrambled them, and
  reported figures as tables; its text mode turned every page into a "table".
  Docling preprocessing runs on the Mac; chunk files are uploaded to S3 and the
  embedder replaces a paper's chunks.
- **`local_ingest/docling_chunks.py`**: text chunks plus **one chunk per table**
  (caption + compact Markdown, split by rows over ~4,000 characters), in the
  chunker's format with the same `document_id`. OCR off; 2–13 s per paper.
- **Table eval:** 13 table questions (value verified in the table) and
  `evals/answer_check.py` (does the chatbot's answer contain the gold value?).
- **Pilot, 20 papers:** table answer accuracy **8/13 → 11/13 (0.62 → 0.85)**;
  table hit@1 0.54 → 0.85. With flat text the right page was found but the
  wrong number read (BERT-Large SWAG 86.3 instead of 86.6).
- **Full rollout, 202 papers** (~34 min, 1,600+ tables):
  - `boto3` was missing from the Docling venv, so uploads were done with the CLI.
  - **T5 failed to embed:** a ~14,000-character table row was 8,257 tokens,
    over Titan's 8,192. The splitter now cuts long rows, and the embedder embeds
    at most 10,000 characters of a chunk. The AWS session had also expired and
    needed `aws login`.
  - Results: tables 0.62 → 0.85 correct; ordinary questions hit@5 unchanged
    (0.93) but hit@1 0.78 → 0.72. Partly a chunker flaw: **figure captions and
    footnotes were dropped** (q21's answer is a figure caption).
- **v2, captions and footnotes kept** (only page headers/footers dropped):
  10,988 chunks. The eval run hit an expired AWS session partway and was re-run
  after `aws login`. Final: table answers **0.85**, table hit@1/hit@5/MRR
  **0.85 / 1.00 / 0.90**, ordinary questions 0.75 / 0.93 / 0.83 (flat was
  0.78 / 0.93 / 0.84, within noise). q21 is back at rank 1.

---

## Current state (2026-09-29)

- **Papers:** 202, most-cited ML/AI, with arXiv metadata; Docling chunks
  (tables as Markdown chunks, captions and footnotes kept); 10,988 chunks in
  Neon, mirrored in Weaviate.
- **Chatbot:** router → SQL library answers, or BM25 (`rag_terms`) + pgvector →
  RRF → Amazon Rerank → Nova Lite with citations. ~2.4–3.9 s per answer.
- **Quality:** ordinary questions hit@5 0.93; table questions hit@5 1.00 and
  85% of table answers correct.
- **Pages:** `/` retrieval lab, `/chat`, `/backends`, `/docs` (Swagger); API
  key required on `/api/*`.
- **Tracing:** Langfuse (EU), with costs, sessions and feedback.
- **Docs:** `README.md` (architecture figure `docs/architecture.svg`, quality
  and timing tables, eval results), this log.

## Figure search (2026-09-29)

- Asked how to search figures; chose option 1: Nova Lite describes each
  Docling-extracted figure and the description is indexed as a chunk (vs.
  ColPali-style image embeddings).
- `docling_chunks.py --figures` saves PNGs + `figures.json`;
  `describe_figures.py` calls Nova Lite (title + caption + image), caches
  descriptions, appends `kind: "figure"` chunks, uploads PNGs and JSONL.
- 9 figure-only questions (f01–f09), answers checked absent from page text.
  Pilot on 20 papers: 0/9 → 6/9; a "Text in figure first" prompt → 7/9.
- Chat UI fixes found while testing: the key `prompt()` is blocked in the app's
  browser pane (replaced by an in-page dialog; Cancel label was white on
  white); answers' Markdown tables now render as HTML tables.
- Thumbnails: PNGs in `s3://…chunks…/figures/`, `rag_chunks.image`, presigned
  `image_url` on chat sources, figure strip under the answer.
- Rollout to all 203 papers (incl. Orca and Self-RAG from `e2e_RAG/data/`):
  1,886 figures, $0.24. Llama 3 failed to embed repeatedly on a Titan
  `ModelErrorException`; added a per-chunk retry in the embedder.
- Final: all 62 questions 0.77 / 0.95 / 0.85; figures 7/9; tables 11/13.
- Filter bug: "shorter side >= 150 px" dropped wide figures (Atari's three,
  YOLO Figure 1, ResNet Figure 2; 16 of 149 in the pilot). Now every captioned
  figure is kept; cached descriptions matched by page/caption/size. Re-run:
  +226 figures (2,112 in 198 papers), $0.026. 73 descriptions are degenerate
  (repeated " | "), e.g. XGBoost's AUC plot; figures 6/9 on this run.
- Degenerate descriptions: new description-first prompt (text grouped by panel,
  no axis ticks, capped); PDF text layer read inside each figure box as a
  spelling hint (as chunk text it lost which pie a value belonged to). 73 → 0;
  figure questions 20/27 → 24/27 (offline, 3 runs). Then all 2,032 other
  figures re-described ($0.253). Live: 7/9. New architecture diagram.

## Pull requests

| PR | Content | State |
|---|---|---|
| `dougc333/geha#9` | aws_rag: chunker, embedder, query Lambda, Bedrock | merged |
| `dougc333/geha#10` | Editable questions, Reranker label, untrack `.aws-sam` | merged |
| `dougc333/geha#11` | Paper chatbot + arXiv ingestion | merged |
| `dougc333/geha#12` | Langfuse tracing, sessions, feedback, costs | merged |
| `dougc333/geha#13` / `#14` | arXiv metadata, 100 papers, Weaviate; then router, `/api/search` fix, connection reuse | merged |
| `dougc333/geha#15` | Retrieval eval, BM25 via `rag_terms`, access key, 202 papers, Docling tables, figure | open |
| `dougc333/united#1` | README: the four Streamlit apps | open |

## Open items

- Storage: 319 MB of Neon's free 0.5 GB; the remaining 100 downloaded papers
  would need a paid plan or trimming.
- The Weaviate sandbox expires ~14 days after creation; it's optional now.
- The Vercel teaching lab (`vercel-teaching` branch) still needs its two papers
  loaded with an OpenAI key.
- Delete the old Vercel project (keep the Neon database). Remove secrets from
  `~/.zshrc` (they're all in SSM). Decide on the untracked Keynote file and
  `e2e_RAG/pymupdf_docling_test/`.
- Credentials pasted into chat (database password, OpenAI key, API key) were
  not rotated, by choice.
