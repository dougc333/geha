# AWS Data Workflow

```bash
cd /Users/dc/geha/advanced_rag
docker compose up --build
```

This directory is the production-oriented AWS counterpart to
`document_ingestion_workflow`. The existing local workflow remains unchanged.

> **Deployment note:** Docling is not required in AWS after preprocessing on
> the Mac has produced `whole-document-context.jsonl` records with contextual
> text and embeddings. The deployed service is a read-only retrieval tier: Jev
> routes each query, `BAAI/bge-small-en-v1.5` embeds the incoming query in the
> same 384-dimensional space as the stored vectors, and BM25 plus vector search
> are combined with reciprocal-rank fusion. It has no Docling/OCR component, no
> reranker, and no answer-generation LLM. S3 stores the prepared indexes and
> DynamoDB stores query-run state. Keeping the compute-heavy Docling ingestion
> step on the Mac avoids leaving an ingestion-sized Fargate task running in AWS,
> which was estimated at roughly $200 per month. The smaller retrieval-only
> service still incurs AWS charges. The current six form records are still
> marked `review_status=pending`; unreviewed retrieval is enabled only for this
> demo and must be disabled before production or member-facing use.

## Status

The local application performs ingestion and contextual-embedding creation.
The AWS deployment is deliberately a separate, read-only ECS/Fargate serving
runtime: S3 contains the contextual JSONL indexes, DynamoDB records query runs,
and TypeSafe Jev performs six-cluster query routing. Docling, OCR, contextual
generation, and answer generation do not run in ECS. An explicitly labelled
deterministic classifier is used if Jev is unavailable.

The larger event-driven Step Functions architecture described later in this
document remains a future target and is not required by the single-service
deployment.

## Single-service AWS deployment

```text
Browser
  -> CloudFront HTTPS
  -> public Application Load Balancer (HTTP origin)
  -> one ECS/Fargate task
       -> TypeSafe Jev query router
       -> BGE query embedding + BM25/vector rank fusion
       -> read-only contextual indexes in S3
       -> DynamoDB query-run records
```

Prerequisites:

- AWS CLI authenticated to the target account
- Docker with Buildx
- Terraform 1.7 or newer
- `TYPESAFE_API_KEY` exported in the deployment shell
- locally completed `whole-document-context.jsonl` artifacts

Terraform creates a dedicated VPC with public subnets in two Availability
Zones; the AWS account does not need a default VPC.

Deploy to `us-west-2`:

```bash
cd /Users/dc/geha/advanced_rag
export TYPESAFE_API_KEY='...'
PREBUILT_RUNTIME_DIR=/Users/dc/geha/advanced_rag/runtime/documents \
  AWS_REGION=us-west-2 ./scripts/deploy-ecs.sh
```

The script finds only prebuilt whole-document artifacts that already contain
embeddings, uploads them under the S3 `indexes/` prefix, transfers the Jev key
without placing it in Terraform state, builds the dedicated
`Dockerfile.runtime` image for `linux/amd64`, applies the stack, waits for ECS
stability, and verifies `/api/health` through CloudFront. The runtime image omits
Docling and all ingestion dependencies. It retains the compact
`BAAI/bge-small-en-v1.5` model because every new browser query must be embedded
in the same 384-dimensional space as the stored document vectors.

The currently prepared form records have `review_status=pending`. Terraform
sets `AWS_RAG_ALLOW_UNREVIEWED=1` for this demo so those six records are visible.
Set it to `0` after approving records, and do not use pending evidence in a
production or member-facing system.

CloudFront provides the browser-facing HTTPS URL, proxies to the ALB over HTTP,
and is also where the deploy script verifies `/api/health`. The ALB security
group permits only CloudFront origin addresses and the deployer's public IPv4
address. A viewer-request function separately restricts the HTTPS URL to exact
viewer addresses. It defaults to the deployer's IPv4; if the browser connects
to CloudFront over IPv6, pass both addresses as a Terraform-list expression:

```bash
export CLOUDFRONT_ALLOWED_IPS='["198.51.100.10","2001:db8::10"]'
```

Set `ALLOWED_CIDR` explicitly if a different IPv4 `/32` must reach the ALB
directly. Add application authentication before exposing non-public documents.

