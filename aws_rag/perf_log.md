# aws_rag: performance log

Every change that moved latency, retrieval quality, answer accuracy, cost or
storage, in order, with the before/after numbers, the cause, the fix, and how
it was measured. Companion to [`log.md`](log.md), which is the full project
history. Dates: 2026-09-28 to 2026-09-29.

**How things were measured**

- **Live latency:** per-stage timings returned by the API (`timings` in
  `/api/chat`, `/api/search` and `/api/compare-backends`), called from a
  laptop with `curl`. The Lambda is in us-west-2 and Neon in us-east-1, so each
  database round trip includes ~60–80 ms of cross-country network time.
- **Retrieval quality:** `evals/run_eval.py`, which runs the deployed query code
  from a laptop against live Neon, Weaviate and Bedrock. *Page hit@k* means the
  page holding the answer is among the top k chunks; *MRR@10* is the mean of
  1/rank of that page (0 if not in the top 10). With 40 questions, one question
  is 2.5 points, so differences under ~5 points are noise.
- **Answer accuracy:** `evals/answer_check.py`: whether the chatbot's final
  answer contains the gold value.
- **Database timing:** `EXPLAIN (ANALYZE)` on Neon, which excludes network time.
- "Laptop" timings include network round trips and vary with the connection.

---

## 1. End-to-end query latency

### 1.1 First Lambda version (OpenAI models): 8.7 s

The Vercel app's FastAPI code in a Lambda, still calling OpenAI for embeddings,
reranking and answers. One hybrid + rerank + answer query on the Orca paper:

