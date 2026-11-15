# AWS ingestion and agent implementation plan

Status: implementation plan. This document turns the existing ingestion specs into a staged, production-shaped demo. It does not authorize processing PHI; the demo uses public or synthetic documents only.

## 1. Outcome

Build a page-level document-ingestion system that:

1. accepts a multipage PDF;
2. segments it into independently retryable page jobs;
3. uses Amazon Textract as the managed extraction path and retains the existing Tesseract/spec pipelines as benchmark and fallback paths;
4. uses a bounded agent loop to diagnose and repair residual extraction errors;
5. sends risky or uncertain pages to a human review queue;
6. exports only approved content to Markdown and the RAG index; and
7. demonstrates horizontal scaling, idempotency, failure recovery, observability, and cost controls on AWS.

The primary hiring signal is reliable distributed processing at scale. Multi-agent behavior is a replaceable implementation detail, not the system boundary.

## 2. Architecture decision

Use managed AWS primitives before Kubernetes:

| Concern | Initial choice | Reason |
|---|---|---|
| HTTP API and review API | FastAPI on ECS/Fargate behind an ALB | Simplest container-native HTTP path without an EKS control plane |
| External API management | API Gateway in front of a private ALB, optional | Add only when client quotas, API keys, usage plans, or a consolidated external API justify the extra hop |
| Page work distribution | SQS Standard queues | At-least-once delivery, buffering, retries, DLQs |
| CPU-heavy workers | ECS/Fargate services | Scale workers on queue backlog per running task |
| Managed document extraction | Asynchronous Amazon Textract | Forms, tables, layout, and query extraction without operating OCR capacity |
| Extraction fallback and benchmark | Tesseract plus PyMuPDF | Local reproducibility, cost comparison, and fallback for unsupported pages |
| Exceptional large jobs | AWS Batch on EC2/Spot, later | Use only if Fargate task shapes or duration become limiting |
| Artifacts | Versioned S3 bucket | Immutable PDFs, PNGs, HTML, specs, Markdown, diffs, run logs |
| Transactional state and retrieval | RDS PostgreSQL with pgvector | Idempotency, approvals, page/run state, audit queries, chunks, embeddings, and cited retrieval |
| Workflow coordination | Database state machine initially | Avoid one Step Functions transition per agent iteration |
| Long-lived document workflows | Step Functions Standard, optional in phase 6 | Add when callback waits and human steps justify it |
| Agent implementation | `AgentLoop` interface in Python | Keeps orchestration framework replaceable |
| Metrics and logs | OpenTelemetry plus CloudWatch | Correlate document, page, run, queue, and model calls |
| Secrets | Secrets Manager | No model credentials in images, task definitions, or Git |
| Infrastructure | AWS CDK or Terraform | Repeatable environments and reviewable changes |
| Deployment identity | AWS CLI profile `geha-terraform` | Keep infrastructure changes attributable to the deployment identity and separate from runtime roles |
| Production operator identity | AWS CLI profile `geha-user` | Invoke, inspect, smoke-test, and troubleshoot the deployed production application without using the provisioning identity |

EKS is a later option only if the platform develops many independently operated services, specialized GPU scheduling, custom operators, or a shared multi-team platform. High throughput alone is not a reason to introduce Kubernetes.

Infrastructure commands run explicitly with the deployment profile so Terraform cannot silently fall back to `default`:

```bash
AWS_PROFILE=geha-terraform terraform init
AWS_PROFILE=geha-terraform terraform plan
AWS_PROFILE=geha-terraform terraform apply
```

Before a plan or apply, verify the selected identity with `aws sts get-caller-identity --profile geha-terraform`. The `geha-terraform` identity is for provisioning only. FastAPI and each worker service receive separate least-privilege ECS task roles; no deployed container receives the Terraform credentials.

Post-deployment production operation uses `geha-user`, not `geha-terraform`. This includes invoking the application, running smoke tests, reading permitted logs and metrics, and troubleshooting. Black-box API tests authenticate as a test client and need no infrastructure credentials. CI should use a dedicated `aws-ingestion-smoke` role. That role may describe ECS/ALB state, read selected CloudWatch metrics and logs, and inspect only the test queues and S3 prefix; it cannot create, update, or delete infrastructure.