The runtime image builds and serves the same three-tab React interface used by
the local demo. Its AWS build is explicitly read-only: the Ingestion tab shows
completed S3 index inventory without upload/run/retry controls, and Contextual
Retrieval displays the precomputed source and contextual text without offering
contextualize or judge actions. Generated query examples, cluster inventory,
Jev routing, and DynamoDB-backed routing history remain available.

## Cluster query router

The AWS browser page accepts a query, routes it through Jev, searches only the
selected cluster with BM25 plus vector similarity and reciprocal-rank fusion,
and returns ranked source text. It does not synthesize an answer. Every search
is written to DynamoDB for demo run history.

The preferred classifier is TypeSafe Jev. When both `typesafe-sdk` and
`TYPESAFE_API_KEY` are available, the API asks Jev to choose among the six
cluster descriptions. Otherwise it uses an inspectable keyword scorer and the
UI prominently reports `JEV unavailable · fallback active`; fallback output is
never presented as a Jev result.

```jsonl
{"user_input":"Which employer benefits surveys report premium changes?"}
{"query":"What are the prior authorization criteria?"}
```

AWS runtime API routes:

- `GET /api/clusters` returns cluster descriptions, document counts, and search
  destinations.
- `POST /api/search` accepts `{"query": "...", "top_k": 6}` and returns the
  Jev route plus ranked source records. Every response includes `latency_ms`
  measurements for routing, query embedding, rank fusion, retrieval,
  persistence, and total server time; the same values are emitted in the
  standard `Server-Timing` response header.
- `GET /api/health` reports the loaded record count and confirms that Docling
  and answer generation are disabled.

## Target workflow

```text
PDF upload to S3
  -> EventBridge
  -> Step Functions Standard
  -> ECS Fargate Docling parsing and chunking workers
  -> deterministic document router
       +-- policy -> bounded review -> contextual embeddings -> policy index
       +-- other  -> generic artifacts
  -> policy query: hybrid BM25 + vector retrieval -> citation-bound answer
  -> S3 artifacts and DynamoDB status
  -> validation/review
  -> canonical manifest
```

## Planned AWS services

| Concern | Service |
| --- | --- |
| Source files and artifacts | Amazon S3 |
| Workflow orchestration | AWS Step Functions Standard |
| CPU/GPU document processing | Amazon ECS on AWS Fargate |
| Container images | Amazon ECR |
| Job and page state | Amazon DynamoDB |
| Events | Amazon EventBridge |
| Logs, metrics, and alarms | Amazon CloudWatch |
| Secrets | AWS Secrets Manager |

## Planned layout

```text
aws_data_workflow/
├── infra/                 # Infrastructure as code
├── src/
│   ├── control_plane/     # Submission, status, and manifest logic
│   └── worker/            # Page extraction and validation containers
├── state_machines/        # Step Functions definitions
├── tests/                 # Unit and integration tests
└── README.md
```

## Docling chunking worker

`src/aws_data_workflow/docling_chunking.py` converts a local document with
Docling and applies `HybridChunker`. It uses `BAAI/bge-small-en-v1.5` for token
counting, defaults to 380 tokens, preserves Docling metadata, and writes one
deterministically identified chunk per JSONL line. It also writes the complete
Docling Markdown as `document.md` beside the JSONL output.

In AWS, the Fargate task should download the source object from S3 to ephemeral
storage, invoke this worker, and upload `chunks.jsonl` to the run's artifact
prefix. S3 transfer and workflow state intentionally remain outside the chunker.

Run it locally:

```bash
cd /Users/dc/geha/aws_data_workflow
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

PYTHONPATH=src python -m aws_data_workflow.docling_chunking \
  /path/to/document.pdf \
  --output artifacts/chunks.jsonl \
  --max-tokens 380
```

## Contextual embeddings

`src/aws_data_workflow/contextual_embeddings.py` implements the next two
stages:

1. A Bedrock chat model produces a short context that situates each chunk in
   the complete document.
2. Amazon Titan Text Embeddings V2 embeds `retrieval_context + original text`.

The original `text` remains unchanged and should be used for citations and
grounding checks. `contextual_retrieval_text` is the retrieval-only field sent
to the embedding model and, later, BM25. Results are checkpointed after every
chunk and matching records are reused after an interrupted task.

For each document, the Bedrock prompt is ordered to maximize cache reuse:

```text
stable system instruction
stable complete document
explicit cache checkpoint
changing target chunk
```

