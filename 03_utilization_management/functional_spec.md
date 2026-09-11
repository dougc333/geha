# Functional Specification — Utilization Management (Flow 3)

**Plan:** GEHA (Government Employees Health Association) — FEHB / PSHB
**Directory:** `03_utilization_management/`
**Related doc:** `../otherprocesses.md` (Flow 3), `../process.md`

> Utilization Management (UM) decides, **before, during, and after** care,
> whether a service is medically necessary and covered. It is the clinical gate
> that precedes (and gates) claims adjudication. GEHA requires **prior
> authorization** for many services and routes UM reviews through partners like
> **EviCore (Evernorth)**.

---

## 1. Purpose

Determine, at the right point in the care timeline, whether a requested or
rendered service is **medically necessary** and within the member's **coverage**,
so that payment can be approved (or not) downstream.

The three UM timing modes:

| Mode | When | What it decides |
|------|------|-----------------|
| **Prior authorization (pre-auth)** | Before service | Approve/deny a planned procedure, test, or Rx |
| **Concurrent review** | During an admission | Approve/deny continued inpatient stay, level of care |
| **Retrospective review** | After care + bill | Confirm the billed care/codes met necessity & coverage |

## 2. Stakeholders & inputs

| Actor | Role | Input |
|-------|------|-------|
| **Provider** | Requester | Procedure/diagnosis codes, clinical documentation, treatment type, length of request |
| **EviCore / Evernorth** | UM partner | Evidence-based clinical criteria, reviews |
| **GEHA medical policy** | Rules | Coverage criteria, code-based & conditional requirements |
| **UM nurse / physician advisor** | Reviewer | Case review for non-automated decisions |

## 3. Key business facts (from GEHA resources)

- GEHA **requires prior authorization before some services** are performed.
- Providers use an online **Prior Authorization Requirement Search & Submission
  Tool** to check whether PA is required for a member + service + date.
- Requirement search returns one of:
  - **Prior authorization required**
  - **Medical necessity / pre-determination** (recommended)
  - **No requirements for the procedure code**
  - **No coverage** for the service (the "conditional" combo: PA + no coverage
    ⇒ not covered)
- UM reviews (e.g. imaging, ABA therapy, sleep studies) route through
  **EviCore by Evernorth** using nationally accepted evidence-based guidelines.
- Coverage criteria are documented per plan (Standard/High); the member ID card
  lists prior-auth contact info.

## 4. High-level tasks & features (to simulate)

### Stage 1 — Requirement Determination
- **Feature 1.1 — Requirement search:** given member, procedure code (CPT),
  diagnosis, provider, and date, look up whether PA / medical-necessity review
  is required.
- **Feature 1.2 — Coverage check:** determine if the service is covered at all
  under the member's plan; a "no coverage" result short-circuits to denial.

### Stage 2 — Authorization Request
- **Feature 2.1 — Request intake:** capture procedure codes, diagnosis codes,
  clinical documentation, length of request, treatment type.
- **Feature 2.2 — Request status:** `DRAFT` → `SUBMITTED` → `UNDER_REVIEW` →
  `APPROVED` / `DENIED` / `PARTIAL`.

### Stage 3 — Clinical Review (auto + manual)
- **Feature 3.1 — Auto-approve:** services that meet published criteria with no
  flags auto-approve.
- **Feature 3.2 — Flag to manual review:** complex/high-cost services route to a
  nurse/physician advisor (the `PENDING_REVIEW` of UM).
- **Feature 3.3 — Medical necessity determination:** apply evidence-based
  criteria; approve/deny.

### Stage 4 — Concurrent / Retrospective Review
- **Feature 4.1 — Concurrent review:** for an admitted member, re-assess
  continued stay against criteria; approve/deny additional days.
- **Feature 4.2 — Retrospective review:** after billing, verify codes + medical
  necessity; flag to claims adjustment if needed.

### Stage 5 — Decision & Outputs
- **Feature 5.1 — UM decision states:** `APPROVED`, `DENIED`,
  `PARTIAL_APPROVAL`, `PENDING_REVIEW`, `NOT_COVERED`.
- **Feature 5.2 — Authorization number** issued on approval (feeds Box 23 of
  the CMS-1500 / prior-auth field in adjudication).
- **Feature 5.3 — Audit trail** for appeals (Flow 5) and compliance (Flow 9).

## 5. Simulation output

`simulate_utilization.py` processes a batch of authorization requests through
requirement → review → decision and produces:

- An **authorization log** (`authorizations.json`) with decisions + auth numbers.
- A **UM event trail** (`um_events.json`).
- A **summary** of approval/denial/pending outcomes.

## 6. Dependencies & hand-offs

- **Feeds claims adjudication:** an approved prior auth (Box 23) prevents denial;
  a denied PA or "no coverage" blocks payment.
- **Feeds appeals** (Flow 5): UM denials are the most appealed decisions.
- **Feeds care management** (Flow 7): high-risk cases identified in review.

## 7. Sample data

Reuse the fabricated CPT codes from `../claims/claims.json` that require auth
(e.g. `95782` sleep study, `74178` CT abdomen/pelvis, `91034` esophageal pH,
`76830` transvaginal US) and the fabricated member IDs. All clinical data is
synthetic.

## 8. Disclaimer

Simulation for education/demo. The criteria and review logic are simplified and
fabricated; real GEHA UM uses proprietary medical policy and EviCore clinical
criteria. No real clinical data is involved.