```bash
# Provision
AWS_PROFILE=geha-terraform terraform apply

# Operate and verify the deployed application as the production user
AWS_PROFILE=geha-user pytest -m smoke \
  --base-url "$(terraform output -raw api_url)" \
  --fixture tests/fixtures/synthetic-one-page-claim.pdf
```

CI should obtain the smoke-test role with short-lived OIDC credentials rather than storing a user access key.

This plan deliberately changes the earlier draft assumption that both local OCR pipelines must run on every page. In the AWS demo, Textract is the primary path. Tesseract and the spec-first parser run on the benchmark set, on explicitly routed fallback pages, or as a sampled cross-check. This keeps production cost and latency bounded while preserving an objective comparison.

## 3. Runtime topology

```text
Browser / client
      |
      +--> API Gateway (optional external API-management layer)
      |              |
      |              v
      +-----------> ALB
                     |
              FastAPI on ECS/Fargate ---------------------> RDS PostgreSQL
                     |                                      + pgvector
                     | presigned upload                     |
                     v                                      | state, idempotency,
                    S3                                      | chunks, embeddings
                     |
              ObjectCreated event
                     |
                    SQS ingest queue
                     |
          Fargate segment/submit workers
                     |
              Amazon Textract async
                     |
              SNS completion topic
                     |
             SQS textract-complete queue
                     |
          Fargate normalization workers
                     |
              SQS llm-extract queue
                     |
          Fargate LLM/agent workers
                     |
       structured PageSpec + verification
                     |
          +----------+-----------+
          |                      |
      approved/clean         needs review
          |                      |
      export/index queue     React review app
          |                      |
          +----> PostgreSQL/pgvector <---- approval event
```

Every queue has a DLQ. Workers acknowledge a message only after artifacts and the corresponding database transition commit successfully.

For the first demo, expose the FastAPI service directly through an ALB. API Gateway is not required merely to reach Fargate; placing it in front of a private ALB introduces a VPC Link and another operational layer. Add API Gateway when its API-management features are part of the demonstrated requirement.

Textract submission is asynchronous. A Fargate task submits the S3 object and records the Textract job ID; it does not wait or poll. Textract publishes completion through SNS, which feeds the completion SQS queue. A normalization worker retrieves all result pages, writes the raw and normalized results to S3, updates PostgreSQL, and emits the LLM-extraction job.

## 4. Work and state boundaries

### Unit of work

The unit of parallelism is one `(doc_sha256, page_no, pipeline, pipeline_version)` run. The database enforces a unique constraint on that tuple.

An SQS delivery is a request to attempt work, not proof that work has not already happened. Each worker:

1. reads the current run row;
2. acquires ownership with an atomic state transition and lease expiry;
3. returns success without recomputation if the exact version is complete;
4. writes artifacts to content-addressed S3 keys;
5. commits metrics and the final state transactionally; and
6. deletes the SQS message only after the commit.

### State machines

Page state:

```text
pending -> segmented -> processing -> needs_review -> approved -> exported
                                |             |
                                v             v
                              failed       rejected -> reprocess
```

Run state:

```text
queued -> leased -> running -> succeeded
                    |    |
                    |    +-> retryable_failure -> queued
                    +------> terminal_failure -> DLQ
```

Leases make worker termination recoverable. A lease has `owner`, `leased_at`, `expires_at`, and a heartbeat. All externally visible writes use an idempotency key.

## 5. Agent boundary

Do not deploy AutoGen Studio. It is a prototyping UI and its SQLite database is not the production runtime.

Define a narrow application interface:

```python
class AgentLoop(Protocol):
    async def repair(self, request: RepairRequest) -> RepairResult: ...
```

`RepairRequest` contains immutable artifact URIs, current error metrics, permitted tools, iteration budget, token budget, and model policy. `RepairResult` contains patches, rationale, tool observations, token usage, model identity, stop reason, and final metrics.

Implementations:

1. `DirectRepairLoop`: explicit Python state machine; build this first as the reference.
2. `LangGraphRepairLoop`: optional comparison because the target job names LangGraph.
3. `AutoGenRepairLoop`: optional adapter for evaluating AutoGen AgentChat without coupling storage or queues to it.

The coarse-grained distributed workflow remains SQS plus PostgreSQL. Agent turns stay inside one worker execution; they are not separate SQS messages. This prevents message storms and makes the five-iteration cost and latency bound enforceable.

