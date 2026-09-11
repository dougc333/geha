# GEHA Medical Claims Processing — Process & Workflow

> A simulation of the medical claims data flow for **GEHA (Government Employees Health Association)**, a not-for-profit provider of health plans to federal employees and annuitants under the **Federal Employees Health Benefits (FEHB)** and **Postal Service Health Benefits (PSHB)** programs.

This document describes how a medical claim moves from a provider's billing system, into GEHA's adjudication pipeline, and out the other side as a payment + Explanation of Benefits (EOB). The companion files in this repo simulate that flow with **20 sample claims** rendered as CMS-1500 forms.

---

## 1. What GEHA is and who it serves

- **GEHA** — Government Employees Health Association. One of the largest FEHB carriers.
- Members are **federal employees, retirees, and their families**, plus Postal Service employees/annuitants (PSHB).
- Plans in the simulation: *GEHA Elevate Plus (HDHP), GEHA Elevate (HDHP), GEHA Standard, GEHA High, GEHA Medical Benefit (PSHB)*.

## 2. How a claim enters GEHA

There are two main submission paths:

| Path | Who submits | Mechanism | When |
|------|-------------|-----------|------|
| **In-network** | The provider | Electronic (EDI 837) via clearinghouse | Provider files automatically — member does nothing |
| **Out-of-network** | Provider **or** member | EDI 39026, or paper CMS-1500 mailed in | Member must use a **Member Claim Submission Form** if provider won't file |

