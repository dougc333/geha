# aws version of RAG

![aws_rag architecture](docs/architecture.svg)

*Current architecture. Source: `docs/architecture.svg` (a PNG copy is in `docs/architecture.png`).*

**Retrieval quality and speed** (40-question eval over 103 papers, see
[Retrieval eval](#retrieval-eval); hit@k = the page holding the answer is in the
top k chunks, MRR@10 = mean of 1/rank of that page):

| Setup | hit@1 | hit@5 | MRR@10 | Retrieval time* |
|---|---|---|---|---|
| **Chatbot now: BM25 + vector → RRF → rerank** | **0.82** | **0.95** | **0.88** | ~1.0 s (rerank ~0.8 s) |
| Chatbot before: full-text + vector → RRF → rerank | 0.75 | 0.85 | 0.79 | ~1.2 s |
| Weaviate hybrid → rerank | 0.82 | 0.95 | 0.88 | ~1.5 s |
| BM25 alone (Postgres, `rag_terms`) | 0.68 | 0.85 | 0.75 | ~0.18 s |
| Vector alone (pgvector) | 0.55 | 0.80 | 0.65 | ~0.19 s |
| Full-text alone (Postgres `ts_rank_cd`) | 0.30 | 0.50 | 0.39 | ~0.31 s |

These are with 103 papers. With 202 papers (10,167 chunks) the chatbot scores
0.78 / 0.93 / 0.84 and Weaviate + rerank 0.78 / 0.95 / 0.85; see
[Scaling from 103 to 202 papers](#retrieval-eval).

\*Median per question, measured from a laptop to Neon/Weaviate/Bedrock
(includes network round trips). In the Lambda, a whole chat answer takes
~2.4–3.9 s: route ~0.4–0.7 s, BM25 ~0.2 s, vector ~0.25 s, rerank ~1 s,
answer ~0.45–1.8 s.

**Improvement from table-aware parsing (Docling)**, all 202 papers, chatbot setup
(BM25 + vector → RRF → rerank → Nova Lite):

| | Flat PDF text (before) | Table-aware, Docling (after) | Change |
|---|---|---|---|
| **Table questions: correct answer** (13) | 8/13 = 0.62 | **11/13 = 0.85** | **+23 points** |
| Table questions: hit@1 | 0.54 | **0.85** | +31 points |
| Table questions: hit@5 | 0.85 | **1.00** | +15 points |
| Table questions: MRR@10 | 0.65 | **0.90** | +25 points |
| Other questions (40): hit@1 / hit@5 / MRR@10 | 0.78 / 0.93 / 0.84 | 0.75 / 0.93 / 0.83 | unchanged within noise |

Flat extraction turns a results table into a run of numbers without rows or
columns, so the model found the right page but read the wrong value (BERT-Large
on SWAG: 86.3 instead of 86.6). Docling rebuilds each table as its own Markdown
chunk with its caption, so the value sits next to its row and column labels. A
first Docling version dropped figure captions and footnotes and cost ordinary
questions some rank-1 hits (hit@1 0.72); keeping them restored it to 0.75 (one
question from flat's 0.78). Details: [Tables: Docling pilot](#tables-docling-pilot).

A serverless RAG demo on AWS. When a PDF is uploaded to S3, it is split into
page-aware text chunks (one JSONL file per document), and those chunks are
embedded and loaded into Postgres/pgvector (Neon). A PDF dropped in S3 shows up
in the UI's document picker within seconds.

The query side, the UI plus the search API with BM25, vector, hybrid, the LLM
reranker and grounded answers, is a FastAPI app in a Lambda behind a public
Function URL.

This project started as a port of `../e2e_RAG/vercel_app`, and that Vercel
deployment has been retired. The code here is now the source of truth.

```
S3 raw bucket (*.pdf)
 │  s3:ObjectCreated
 ▼
SQS ChunkQueue ──(3 failures)──► SQS dead-letter queue
 │  batches of up to 5
 ▼
Lambda Chunker (Python 3.12 + PyMuPDF)
 │  text per page → 350-word chunks, 50-word overlap
 ▼
S3 chunks bucket: chunks/<sha256 of PDF>.jsonl
 │  s3:ObjectCreated (prefix chunks/, suffix .jsonl)
 ▼
SQS EmbedQueue ──(3 failures)──► SQS dead-letter queue
 │  one file at a time, at most 2 Lambdas at once
 ▼
Lambda Embedder (Amazon Titan Text Embeddings v2 on Bedrock, 1024-d, 8 calls in parallel)
 │  one transaction: upsert rag_documents, replace rag_chunks
 ▼
Postgres + pgvector on Neon (DATABASE_URL)
 ▲
 │  BM25 / vector / hybrid retrieval, rerank, answer
Lambda QueryApi (FastAPI via Mangum) ◄── Function URL ◄── browser
 │  GET /  serves the UI; /api/documents, /api/search
 ▼
Amazon Bedrock (Titan v2 query embedding, Amazon Rerank 1.0, Nova Lite answer)
```

Each JSONL line looks like:

```json
{"document_id": "<sha256>", "source": "s3://<bucket>/<key>", "chunk_index": 0, "page_number": 1, "content": "..."}
```

## Layout

| Path | Purpose |
|---|---|
| `template.yaml` | AWS SAM stack: both buckets, both queues + DLQs, queue policies, S3 notifications, both Lambdas |
| `chunker/handler.py` | Lambda handler (SQS → S3 PDF → JSONL) |
| `schema.sql` | `rag_documents` / `rag_chunks` tables and the HNSW vector index |
| `chunker/rag_core.py` | `chunk_text()` and retrieval helpers (same file as `query/rag_core.py`) |
| `chunker/requirements.txt` | Lambda dependencies (`pymupdf`; `boto3` is provided by the runtime) |
| `embedder/handler.py` | Lambda handler (SQS → S3 JSONL → Bedrock embeddings → Postgres) |
| `embedder/requirements.txt` | `psycopg[binary]`, `pgvector` (`boto3` comes with the runtime) |
| `query/lambda_function.py` | Lambda entry point: loads `DATABASE_URL` from Parameter Store, serves `index.html` at `/`, wraps the app with Mangum |
| `query/app.py` | FastAPI search API: `/api/documents`, `/api/search` (BM25, vector, hybrid, rerank, answer) |
| `query/rag_core.py` | BM25 and reciprocal-rank fusion |
| `query/index.html` | The retrieval lab UI (`/`) |
| `query/chat.py`, `query/chat.html` | Paper chatbot: `/api/chat`, `/api/arxiv`, and the `/chat` page |
| `query/requirements.txt` | `fastapi`, `mangum`, `psycopg[binary]`, `pgvector`, `langfuse` |

## Prerequisites

- **Amazon Bedrock access in the stack's region.** Amazon models (Nova, Titan)
  work out of the box, and every model in this stack is an Amazon model. (Third-
  party models such as Cohere are billed through AWS Marketplace and fail with
  `INVALID_PAYMENT_INSTRUMENT` unless the account has a payment method
  Marketplace accepts.) No model API keys are involved: the Lambdas
  authenticate to Bedrock with their IAM roles.

- An AWS account and credentials that can create S3, SQS, Lambda, IAM roles and
  CloudFormation stacks.
- AWS CLI v2: `aws sts get-caller-identity` should print your account.
- AWS SAM CLI: `brew install aws-sam-cli`.
- Docker (recommended): lets `sam build` install PyMuPDF's Linux wheel.

If your AWS profile uses `aws login` and SAM says it needs `botocore[crt]`,
export temporary credentials into the shell first:

```bash
eval "$(aws configure export-credentials --format env)"
```

## One-time setup: database and connection string

The pipeline uses a Postgres database with pgvector: a Neon database
(originally created through Vercel's Neon integration). Create the tables once;
this is safe to re-run:

```bash
psql "$DATABASE_URL" -f schema.sql
```

The Lambda has no VPC, so the database must accept connections from the
internet (Neon, Supabase and similar do, over TLS). Include `sslmode=require` in
the URL if your provider needs it.

Store the connection string as an SSM Parameter Store SecureString in the
stack's region. Standard parameters are free (Secrets Manager costs
$0.40/month). Parameter names can't start with `aws`. With `DATABASE_URL`
exported in your shell:

```bash
printf %s "$DATABASE_URL" | aws ssm put-parameter --region us-west-2 \
  --name /rag-demo/database-url --type SecureString --value file:///dev/stdin
```

To change it later, run the same command with `--overwrite`. Running Lambdas
pick up the new value on their next cold start. A different parameter name can
be passed with `sam deploy --parameter-overrides DatabaseUrlParameter=/...`.

## Deploy

```bash
cd /Users/dc/geha/aws_rag
sam build --use-container
sam deploy --guided
```

In the `--guided` prompts, pick a stack name (e.g. `pdf-chunker`) and a region,
answer **Y** to "Allow SAM CLI IAM role creation", and save the answers to
`samconfig.toml`. After that, redeploys are just `sam build --use-container && sam deploy`.

Always run `sam build` before `sam deploy`. Without it, SAM uploads the raw
`chunker/` folder with no PyMuPDF, and every invocation fails with
`Runtime.ImportModuleError: No module named 'pymupdf'`. Plain `sam build`
(without Docker) also works: it fetches PyMuPDF's manylinux wheel.

The bucket names come from the stack name and account ID, so they are:

- `<stack>-raw-<account-id>`: upload PDFs here
- `<stack>-chunks-<account-id>`: chunk files appear here

To print them and the queue URLs:

```bash
aws cloudformation describe-stacks --stack-name pdf-chunker \
  --query "Stacks[0].Outputs" --output table
```

## Run it

Set variables from the stack outputs:

```bash
STACK=pdf-chunker
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
RAW=$STACK-raw-$ACCOUNT
CHUNKS=$STACK-chunks-$ACCOUNT
```

Upload a PDF (any key ending in `.pdf` triggers the chunker):

```bash
aws s3 cp ../e2e_RAG/data/1706.03762v7.pdf s3://$RAW/papers/
```

Within a few seconds a chunk file appears:

```bash
aws s3 ls s3://$CHUNKS/chunks/
aws s3 cp s3://$CHUNKS/chunks/<sha256>.jsonl - | head -3
```

Follow the Lambda logs (each document logs `source -> output (N chunks)`):

```bash
sam logs --stack-name $STACK --name Chunker --tail
sam logs --stack-name $STACK --name Embedder --tail
```

A few seconds after the chunk file lands, the embedder logs
`-> rag_chunks (N chunks, document …)`. The document then appears in the
UI's document picker, titled with the PDF's file name, or you can check with:

```bash
psql "$DATABASE_URL" -c "SELECT d.title, count(c.id) FROM rag_documents d JOIN rag_chunks c ON c.document_id = d.id GROUP BY d.title"
```

### Access key

Every `/api/*` call except `/api/health` needs a shared access key in the
`X-API-Key` header; without it the API returns 401. The pages themselves (`/`,
`/chat`, `/backends`, `/docs`) load without it: on the first API call they ask
for the key once and remember it in the browser (localStorage). In Swagger
(`/docs`), click **Authorize** and paste the key. `chatbot/add_arxiv.py` reads it
from `CHATBOT_API_KEY` or SSM.

The key is an SSM SecureString, `/rag-demo/api-key`. Show it, or replace it:

```bash
aws ssm get-parameter --region us-west-2 --name /rag-demo/api-key --with-decryption --query Parameter.Value --output text
python3 -c "import secrets; print(secrets.token_urlsafe(24), end='')" | aws ssm put-parameter --region us-west-2 --name /rag-demo/api-key --type SecureString --value file:///dev/stdin --overwrite
```

A new key takes effect when Lambda containers restart (redeploy to force it).
If the parameter is configured but missing, the Lambda refuses to start rather
than serving without a key. It's one shared key, not per-user accounts: anyone
you give it to has full access, including adding papers.

### Query UI and API

Open the `QueryUrl` output in a browser:

```bash
aws cloudformation describe-stacks --stack-name $STACK \
  --query "Stacks[0].Outputs[?OutputKey=='QueryUrl'].OutputValue" --output text
```

Pick a document, a retrieval mode, and optionally the reranker and answer
generation. Selecting a document fills in a starter question for the three
demo papers; the question box is editable. The API can also be called
directly:

```bash
URL=$(aws cloudformation describe-stacks --stack-name $STACK \
  --query "Stacks[0].Outputs[?OutputKey=='QueryUrl'].OutputValue" --output text)
KEY=$(aws ssm get-parameter --region us-west-2 --name /rag-demo/api-key --with-decryption --query Parameter.Value --output text)
curl -s -H "X-API-Key: $KEY" ${URL}api/documents
curl -s -X POST ${URL}api/search -H "X-API-Key: $KEY" -H 'Content-Type: application/json' -d '{
  "document_id": "<id from /api/documents>", "query": "what is orca",
  "retrieval_mode": "hybrid", "use_reranker": true, "generate_answer": true, "top_k": 3}'
```

A hybrid + rerank + answer query takes about 3–3.5 s: roughly 0.3 s BM25,
0.3 s vector, 0.5 s rerank and 0.8–1.3 s generation. The first request after
idle adds a second or two of cold start.

The Function URL is public (`AuthType: NONE`), and
each search with rerank or answer generation costs Bedrock usage. Switch to
`AuthType: AWS_IAM` or put it behind CloudFront + WAF if it shouldn't be open.

### Paper chatbot

`/chat` on the same URL (the `ChatUrl` output) is a multi-turn chatbot over all
indexed papers, with cited answers and an "add an arXiv paper" box. It's served
by `query/chat.py` (`POST /api/chat`, `POST /api/arxiv`) and `query/chat.html`.
Papers added by arXiv ID land in `s3://<raw>/arxiv/`, with their title passed
through S3 metadata → chunker → embedder. See [`../chatbot`](../chatbot) for
the design, the `add_arxiv.py` command-line loader, cost and limits.

### Tracing with Langfuse

Every chat message and lab search is traced to [Langfuse](https://langfuse.com)
(Langfuse Cloud, EU region by default). A chat trace (`chat-turn`) contains
`rewrite` (follow-ups only), `retrieve` → `embed-query`, `rerank` and `answer`,
with the prompts, retrieved chunk IDs, rerank scores, token usage and timings.
Each chat page load is one Langfuse **session**, and 👍/👎 under an answer is
stored as a `user-feedback` score on its trace (`POST /api/feedback`).

Setup: create a Langfuse project, then store its keys in Parameter Store:

```bash
printf %s "$LANGFUSE_PUBLIC_KEY" | aws ssm put-parameter --region us-west-2 \
  --name /rag-demo/langfuse-public-key --type SecureString --value file:///dev/stdin
printf %s "$LANGFUSE_SECRET_KEY" | aws ssm put-parameter --region us-west-2 \
  --name /rag-demo/langfuse-secret-key --type SecureString --value file:///dev/stdin
```

For a US-region project deploy with
`--parameter-overrides LangfuseBaseUrl=https://us.cloud.langfuse.com`. Without
the parameters, tracing is disabled and everything else works. Traces are
flushed at the end of each request, because Lambda freezes between requests.

Costs: Langfuse has no Bedrock prices built in. The code reports embedding
and rerank costs itself (`EMBEDDING_PRICE_PER_TOKEN`, default $0.02/1M Titan
tokens; `RERANK_PRICE_PER_UNIT`, default $0.001 per search unit of up to 100
chunks). Nova Lite is priced by a model definition in the Langfuse project
(**Settings → Models**: `amazon.nova-lite-v1:0`, $0.06 input / $0.24 output
per 1M tokens), so add one there if you change `GenerationModel`. A follow-up
chat message comes to about $0.0012, mostly rerank. Prices apply to traces
received after they're set.

Traces contain questions, retrieved passages and answers. That's fine for
public arXiv papers; think twice before tracing sensitive documents.

### Paper metadata (arXiv)

`rag_documents` stores each paper's arXiv metadata: `arxiv_id`, `authors`,
`published`, `updated`, `abstract`, `primary_category`, `categories`,
`comment`, `journal_ref` and `doi` (see `schema.sql`). The metadata travels
with the PDF as a sidecar JSON next to it in S3 (`papers/2306.02707.pdf` +
`papers/2306.02707.json`). The chunker adds it to the first line of the chunk
file, and the embedder writes it to the row; a re-run without metadata keeps
what's stored. `POST /api/arxiv` writes the sidecar automatically (via
`query/arxiv_meta.py`). For papers indexed earlier, run once:

```bash
python scripts/backfill_arxiv_metadata.py --dry-run   # then without --dry-run
```

Questions about the library itself ("which papers do you have?", "who wrote
X?") are answered from these columns with SQL; see "Chat routing" below.
`GET /api/documents` takes the same filters: `author` (whole words, e.g.
`?author=Kaiming%20He`), `year_from`, `year_to`, `category` (arXiv code, e.g.
`cs.CV`) and `q` (words in the title or abstract, ranked by relevance).

### Chat routing

Every chat message first goes through a **router**. Questions about the
library are answered exactly from `rag_documents` with SQL; everything else
goes through RAG as before.

```
POST /api/chat → QueryApi Lambda (chat.py)
  _route(messages)        one Nova Lite call → {"route": "list" | "find" | "content",
                          filters (author, years, category, title, topic), search_query}
  ├─ list   → library.find_papers(filters)            "show all titles", "how many papers",
  │                                                    "papers by Kaiming He", "who wrote Adam?"
  ├─ find   → library.find_papers(topic=…) over        "which papers are about object detection?",
  │           title + abstract (Postgres full-text)    "anything on GANs?"
  └─ content → search → rerank → Nova Lite answer      "what is dropout?", "how was Orca evaluated?"
```

- **List and find answers are built by code, not written by the model.** They're
  complete (all 103 titles, not the ~10 a model will reproduce), carry no invented
  citations, and take about 1.5–2.5 s. The chat page renders them as a numbered
  list linking to arXiv.
- **The router replaces the old rewrite step:** its `search_query` is the
  standalone version of a follow-up, so a content turn still makes one extra
  model call. The router also runs on the first turn, adding ~0.4 s there.
- **The paper catalog is no longer in the answer prompt,** saving ~6,000 input
  tokens on every content question at 100 papers.
- **Topic search** matches the router's `topic` against titles and arXiv
  abstracts. The router adds synonyms ("GAN or generative adversarial"); all
  words are required first, then any word if nothing matches.
- **If the router's JSON can't be parsed,** the message falls back to `content`,
  so the worst case is today's RAG behaviour. Each decision is recorded on the
  Langfuse trace (`route` generation, `route` metadata on `chat-turn`).
- **Mixed questions** ("summarise the papers by Kaiming He") go to `content`;
  answering them needs a list-then-retrieve step that isn't built.

**What implements the router:** a function (`_route`, plus `_answer_library`
and `library.py`) inside the existing QueryApi Lambda, not a separate Lambda.
It needs the same database connection, Bedrock client and request context, and
a Lambda-to-Lambda hop would add network latency and a possible second cold
start to a ~0.4 s decision. It would be worth splitting out if routes needed
different compute or scaling (Step Functions or separate Lambdas), were owned
by different teams (separate services behind API Gateway paths), or if a model
should orchestrate multi-step tool use (Amazon Bedrock Agents with SQL and
search as tools: more capable for mixed questions, but slower, costlier and
less predictable).

### Weaviate comparison

The same chunks and Titan vectors are mirrored into a Weaviate collection
(`Chunk`) so the two search engines can be compared on identical data:

- **Postgres:** BM25 in SQL over `rag_terms` + pgvector (HNSW) → our RRF
  (full-text `ts_rank_cd` before 2026-09-29).
- **Weaviate:** one `hybrid` query (native BM25 + vector, fused in the engine),
  with `alpha` (0 = keyword, 1 = vector) and `relative_score` or `ranked` fusion.

`/backends` shows both top-k lists side by side (`POST /api/compare-backends`),
and the chat page has a search-engine selector (`backend` on `/api/chat`).

Setup: create a Weaviate Cloud cluster, store its URL and key in SSM
(`/rag-demo/weaviate-url`, `/rag-demo/weaviate-api-key`), then copy the chunks
(no re-embedding; object IDs come from `rag_chunks.id`, so re-runs update):

```bash
python scripts/load_weaviate.py            # --recreate to rebuild the collection
```

Weaviate Cloud sandboxes only allow the HFresh vector index, not HNSW, so the
approximate-nearest-neighbour algorithms differ between the two engines. New
papers are not copied automatically; re-run the script after loading more.

### Performance

**Postgres connection reuse.** The query Lambda reuses one Postgres connection
between requests (`database()` in `query/app.py`) instead of opening a new TLS
connection to Neon for each one. It cuts ~1 s from every chat message (content
questions ~5 s → ~4 s) and makes the Postgres-vs-Weaviate timing comparison
fair. After 60 s idle it pings the connection first, and it reconnects if Neon
has dropped it.

**Where the time goes now.** The Postgres-vs-Weaviate comparison is fair:
about 310 ms vs 160 ms, and the gap that remains is real query time. The first
request after idle is still slow (~6 s) while Neon wakes up and the connection
opens. In a content answer, most of the time goes to rerank (~1 s) and writing
the answer (~1–1.8 s), not retrieval.

| Step (warm) | Time |
|---|---|
| Route (Nova Lite) | ~0.5 s |
| BM25 + vector search (Postgres) | ~0.45 s (BM25 ~0.2 s, vector ~0.25 s) |
| Rerank (Amazon Rerank) | ~1 s |
| Answer (Nova Lite) | ~1–1.8 s |
| **Content question, total** | **~3–3.8 s** |
| Library question (route + SQL), total | ~0.75 s |

### Retrieval eval

`evals/` measures how often retrieval finds the page that answers a question.

- `evals/generate_questions.py` builds `evals/questions.jsonl`: 40 questions
  (20 about specific facts, 20 paraphrasing a concept), each from a different
  paper, written by Nova Lite from one chunk and kept only if its evidence quote
  appears verbatim on that page. It skips reference lists, questions about
  citations, and questions that don't name their subject; `--replace q03,q17`
  regenerates individual questions.
- `evals/run_eval.py` runs every question through each setup using the deployed
  query code (`chat.keyword_search`, `chat.vector_search`, `app._rerank`,
  `weaviate_store.hybrid`), and writes `evals/results.md` and `evals/results.json`
  (every ranking). About $0.08 per run, mostly reranking.

Results on 2026-09-29 (page hit@5 = the answer's page is in the top 5 chunks):

| Setup | hit@1 | hit@5 | MRR@10 | fact hit@5 | paraphrase hit@5 | median time* |
|---|---|---|---|---|---|---|
| Postgres full-text (`ts_rank_cd`) | 0.30 | 0.50 | 0.39 | 0.65 | 0.35 | 311 ms |
| Postgres BM25 (`rag_terms`) | 0.68 | 0.85 | 0.75 | 0.95 | 0.75 | 184 ms |
| Postgres vector | 0.55 | 0.80 | 0.65 | 0.85 | 0.75 | 186 ms |
| Postgres hybrid (full-text + vector, RRF) | 0.57 | 0.78 | 0.66 | 0.80 | 0.75 | – |
| Postgres hybrid, RRF weighted 2:1 to vector | 0.57 | 0.78 | 0.67 | 0.80 | 0.75 | – |
| Postgres hybrid (BM25 + vector, RRF) | 0.60 | 0.85 | 0.70 | 0.90 | 0.80 | – |
| Postgres full-text hybrid + rerank (chatbot until 2026-09-29) | 0.75 | 0.85 | 0.79 | 0.85 | 0.85 | 1,235 ms |
| Postgres vector + rerank | 0.78 | 0.88 | 0.81 | 0.85 | 0.90 | 1,622 ms |
| **Postgres BM25 hybrid + rerank (chatbot now)** | **0.82** | **0.95** | **0.88** | 0.95 | 0.95 | 1,025 ms |
| Weaviate BM25 (alpha 0) | 0.62 | 0.85 | 0.72 | 0.95 | 0.75 | 168 ms |
| Weaviate hybrid (alpha 0.5) | 0.60 | 0.90 | 0.71 | 0.95 | 0.85 | 98 ms |
| Weaviate vector (alpha 1) | 0.55 | 0.80 | 0.65 | 0.85 | 0.75 | 95 ms |
| **Weaviate hybrid + rerank** | **0.82** | **0.95** | **0.88** | 0.95 | 0.95 | 1,499 ms |

\*Median per question from a laptop (network included). "–": the setup reuses
retriever results already timed in another row; the query itself is RRF only.
Rerank setups include the ~0.8–1 s Amazon Rerank call.

These are the 103-paper results (`evals/results_103_papers.md`).

**Scaling from 103 to 202 papers** (10,167 chunks; the same 40 questions, all
from the first 100 papers, so the new papers act as distractors):

| Setup | hit@1 (103 → 202) | hit@5 | MRR@10 | median time* |
|---|---|---|---|---|
| **Chatbot: BM25 + vector + rerank** | 0.82 → 0.78 | 0.95 → 0.93 | 0.88 → 0.84 | 1,025 → 1,054 ms |
| Weaviate hybrid + rerank | 0.82 → 0.78 | 0.95 → 0.95 | 0.88 → 0.85 | 1,499 → 1,632 ms |
| Full-text + vector + rerank (old chatbot) | 0.75 → 0.70 | 0.85 → 0.85 | 0.79 → 0.76 | 1,235 → 1,206 ms |
| BM25 alone | 0.68 → 0.65 | 0.85 → 0.85 | 0.75 → 0.73 | 184 → 294 ms |
| Vector alone | 0.55 → 0.47 | 0.80 → 0.78 | 0.65 → 0.58 | 186 → 363 ms |
| Full-text alone | 0.30 → 0.23 | 0.50 → 0.40 | 0.39 → 0.31 | 311 → 368 ms |

- **Reranked setups barely move:** the chatbot drops one question at hit@5, within
  noise. The reranker still finds the right page among twice as many near-misses.
- **Vector search loses most at the top** (hit@1 −3 questions): similar passages
  from the new papers crowd out the right one; BM25 and reranking compensate.
- **BM25 slows as common words match more chunks** (184 → 294 ms from a laptop),
  but the ~1 s rerank still dominates. Laptop timings vary with the network.
- Full 202-paper results: `evals/results.md`.

What it shows (103 papers):

- **Postgres full-text ranking was the weak link, not Postgres.** `ts_rank_cd`
  finds the page for 50% of questions; real BM25 over the same words finds 85%,
  the same as Weaviate's BM25. With BM25 + vector + rerank, Postgres **matches
  Weaviate + rerank exactly** (0.82 / 0.95 / 0.88), so the chatbot now uses it
  (`KEYWORD_SEARCH=bm25`, the default; `fts` switches back).
- **How BM25 runs in Postgres:** Neon no longer allows the `pg_search`
  extension, so `rag_terms` holds one row per (word, chunk, count), filled by a
  trigger from each chunk's `tsvector` (656k rows, 70 MB for 5,300 chunks).
  `chat.bm25_search` looks up only the query's words through the index and
  scores them with Okapi BM25 (k1 1.2, b 0.75): 9–38 ms in the database. The
  first version, which unpacked every candidate chunk's `tsvector`, took ~8.5 s.
- **Weighting fusion toward vector doesn't help** (0.78); dropping keyword search
  and reranking vector results alone does a little better than the old setup (0.88).
- **Vector search is identical in both engines** (0.80) because the vectors are the same.
- **The reranker is worth its ~1 s:** +18 to +22 points of hit@1.
- **Caveats:** 40 questions, so one question is 2.5 points and differences under
  ~5 points are noise. Generated questions tend to reuse the page's wording,
  which favours keyword search. Timings in `results.md` are from a laptop, not
  the Lambda; a retriever shared by several setups is timed once (0 ms rows).

### Tables: Docling pilot

The chunker flattens each page's text, so a results table becomes a run of
numbers without rows or columns. `local_ingest/docling_chunks.py` (run on a laptop
with Docling from `/Users/dc/geha/.venv`, OCR off for born-digital PDFs) instead
writes text chunks plus **one chunk per table**: "Table N: caption" and the table
as compact Markdown, split by rows with the header repeated if it's over ~4,000
characters. It produces the same chunk-file format with the same `document_id`
(the PDF's SHA-256), so uploading to `s3://<chunks bucket>/chunks/` replaces a
paper's flat chunks through the normal embedder. It takes 2–13 s per paper.

Pilot: 20 of the most-cited papers (≤ 30 pages; 136 tables). 13 table questions
(`type: "table"` in `evals/questions.jsonl`, from `evals/generate_table_questions.py`)
each ask for one value in a table. `evals/answer_check.py` asks the chatbot's
full content path and checks the answer contains the gold value.

| Chatbot setup (BM25 + vector + rerank) | Flat chunks | Docling chunks |
|---|---|---|
| Table questions: **answer accuracy** | 8/13 = 0.62 | **11/13 = 0.85** |
| Table questions: hit@1 / hit@5 / MRR@10 | 0.54 / 0.85 / 0.65 | **0.85 / 0.92 / 0.86** |
| Other 40 questions: hit@1 / hit@5 / MRR@10 | 0.78 / 0.93 / 0.84 | 0.80 / 0.93 / 0.85 |

With flat chunks the right page was usually retrieved, but the model read the
wrong number off it (BERT-Large SWAG 86.3 instead of 86.6; FCN-16s pixel
accuracy 78.6 instead of 85.2). Docling fixed those. The two remaining misses
pick the wrong row or column of a wide table. Docling occasionally mistakes an
author block for a table; those questions were dropped.

**Full rollout (all 202 papers, 2026-09-29):** 1,600+ tables as their own chunks,
10,230 chunks in total, ~34 minutes of Docling on a laptop.

| Chatbot setup (BM25 + vector + rerank) | Flat (202 papers) | Docling (202 papers) |
|---|---|---|
| Table questions (13): **answer accuracy** | 8/13 = 0.62 | **11/13 = 0.85** |
| Table questions: hit@1 / hit@5 / MRR@10 | 0.54 / 0.85 / 0.65 | **0.85 / 0.92 / 0.86** |
| Other 40 questions: hit@1 / hit@5 / MRR@10 | 0.78 / 0.93 / 0.84 | 0.72 / 0.93 / 0.80 |

**Docling v2 (captions and footnotes kept):** tables 0.85 / **1.00** / 0.90
(hit@1 / hit@5 / MRR@10), answers 11/13; ordinary questions 0.75 / 0.93 / 0.83;
10,988 chunks. The v1 numbers above were before this fix. With v1, tables
improved a lot and hit@5 on ordinary questions held, but three ordinary
questions dropped from rank 1. One (q21, answer in "Figure 7: …") is a
chunker flaw: `docling_chunks.py` drops captions and footnotes from the text, so
**figure captions are not indexed**. The fix is to keep them and drop only page
headers/footers; it needs a re-run. Weaviate with Docling chunks: tables
0.77 / 0.92 / 0.82, other questions 0.72 / 0.90 / 0.80. Full results:
`evals/results.md` (53 questions) vs `evals/results_202_flat.md`.

Oversized chunks: one T5 table row was ~14,000 characters (8,257 tokens), over
Titan's 8,192-token limit, so that paper failed to embed. The splitter now cuts
long rows, and the embedder embeds at most the first 10,000 characters of a
chunk (`MAX_EMBED_CHARS`; the full text is stored and searched by BM25).

Notes: papers converted this way have `source = docling:<file>` in
`rag_documents`. Re-uploading such a PDF to the raw bucket would re-chunk it flat
and overwrite the Docling version. Weaviate needs `scripts/load_weaviate.py` after
re-chunking. Results: `evals/results_tables_{flat,docling}.md`,
`evals/answers_tables_{flat,docling}.json`, `evals/results_docling_pilot.md`.

### Figures: descriptions with Nova Lite

Text search can't see what's inside a figure: the values on a chart, the blocks
in an architecture diagram, the example input in an illustration. Two steps add
a **figure chunk** for each figure:

1. `local_ingest/docling_chunks.py --figures` also saves each figure (Docling
   "picture" or "chart", at 2x scale; every captioned figure, and uncaptioned
   images of at least 150 x 150 px of area, so logos and icons are skipped) as a PNG in
   `local_ingest/out/figures/<document_id>/`, with its page and caption in
   `figures.json`.
2. `local_ingest/describe_figures.py` sends each image, with the paper title and
   caption, to **Nova Lite** and appends one chunk per figure to the paper's JSONL:

   ```
   Figure (page 6) from "You Only Look Once: …": Figure 4: Error Analysis: …
   Text in figure: Fast R-CNN | YOLO | Background: 13.6% | … | Loc: 19.0% | Correct: 65.5%
   Description: two pie charts comparing …
   ```

   The prompt asks for every word and number in the figure verbatim first, then a
   short description, using only what is visible. Descriptions are cached in
   `figures.json`, so re-runs are free (`--redo` to describe again). With
   `--upload` it puts the PNGs at `s3://<chunks bucket>/figures/<document_id>/`
   (not a trigger path) and then the JSONL, which the embedder indexes as usual.

```bash
/Users/dc/geha/.venv/bin/python local_ingest/docling_chunks.py <pdf folder> --figures
uv run --with boto3 --with 'botocore[crt]' python local_ingest/describe_figures.py --upload
```

Figure chunks store their PNG's S3 key in `rag_chunks.image`. `/api/chat` looks
it up for the chosen sources and returns a presigned `image_url` (1 hour); the
chat page shows those figures as thumbnails under the answer.

**Pilot, 20 papers (133 figures), $0.0175 of Nova Lite.** Nine questions
(`type: "figure"`, f01–f09) whose answer appears only in a figure, not in the
page text (checked with grep): chart values, diagram labels, an example input.

| Chatbot setup (BM25 + vector + rerank) | Before | With figure chunks |
|---|---|---|
| Figure questions: **answer accuracy** | 0/9 | **7/9** |
| Figure questions: hit@1 / hit@5 / MRR@10 | 0.78 / 1.00 / 0.87 | **1.00 / 1.00 / 1.00** |
| Other 53 questions: hit@1 / hit@5 / MRR@10 | 0.77 / 0.94 / 0.85 | 0.75 / 0.94 / 0.84 |

What Nova Lite gets right and wrong:

- Charts with printed numbers are transcribed exactly (every value in YOLO's
  error-analysis pies).
- A first prompt ("describe the figure") only summarized diagrams, often from the
  caption; asking for "Text in figure: …" first got "PixelNorm" (StyleGAN) and the
  BERT example tokens. The Transformer diagram still comes back as a summary
  (f07 misses "Outputs (shifted right)"); Nova Pro transcribes it.
- Plots without printed values are weaker: Faster R-CNN's recall curves (f08)
  lost "which curve is highest" with the new prompt, and in GCN's timing chart
  both Nova Lite and Nova Pro say the *CPU* ran out of memory; it was the GPU.
- Docling occasionally renders a vector drawing badly (ViT Figure 1 is a jumble
  of boxes); the description then just restates the caption.

The other 53 questions are unchanged apart from one question moving from rank 1
to rank 2. Results: `evals/results_figures.md`, `evals/results_with_figures.md`,
`evals/answers_figures_{before,after}.json`.

**Full rollout (all 203 papers, 2026-09-29): 1,886 figures, $0.24 of Nova Lite**
(2.28 M input / 0.44 M output tokens), ~70 minutes of Docling on a laptop.
Neon now holds 12,916 chunks; Weaviate was re-synced.

| Chatbot setup (BM25 + vector + rerank), 203 papers | hit@1 | hit@5 | MRR@10 | Answers |
|---|---|---|---|---|
| Figure questions (9) | 1.00 | 1.00 | 1.00 | **7/9** |
| Table questions (13) | | 1.00 | | 11/13 |
| All 62 questions | 0.77 | 0.95 | 0.85 | |
| Weaviate hybrid + rerank, all 62 | 0.76 | 0.95 | 0.84 | |

Adding 1,886 figure chunks didn't hurt the other questions (0.77 / 0.94 / 0.85
on the 53 before). f05 passes as "Pixel normalization" (the checker ignores
spaces), close to but not the diagram's exact label. Full results:
`evals/results_figures_all.md`, `evals/answers_figures_all.json`.

The rollout exposed an embedder weakness: Titan sometimes returns
`ModelErrorException` ("try your request again") for a request that succeeds on
retry. botocore doesn't retry it, so one failed call failed the whole paper;
Llama 3 (274 chunks) failed on every redelivery. The embedder now retries each
chunk up to 3 times with backoff.

**Filter fix (same day): 2,112 figures in 198 papers.** The first rollout skipped
any image whose *shorter* side was under 150 px, which also dropped wide
figures: 16 of 149 in the pilot papers (e.g. YOLO Figure 1, ResNet Figure 2,
DenseNet Figure 2) and all three in the Atari paper. Captioned figures are now
always kept. Re-running all 203 papers added 226 figures for $0.026 (existing
descriptions are reused, matched by page, caption and size, because file names
are renumbered). The 5 papers without figures (scikit-learn, VGG, RoBERTa,
Distillation, the deep-learning survey) have none. Retrieval is unchanged
(all 62: 0.77 / 0.95 / 0.85); figure answers 6/9 (f06 flipped: see below),
tables 11/13. Results: `evals/results_figures_v2.md`, `evals/answers_figures_v2.json`.

Known issue: 73 descriptions (3.5%) are degenerate. Nova Lite transcribed the
labels, then repeated empty " | " separators until the token limit and never
wrote the description. XGBoost's AUC plot (f06) is one, so the model guesses
which curve is lowest, and its answer changes between runs. They can be
re-described with `describe_figures.py --redo --files …`, e.g. with Nova Pro.

### Existing PDFs (backfill)

S3 only sends events for new objects. To chunk PDFs that were already in the
bucket, copy them onto themselves, which fires `ObjectCreated:Copy`:

```bash
aws s3 cp s3://$RAW/ s3://$RAW/ --recursive --exclude "*" --include "*.pdf" \
  --metadata-directive REPLACE
```

Re-processing is safe: the output key is the PDF's SHA-256, so the same file
always overwrites the same chunk file, and the embedder replaces that
document's rows instead of adding duplicates.

To re-embed without re-chunking (e.g. after changing the embedding model), do the same
for the chunk files:

```bash
aws s3 cp s3://$CHUNKS/chunks/ s3://$CHUNKS/chunks/ --recursive \
  --metadata-directive REPLACE
```

## Backup and restore

**Neon is the only store that matters.** Weaviate is rebuilt from it by
`scripts/load_weaviate.py` (~2.5 minutes, stored vectors, no re-embedding), so it
needs no backup.

**Back up** (≈ 1.5 minutes; 80 MB compressed on 2026-09-29, 203 papers, 12,916 chunks):

```bash
brew install libpq@18        # pg_dump must match Neon's Postgres 18
scripts/backup_db.sh         # → s3://<chunks bucket>/backups/rag_neon_<UTC time>.dump
```

The script reads the connection string from `/rag-demo/database-url`, writes a
`pg_dump --format=custom` file, checks it with `pg_restore --list`, uploads it,
and deletes the local copy (`--keep-local` keeps it in `backups/`, which git
ignores). `backups/` in the chunks bucket doesn't trigger the embedder.

**Restore** into an empty database (a new Neon project or branch, or a local
Postgres 18 with pgvector):

```bash
aws s3 cp s3://<chunks bucket>/backups/<file>.dump .
export TARGET_URL='postgresql://…'          # the new database
psql "$TARGET_URL" -c 'CREATE EXTENSION IF NOT EXISTS vector; CREATE SCHEMA IF NOT EXISTS teaching'
pg_restore --no-owner --no-privileges -n public -n teaching \
  --dbname="$TARGET_URL" <file>.dump
```

Then point `/rag-demo/database-url` at the new database and redeploy (or wait
for the Lambdas to reconnect). `-n public -n teaching` skips `neon_auth` (and, with `-n`, pg_restore doesn't create
the `teaching` schema, hence the `CREATE SCHEMA`), a
Neon-managed schema that the new project creates itself. Tables load before
triggers and indexes are created, so the BM25 trigger doesn't duplicate
`rag_terms`; the HNSW vector index is rebuilt during restore (a few minutes).

**Without a dump:** the chunk files and figure PNGs are still in the chunks
bucket. Re-uploading `chunks/*.jsonl` refills a fresh database through the
embedder (Titan re-embedding only, no Docling or Nova).

## Tests

`tests/` has fast unit tests (35, well under a second) that need no AWS,
database or network: `tests/support.py` sets fake credentials and settings and
the tests stub Bedrock, S3 and Postgres. They cover chunking and table splitting,
RRF/BM25, the eval's answer matching, the embedder (Titan retry, NUL stripping,
figure `image`), `describe_figures.py` (caching, `--redo`, upload order), and the
query API (access key, `no-cache` pages, `/api/chat` route, router fallback,
presigned figure URLs). CI runs them in the `aws-rag` job.

```bash
uv run --no-project --python 3.12 --with-requirements query/requirements.txt \
  --with boto3 --with httpx python -m unittest discover -s tests
```

Retrieval and answer quality need the live stack: see `evals/`.

## Failures

A message that fails 3 times moves to its dead-letter queue. For the chunker,
the usual cause is a scanned PDF with no text layer (`no extractable text`).
For the embedder, it is a missing or wrong `DATABASE_URL` parameter, a database that refuses the
connection, or missing tables. Check the `EmbedDeadLetterQueueUrl` output the
same way as below.

```bash
DLQ=$(aws cloudformation describe-stacks --stack-name $STACK \
  --query "Stacks[0].Outputs[?OutputKey=='DeadLetterQueueUrl'].OutputValue" --output text)
aws sqs get-queue-attributes --queue-url $DLQ --attribute-names ApproximateNumberOfMessages
aws sqs receive-message --queue-url $DLQ --max-number-of-messages 10
```

Once the cause is fixed, move the messages back to the main queue from the
SQS console (**Start DLQ redrive**) or with `aws sqs start-message-move-task`.

## Configuration

Set these Lambda environment variables in `template.yaml`:

| Variable | Default | Meaning |
|---|---|---|
| `OUT_BUCKET` | chunks bucket | Where JSONL is written |
| `OUT_PREFIX` | `chunks/` | Key prefix for output |
| `CHUNK_WORDS` | `350` | Words per chunk |
| `CHUNK_OVERLAP` | `50` | Words shared between consecutive chunks |

Embedder variables:

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL_PARAMETER` | `/rag-demo/database-url` | SSM SecureString with the connection string |
| `EMBEDDING_MODEL` | `amazon.titan-embed-text-v2:0` | Must match `QueryApi`'s model |
| `EMBEDDING_DIMENSIONS` | `1024` | Must match `vector(1024)` in `schema.sql` |
| `EMBED_CONCURRENCY` | `8` | Parallel Titan calls (Titan embeds one text per call) |
| `EMBED_BATCH_SIZE` | `100` | Chunks per embeddings request |

QueryApi variables: `DATABASE_URL_PARAMETER`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`,
`RERANK_MODEL`, `GENERATION_MODEL` and `RERANK_CANDIDATES` (default 50: the
whole fused hybrid pool is reranked, since fusion can push a strong vector hit
past position 20, and Bedrock bills reranking per 100 documents).

The models are stack parameters, so both Lambdas always share the embedding
model. Change them at deploy time, e.g.:

```bash
sam deploy --parameter-overrides GenerationModel=us.amazon.nova-2-lite-v1:0
```

| Parameter | Default | Notes |
|---|---|---|
| `EmbeddingModel` | `amazon.titan-embed-text-v2:0` | Changing it means re-embedding every document (see backfill) |
| `EmbeddingDimensions` | `1024` | 256, 512 or 1024; changing it also needs a `schema.sql` change and a re-embed |
| `RerankModel` | `amazon.rerank-v1:0` | `cohere.rerank-v3-5:0` needs AWS Marketplace billing |
| `GenerationModel` | `amazon.nova-lite-v1:0` | Any Bedrock Converse model: `us.amazon.nova-2-lite-v1:0`, `openai.gpt-oss-120b-1:0`, `us.meta.llama3-3-70b-instruct-v1:0`, … |

`ScalingConfig.MaximumConcurrency` caps how many Lambdas run at once: 10 for
the chunker, 2 for the embedder so it doesn't exhaust database connections or
hit Bedrock quotas.

## Limits

- **Scanned or image-only PDFs** produce no text. Route them to Amazon Textract
  (`StartDocumentTextDetection`) instead.
- **Lambda runs at most 15 minutes.** Very large PDFs need Step Functions
  (split by page range) or an ECS Fargate task.
- **PyMuPDF is AGPL-licensed.** Check that this fits before using it in a
  commercial service.

## Tear down

Empty the buckets first; CloudFormation can't delete non-empty buckets.

```bash
aws s3 rm s3://$RAW --recursive
aws s3 rm s3://$CHUNKS --recursive
sam delete --stack-name $STACK
aws ssm delete-parameter --name /rag-demo/database-url --region us-west-2
```

`sam delete` leaves the rows in Postgres. Remove them with
`DELETE FROM rag_documents WHERE source LIKE 's3://%'`; chunks cascade.