### Agent roles

Begin with one repair agent using deterministic tools. Add specialist agents only if evaluation shows a measurable gain:

- `layout_inspector`: finds region, reading-order, and table-shape differences;
- `content_verifier`: checks words, numeric tokens, and unsupported additions;
- `patch_planner`: proposes the smallest allowed JSON Patch or HTML edit;
- `final_judge`: deterministic checks first, model-based vision judgment only where ground truth is unavailable.

A multi-agent team is rejected unless it improves the benchmark enough to justify its extra tokens and latency.

### Guardrails

- Maximum five repair iterations.
- Per-page token and dollar budget.
- Model timeout and retry budget.
- JSON-schema validation before accepting tool arguments or patches.
- Pipeline 2 patches the page spec only; HTML remains deterministic output.
- Reject patches that introduce unseen numeric tokens.
- Revert a patch when the error score worsens by more than 20%.
- Record every model call, tool result, patch, rationale, and model version.
- No arbitrary shell or unrestricted network tool in the worker.

## 6. Queues and worker classes

| Queue | Worker | Scaling signal | Retry policy |
|---|---|---|---|
| `ingest` | PyMuPDF segmenter and Textract submitter | backlog per task | 3 attempts |
| `textract-complete` | Textract result collector and normalizer | backlog per task | 3 attempts |
| `llm-extract` | PageSpec extraction and bounded agent loop | oldest-message age plus backlog per task | 2 attempts |
| `fallback-ocr` | Tesseract/PyMuPDF benchmark or fallback | backlog weighted by page size | 3 attempts |
| `verify` | render, diff, numeric, and structural checks | backlog per task | 2 attempts |
| `export` | Docling, Markdown, embedding, and pgvector indexing | backlog per task | 3 attempts |

Visibility timeout starts above the observed p99 processing time. Long jobs extend visibility with a heartbeat. ECS task scale-in protection is enabled while a worker owns a lease.

Use separate queues so slow vision/model calls cannot consume all extraction-completion capacity. Configure maximum concurrency for Textract submissions and model-calling workers to respect AWS/model quotas and the project cost ceiling.

## 7. Storage layout

```text
s3://<bucket>/documents/<doc_sha256>/source.pdf
s3://<bucket>/documents/<doc_sha256>/pages/<page_no>/source.pdf
s3://<bucket>/documents/<doc_sha256>/pages/<page_no>/source-150.png
s3://<bucket>/documents/<doc_sha256>/pages/<page_no>/source-300.png
s3://<bucket>/runs/<run_id>/baseline.html
s3://<bucket>/runs/<run_id>/page.spec.json
s3://<bucket>/runs/<run_id>/iterations/<n>/observation.json
s3://<bucket>/runs/<run_id>/iterations/<n>/patch.json
s3://<bucket>/runs/<run_id>/iterations/<n>/render.png
s3://<bucket>/runs/<run_id>/final.html
s3://<bucket>/runs/<run_id>/page.md
s3://<bucket>/runs/<run_id>/run.json
```

Artifacts are immutable. Corrections create a new run/version. Approvals refer to the SHA-256 of the exact reviewed content.

## 8. Database additions

Keep the entities in `docs/ingestion_design.md` and add:

```text
job(id, kind, idempotency_key, state, attempt_count, queued_at,
    owner, leased_at, expires_at, last_error)

artifact(id, run_id, kind, uri, sha256, bytes, created_at)

agent_step(id, run_id, iteration, model, prompt_version, tool_name,
           input_uri, output_uri, tokens_in, tokens_out, latency_ms,
           estimated_cost, error_count_before, error_count_after, created_at)

outbox(id, event_type, aggregate_id, payload, published_at, created_at)
```

Use a transactional outbox so a committed database transition cannot lose the follow-on queue event. A publisher sends unpublished events to SQS and records `published_at`; duplicate publication is safe because consumers are idempotent.

## 9. API plan

Add to the review API already specified:

```text
POST /documents/uploads             -> presigned S3 upload
POST /documents                     -> register completed upload by sha256
GET  /documents/:id                 -> document and aggregate status
POST /documents/:id/reprocess       -> explicit new pipeline version
GET  /runs/:id                      -> state, metrics, artifacts, agent steps
GET  /health/live
GET  /health/ready
```

