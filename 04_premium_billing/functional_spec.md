# Functional Specification — Premium Billing & Reconciliation (Flow 4)

**Plan:** GEHA (Government Employees Health Association) — FEHB / PSHB
**Directory:** `04_premium_billing/`
**Related doc:** `../otherprocesses.md` (Flow 4), `01_membership_benefits/`

> This is the **revenue side** — collecting the money that funds claims payment.
> For FEHB, the government pays up to ~75% of premiums and the employee/annuitant
> pays the remainder, usually via **payroll or annuity withholding** (often
> pre-tax "premium conversion"). This flow bills, collects, and reconciles those
> premiums.

---

## 1. Purpose

Ensure every covered member's premium is billed, collected, and reconciled, and
that non-payment properly lapses coverage (feeding the eligibility check in
adjudication).

## 2. Stakeholders & inputs

| Actor | Role | Input |
|-------|------|-------|
| **OPM** | Program administrator | Sets govt-share weighted-average premiums; annual appropriation for annuitants |
| **Employing agency / payroll** (NFC, MyPay, etc.) | Collector | Payroll/annuity withholding of the enrollee share |
| **Member / annuitant** | Payer | The employee/annuitant share of premium |
| **GEHA billing** | Processor | Billing statements, delinquency, reconciliation |

## 3. Key business rules (from OPM / GEHA materials)

- **Government share:** OPM computes a program-wide weighted average of premiums
  and appropriates the government contribution; government pays up to **~75%**.
- **Enrollee share:** the member pays all premium above the government share,
  withheld each pay period from salary or annuity.
- **Premium conversion:** employees can pay their FEHB share **pre-tax** via a
  payroll allotment, reducing taxable income.
- **2026 rates (your share):** e.g. High Option Self Only $195.29 biweekly /
  $423.13 monthly; Standard Self Only $86.75 biweekly / $187.95 monthly.
- **Error correction:** withholding errors are corrected in a later pay period,
  retroactive to the effective date.
- **Delinquency → lapse:** unpaid premiums lead to coverage lapse (grace period
  rules), surfacing as an eligibility failure at adjudication.

## 4. High-level tasks & features (to simulate)

### Stage 1 — Premium Calculation
- **Feature 1.1 — Calculate premium:** given plan code + coverage level, compute
  the monthly/periodic premium (from the plan rate table) and the split between
  government share and enrollee share.
- **Feature 1.2 — Billing cycle:** generate a billing line for each member each
  period (biweekly for employed, monthly for annuitants).

### Stage 2 — Collection
- **Feature 2.1 — Payroll/annuity withholding:** record the enrollee share as
  withheld from salary/annuity (with premium-conversion pre-tax flag where
  applicable).
- **Feature 2.2 — Direct billing:** for members not on payroll, issue a
  statement and record payments received.

### Stage 3 — Delinquency & Grace
- **Feature 3.1 — Delinquency tracking:** apply configured grace-period rules;
  flag accounts in arrears.
- **Feature 3.2 — Coverage lapse:** after grace expires with no payment, mark
  the member `LAPSED` (feeds eligibility).

### Stage 4 — Reconciliation
- **Feature 4.1 — Payments vs. billed:** reconcile premium received against
  expected for each member/group; flag discrepancies.
- **Feature 4.2 — Error correction:** adjust for withholding errors (retroactive
  corrections).

### Stage 5 — Status & Outputs
- **Feature 5.1 — Billing states:** `CURRENT`, `PAST_DUE`, `LAPSED`, `RECONCILED`.
- **Feature 5.2 — Audit trail** for compliance (Flow 9).

## 5. Simulation output

`simulate_premium_billing.py` processes a billing cycle across the fabricated
members and produces:

- A **premium ledger** (`premium_ledger.json`): per member, premium due, govt
  share, enrollee share, amount paid, status.
- A **billing event log** (`billing_events.json`).
- A **summary** of current / past-due / lapsed accounts.

## 6. Dependencies & hand-offs

- **Consumes membership** (Flow 1): plan code + coverage level determine premium.
- **Feeds eligibility** (Flow 1 / adjudication): a lapsed member fails eligibility.
- **Feeds compliance** (Flow 9): reconciliation records.

## 7. Sample data

Reuse the fabricated members from `01_membership_benefits/members.json` and the
2026 plan rates from the GEHA brochure. All dollar figures are fabricated.

## 8. Disclaimer

Simulation for education/demo. Rates and amounts are simplified/fabricated.
No real premium or member data is involved.