The stable document is never repeated after the changing chunk. Each output
record stores `cache_read_input_tokens` and `cache_write_input_tokens` under
`prompt_cache`; the CLI summary aggregates both values. A cache hit is proven
by a nonzero `cache_read_input_tokens` value, not merely by sending the same
prefix. The configured Bedrock context model must support explicit Converse
cache checkpoints, and its document prefix must meet that model's minimum
cacheable token count.

```bash
export AWS_REGION=us-east-1
export BEDROCK_CONTEXT_MODEL_ID='<enabled Bedrock chat model ID>'

PYTHONPATH=src python -m aws_data_workflow.contextual_embeddings \
  --document artifacts/document.md \
  --chunks artifacts/chunks.jsonl \
  --output artifacts/contextual-chunks.jsonl
```

The Fargate task role needs permission to invoke both configured Bedrock
models. Context generation makes one model request per chunk, followed by one
embedding request per chunk, so the production workflow should enforce
concurrency and cost limits.

### Local Claude page-context workspace

The React dashboard also has a **Contextual Retrieval** tab for inspecting and
running the contextualization step before AWS integration. Select an ingested
document and click **Run page context**. The local API uses the same Anthropic
prompt contract as `crawl_dir/src/pipeline/contextual_retrieval.py`:

```text
stable system instruction
stable complete extracted document  <- ephemeral Claude cache block
changing page chunk                  <- one request per page
```

The source chunk is the best available Markdown for each page, preferring
`docling.normalized.md`, then the run's configured OCR output, then the other
page extractors. The original page text is never modified. Claude produces a
short `retrieval_context`, and the retrieval-only representation is:

```text
retrieval_context + blank line + original page text
```

Outputs live under the document runtime directory:

```text
runtime/documents/<document-id>/contextual-retrieval/
├── contextual-pages.jsonl       # one completed page record per line
└── contextual-retrieval.json    # live progress, page states, and cache usage
```

Both files are replaced atomically after each successful page. Clicking Run
again reuses a page only when its extracted-text hash, the complete-document
hash, model, and prompt version still match. This provides exact page progress,
page-level restart, and safe invalidation when any extracted page changes.
`cache_creation_input_tokens` and `cache_read_input_tokens` are displayed in the
UI; a nonzero cache-read count is evidence that Claude reused the document
prefix.

The API process must inherit `ANTHROPIC_API_KEY` (or an Anthropic auth profile).
The default is `claude-sonnet-5-5`; override it with
`ANTHROPIC_CONTEXT_MODEL`. The Run button explicitly confirms that every stale
page incurs one paid Claude request.

### LLM judge for extracted text and supplied context

After contextual retrieval completes, click **Judge contexts**. A separate
Claude request compares each original extracted page with its retrieval context
and returns a constrained judgment with two independent checks:

- `source_integrity`: `clean`, `suspect`, or `corrupt` for obvious extraction
  damage such as gibberish, duplicated fragments, broken reading order, and
  synthetic table headers such as `0`, `1`, `2`;
- `context_grounding`: `grounded`, `partially_grounded`, or `unsupported` for
  claims in the supplied context that are or are not supported by the chunk.

The combined verdict is `pass`, `review`, or `fail`. The UI shows live
page-by-page progress, colors the two comparison panels independently, adds a
pass/review/fail dot to every page tile, and displays the rationale and issue
lists below the panels. Results are checkpointed after every page:

The visible retrieval lifecycle is `EXTRACTED → CONTEXTUALIZED → JUDGED → INDEXED`.
`EXTRACTED` covers the Docling, DeepSeek, or LlamaParse extraction/OCR result.
`CONTEXTUALIZED` is persisted immediately after Claude has successfully added
retrieval context to every page; it is not an OCR state or a final quality verdict.

```text
runtime/documents/<document-id>/contextual-retrieval/judge/
├── judgments.jsonl  # structured, resumable page judgments
└── status.json      # current page, totals, and verdict counts
```

The judge reuses a result only when the source hash, context hash, judge model,
and prompt version match. Set `ANTHROPIC_JUDGE_MODEL` to use a model different
from the contextualization model. This text-only judge detects corruption
visible in the extracted Markdown; validating extraction against PDF pixels
requires a separate vision-judge pass using `page-NNN/source.pdf` or
`source.png`.

## Page, table, and figure processing

### Docling-first page extraction

