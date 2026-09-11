# Functional Specification — Customer / Member Services (Flow 8)

**Plan:** GEHA (Government Employees Health Association) — FEHB / PSHB
**Directory:** `08_member_services/`
**Related doc:** `../otherprocesses.md` (Flow 8), all prior flows

> The human (and digital) front line. Member Services answers inquiries about
> eligibility, benefits, claims status, cost-sharing, premium bills, ID cards,
> and authorizations — powered by a **360-degree member view** that draws on
> every other flow. This flow routes and resolves those inquiries.

---

## 1. Purpose

Resolve member and provider inquiries efficiently and accurately, using a
consolidated view of the member's record across membership, claims, UM, premium,
and care-management data.

## 2. Stakeholders & inputs

| Actor | Role | Input |
|-------|------|-------|
| **Member / provider** | Inquirer | Question (claims, benefits, eligibility, ID card, premium) |
| **Customer Care rep** | Resolver | Handles the inquiry via the 360-degree member view |
| **MyGEHA portal / live chat** | Self-service | Member-initiated resolution |
| **All upstream flows** | Data source | Membership, claims, UM, premium, care data |

## 3. Key business facts (from GEHA)

- **Customer Care:** 1-800-821-6136, **Mon–Fri 8am–8pm ET**; dental 877-434-2336.
- **MyGEHA member portal** + **live chat** for self-service.
- Inquiry categories: **Benefits, Claims, Web Account Assistance, Other**;
  provider inquiries include claim/status, eligibility (270/271), claim status
  (276/277), ID card replacement, prior auth.
- Contact form fields show the data needed to resolve: member ID, DOB, claim
  number, date of service, amount, provider name.

## 4. High-level tasks & features (to simulate)

### Stage 1 — Inquiry Intake
- **Feature 1.1 — Inquiry routing:** classify the inquiry type (BENEFITS,
  CLAIM_STATUS, ELIGIBILITY, ID_CARD, PREMIUM, PRIOR_AUTH, OTHER).
- **Feature 1.2 — Identity verification:** verify the caller via member ID +
  DOB.

### Stage 2 — Resolution (360-degree member view)
- **Feature 2.1 — Claims status lookup:** pull the claim's adjudication status
  from the claims flow (audit trails).
- **Feature 2.2 — Eligibility lookup:** pull eligibility from membership (Flow 1).
- **Feature 2.3 — Benefits lookup:** show plan cost-sharing (deductible,
  coinsurance) from plan config (Flow 1).
- **Feature 2.4 — Prior-auth status:** pull from UM (Flow 3).
- **Feature 2.5 — Premium/balance lookup:** pull from premium billing (Flow 4).

### Stage 3 — Resolution & Escalation
- **Feature 3.1 — First-call resolution:** answer directly when data is
  available.
- **Feature 3.2 — Escalation:** route complex cases to the right team (appeals →
  Flow 5, care → Flow 7, provider ops → Flow 2).

### Stage 4 — Status & Outputs
- **Feature 4.1 — Inquiry states:** `OPEN`, `RESOLVED`, `ESCALATED`,
  `RESOLVED_FIRST_CALL`.
- **Feature 4.2 — Audit trail** for service-quality reporting.

## 5. Simulation output

`simulate_member_services.py` processes a batch of member/provider inquiries and
produces:

- An **inquiry log** (`inquiries.json`): type, verification, resolution source,
  status.
- A **service event trail** (`service_events.json`).
- A **summary** of resolved-first-call / resolved / escalated / unresolved.

## 6. Dependencies & hand-offs

- **Reads all upstream flows** (membership, claims, UM, premium, care).
- **Routes to appeals** (Flow 5), **care** (Flow 7), **provider ops** (Flow 2).

## 7. Sample data

Reuse fabricated members/claims/UM results from prior flows (e.g. query a
member's claim `CLM-100005`, eligibility `G1005`, a UM auth `PA-1000`). All data
is synthetic.

## 8. Disclaimer

Simulation for education/demo. Service logic is simplified/fabricated. No real
member inquiry data is involved.
