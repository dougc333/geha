# GEHA Validated Document RAG

Production-style AWS retrieval for GEHA coverage policies, medical plan
documents, and dental documents. This project intentionally contains no arXiv
loader, research-paper schema, paper corpus, or unvalidated PDF fallback.

## Trust boundary

Only text that passes page-level visual comparison is eligible for indexing.
The original PDF is immutable and remains the citation artifact. Every
validated sidecar records the PDF SHA-256, ordered page text, per-page content
hashes, extraction method, correction history, and MCP/AWS processing run.

```text
crawl_dir/downloads (54 original PDFs)
        │ upload PDF + metadata
        ▼
S3 incoming/
        │ EventBridge
        ▼
Step Functions ── ECS/Fargate PDF processor
        │ split/render → native Docling or Bedrock vision OCR
        │ render HTML → visual comparison/correction (≤7 passes)
        ├── failure → S3 quarantine/ + execution failure
        └── match   → S3 runs/ evidence
                      S3 validated/<document>.pdf.validated.json
                      S3 validated/<document>.pdf
                                      │
                                      ▼
SQS → Lambda chunker → S3 JSONL → SQS → Lambda embedder
                                      │
                                      ▼
                      Okapi BM25 + pgvector + RRF
                                      │
                                      ▼
                         authenticated search/chat API
```

Bedrock vision is not treated as an authority by itself. It performs OCR and
compares the page image with rendered extraction output. A page must finish
with `matched`; uncertain, failed, or max-pass pages quarantine the document.

## Repository layout

- `processor/`: containerized Docling, rendering, Bedrock OCR, and visual QA.
- `chunker/`: strict sidecar validation and page-preserving chunks.
- `embedder/`: Titan embeddings and atomic pgvector replacement.
- `query/`: GEHA-scoped Okapi BM25 and pgvector search, RRF fusion,
  grounded answers, citations, and minimal UI.
- `scripts/`: curated-corpus uploader and local sidecar tooling.
- `schema.sql`: GEHA metadata and retrieval schema.
- `template.yaml`: buckets, queues, DLQs, Fargate, Step Functions, Lambdas,
  least-privilege roles, logs, lifecycle rules, and alarms.

## Build and deploy

Prerequisites: AWS CLI, SAM CLI, Docker, an ECR repository, a VPC with outbound
HTTPS access, PostgreSQL with pgvector, and access to the configured Bedrock
models. Store the database URL and API key as SecureStrings:

```bash
aws ssm put-parameter --name /geha-rag/database-url --type SecureString \
  --value "$DATABASE_URL" --overwrite
aws ssm put-parameter --name /geha-rag/api-key --type SecureString \
  --value "$GEHA_RAG_API_KEY" --overwrite
psql "$DATABASE_URL" -f schema.sql
```

Build and push the processor image:

```bash
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REGION=us-west-2
REPO=geha-pdf-processor
aws ecr describe-repositories --repository-names "$REPO" >/dev/null 2>&1 || \
  aws ecr create-repository --repository-name "$REPO"
aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com"
docker build -t "$REPO" processor
docker tag "$REPO:latest" "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:latest"
docker push "$ACCOUNT.dkr.ecr.$REGION.amazonaws.com/$REPO:latest"
```

Validate and deploy the infrastructure:

```bash
sam validate --lint
sam build
sam deploy --guided
```

Use a new stack name such as `geha-validated-rag`; do not reuse or mutate the
legacy `sam-app` research stack during acceptance testing.

## Queue the curated corpus

First prove the local corpus and manifest agree without changing AWS:

```bash
/Users/dc/geha/.venv/bin/python scripts/upload_incoming.py \
  --corpus-dir /Users/dc/geha/crawl_dir/downloads \
  --manifest /Users/dc/geha/crawl_dir/src/documents.json \
  --bucket <DocumentBucketName> --dry-run
```

Remove `--dry-run` to upload metadata first and each original PDF second. Each
PDF starts one Step Functions execution. The processor publishes to
`validated/` only after every page matches; otherwise evidence goes to
`quarantine/` and no retrieval chunks are created.

## Operations

- Use Step Functions execution history for document-level status.
- Use `/aws/ecs/<stack>/pdf-processor` for extraction and correction logs.
- Inspect `runs/<run_id>/batch.json` for page/pass error counts.
- Treat either DLQ alarm as an ingestion incident.
- S3 versioning protects published source and sidecar objects.
- Processing evidence expires after 90 days; quarantined evidence after 180.
- API routes other than `/api/health` require `X-API-Key`.

## Acceptance gates

Before retiring the old research stack:

1. All 54 curated PDFs have successful Step Functions executions.
2. Every validated PDF has a matching sidecar SHA and complete page sequence.
3. Document count in `geha_documents` is 54 with zero unexpected paths.
4. Retrieval evaluation passes separately for coverage, FEHB, PSHB, and FEDVIP.
5. Citation pages resolve to the original PDFs.
6. DLQs are empty and no document remains silently quarantined.

Only after these checks should the old arXiv S3 objects and database records be
removed. Deleting the legacy stack is a separate, explicit operation.
