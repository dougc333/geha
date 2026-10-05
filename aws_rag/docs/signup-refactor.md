# Guided signup refactor (1–11)

The signup assistant is a transactional workflow with RAG available as a
read-only side path. Retrieval never decides eligibility, plan selection,
validation, confirmation, or completion.

1. **Reusable retrieval** — `query/retrieval.py` owns Postgres FTS/BM25,
   pgvector search, and reciprocal-rank fusion. Existing `chat.*` names remain
   available for the evaluation scripts.
2. **API models** — `query/signup/models.py` validates session and message
   commands, versions, and allowed slot updates.
3. **State machine** — `query/signup/graph.py` contains deterministic stages:
   eligibility → household → plan selection → contact → review → completed.
4. **Persistence** — `query/signup/repository.py` stores applications, messages,
   and events in the `signup` Postgres schema.
5. **Application service** — `query/signup/service.py` keeps orchestration outside
   the API and resumes the current state after a benefits question.
6. **Signup API** — `query/signup/router.py` exposes create, resume, message,
   confirm, and handoff endpoints.
7. **PII-safe tracing** — `query/signup/tracing.py` creates one Langfuse trace per
   turn and one session per application. `redaction.py` removes sensitive values.
8. **Concurrency and retries** — every message carries a client UUID and expected
   application version. Duplicate messages replay; stale writes return HTTP 409.
9. **Versioned benefits** — `signup.plan_versions` maps product/year/plan to the
   only RAG documents permitted for that signup.
10. **AWS configuration and UI** — `template.yaml`, `lambda_function.py`, and
    `signup.html` expose the workflow without changing the existing lab/chat UI.
11. **Tests** — `tests/test_signup.py` covers transitions, RAG interruptions, and
    telemetry redaction; existing query tests verify the new page and old APIs.

## Database migration

Apply `schema.sql` to the same Postgres database used by the query Lambda. Then
map the 2026 dental brochure after it has been ingested:

```sql
INSERT INTO signup.plan_versions
    (product, coverage_year, plan_code, document_ids)
VALUES
    ('dental', 2026, 'all', ARRAY['<sha256-from-docling-jsonl-filename>'])
ON CONFLICT (product, coverage_year, plan_code)
DO UPDATE SET document_ids = EXCLUDED.document_ids, active = true;
```

`SignupDocumentIds` is a deployment-time fallback only. The database mapping is
preferred because it is explicit and auditable.

`local_ingest/docling_chunks.py` names its JSONL output
`<document-sha256>.jsonl`; use that 64-character SHA-256 value as the document
ID, not the source PDF filename.

## API lifecycle

```text
POST /api/signup/sessions
GET  /api/signup/{application_id}
POST /api/signup/{application_id}/messages
POST /api/signup/{application_id}/confirm
POST /api/signup/{application_id}/handoff
```

Message example:

```json
{
  "client_message_id": "f48846ad-7e0c-4ea4-b219-ae8ddbbb8824",
  "message": "Does the High plan cover crowns?",
  "expected_version": 2,
  "slot_updates": {}
}
```

## Authentication boundary

The shared `X-API-Key` remains suitable only for the demo. With
`SignupAuthRequired=true`, signup endpoints require a JWT `sub` claim supplied
by an upstream API Gateway authorizer. Do not enable that setting on the Lambda
Function URL alone, because Function URLs do not populate JWT authorizer claims.

Use an opaque identity-provider subject as `member_ref`. Store the HMAC key in
the `SignupHashKeyParameter` SecureString so Langfuse receives only a stable
pseudonym. Langfuse is telemetry, not the signup system of record.