Every PDF is split into single-page PDFs before the UI starts. Docling consumes
those `page-NNN/source.pdf` files one at a time, checkpoints each completed page,
and then uses a quality-gated cascade instead of sending every page to a paid
vision service:

```text
single-page PDF
  -> Docling Markdown
  -> deterministic quality gate
       +-- accepted -> ingest docling.md
       +-- low quality -> DeepSeek or LlamaParse fallback
```

The gate compares Docling output with embedded PDF text, checks token recall,
unexpected replacement characters, suspiciously short output, and image/scanned
pages with insufficient extracted text. This is an automated routing heuristic,
not ground-truth accuracy. Low-confidence pages remain explicitly reviewable.

Each page stores `docling.md` and `docling-quality.json`; the document-level
decision report is `pages/docling-preflight.json`. That report is rewritten
after every page with `completed_pages`, `remaining_pages`, and `status`, so an
interrupted run can resume without repeating completed pages. Use `--force` only
when every cached page should be extracted again.

Run the preflight directly:

```bash
cd /Users/dc/geha/aws_data_workflow
source ../.venv/bin/activate

PYTHONPATH=src python -m aws_data_workflow.docling_preextract \
  runtime/documents/<document-id>/source.pdf \
  runtime/documents/<document-id>/pages
```

The command prints exact page progress, for example:

```text
[34/104] page-034: accepted
```

Stopping the command preserves pages 1-34. Running the same command again skips
their valid `docling.md` plus `docling-quality.json` checkpoints and resumes at
page 35.

For the registered corpus, process different PDFs on separate CPU workers while
keeping each PDF's pages sequential and race-free:

```bash
PYTHONPATH=src python -m aws_data_workflow.batch_docling_preextract \
  --workers 2
```

Two workers is the recommended default on a laptop because every worker loads a
separate Docling/ONNX model stack. Increase to three or four only after watching
memory pressure. The command is resumable at page granularity.

### Second-pass table header normalization

After every PDF finishes its first-pass page extraction, the batch command runs
a deterministic table post-processing pass. This is deliberately deferred so
cross-page evidence is available and first-pass extraction remains resumable.

The pass detects placeholder headers emitted by pandas or Docling, including
`0,1,2,...` and `Unnamed: 0, Unnamed: 1,...`. Legitimate numeric labels such as
`2022, 2023, 2024` are not treated as placeholders. For an adjacent table
continuation with the same column count, headers are inherited from the prior
page. A headerless two-column key/value table is normalized to `Field` and
`Details`. Cases without a confident deterministic repair are marked
`review_required` rather than guessed.

Raw files are never overwritten. The post-process writes:

```text
pages/page-NNN/docling.md             # immutable first-pass extraction
pages/page-NNN/docling.normalized.md  # retrieval-safe table headers
visuals/tables/table-NNN/table.csv    # immutable structured extraction
visuals/tables/table-NNN/table.normalized.csv
visuals/tables/table-NNN/table.normalized.json
visuals/tables/table-NNN/table.normalized.md
table-postprocess.json                # repairs and unresolved review items
```

It runs automatically after `batch_docling_preextract` finishes. To run or
resume only the post-processing step:

```bash
cd /Users/dc/geha/aws_data_workflow
source ../.venv/bin/activate

PYTHONPATH=src python -m aws_data_workflow.table_postprocess
```

Restrict it to one registered document when debugging:

```bash
PYTHONPATH=src python -m aws_data_workflow.table_postprocess \
  --document-id doc-925d61c412d6
```

The known Kentucky Medicaid application case is a headerless two-column table
whose raw CSV begins with `0,1`; the normalized artifact uses `Field,Details`.

Docling mode enables page, table, and picture images in addition to structure
extraction. Each job writes a visual manifest and reviewable artifacts:

```text
runtime/documents/<document-id>/pages/
├── manifest.json
└── page-NNN/
    ├── source.png
    ├── docling.md
    ├── deepseek.md       # when Nous vision is configured
    └── metadata.json

runtime/documents/<document-id>/visuals/
├── manifest.json
├── tables/table-NNN/
│   ├── crop.png
│   ├── table.csv
│   ├── table.json
│   ├── table.html
│   └── metadata.json
└── figures/figure-NNN/
    ├── crop.png
    ├── native-text.txt
    ├── figure.json       # when a vision model is configured
    ├── figure.md         # accessible data/description
    └── metadata.json
```

