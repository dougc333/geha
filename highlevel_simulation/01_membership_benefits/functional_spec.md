# Functional Specification — Membership & Benefits Administration (Flow 1)

**Plan:** GEHA (Government Employees Health Association) — FEHB / PSHB
**Directory:** `01_membership_benefits/`
**Related doc:** `../process.md` (claims), `../otherprocesses.md` (flow overview)

> This is the **front door** of the payer. It establishes and maintains *who* is
> covered (membership) and *under what terms* (benefits/plan configuration).
> Claims adjudication reads the records this flow produces: if membership is
> wrong, the "Eligibility" stage of adjudication fails.

---

## 1. Purpose

Membership & Benefits Administration manages the full lifecycle of a member and
their coverage:

- **Enroll** new members (and their dependents) into a GEHA plan.
- **Maintain** eligibility, addresses, family/dependent structure, and coverage
  elections over time.
- **Configure** the benefit plan so that downstream claims adjudication knows
  deductibles, copays, coinsurance, coverage limits, and exclusions.
- **Produce** the member artifacts that make coverage usable: ID cards,
  QuestSelect lab cards, welcome materials, HSA account linkage.

## 2. Stakeholders & inputs

| Actor | Role | Input they provide |
|-------|------|--------------------|
| **Federal employee / annuitant** | Subscriber | SF-2809 Health Benefits Registration Form, personal data |
| **OPM** (Office of Personnel Management) | Program administrator | Enrollment authorization, eligibility confirmation, premium shares |
| **Employing agency** (e.g. DoD, DOE, VA, NFC) | Payroll | Employment/retirement status, payroll deduction start |
| **GEHA enrollment dept** | Processor | Validates, creates the member record, issues ID cards |
| **Member services** | Front line | Change requests (address, dependents, card replacement) |

## 3. Key business rules (from the 2026 FEHB brochure)

- **Eligibility:** All Federal Employees and Annuitants eligible for the FEHB
  Program may enroll. **Postal employees/annuitants are NOT eligible for the
  GEHA Benefit Plan** (except under Temporary Continuation of Coverage) — they
  use PSHB plans instead.
- **Membership:** Joining requires a signed **Standard Form 2809** (Health
  Benefits Registration Form). There are **no membership dues** for 2026.
- **Enrollment codes / options** (each a distinct benefit plan):

  | Code | Option | Coverage |
  |------|--------|----------|
  | 311 | High | Self Only |
  | 313 | High | Self Plus One |
  | 312 | High | Self and Family |
  | 314 | Standard | Self Only |
  | 316 | Standard | Self Plus One |
  | 315 | Standard | Self and Family |

  (HDHP "Elevate", "Elevate Plus", and PSHB plans have their own codes.)
- **Coverage effective date:** benefits usable as soon as coverage is effective;
  FEHB plans cover **all pre-existing conditions**; the government pays **up to
  75%** of premiums.
- **Government/employee premium split:** e.g. High Option Self Only — govt
  $703.65/mo, your share $423.13/mo (2026 rates).
- **Plan-level benefit knobs** that must be configured and enforced downstream:
  deductible, coinsurance, copays, out-of-pocket max, coverage exclusions,
  preventive-care coverage, telehealth, wellness rewards (up to $250–$500/yr),
  Medicare Part B premium reimbursement (High Option, up to $1,000/yr).

## 4. High-level tasks & features (to simulate)

The simulated flow covers the membership lifecycle in stages. Each stage is a
deterministic, rule-based step (no ML) so it is reproducible, mirroring the
style of `simulate_flow.py` in the project root.

### Stage 1 — Enrollment / Registration
- **Feature 1.1 — New subscriber enrollment:** ingest an SF-2809-equivalent
  record (name, DOB, SSN fragment, employment status, chosen plan code,
  coverage level). Validate eligibility (federal employee/annuitant; not a
  postal worker on the FEHB Benefit Plan).
- **Feature 1.2 — Dependent attachment:** add eligible dependents (spouse,
  children, over-age/disabled children) and derive coverage level
  (Self / Self Plus One / Self and Family) from the enrollment code.
- **Feature 1.3 — Plan selection & configuration snapshot:** bind the member to
  a plan code (311/313/312/314/315/316 or HDHP/PSHB), capturing the benefit
  parameters that adjudication will read later.

### Stage 2 — Eligibility & Verification
- **Feature 2.1 — Eligibility verification:** confirm the member is active on
  the plan at the date of service (the check adjudication performs). Return
  active/inactive + effective dates.
- **Feature 2.2 — COB / coordination setup:** record whether another plan
  (Medicare, Tricare, a spouse's plan) is primary/secondary so benefits
  coordinate correctly.

### Stage 3 — Maintenance / Change Management
- **Feature 3.1 — Address & contact change:** update member contact info.
- **Feature 3.2 — Dependent add/remove:** mid-year family changes.
- **Feature 3.3 — Coverage-level change:** e.g. Self → Self and Family on a
  qualifying life event or open season.
- **Feature 3.4 — Plan change:** open-season switch between High/Standard/HDHP.

### Stage 4 — ID Card & Artifact Production
- **Feature 4.1 — ID card issuance:** generate member ID (`Gxxxxxxxx`), issue a
  health plan ID card; mark the card status (active / replacement / temp).
- **Feature 4.2 — QuestSelect card:** for Standard-option members without
  Medicare.
- **Feature 4.3 — Welcome packet:** links to plan resources.

### Stage 5 — Status & Outputs
- **Feature 5.1 — Membership lifecycle states:** `ACTIVE`, `PENDING_VERIFY`,
  `LAPSED` (non-payment → feeds premium billing), `TERMINATED`, `SUSPENDED`.
- **Feature 5.2 — Audit trail:** every membership event logged with a timestamp
  and reason, for compliance (Flow 9) and dispute resolution (Flow 5).

## 5. Simulation output

The simulation (`simulate_membership.py`) will process a batch of enrollment and
maintenance events and produce:

- A **member roster** (`members.json`) with one record per subscriber + plan
  config + status.
- An **event log** (`membership_events.json`) — the audit trail.
- A **summary** of lifecycle outcomes (enrolled, verified, changed, terminated).

## 6. Dependencies & hand-offs

- **Feeds claims adjudication** (root `simulate_flow.py`): eligibility + plan
  config (deductible, coinsurance) come from here.
- **Feeds premium billing** (Flow 4): coverage level and plan code determine
  the premium to bill.
- **Feeds care management** (Flow 7): member risk flags / demographics.
- **Consumed by member services** (Flow 8): the 360-degree member record.

## 7. Sample data (for the simulation)

Reuse the fabricated members from `../claims/claims.json` (e.g. member IDs
`G1000`, `G1017`, …; plans `GEHA Elevate (HDHP)`, `GEHA Standard`, `GEHA High`,
`GEHA Medical Benefit (PSHB)`), plus a few synthetic enrollment events.

## 8. Disclaimer

Simulation for education/demo. Field names follow GEHA's published FEHB
materials, but all members, dependents, and data are fabricated. No real member
information is involved.