| Stage | Time |
|---|---|
| BM25 (Python, over one paper's chunks) | 0.30 s |
| Vector (OpenAI embedding + pgvector) | 1.65 s |
| Rerank (`gpt-4o-mini` ranking chunks as JSON) | 3.37 s |
| Answer (`gpt-4o-mini`) | 2.31 s |
| **Total** | **8.72 s** |

### 1.2 Switch to Amazon Bedrock: 8.7 s → 3.2–3.5 s

Titan Text Embeddings v2, Amazon Rerank 1.0 (a scoring model rather than a chat
model asked to sort) and Nova Lite:

| Stage | OpenAI | Bedrock |
|---|---|---|
| BM25 | 0.30 s | 0.30–0.34 s |
| Vector | 1.65 s | 0.29–0.35 s |
| Rerank | 3.37 s | 0.53–0.55 s |
| Answer | 2.31 s | 0.79–1.32 s |
| **Total** | **8.72 s** | **3.21–3.53 s** |

The biggest single saving came from replacing the LLM reranker with a
purpose-built reranker: 3.4 s → 0.55 s. Cost per message also dropped
(section 6).

### 1.3 Chatbot at 4 papers: ~3.5–5.5 s

The chatbot added a rewrite step for follow-ups (~0.3 s) and searched all papers:

| Stage | Time |
|---|---|
| Rewrite (Nova Lite; follow-ups only) | 0–0.32 s |
| BM25 (Python, all chunks loaded per turn) | 0.47–0.52 s |
| Vector | 0.22–0.41 s |
| Rerank | 0.74–1.21 s |
| Answer | 1.16–2.11 s |
| **Total** | **3.5–5.5 s** |

### 1.4 Langfuse tracing overhead: +0.1–0.3 s

Traces are flushed to Langfuse's EU region at the end of every request,
because Lambda freezes between requests: 3.9–4.4 s per message.

### 1.5 Postgres connection reuse: −1 s per message

**Cause:** each request opened a new TLS connection to Neon.

| Measurement | New connection | Reused connection |
|---|---|---|
| One query from a laptop | 1,583–2,181 ms | 77–83 ms |
| After 2 min idle (ping, then reuse) | – | 154 ms |

**Fix:** one autocommit connection per Lambda container, pinged after 60 s idle,
reconnecting if Neon dropped it.

| Live | Before | After |
|---|---|---|
| Postgres retrieval (`/api/compare-backends`) | ~1,500 ms | **~310 ms** |
| Chat, content question | ~4.9 s | **~3.0–3.8 s** |
| Chat, library question | ~1.7 s | **~0.75 s** |

### 1.6 Router instead of a prompt catalog

At 103 papers the catalog of all papers in every answer prompt was ~6,000
tokens. The router sends library questions to SQL and removed the catalog
from content answers:

| Question | Before (model) | After (router → SQL) |
|---|---|---|
| "show me all 100 titles" | 10 of 103 listed, 11.9 s | **all 103**, 2.6 s (1.8 s later with connection reuse) |
| "how many papers?" | correct, ~3 s | 1.8 s |
| "papers by Kaiming He" | unreliable | 7 correct, 1.6 s → 0.75 s |

The router replaced the rewrite step, so a content message still makes one
extra Nova Lite call (~0.4–0.7 s), and the ~6,000 catalog tokens are gone from
every content answer.

### 1.7 Current breakdown (202 papers, warm)

| Stage | Time |
|---|---|
| Route (Nova Lite → JSON) | 0.43–0.71 s |
| BM25 over `rag_terms` | ~0.19 s (9–38 ms in the database; the rest is network) |
| Vector (Titan embedding + pgvector) | 0.25–0.35 s |
| Rerank (top 50 → 6) | ~1.0 s |
| Answer (Nova Lite) | 0.44–1.8 s |
| **Content question** | **~2.4–3.9 s** |
| Library question (route + SQL) | **~0.75 s** |

The first request after idle takes ~4–6 s while Neon's compute wakes up.

---

## 2. Keyword search

### 2.1 Python BM25 → Postgres full-text: 0.5 s → 0.15 s, but worse ranking

The chatbot computed BM25 in Python by loading every chunk from the database
on each turn: ~0.5 s at 260 chunks, and growing with the library. It was
replaced with Postgres full-text search (generated `tsvector` column + GIN
index, `websearch_to_tsquery`, `ts_rank_cd`): **~150–170 ms at 5,300 chunks**.

The eval later showed the cost: `ts_rank_cd` isn't BM25, and it ranked poorly
(section 3.2).

### 2.2 Real BM25 in SQL, first version: 8.5 s

Neon no longer allows the `pg_search` BM25 extension ("deprecated and no
longer allowed"), so BM25 was written in SQL: stem the query words, count
document frequency through the GIN index, and read term frequency from each
candidate chunk's `tsvector`.

- **Correct:** "YOLOv3-320 inference time" now finds the YOLOv3 paper (full-text
  search returned Orca and Llama 3).
- **Slow:** 1.2–2.6 s on test queries, **median 8.5 s** in the eval, because it
  unpacked the `tsvector` of every candidate chunk, thousands for common words.

### 2.3 `rag_terms` inverted index: 8.5 s → 147 ms

A precomputed table, one row per (word, chunk, count), filled by an
`AFTER INSERT` trigger from each chunk's `tsvector` and deleted by cascade.
At 5,300 chunks: **656,243 rows, 70 MB**, built in 13.6 s. BM25 became a join
on this table: 250–670 ms from a laptop, 136–160 ms in the database.

`EXPLAIN ANALYZE` showed the remaining problem: a **parallel sequential scan of
all 656k rows** (~110 ms of the ~147 ms), even though only the query's words
were needed.

### 2.4 Forcing index lookups: 147 ms → 9–38 ms

A `LATERAL` subquery per query word still got flattened into a full scan by the
planner. Adding `OFFSET 0` (an optimization fence) made it look up each word
through the primary-key index:

| Query | Before | After | Plan |
|---|---|---|---|
| Layer norm vs batch norm | 152 ms | **15.7 ms** | seq scan → index lookups |
| YOLOv3-320 inference time | 136 ms | **8.6 ms** | " |
| Image recognition with residual learning | 160 ms | **38.0 ms** | " |

Rankings were unchanged. **Overall: ~8.5 s → 9–38 ms in the database**
(~0.19 s from the Lambda, ~0.18 s median from a laptop at 103 papers,
~0.29 s at 202 papers).

---

## 3. Retrieval quality (40-question eval)

### 3.1 Rerank pool 20 → 50

In hybrid mode, fusion pushed the Orca definition (vector rank 11) to about
position 21, so the reranker (top 20) never saw it. Given 50 candidates, the
reranker ranked it first. Amazon Rerank bills per 100 documents, so 50
candidates cost the same as 20.

### 3.2 The first eval (103 papers)

| Setup | hit@1 | hit@5 | MRR@10 |
|---|---|---|---|
| Postgres full-text alone | 0.28–0.30 | 0.50–0.55 | 0.39 |
| Postgres vector alone | 0.55 | 0.80 | 0.65 |
| Postgres hybrid (full-text + vector) | 0.57 | 0.78 | 0.66 |
| **Postgres hybrid + rerank (chatbot then)** | **0.75** | **0.85** | **0.79** |
| Weaviate BM25 alone | 0.62 | 0.85 | 0.72 |
| Weaviate hybrid + rerank | 0.82 | 0.95 | 0.88 |

The findings: full-text ranking was the weak link, so fusing it with vector
search added noise (hybrid no better than vector alone). Weighting fusion 2:1
toward vector didn't help (0.78). Vector + rerank without keyword search did
slightly better (0.78 / 0.88 / 0.81).

### 3.3 Real BM25: Postgres matches Weaviate (103 papers)

| Setup | hit@1 | hit@5 | MRR@10 | median time (laptop) |
|---|---|---|---|---|
| Postgres BM25 alone | 0.68 | 0.85 | 0.75 | 184 ms |
| **Postgres BM25 + vector + rerank (chatbot now)** | **0.82** | **0.95** | **0.88** | 1,025 ms |
| Weaviate hybrid + rerank | 0.82 | 0.95 | 0.88 | 1,499 ms |

The chatbot's hit@1 went from 0.75 to 0.82 and hit@5 from 0.85 to 0.95, and
the dependency on the Weaviate sandbox went away.

### 3.4 The reranker's contribution

Reranking adds **+18 to +22 points of hit@1** on both engines, for ~1 s:
Postgres BM25 hybrid 0.60 → 0.82, Weaviate hybrid 0.60 → 0.82 (103 papers).

### 3.5 Scaling 103 → 202 papers

The same 40 questions (all from the first 100 papers), with twice as many
distractors (5,300 → 10,167 chunks):

| Setup | hit@1 | hit@5 | MRR@10 | median time (laptop) |
|---|---|---|---|---|
| Chatbot: BM25 + vector + rerank | 0.82 → 0.78 | 0.95 → 0.93 | 0.88 → 0.84 | 1,025 → 1,054 ms |
| Weaviate hybrid + rerank | 0.82 → 0.78 | 0.95 → 0.95 | 0.88 → 0.85 | 1,499 → 1,632 ms |
| BM25 alone | 0.68 → 0.65 | 0.85 → 0.85 | 0.75 → 0.73 | 184 → 294 ms |
| Vector alone | 0.55 → **0.47** | 0.80 → 0.78 | 0.65 → 0.58 | 186 → 363 ms |
| Full-text alone | 0.30 → 0.23 | 0.50 → 0.40 | 0.39 → 0.31 | 311 → 368 ms |

Reranked setups hold up (one question, within noise). Vector search suffers
most at the top as similar passages from new papers crowd in. BM25 slows as
common words match more chunks, but the ~1 s rerank still dominates.

---

## 4. Table-aware parsing (Docling)

### 4.1 Extractor comparison (Attention paper, 15 pages, 4 real tables)

| | PyMuPDF `find_tables` (lines) | PyMuPDF (text) | Docling |
|---|---|---|---|
| Real tables found | 2 of 4 | 0 usable | **4 of 4** |
| False positives | 4 (figures) | 15 (every page) | 0 |
| Captions | no | no | **yes** |
| Time | 4.9 s | 61 s | 22.9 s (OCR on) |

### 4.2 Conversion speed

With OCR off (the PDFs are born-digital): **2–13 s per paper** for the pilot;
34 minutes for 182 papers (the slowest took 135 s); T5 took 57 s.

### 4.3 Pilot, 20 papers

13 table questions, each asking for a single value from a table.

| Chatbot setup | Flat text | Docling |
|---|---|---|
| **Answer contains the right value** | 8/13 = 0.62 | **11/13 = 0.85** |
| Table hit@1 / hit@5 / MRR@10 | 0.54 / 0.85 / 0.65 | 0.85 / 0.92 / 0.86 |
| Other 40 questions | 0.78 / 0.93 / 0.84 | 0.80 / 0.93 / 0.85 |

With flat text the right page was found but the wrong number was read
(BERT-Large SWAG 86.3 instead of 86.6; FCN-16s pixel accuracy 78.6 instead of
85.2). The answer checker originally treated "{0.001, 0.003,…}" differently
from "{ 0.001, 0.003,…}"; after fixing it to ignore whitespace, the Docling
score became 11/13.

### 4.4 Full rollout, 202 papers

| Chatbot setup | Flat text | Docling v1 |
|---|---|---|
| Table answers correct | 0.62 | **0.85** |
| Table hit@1 / hit@5 / MRR@10 | 0.54 / 0.85 / 0.65 | 0.85 / 0.92 / 0.86 |
| Other 40: hit@1 / hit@5 / MRR@10 | 0.78 / 0.93 / 0.84 | 0.72 / 0.93 / 0.80 |

The drop in hit@1 on ordinary questions was partly a chunker flaw: figure
captions and footnotes were dropped from the text (q21's answer is a figure
caption; its rank went 1 → 4).

**Docling v2 (captions and footnotes kept; only page headers/footers dropped),
202 papers, 10,988 chunks:**

| Chatbot setup | Flat | Docling v1 | Docling v2 |
|---|---|---|---|
| Table answers correct | 0.62 | 0.85 | **0.85** |
| Table hit@1 / hit@5 / MRR@10 | 0.54 / 0.85 / 0.65 | 0.85 / 0.92 / 0.86 | **0.85 / 1.00 / 0.90** |
| Other 40: hit@1 / hit@5 / MRR@10 | 0.78 / 0.93 / 0.84 | 0.72 / 0.93 / 0.80 | **0.75 / 0.93 / 0.83** |

q21 is back at rank 1. Weaviate + rerank on the same chunks: tables
0.85 / 1.00 / 0.89, ordinary 0.75 / 0.93 / 0.83. BM25 alone improved to
0.68 / 0.91 / 0.76 over all 53 questions. The v2 re-conversion took about the
same time as v1 (~35 minutes); upload, re-embedding and Weaviate sync ~12 minutes.

### 4.5 Failure: an oversized table chunk

T5 failed to embed: `Too many input tokens. Max input tokens: 8192, request
input token count: 8257` for a ~14,000-character table row. The splitter now
cuts long rows (T5's longest chunk: 13,967 → 4,680 characters), and the
embedder embeds at most 10,000 characters of a chunk (`MAX_EMBED_CHARS`) while
storing the full text.

---

## 5. Ingestion and batch jobs

| Job | Time |
|---|---|
| Chunker, per paper | 0.3–0.35 s (+1.5 s cold start) |
| Embedder (OpenAI), 27 chunks | ~5 s |
| Embedder (Titan, 8 calls in parallel), per paper | 3.2–5.6 s |
| 100 papers through the pipeline | ~10–15 min (embedder capped at 2 concurrent) |
| arXiv paper via `/api/arxiv`, until searchable | ~8 s |
| `load_weaviate.py`: 5,300 chunks | 131.5 s |
| `load_weaviate.py`: 10,167 chunks | 39.8 s (updates); 293 s with pruning |
| `load_weaviate.py`: 10,230 chunks (after Docling) | 59.8 s; removed 10,167 stale objects |
| `rag_terms` backfill, 5,300 chunks | 13.6 s |
| Eval run (40–53 questions, 16 setups) | >10 min → ~5 min after per-question caching of shared retriever results |

Load failures and fixes: 29 of the first 100 papers had NUL characters (fixed
by stripping them); a transient Bedrock `ModelErrorException` (re-triggered);
the image-only 2203.00667 (no text); T5 (section 4.5).

---

## 6. Cost per message

| | Cost |
|---|---|
| Content message (Langfuse, follow-up) | **~$0.0012**: rerank $0.001, answer ~$0.0002, rewrite ~$0.00001, embedding ~$0.0000004 |
| Nova Lite prices | $0.06 / $0.24 per million input / output tokens |
| Amazon Rerank | $0.001 per search unit (≤100 documents) |
| Titan Embeddings v2 | $0.02 per million tokens (~$0.0002 per 15-page paper) |
| Lambda, SQS, CloudWatch | within the always-free tier at demo volume |
| Parameter Store | free (Secrets Manager's $0.40/month removed) |
| Removing the prompt catalog | ~6,000 fewer input tokens per content answer at 103 papers |

---

## 7. Storage (Neon)

| Point | Database size |
|---|---|
| 103 papers, 5,300 chunks, before `rag_terms` | ~100 MB |
| + `rag_terms` (656k rows, 70 MB) | 171 MB |
| 202 papers, 10,167 chunks | **319 MB** of the free plan's 0.5 GB |
| After Docling v1 (10,230 chunks) | `rag_terms` 1,246,705 rows |
| After Docling v2 (10,988 chunks, captions/footnotes kept) | |

The remaining ~100 downloaded papers would exceed the free plan.

---

## 8. Summary

| Metric | First version | Now |
|---|---|---|
| Content answer latency | 8.7 s | **2.4–3.9 s** |
| Library answer ("all titles") | 10 of 103 in 11.9 s | **all 103**; ~0.75 s for filtered lists |
| Keyword search | 0.5 s (Python, 260 chunks) | **9–38 ms** in the database at 10k chunks |
| Postgres connection | ~1–2 s per request | ~80 ms (reused) |
| Retrieval hit@5 (chatbot) | 0.85 (103 papers) | **0.95** (103) / 0.93 (202) |
| Retrieval hit@1 (chatbot) | 0.75 (103 papers) | **0.82** (103) / 0.78 (202) |
| Table answers correct | 0.62 | **0.85** |
| Cost per message | OpenAI pricing | ~$0.0012 |