Tables are validated for empty output, missing structure, empty headers, and
excessive missing cells. Figure crops require a structured vision description;
native numeric tokens are checked against the returned specification. Any
failed validation increments `reviewIssues` and holds a policy job at the
`reviewing` stage, preventing uncertain visual content from reaching embeddings
or the policy index.

To process figures automatically with Nous-hosted DeepSeek V4.1 Flash 1017,
keep the API key in your shell configuration rather than this repository:

```bash
# Already present in ~/.zshrc on the development machine:
export NOUS_KEY='...'

source ~/.zshrc
PYTHONPATH=src python -m uvicorn aws_data_workflow.server:app --host 127.0.0.1 --port 8000
```

The default Nous model is `deepseek/deepseek-v4.1-flash-1017`. Override it only
when intentionally testing another multimodal model:

```bash
export NOUS_VISION_MODEL='deepseek/deepseek-v4.1-flash-1017'
```

The server accepts `NOUS_API_KEY` as an alias for `NOUS_KEY`. It never writes the
key to an artifact. If neither Nous variable is present, an optional
`BEDROCK_VISION_MODEL_ID` is used as a fallback. Without either provider, figure
crops and metadata are still saved, but each figure is marked `review_required`
for manual correction.

For every page, the pipeline saves the original page and Docling Markdown.
DeepSeek or LlamaParse Markdown is created only when the Docling quality gate
requests fallback. The React inspector advances the single-page PDF and matching
Markdown together. Only fallback pages are sent to the selected external
provider; do not enable those routes for documents that cannot be shared.

## Policy RAG

### Whole-document forms and applications

Forms and applications are not ordinary narrative reports. Splitting blank
fields, instructions, certifications, and signature sections into independent
retrieval chunks removes the relationships that give the form meaning. The
document router therefore assigns confirmed forms and applications to
`whole_document_context` with `storage_strategy=whole_document`.

This route preserves the complete extracted document as one source record.
Single-page PDFs and Markdown remain available as OCR provenance, but they are
never written as separate retrieval records. The local dashboard sends the
complete form to Claude once and produces a concise retrieval context containing
the form name, issuer, purpose, intended applicant, major sections, required
information, and submission instructions. The locally cached
`BAAI/bge-small-en-v1.5` model embeds that context on-device as one normalized
vector. The database row also retains context plus the complete form text. The
generated context does not replace the original form and is not treated as
evidence.

The 50-document demonstration corpus contains these six forms/applications:

| Document | Kind |
|---|---|
| `Revised_KYState_MedicaidKCHIPQHPAppForOnePerson.pdf` | Kentucky health-coverage application |
| `Revised_KYState_MedicaidKCHIPQHPAppForFamily.pdf` | Kentucky household health-coverage application |
| `IM-1SSL-Fillable-Secured-6-24-21.pdf` | Missouri health-coverage application |
| `im-1sslsp.pdf` | Spanish Missouri health-coverage application |
| `IM-1ABDS_Spanish.pdf` | Spanish aged, blind, and disabled application supplement |
| `ODM06723fillx.pdf` | Ohio Medicaid authorized-representative form |

`optical_providers_adult_medicaid.pdf` remains a provider directory, and
`AZ-AHCCCS-State-Fair-Hearing-EN.pdf` remains hearing instructions; neither is
routed as a form merely because it belongs near administrative content.

The **Contextual Retrieval** tab shows all six documents with a `1 unit` badge.
Select a form and click **Run whole form**. The local artifacts are:

```text
runtime/documents/<document-id>/source.pdf
runtime/documents/<document-id>/contextual-retrieval/
├── whole-document-context.jsonl
└── contextual-retrieval.json
runtime/vector-db/forms.sqlite3
```

`forms.sqlite3` contains one row per completed form. Every row stores the
retrieval context, embedding, filesystem path, and API link back to the unchanged
`source.pdf`. The UI exposes both **Open unchanged filesystem form** and the
generated contextual record. Re-running is idempotent when the complete-document
hash, prompt, Claude model, and embedding model match.

Embedding is intentionally local: complete form contents are not sent to a
second model provider. Only the explicitly requested Claude contextualization
call leaves the machine.

The AWS-oriented worker retains its optional Bedrock/Titan implementation in
`whole_document_context.py`; the local dashboard path uses the direct Anthropic
call and prompt-cache structure shared by `page_contextual_retrieval.py`.

