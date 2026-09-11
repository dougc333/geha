# Functional Specification — Post-Adjudication & Disputes (Appeals) (Flow 5)

**Plan:** GEHA (Government Employees Health Association) — FEHB / PSHB
**Directory:** `05_appeals_disputes/`
**Related doc:** `../otherprocesses.md` (Flow 5), `../process.md`, `03_utilization_management/`

> When a member or provider disagrees with an adverse determination — a denied
> claim, a denied prior authorization, or a partial payment — they can challenge
> it. This flow manages the **appeals and grievances** process, including
> internal appeal and escalation to **external/independent review** (for FEHB,
> through **OPM**).

---

## 1. Purpose

Give members and providers a formal, regulated path to contest adverse
determinations, and ensure the plan responds within required timeframes.

## 2. Stakeholders & inputs

| Actor | Role | Input |
|-------|------|-------|
| **Member / provider** | Appellant | Appeal request, supporting documentation |
| **GEHA appeals unit** | Internal reviewer | Re-review of the original decision |
| **OPM** | External reviewer (FEHB) | Independent reconsideration of disputed claims |
| **External reviewer** | Independent body | Final decision on external review |

## 3. Key business rules (from GEHA / OPM / healthcare.gov)

- **What can be appealed:** denied claims, denied/reduced prior authorizations,
  and other adverse benefit determinations. GEHA publishes a **Post-Service
  Appeal Request Form** and an **Appeal Process & Disputed Claims FAQ**.
- **Internal appeal first:** you must generally exhaust the plan's internal
  appeal process before external review.
- **OPM external review (FEHB):** OPM reaches a decision in **~30 days** in most
  cases, after the internal process is exhausted.
- **External review (general standard):** file within **4 months** of the final
  denial notice; standard external reviews decided within **45 days**; expedited
  (urgent) within **72 hours**.

## 4. High-level tasks & features (to simulate)

### Stage 1 — Appeal Intake
- **Feature 1.1 — Appeal filing:** accept a disputed claim/authorization, capture
  the underlying decision, the appellant's basis, and supporting documents.
- **Feature 1.2 — Filing-deadline check:** reject appeals filed too late (after
  the appeal window).

### Stage 2 — Internal Review
- **Feature 2.1 — Re-review:** re-evaluate the original determination against the
  benefit plan and any new documentation.
- **Feature 2.2 — Decision:** `UPHELD` (original decision stands) or `OVERTURNED`
  (decision reversed in appellant's favor).

### Stage 3 — Escalation to External Review
- **Feature 3.1 — External review request:** if the internal appeal is upheld and
  the appellant escalates, route to **OPM / external reviewer**.
- **Feature 3.2 — External decision:** the external body upholds or overturns;
  the plan must accept the external decision.

### Stage 4 — Grievances (non-claim)
- **Feature 4.1 — Grievance intake:** member/provider complaints about service,
  access, or quality (not tied to a specific claim payment).

### Stage 5 — Status & Outputs
- **Feature 5.1 — Appeal states:** `FILED`, `UNDER_INTERNAL_REVIEW`, `UPHELD`,
  `OVERTURNED`, `ESCALATED`, `EXTERNAL_DECISION`.
- **Feature 5.2 — Overturned cases** feed a **claim adjustment/refund** back into
  adjudication/payment.
- **Feature 5.3 — Audit trail** for compliance (Flow 9).

## 5. Simulation output

`simulate_appeals.py` processes a batch of disputed determinations (reusing the
DENIED / PENDING / PARTIAL outcomes from the claims and UM simulations) and
produces:

- An **appeals log** (`appeals.json`): outcome per appeal.
- A **dispute event trail** (`appeals_events.json`).
- A **summary** of upheld / overturned / escalated outcomes.

## 6. Dependencies & hand-offs

- **Consumes adverse determinations** from claims adjudication (`../claims/
  audit_trails.json`) and UM (`03_utilization_management/authorizations.json`).
- **Feeds payment correction:** overturned appeals trigger claim adjustment.
- **Feeds compliance** (Flow 9): appeal timelines and outcomes are regulated.

## 7. Sample data

Reuse the fabricated denied/pending claims (e.g. `CLM-100005` DENIED dental,
`CLM-100002` PARTIAL) and UM denials from prior flows. All data is synthetic.

## 8. Disclaimer

Simulation for education/demo. Appeal rules follow published FEHB/GEHA/OPM
processes but are simplified and fabricated. No real dispute data is involved.