No request waits for OCR or an LLM. Mutation endpoints accept an idempotency key. The API returns `202 Accepted` for asynchronous operations.

## 10. Observability and operations

Every log and span includes `document_id`, `doc_sha256`, `page_no`, `run_id`, `pipeline`, `pipeline_version`, `job_id`, and `attempt`.

Dashboards:

- API p50/p95/p99 and error rate;
- queue depth, backlog per task, and oldest-message age by stage;
- pages completed per minute and end-to-end time to review;
- worker utilization, task starts/stops, retry and DLQ counts;
- OCR, render, model, database, and S3 latency;
- errors before/after each agent iteration;
- token use and estimated cost per page/document;
- approval rate, reviewer corrections, and false-clean sample rate.

Alarms:

- oldest-message age exceeds the stage SLO;
- any DLQ receives a message;
- duplicate-commit constraint violations rise;
- model spend or token rate exceeds its budget;
- database connections, storage, or CPU cross thresholds;
- review backlog grows continuously.

Runbooks cover queue backlog, poisoned messages, model-provider outage, RDS failover, worker crash loops, bad pipeline release, and approval rollback.

## 11. Security boundary

The demo uses only synthetic or public documents. Before any PHI workload:

- execute the required AWS BAA and confirm every service is eligible for the intended use;
- use private subnets and VPC endpoints where appropriate;
- encrypt S3, RDS, SQS, logs, and secrets with managed keys and documented rotation;
- give every ECS task role least-privilege access to only its queues and S3 prefixes;
- prohibit document content in application logs;
- redact model traces and define retention/deletion policies;
- maintain append-only approval and administrative audit history;
- verify the selected model provider and data-handling configuration contractually permit the workload.

## 12. Implementation phases

### Phase 0: repository and contracts

- Add Python project structure, linting, typing, tests, and local Docker Compose.
- Turn existing schemas and state diagrams into executable types and migrations.
- Create golden page fixtures covering text, scan, form, table, and figure pages.
- Implement fake S3/SQS/model adapters for deterministic tests.

Exit: CI validates schemas and runs deterministic unit tests without AWS credentials.

### Phase 1: local vertical slice

- Implement segmenter and manifest.
- Implement deterministic pipeline 2 spec renderer first.
- Implement baseline pipeline A and B without an agent.
- Persist artifacts locally behind the same storage interface used by S3.

Exit: one benchmark PDF produces both baseline HTML outputs and reproducible metrics.

### Phase 2: deterministic verification

- Implement render, text diff, numeric check, table-shape check, and diff-region tools.
- Implement stop conditions and patch rollback.
- Establish the no-agent benchmark and error taxonomy.

Exit: tool results are repeatable and every error count can be reproduced offline.

### Phase 3: bounded agent loop

- Implement `DirectRepairLoop`.
- Add structured tool calls, patch validation, budgets, traces, and replay.
- Evaluate single-agent results before implementing specialist agents.
- Optionally implement AutoGen and LangGraph adapters against the identical interface.

Exit: the selected agent implementation beats the no-agent baseline on the benchmark without violating numeric or unsupported-text checks.

### Phase 4: AWS distributed execution

- Provision S3, RDS PostgreSQL with pgvector, ECR, SQS/DLQs, SNS, ECS/Fargate, ALB, Secrets Manager, and CloudWatch.
- Implement asynchronous Textract submission, SNS completion delivery, result pagination, normalization, and fallback routing.
- Implement leases, idempotent consumers, visibility heartbeats, task scale-in protection, and the outbox publisher.
- Deploy separate worker services and queue-based autoscaling.

Exit: killing workers and redelivering messages produces no duplicate committed run or lost page.

### Phase 5: review and approval

- Build the React queue and page-review screens in `specs/review_app.md`.
- Implement authenticated, append-only approvals and invalidation on content change.
- Export approved pages only.

Exit: a reviewer can compare pipelines, edit a spec, approve the exact content hash, and observe that a later edit revokes approval.

### Phase 6: RAG and workflow extensions

- Chunk approved Markdown with page/block provenance.
- Store embeddings in pgvector and expose retrieval with document, page, block, content-hash, and approval citations.
- Add Step Functions only if document-level callbacks, human waits, or audit requirements are clearer than the database state machine.
- Route exceptional large jobs to AWS Batch if load evidence justifies it.