`src/aws_data_workflow/policy_rag.py` provides a small end-to-end policy query
path over `contextual-chunks.jsonl`:

```text
question
  +-- BM25 over contextual_retrieval_text --------+
  +-- Titan query vector + cosine similarity -----+--> reciprocal-rank fusion
                                                        -> top evidence chunks
                                                        -> Bedrock answer
                                                        -> numbered citations
```

Only chunks whose `review_status` is `approved` or `passed` are searchable by
default. Retrieval uses generated context, but answer generation receives only
the preserved original `text`. This prevents generated indexing annotations
from becoming policy evidence.

```bash
export AWS_REGION=us-east-1
export BEDROCK_ANSWER_MODEL_ID='<enabled Bedrock chat model ID>'

PYTHONPATH=src python -m aws_data_workflow.policy_rag \
  --chunks artifacts/contextual-chunks.jsonl \
  --query 'Are preventive dental services covered in network?'
```

`--allow-unreviewed` exists only for local development. Do not enable it in a
production policy-answering service. The in-memory ranking implementation is a
testable reference contract; production deployment should move its BM25 and
vector operations to the selected managed search store while preserving the
same reviewed-chunk and citation rules.

## Policy detection and state-machine routing

`src/aws_data_workflow/document_router.py` classifies documents from the source
filename and Docling Markdown. It uses explicit, versioned signals rather than
asking an LLM to make an opaque routing decision. The result includes the score,
threshold, every matching signal, document type, and selected route.

```bash
PYTHONPATH=src python -m aws_data_workflow.document_router \
  --source-name geha-coverage-policy-bendamustine.pdf \
  --document artifacts/document.md \
  --output artifacts/classification.json
```

The Step Functions definition at
`state_machines/document_ingestion.asl.json` runs Docling first and then uses
`$.classification.is_policy` in a `Choice` state:

- policy documents enter bounded table/figure review;
- only a `passed` review can reach contextual embedding and policy indexing;
- failed or uncertain review is held for a person;
- non-policy documents are stored as generic artifacts and never enter the
  policy RAG index.

The `${...FunctionArn}` values are deployment placeholders to be substituted by
the infrastructure stack. The state-machine definition does not itself deploy
Lambda functions or IAM roles.

Run the lightweight unit tests without parsing a PDF:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## React ingestion dashboard

`web/` is a TypeScript and Tailwind control-plane UI for monitoring a batch of
50 PDFs across the AWS ingestion stages. It has a normalized reducer-backed
store and narrowly scoped hooks, so shared document/job state is not prop
drilled through layout components.

`src/aws_data_workflow/server.py` is the local FastAPI control plane. It owns
the persistent job state, accepts PDF uploads, serves source PDFs, runs or
retries jobs, and exposes the document list polled by React. On the first run it
idempotently registers the first 50 PDFs from the ignored `tests/documents/`
corpus when that corpus is present. Existing runtimes are topped up without
duplicating the original 18 records. Set a different limit with
`AWS_WORKFLOW_SEED_LIMIT`, or disable seeding with
`AWS_WORKFLOW_SEED_TEST_PDFS=0`.

Local files are stored as:

```text
runtime/documents/<document-id>/
├── source.pdf
├── job.json
├── document.md       # Docling mode
└── chunks.jsonl      # Docling mode
```

Start the backend with the existing GEHA environment:

```bash
cd /Users/dc/geha/advanced_rag
source /Users/dc/geha/.venv/bin/activate
PYTHONPATH=src python -m aws_data_workflow.server
```

The built React application is then available at `http://127.0.0.1:8000`.
Swagger API documentation is available at `http://127.0.0.1:8000/docs`.

For frontend development, leave the backend running and start Vite separately:

```bash
cd /Users/dc/geha/advanced_rag/web
npm install
npm run dev
```

Open `http://localhost:5175`; Vite proxies `/api` to port 8000. Use **Run
next** to process one queued record at a time, select a document to inspect its route
and artifact destination, or add local PDFs to the queue.

### Docker

The Docker image builds the React application first, then serves the compiled UI
and FastAPI API together on port 8000. Runtime documents and generated artifacts
remain on the host through the `./runtime:/app/runtime` volume.

