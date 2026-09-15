# Functional Specification — Payment Integrity / Fraud, Waste & Abuse (Flow 6)

**Plan:** GEHA (Government Employees Health Association) — FEHB / PSHB
**Directory:** `06_payment_integrity/`
**Related doc:** `../otherprocesses.md` (Flow 6), `../process.md`

> This flow protects the money paid out by adjudication. It detects and corrects
> **improper payments** — fraud, waste, abuse, and billing error — both before
> payment (pre-payment review) and after (post-payment recovery).

---

## 1. Purpose

Minimize improper payments and claims leakage by screening claims for red flags
before they're paid and auditing/recovering after payment.

Definitions:
- **Fraud** — intentional misrepresentation to gain a benefit (e.g. billing for
  services not provided, falsified diagnoses, duplicate billing).
- **Waste** — unnecessary consumption of health-care resources.
- **Abuse** — unsound/improper billing practice that may not be intentional
  (e.g. upcoding, unbundling, excessive services).
- **Error** — unintentional billing mistakes.

## 2. Stakeholders & inputs

| Actor | Role | Input |
|-------|------|-------|
| **Providers** | Billers | Claims (CPT, ICD-10, charges) — sometimes with errors/abuse |
| **Payment-integrity / SIU team** | Analysts | Rules, analytics, investigation |
| **Pre-payment review systems** | Automator | Screen claims before adjudication pays |
| **False Claims Act / regulators** | Oversight | Legal accountability for dishonest claims |

## 3. Key business facts (from industry sources)

- **~3% of healthcare spend** (~$300B/yr nationally) is lost to fraud/waste.
- **Pre-payment review** uses rules + analytics to catch: illogical
  procedure/diagnosis pairings, duplicate billing, upcoding/downcoding,
  unbundling, non-covered services.
- **Post-payment controls** detect residual errors for **recovery** and feed
  findings back ("shifted left") into pre-pay prevention.
- Closed loop with **SIU/FWA, UM, benefits, and contracting** teams.

## 4. High-level tasks & features (to simulate)

### Stage 1 — Pre-Payment Screening
- **Feature 1.1 — Rules engine:** screen each claim for red flags: duplicate
  billing, illogical dx/procedure pairing, upcoding, unbundling, non-covered
  service.
- **Feature 1.2 — Risk score:** assign a risk score; low = auto-pass, high =
  hold for review.
- **Feature 1.3 — Auto-adjudicate vs. hold:** clean claims pass; flagged claims
  are held before payment.

### Stage 2 — Investigation
- **Feature 2.1 — Case review:** SIU reviews flagged claims against the medical
  record and coding rules.
- **Feature 2.2 — Classification:** classify as `CLEAN`, `ERROR`, `ABUSE`,
  `FRAUD` (or `OVERPAYMENT`).

### Stage 3 — Correction & Recovery
- **Feature 3.1 — Pre-payment correction:** adjust/deny improper charges before
  payment.
- **Feature 3.2 — Post-payment recovery:** identify overpayments already made and
  initiate recoupment.

### Stage 4 — Reporting & Feedback
- **Feature 4.1 — Reporting:** track improper-payment metrics.
- **Feature 4.2 — Feedback loop:** feed findings to policy/UM/contracting to
  "shift left" prevention.

### Stage 5 — Status & Outputs
- **Feature 5.1 — Claim integrity states:** `CLEAN`, `HELD_FOR_REVIEW`,
  `ADJUSTED`, `OVERPAYMENT_RECOVERED`, `FRAUD_REFERRED`.
- **Feature 5.2 — Audit trail** for compliance (Flow 9) and legal.

## 5. Simulation output

`simulate_payment_integrity.py` screens a batch of claims (reusing the fabricated
claims/audit trails) for red flags and produces:

- A **screening log** (`screening_log.json`): risk score, flags, decision.
- An **integrity event trail** (`integrity_events.json`).
- A **summary** of clean / held / adjusted / recovered / fraud-referred.

## 6. Dependencies & hand-offs

- **Consumes claims** from adjudication (`../claims/claims.json`).
- **Feeds payment corrections** back into adjudication/payment.
- **Feeds compliance** (Flow 9) and legal/FCA referrals.

## 7. Sample data

Reuse the fabricated claims. Inject a few seeded red flags (duplicate billing,
upcoded charges, illogical dx pairing) for a realistic mix. All data synthetic.

## 8. Disclaimer

Simulation for education/demo. FWA rules are simplified/fabricated. No real
claim or fraud data is involved.
