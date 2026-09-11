# Functional Specification — Care & Case Management (Flow 7)

**Plan:** GEHA (Government Employees Health Association) — FEHB / PSHB
**Directory:** `07_care_case_management/`
**Related doc:** `../otherprocesses.md` (Flow 7), `03_utilization_management/`

> Beyond paying claims, a plan actively manages the health of high-risk and
> chronic-condition members to improve outcomes and control cost. This flow
> identifies eligible members and enrolls them in **care / case / disease
> management** programs run by nurse care managers and health coaches.

---

## 1. Purpose

Proactively support members with chronic conditions or high-risk situations,
coordinating care and education to improve health outcomes and reduce avoidable
cost.

## 2. Stakeholders & inputs

| Actor | Role | Input |
|-------|------|-------|
| **Member** | Participant | Health status, willingness to enroll |
| **Nurse case manager / health coach** | Coordinator | Care planning, education, outreach |
| **Clinical programs** (GEHA) | Program owner | Program criteria, materials |
| **UM / claims data** | Trigger source | Claims, auth, risk data to identify candidates |

## 3. Key business facts (from GEHA)

- GEHA offers multiple **clinical programs** (heart disease, diabetes,
  high-risk pregnancy, transplants, durable medical equipment, etc.).
- **Nurse case managers** may contact eligible members to coordinate care and
  education.
- Members can call **1-866-609-4143** (M–F 8am–8pm ET) for clinical program
  assistance.
- Programs include disease management, medical case management for high-risk
  members, maternity program, family-planning care, and weight management.

## 4. High-level tasks & features (to simulate)

### Stage 1 — Identification & Eligibility
- **Feature 1.1 — Candidate identification:** use claims/risk data to flag
  members with chronic conditions or high-risk profiles (e.g. diabetes, heart
  disease, high-risk pregnancy, high-cost utilizers).
- **Feature 1.2 — Program eligibility:** match candidate to a program
  (disease mgmt / case mgmt / maternity / etc.) and confirm eligibility.

### Stage 2 — Enrollment & Intake
- **Feature 2.1 — Outreach:** a nurse case manager contacts the member; member
  enrolls or declines.
- **Feature 2.2 — Risk assessment:** assess severity/risk level
  (LOW / MEDIUM / HIGH).

### Stage 3 — Care Planning
- **Feature 3.1 — Care plan:** build a member-specific plan (education, follow-up
  schedule, goals, provider coordination).
- **Feature 3.2 — Coordination:** coordinate with providers, UM, and other
  programs.

### Stage 4 — Monitoring & Reassessment
- **Feature 4.1 — Follow-up tracking:** scheduled check-ins, adherence to plan.
- **Feature 4.2 — Reassessment:** periodically re-score risk; escalate or
  graduate the member.

### Stage 5 — Status & Outputs
- **Feature 5.1 — Case states:** `IDENTIFIED`, `ENROLLED`, `ACTIVE_PLAN`,
  `MONITORING`, `COMPLETED` / `GRADUATED`, `DECLINED`.
- **Feature 5.2 — Audit trail** for outcomes reporting and compliance.

## 5. Simulation output

`simulate_care_management.py` processes a batch of candidate members through
identification → enrollment → care plan → monitoring and produces:

- A **case roster** (`care_cases.json`): member, program, risk level, status.
- A **care event trail** (`care_events.json`).
- A **summary** of enrolled / monitoring / declined / graduated cases.

## 6. Dependencies & hand-offs

- **Consumes claims/risk data** from adjudication (Flow 0) and UM (Flow 3).
- **Coordinates with UM** (Flow 3) and member services (Flow 8).
- **Feeds compliance** (Flow 9) for outcomes reporting.

## 7. Sample data

Reuse the fabricated members/diagnoses (e.g. diabetes `E11.9`, hypertension `I10`,
asthma `J45.909`, sleep apnea `G47.33`). All clinical data is synthetic.

## 8. Disclaimer

Simulation for education/demo. Care-management logic is simplified/fabricated.
No real member or clinical data is involved.