Export any provider keys needed by the workflow in the shell that launches
Compose. Compose passes through Anthropic, LlamaParse, Nous, TypeSafe Jev, Muse,
and standard AWS credential variables when they are present.

```bash
cd /Users/dc/geha/advanced_rag
docker compose up --build
```

Open `http://127.0.0.1:8000`. Stop the stack with `Ctrl-C`, or run
`docker compose down` from the same directory.

The default `AWS_WORKFLOW_PROCESSING_MODE=docling` runs real Docling extraction,
chunking, table normalization, and figure cropping. Set it to `simulate` only
for fast UI demonstrations. Bedrock contextualization and managed indexing
remain explicit AWS integration boundaries. Production should replace the filesystem
store with S3/DynamoDB and submit Step Functions executions while preserving
the API's `DocumentRecord` contract.

### Local PDF test corpus

The local, ignored `tests/documents/` directory mirrors PDF fixtures from
`/Users/dc/united/pdfs` while preserving their source-domain paths. The corpus
is intentionally excluded from Git because it contains thousands of files and
is several gigabytes. Tests that depend on it should skip cleanly when the
directory is absent in CI.

Start with public documents only. Add private or regulated documents only after
access controls, encryption, retention, audit logging, and compliance review are
in place.

## Clustered RAGAS query set

`evals/cluster_manifest.json` labels the 50-document United corpus with six
ingestion clusters. `evals/generate_cluster_ragas_queries.py` asks an LLM for one
grounded query per document. Each output row records the cluster, source path,
content hash, and exact evidence quotes. Multi-document queries are deliberately
excluded.

Validate the corpus and pair assignments without an API call:

```bash
cd /Users/dc/geha/aws_data_workflow
/Users/dc/geha/.venv/bin/python \
  evals/generate_cluster_ragas_queries.py --dry-run
```

Generate 50 single-document RAGAS-compatible records:

```bash
source ~/.zshrc
/Users/dc/geha/.venv/bin/python \
  evals/generate_cluster_ragas_queries.py \
  --model gpt-4.1-mini \
  --max-workers 4
```

The combined output is `evals/generated/cluster_ragas_queries.jsonl`. The same
run also writes one record per document under
`evals/generated/by_document/<source path without .pdf>/ragas.jsonl`. Preserving
the source path prevents PDFs with the same filename from overwriting each
other. For example:

```text
evals/generated/by_document/
  example.org/reports/benefits-study/ragas.jsonl
```

The LLM generates each query and reference answer, while code validates that
its quoted evidence is present in the labeled source document.

## OCR engine selection and run artifacts

The React toolbar selects the fallback engine used by **Run selected**:

- **DeepSeek (default)** uses the Nous-hosted DeepSeek vision model and requires
  `NOUS_API_KEY` (or `NOUS_KEY`).
- **LlamaParse** uses the current `llama-cloud` SDK, defaults to the `agentic`
  tier, and requires `LLAMA_CLOUD_API_KEY`. Override its tier with
  `LLAMAPARSE_TIER`.

The control-plane record remains under `runtime/documents/<document-id>`, while
every real execution now creates an immutable, document-ingestion-compatible
run:

```text
runtime/runs/documents/<document-slug>/<run-id>/
  input/
    source.pdf
    source-reference.json
  candidate/
    document.md
    chunks.jsonl
    visuals/
  pages/
    page-001/
      source.pdf
      source.png
      page.md
      deepseek.md or llamaparse.md
      docling.md
      page-manifest.json
  run-manifest.json
  qc-report.json
  errors.json
```

The input PDF is split when it is registered, before the UI starts. Runs copy
the prepared `pages/page-NNN/source.pdf` artifacts, so page evidence exists
before Docling or fallback extraction begins.

Docling runs first for every page. DeepSeek or LlamaParse receives only page
numbers listed in `docling-preflight.json` as `fallback_pages`. Provider output
is stored as `page-NNN/deepseek.md` or `page-NNN/llamaparse.md` and promoted to
`page-NNN/page.md`; accepted pages promote `docling.md` instead.

`errors.json` is initialized for every run. Processing failures append a
structured record containing the timestamp, document ID, current stage, OCR
engine, exception type, and message. Per-page OCR failures name the relevant
`page-NNN` in the message.

`page.md` is the Markdown selected for ingestion. It is Docling output when the
quality gate accepts the page and fallback-engine output otherwise.
