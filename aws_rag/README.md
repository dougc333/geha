# aws version of RAG

Serverless PDF ingestion on AWS for the RAG demo in `../e2e_RAG/vercel_app`.
When a PDF is uploaded to S3, it is split into page-aware text chunks (one JSONL
file per document), and those chunks are then embedded and loaded into the same
Postgres/pgvector database the Vercel app searches. The chunking logic
(`rag_core.chunk_text`) and the table layout match `vercel_app/scripts/ingest.py`,
so a PDF dropped in S3 shows up in the Vercel app's document picker.

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
Lambda Embedder (OpenAI text-embedding-3-small, batches of 100)
 │  one transaction: upsert rag_documents, replace rag_chunks
 ▼
Postgres + pgvector (DATABASE_URL, the one the Vercel app uses)
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
| `chunker/rag_core.py` | `chunk_text()` and retrieval helpers, copied from `vercel_app` |
| `chunker/requirements.txt` | Lambda dependencies (`pymupdf`; `boto3` is provided by the runtime) |
| `embedder/handler.py` | Lambda handler (SQS → S3 JSONL → OpenAI embeddings → Postgres) |
| `embedder/requirements.txt` | `openai`, `psycopg[binary]`, `pgvector` |

## Prerequisites

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

## One-time setup: database and secret

The embedder writes to an existing Postgres database with the pgvector tables
from the Vercel app. If that database is new, create the tables first:

```bash
psql "$DATABASE_URL" -f ../e2e_RAG/vercel_app/schema.sql
```

The Lambda has no VPC, so the database must accept connections from the
internet (Neon, Supabase and similar do, over TLS). Include `sslmode=require` in
the URL if your provider needs it.

Store the connection string and OpenAI key in Secrets Manager, in the same
region as the stack. With `DATABASE_URL` and `OPENAI_API_KEY` exported in your
shell, this builds the JSON without echoing the values:

```bash
aws secretsmanager create-secret --region us-west-2 --name aws-rag/embedder \
  --secret-string "$(python3 -c 'import json,os; print(json.dumps({k: os.environ[k] for k in ("DATABASE_URL","OPENAI_API_KEY")}))')"
```

To rotate either value later, run the same command with `put-secret-value
--secret-id aws-rag/embedder` in place of `create-secret --name aws-rag/embedder`.
Running Lambdas pick up the new value on their next cold start. A different
secret name can be passed with `sam deploy --parameter-overrides SecretName=...`.

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
Vercel app's picker, titled with the PDF's file name, or you can check with:

```bash
psql "$DATABASE_URL" -c "SELECT d.title, count(c.id) FROM rag_documents d JOIN rag_chunks c ON c.document_id = d.id GROUP BY d.title"
```

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

To re-embed without re-chunking (e.g. after fixing the secret), do the same
for the chunk files:

```bash
aws s3 cp s3://$CHUNKS/chunks/ s3://$CHUNKS/chunks/ --recursive \
  --metadata-directive REPLACE
```

## Failures

A message that fails 3 times moves to its dead-letter queue. For the chunker,
the usual cause is a scanned PDF with no text layer (`no extractable text`).
For the embedder, it is a missing or wrong secret, a database that refuses the
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
| `SECRET_ID` | `aws-rag/embedder` | Secret with `DATABASE_URL` and `OPENAI_API_KEY` |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Must match the Vercel app's query model and `vector(1536)` |
| `EMBED_BATCH_SIZE` | `100` | Chunks per embeddings request |

`ScalingConfig.MaximumConcurrency` caps how many Lambdas run at once: 10 for
the chunker, 2 for the embedder so it doesn't exhaust database connections or
hit OpenAI rate limits.

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
aws secretsmanager delete-secret --secret-id aws-rag/embedder --region us-west-2
```

`sam delete` leaves the rows in Postgres. Remove them with
`DELETE FROM rag_documents WHERE source LIKE 's3://%'`; chunks cascade.