Exit: every answer citation resolves to an approved document page and block.

### Phase 7: load, failure, and cost demonstration

- Run a metadata/no-op test to validate orchestration at 10,000 page jobs.
- Run real OCR/render/model processing on the bounded benchmark set.
- Inject duplicate messages, worker termination, slow model calls, throttling, corrupt PDFs, and database failover.
- Publish throughput, latency, accuracy, recovery, and cost results.

Exit: the acceptance criteria below are met and the live demonstration is repeatable from infrastructure code.

### Smoke-test suite

Run this after every development deployment:

1. `GET /health/ready` returns success and the expected build version.
2. Request a presigned upload and upload a one-page synthetic PDF.
3. Register the document twice with the same idempotency key and receive one document/run identity.
4. Poll the public status API until Textract, normalization, and LLM extraction complete.
5. Validate the resulting `PageSpec` against `page_spec.schema.json`.
6. Confirm the page remains absent from retrieval before approval.
7. Approve the synthetic fixture through the test-only reviewer identity.
8. Query retrieval and verify the result resolves to the approved document, page, block, and content hash.
9. Confirm no smoke-test message reached a DLQ and the end-to-end duration stayed within the smoke SLO.
10. Delete or expire only resources tagged with the smoke run ID.

The ordinary smoke suite uses one small synthetic document and does not deliberately create DLQ failures. Duplicate delivery, worker termination, provider throttling, and poisoned-message scenarios belong to scheduled integration or failure-injection tests so routine deployments remain fast and inexpensive.

## 13. Acceptance criteria

Correctness:

- zero duplicate committed runs under duplicate SQS delivery;
- every artifact checksum is recorded and verified;
- no unapproved page reaches the RAG index;
- later content modification invalidates the prior approval;
- all unsupported numeric additions force `needs_review`;
- every agent decision can be replayed from stored inputs and outputs.

Reliability:

- a terminated worker's job becomes available and completes on another worker;
- poison messages reach a DLQ after the configured attempt budget;
- model-provider failure pauses or retries agent work without blocking OCR queues;
- deployment rollback does not strand leased jobs.

Performance targets for the demo:

- upload/register API p95 below 300 ms, excluding direct S3 transfer;
- no-op orchestration sustains 10,000 page jobs with no lost state transition;
- queue backlog begins draining within two autoscaling evaluation periods;
- review-ready latency and pages/minute are reported separately for text, scan, table, and figure classes rather than hidden in one average.

Quality and cost:

- pages with a text layer meet the existing <= 0.5% word-error target or are sent to review;
- agent quality is compared with the no-agent baseline and with each optional framework adapter;
- report tokens, model dollars, compute dollars, and reviewer time per accepted page;
- a page cannot exceed its configured model-call, iteration, or dollar cap.

## 14. Demonstration script

1. Upload a benchmark PDF and show immediate `202 Accepted`.
2. Show S3 ingestion, SQS buffering, asynchronous Textract completion, and Fargate normalization.
3. Open one run's Textract evidence, deterministic checks, bounded agent repair trace, and optional Tesseract cross-check.
4. Generate a traffic burst and show backlog-per-task autoscaling.
5. Terminate a worker; show lease expiry, redelivery, and one committed result.
6. Send a corrupt page to the DLQ without stopping the document.
7. Review a high-risk page, edit its spec, and approve its content hash.
8. Demonstrate that an unapproved page is absent from RAG.
9. Query an approved page and follow its citation back to the reviewed source block.
10. Finish with throughput, p95 latency, error reduction, retries, cost/page, and reviewer-correction rate.

## 15. Immediate next tasks

1. Choose CDK or Terraform and record the decision.
2. Create the Python package boundaries: `api`, `domain`, `workers`, `pipelines`, `agent`, `storage`, `observability`.
3. Add PostgreSQL migrations for document, page, run, job, artifact, agent step, approval, and outbox.
4. Implement the page-spec renderer and golden tests.
5. Implement deterministic verification tools and the no-agent benchmark.
6. Implement the direct bounded repair loop before adding an agent framework.
7. Deploy the first SQS-to-Fargate worker and prove idempotent redelivery.
8. Add the Textract SNS-to-SQS completion path and normalize one page into `PageSpec`.
9. Enable pgvector and prove that retrieval returns only approved content with resolvable citations.

