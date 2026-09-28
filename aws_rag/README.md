# aws version of RAG

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
| `query/requirements.txt` | `fastapi`, `mangum`, `psycopg[binary]`, `pgvector` |

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
curl -s ${URL}api/documents
curl -s -X POST ${URL}api/search -H 'Content-Type: application/json' -d '{
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
