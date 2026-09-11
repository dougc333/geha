# Functional Specification — Provider Operations (Flow 2)

**Plan:** GEHA (Government Employees Health Association) — FEHB / PSHB
**Directory:** `02_provider_operations/`
**Related doc:** `../otherprocesses.md` (Flow 2 overview), `../process.md`

> This flow builds and maintains the **provider network** that files claims and
> serves members. It is the mirror image of membership: where Flow 1 tracks
> "who is covered," this flow tracks "who is treating and billing." Adjudication
> depends on it for two things: (1) the **allowed amount** (from the provider
> contract) and (2) the **in-network/out-of-network** status that drives member
> cost-sharing.

---

## 1. Purpose

Manage the full lifecycle of a health-care provider in GEHA's network:

- **Recruit & enroll** providers and facilities into the network.
- **Credential / re-credential** them (verify licenses, education, malpractice,
  sanctions).
- **Contract** with them to set reimbursement (fee schedules / allowed amounts).
- **Maintain** the provider directory (accurate for members and regulators).

## 2. Stakeholders & inputs

| Actor | Role | Input |
|-------|------|-------|
| Provider / facility | Applicant | NPI, tax ID, licenses, specialties, malpractice coverage, sanctions history |
| **CAQH / ProView** (or similar) | Data source | Standardized credentialing data |
| GEHA provider relations | Processor | Validates, contracts, enrolls |
| Provider portal (`provider.mygeha.com`) | Interface | Application status, contract docs, directory updates |
| Member find-a-care tool | Consumer | Searches the provider directory |

## 3. Key business facts (from GEHA resources)

- GEHA network is **~1.7 million providers** nationwide (the "Find an In-Network
  Provider" tool).
- Providers join via the **provider portal**; required documents vary by state.
- Network nomination/onboarding can take **~60 days** (dental nomination form).
- Providers must be **credentialed** before they can bill; uncredentialed
  providers face **denied claims and compliance risk**.

## 4. High-level tasks & features (to simulate)

Each stage is deterministic and rule-based, consistent with the other flows.

### Stage 1 — Provider Enrollment
- **Feature 1.1 — Application intake:** collect NPI, tax ID, provider name,
  specialties, practice addresses, and contact.
- **Feature 1.2 — Sanctions / exclusion screening:** check the provider against
  exclusion lists (OIG, state Medicaid). A hit = reject.
- **Feature 1.3 — Application status:** `SUBMITTED` → `UNDER_REVIEW` →
  `CREDENTIALED` / `REJECTED`.

### Stage 2 — Credentialing
- **Feature 2.1 — License verification:** valid state license for the practice
  state.
- **Feature 2.2 — Education / board certification check.**
- **Feature 2.3 — Malpractice coverage:** minimum coverage in force.
- **Feature 2.4 — Work history / gaps review.**
- **Feature 2.5 — Re-credentialing cycle** (e.g. every 3 years): re-verify and
  update the credential status.

### Stage 3 — Network Contracting
- **Feature 3.1 — Contract creation:** assign a participating-provider contract
  with a **fee schedule** → this defines the **allowed amount** used in
  adjudication.
- **Feature 3.2 — Network status:** assign `IN_NETWORK` / `OUT_OF_NETWORK`.
- **Feature 3.3 — Contract terms:** PPO/participating discount rate.

### Stage 4 — Directory Management
- **Feature 4.1 — Directory entry:** add/update the provider record shown in the
  find-a-care tool.
- **Feature 4.2 — Directory accuracy checks:** flag missing/invalid addresses,
  NPI mismatches.
- **Feature 4.3 — Deactivation:** remove a provider (left network, sanctioned,
  retired).

### Stage 5 — Status & Outputs
- **Feature 5.1 — Provider states:** `CREDENTIALED_IN_NETWORK`,
  `CREDENTIALED_OUT_OF_NETWORK`, `PENDING`, `REJECTED`, `TERMINATED`.
- **Feature 5.2 — Audit trail** for compliance and dispute resolution.

## 5. Simulation output

`simulate_providers.py` will process a batch of provider applications and
produce:

- A **provider roster** (`providers.json`) with NPI, status, network status,
  fee schedule / allowed-amount factor.
- A **credentialing event log** (`provider_events.json`).
- A **summary** of outcomes (credentialed, rejected, sanctioned, terminated).

## 6. Dependencies & hand-offs

- **Feeds claims adjudication:** the allowed amount and in/out-of-network status
  used in `../simulate_flow.py`.
- **Feeds member services** (Flow 8): the find-a-care directory.
- **Feeds compliance** (Flow 9): exclusion screening and re-credentialing
  evidence.

## 7. Sample data

Reuse the fabricated provider NPIs from `../claims/claims.json` and
`../claims/claims.csv` (e.g. `1982635411`, `1674892022`, `1325478890`), plus the
facility names. All provider identities are fabricated.

## 8. Disclaimer

Simulation for education/demo. Provider, NPI, license, and contract data are
fabricated. No real provider information is involved.
