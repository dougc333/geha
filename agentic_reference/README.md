# GEHA Agentic Processing Reference

DO NOT DELETE. Needed for langgraph demo

A governed, synthetic reference implementation for agent-assisted GEHA payer
operations. It extends the existing deterministic simulations in the parent
directory with:

- public-reference retrieval with citations;
- authorized synthetic claim lookup;
- claim-submission, prior-authorization, and appeal support;
- mandatory human-review gates for high-impact decisions;
- PHI-minimized audit events;
- a dependency-free demo, optional semantic embeddings, and optional FastAPI.

This project is not affiliated with or endorsed by GEHA. It is not an actual
claims adjudicator, benefit engine, medical-necessity system, or source of plan
coverage decisions. All local member and claim data is fabricated.

## Why this architecture

Research of GEHA's public resources indicates these primary processing needs:

1. **Claim intake and status** — provider and member submission paths.
2. **Document processing** — forms, EOBs, receipts, clinical attachments.
3. **Eligibility and benefit context** — plan, option, program, and plan year.
4. **Prior authorization** — requirement lookup, evidence intake, review.
5. **Appeals and disputed claims** — initial appeal, reconsideration, OPM review.
6. **Provider operations** — code, network, and submission-channel support.
7. **Member service** — grounded explanations and next-step guidance.
8. **Compliance** — authorization, auditability, privacy, and secure transmission.

The agent is therefore a constrained orchestrator over approved tools. Exact
claim facts stay in structured repositories; public guidance is retrieved from
an allowlisted corpus; and high-impact determinations remain with qualified
reviewers.

## Run the dependency-free demo

From this directory:

```bash
PYTHONPATH=src python -m geha_reference.demo
```

Run tests:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Use semantic embeddings

The default `HashingEmbeddingProvider` is deterministic and dependency-free. It
exists for tests and architecture demonstrations; it is not a semantic model.

For local semantic retrieval:

```bash
python -m pip install -e '.[embeddings]'
```

```python
from geha_reference.bootstrap import build_agent

agent = build_agent(semantic_model="sentence-transformers/all-MiniLM-L6-v2")
```

An approved healthcare-domain embedding model should be evaluated against a
GEHA-specific retrieval benchmark before production use. Do not mix vectors
created by different embedding models in the same index.

## Optional API

```bash
python -m pip install -e '.[api]'
uvicorn 'geha_reference.api:create_app' --factory --port 8000
```

The API request accepts identity fields only so the demo is easy to inspect.
That is **not secure for production**. A real deployment must derive role,
member scope, and claim scope from verified identity-provider tokens and policy
enforcement, not from caller-controlled JSON.

## Agent/tool boundary

```text
Authenticated user
       |
       v
Intent router / safety gate
       |
       +--> public reference search ------> allowlisted policy corpus
       |
       +--> authorized claim lookup ------> structured claim repository
       |
       +--> appeal checklist -------------> official appeal references
       |
       `--> human-review queue ------------> adjuster / clinician / appeals unit
```

The reference agent may summarize, retrieve, validate completeness, and suggest
next administrative steps. It may not independently:

- approve or deny a claim;
- decide coverage or medical necessity;
- determine fraud;
- calculate or authorize payment;
- issue adverse-benefit communications;
- change a system-of-record value.

## Production adapters still required

- verified SSO/OIDC identity and centralized authorization;
- HIPAA-appropriate object, relational, and vector stores;
- document malware scanning, OCR, and layout extraction;
- benefit configuration and plan-year versioning;
- code-set and provider-directory services;
- claims/authorization/appeal system-of-record APIs;
- workflow queues, dual control, and electronic signatures;
- model gateway, prompt/version registry, evaluations, and rollback;
- immutable audit export, SIEM integration, retention, and legal hold;
- business associate agreements and completed security/privacy review.

## Official sources represented in the seed corpus

- [GEHA claims](https://www.geha.com/membership/claims)
- [GEHA forms and documents](https://www.geha.com/resource-center/forms-and-documents)
- [GEHA appeals FAQs](https://www.geha.com/legal/geha-appeal-process-and-disputed-claims-faqs)
- [GEHA authorizations](https://www.geha.com/en/resource-center/provider-resources/authorizations-precertifications)
- [OPM FEHB Carrier Letter 2025-05](https://www.opm.gov/healthcare-insurance/carriers/fehb/2025/2025-05.pdf)
- [HHS HIPAA Security Rule summary](https://www.hhs.gov/hipaa/for-professionals/security/laws-regulations/index.html)