Key addresses / identifiers:
- **Electronic claims:** submit to **EDI 39026** (GEHA's payer ID).
- **Paper medical claims (mail):** `GEHA Medical Claims, P.O. Box 21172, Eagan, MN 55121`.
- **Dental (mail):** `GEHA Dental Claims, P.O. Box 21191, Eagan, MN 55121`.
- **Medicare primary:** GEHA participates in CMS's **Coordination of Benefits Agreement (COBA)** — Medicare primary benefits arrive electronically from the COBC.

The standard form for professional/outpatient services is the **CMS-1500 (HCFA-1500)**; facility/inpatient services use the **UB-04**.

### The CMS-1500 form (what the simulation renders)

The CMS-1500 is a 33-box claim form approved by the National Uniform Claim Committee (NUCC). Every box carries a specific data element the adjudication engine depends on:

**Patient & insured (Boxes 1–13)**
| Box | Field |
|-----|-------|
| 1 | Plan type (Medicare, Medicaid, Tricare, CHAMPVA, Group, FECA, Other) |
| 1a | Insured's ID number |
| 2 | Patient's name (Last, First, MI) |
| 3 | Patient's birth date, sex |
| 4 | Insured's name |
| 5 | Patient's address |
| 6 | Patient relationship to insured |
| 7 | Insured's address |
| 9 | Other insured's name (COB) |
| 10 | Condition related to employment/auto/other accident (a–c) |
| 11 | Insured's policy, group, or FECA number |
| 12/13 | Patient / insured signature |

**Condition & diagnosis (Boxes 14–23)**
| Box | Field |
|-----|-------|
| 14 | Date of current illness/injury/pregnancy |
| 15 | Other date |
| 17 | Referring provider |
| 21 | Diagnosis or nature of illness (**ICD-10-CM code**, e.g. `J06.9`) |
| 22 | Resubmission code / original ref no. |
| 23 | Prior authorization number |

**Service lines (Box 24, rows A–J)**
| Column | Field |
|--------|-------|
| 24A | Date(s) of service — from/to |
| 24B | Place of service (`11` office, `21` inpatient, `22` outpatient, `23` ED) |
| 24D | **CPT / HCPCS procedure code** (e.g. `99213`, `90670`) |
| 24E | Modifier |
| 24F | Diagnosis pointer (links to Box 21 codes, e.g. `A`) |
| 24G | **$ Charges** |
| 24H | Days/units |
| 24J | Rendering provider NPI |

**Billing & payment (Boxes 25–33)**
| Box | Field |
|-----|-------|
| 25 | Federal Tax ID |
| 27 | Accept assignment? |
| 28 | **Total charge** |
| 29 | Amount paid |
| 31 | Physician/supplier signature |
| 32 | Service facility location |
| 33 | Billing provider info & phone |
| 33a | Billing provider NPI |

---

## 3. The adjudication pipeline (simulated)

Once GEHA receives a claim, it passes through a series of automated and human checkpoints. The simulation implements this as an **agentic state machine** — each stage is a step the claim flows through, with rule-based logic deciding the outcome.

```
 SUBMIT ──▶ RECEIVE ──▶ INTAKE/EDIT ──▶ ELIGIBILITY ──▶ CODING/VALIDATION
                                                          │
                                                          ▼
                                             MEDICAL NECESSITY / MANUAL REVIEW
                                                          │
                                                          ▼
                                             ADJUDICATION ──▶ PAY (ERA + EOB)
                                                          │
                                          ┌───────────────┼───────────────┐
                                          ▼               ▼               ▼
                                       PAID           PARTIAL        DENIED
                                          │               │               │
                                          └───────────────┼───────────────┘
                                                          ▼
                                              EOB to member / ERA to provider
```

### Stage 1 — Intake & edits (initial processing review)
Automatic syntax check. The engine verifies:
- Member ID format & patient name/DOB match.
- Required boxes are populated (no missing CPT, charge, diagnosis).
- Claim is **not a duplicate** of one already on file.
- Submission channel is valid (EDI 39026 / paper).

> Most simple denials happen here (missing/invalid data → returned to submitter).

### Stage 2 — Eligibility
Confirms the member is active under the plan on the date(s) of service, and benefits are in force.

### Stage 3 — Coding & validation
- **Diagnosis (Box 21)** must be a valid **ICD-10-CM** code.
- **Procedure (Box 24D)** must be a valid **CPT/HCPCS** code.
- Diagnosis pointer (24F) must reference an active Box 21 code.
- Bundled/unbundled code checks.

### Stage 4 — Medical necessity & manual review
Claims that don't auto-adjudicate (high charge, unusual code, no prior auth, or flagged by rules) route to a **manual reviewer**. In the simulation this is the `PENDING_REVIEW` state.

### Stage 5 — Adjudication & payment determination
The engine applies the member's **benefit plan** (deductible, coinsurance, network status) and renders one of:

| Determination | Meaning |
|---------------|---------|
| **PAID** | Approved in full; GEHA pays the allowed amount. |
| **PARTIAL** | Approved but only a portion is covered (e.g. deductible/coinsurance applied, or a service-line subset approved). |
| **PENDING_REVIEW** | Held for manual review; no payment yet. |
| **DENIED** | Not payable (not covered, invalid code, no auth, member ineligible). |

### Stage 6 — Outputs
- **ERA (Electronic Remittance Advice)** → sent to the provider (adjudication result + payment).
- **EOB (Explanation of Benefits)** → sent to the member (what was paid, what the member owes, remaining deductible/copay).
- **Payment** → delivered to the provider (check or EFT).

---

## 4. Sample-claim status distribution

The 20 simulated claims have the following statuses (seeded, reproducible):

| Status | Count | Example claim |
|--------|-------|---------------|
| PAID | 11 | Routine office visit, immunization |
| PENDING_REVIEW | 4 | High-cost imaging / polysomnography |
| PARTIAL | 2 | Multiple service lines, one not covered |
| DENIED | 3 | Invalid diagnosis pointer / not-covered service |

---

## 5. Repository layout

```
geha/
├── process.md                    # this file — the workflow & CMS-1500 field reference
├── generate_claims.py            # builds claims/claims.json + claims/claims.csv
├── claims/
│   ├── claims.json               # 20 structured CMS-1500 claim records
│   └── claims.csv                # flattened (one row per service line)
├── render_forms.py               # draws CMS-1500 PNG forms for all 20 claims
├── simulate_flow.py              # agentic adjudication state machine over the 20 claims
└── forms/
    └── CLM-100000.png ...        # rendered CMS-1500 form per claim
```

---

## 6. Disclaimer

This is a **simulation** for educational/demo purposes. Field names and the general workflow are based on the real CMS-1500 form and GEHA's published claims guidance, but all members, providers, diagnoses, NPIs, and amounts are **fabricated**. No real patient data is involved.
