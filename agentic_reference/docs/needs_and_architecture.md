# Inferred Needs and Reference Architecture

## Scope and assumptions

This architecture is inferred from public GEHA, OPM, and HHS materials plus the
synthetic workflow models in the parent project. It does not describe GEHA's
internal technology or proprietary adjudication rules.

The first implementation target is an **administrative copilot** for members,
providers, adjusters, and appeals staff. It retrieves evidence and prepares
work; it does not replace a benefit engine or qualified decision maker.

## Inferred user journeys

| Actor | Questions and tasks | Required systems |
|---|---|---|
| Member | claim status, EOB explanation, missing documents, appeal steps | member/claim scope, EOB, official guidance |
| Provider | submission channel, authorization requirements, missing evidence | provider identity, claim/UM systems, code services |
| Adjuster | consolidated claim timeline, policy evidence, discrepancy list | claims, eligibility, provider, benefits, documents |
| Clinical reviewer | clinical packet completeness and cited policy criteria | UM queue, clinical documents, medical policies |
| Appeals reviewer | original determination, new evidence, deadlines, record packet | claims/UM, correspondence, official appeal rules |
| Compliance | audit trail, access history, overrides, model and source versions | immutable logs, IAM, model registry, case systems |

## Data plane

Use the correct store for each type of information:

```text
Relational/system of record
  claim IDs, codes, dates, amounts, status, eligibility, authorization

Object/document store
  original EOBs, forms, receipts, letters, clinical attachments

Vector + keyword indexes
  approved public guidance, plan clauses, medical policies, narratives

Immutable audit/event store
  access, retrieval, recommendations, reviewer actions, overrides
```

Do not treat a vector database as the claim system of record. Exact identifiers,
dates, codes, and dollar amounts should be retrieved deterministically.

## Retrieval strategy

1. Authenticate the actor and compute resource scope.
2. Classify the request without exposing unrelated case data.
3. Apply member/claim/plan-year filters before private retrieval.
4. Retrieve exact structured facts.
5. Run hybrid keyword and vector search over approved documents.
6. Rerank by relevance, authority, plan match, and effective date.
7. Reject conflicting, expired, or insufficient evidence.
8. Generate a cited draft and route high-impact work to a human.

Important metadata:

```text
program: FEHB | PSHB
plan_option
plan_year
document_type
effective_from / effective_to
section / page
claim_id (private indexes only)
member_scope (private indexes only)
source_authority
content_hash
ingested_at
```

## Agent roles

The production system can expose the following agents as constrained workflows:

### Intake agent

- classify incoming document;
- extract fields with confidence;
- check completeness;
- route unreadable or inconsistent documents to operations.

### Claims reference agent

- retrieve an authorized claim timeline;
- explain administrative status and reason codes using approved references;
- identify missing information;
- never change claim status or decide coverage.

### Prior-authorization support agent

- identify the correct portal and document checklist;
- assemble a review packet;
- detect missing clinical evidence;
- route the packet to a nurse or physician reviewer.

### Appeals support agent

- assemble claim, determination, correspondence, and new evidence;
- calculate candidate deadlines using authoritative rules, then require review;
- identify the exact plan provisions cited by each side;
- draft, but never issue, outcome correspondence.

### Compliance agent

- inspect audit completeness and access anomalies;
- report expired sources and missing citations;
- measure reviewer overrides and model failure patterns;
- never infer fraud from model output alone.

## Mandatory control points

- Policy/plan-year mismatch stops generation.
- No private retrieval before resource authorization.
- Retrieved documents are untrusted data, not executable instructions.
- Evidence must include a resolvable citation and content version.
- Coverage, payment, fraud, medical-necessity, and adverse decisions require a
  qualified reviewer.
- Reviewer identity, evidence, decision, and override rationale are audited.
- Low-confidence extraction or conflicting evidence routes to manual review.
- No model is allowed direct write credentials to a system of record.

## Evaluation plan

Build a de-identified or synthetic golden set with:

- exact claim-status answers;
- plan/year disambiguation;
- citation precision and citation entailment;
- missing-document detection;
- authorization and appeal routing;
- refusal when evidence is absent;
- cross-member isolation attacks;
- prompt injection embedded in uploaded documents;
- stale-policy and conflicting-policy tests;
- code/date/amount fidelity;
- reviewer acceptance and override rates.

Gate deployment on both retrieval and end-to-end results. Aggregate answer
quality is insufficient if even one test exposes another member's records.

## Validation finding in the existing synthetic fixtures

The reference system performs deterministic chronology and amount checks before
presenting a claim summary. A scan of the parent project's 20 synthetic claims
found 18 with at least one chronology issue:

- 7 have a received date before the submitted date;
- 14 have a submitted date before the service date;
- 11 have a received date before the service date.

These fixtures were intentionally left unchanged so the agent can demonstrate
data-quality escalation. They should be regenerated with constrained date
ordering before they are used as a golden evaluation dataset.
