# Functional Specification — Compliance & Regulatory (Flow 9)

**Plan:** GEHA (Government Employees Health Association) — FEHB / PSHB
**Directory:** `09_compliance/`
**Related doc:** `../otherprocesses.md` (Flow 9), all other flows

> Compliance & Regulatory is the **overlay** that all other flows must satisfy.
> For an FEHB carrier like GEHA, it means meeting **OPM** requirements,
> maintaining **accreditation** (NCQA / URAC / AAAHC), protecting **privacy**
> (HIPAA), and producing required **reports and audit** evidence.

---

## 1. Purpose

Ensure the plan operates lawfully and meets program and quality standards:
- Report required data to **OPM** and permit audits/examinations.
- Maintain **accreditation** (NCQA HEDIS/CAHPS, URAC, AAAHC).
- Protect **member privacy** under **HIPAA**.
- Produce regulated **reports** (appeal timelines, grievance compliance,
  network adequacy, etc.).

## 2. Stakeholders & inputs

| Actor | Role | Input |
|-------|------|-------|
| **OPM** | Program regulator | Requires reporting, permits audits/examinations |
| **Accreditors (NCQA/URAC/AAAHC)** | Quality oversight | Standards for credentialing, UM, network, member rights |
| **HHS / regulators** | Privacy/oversight | HIPAA privacy & security rules |
| **All internal flows** | Data source | Claims, UM, appeals, credentialing, grievance data |

## 3. Key business facts (from OPM / NCQA / URAC)

- **OPM** "requires Carriers to report necessary information and permit audits
  and examinations to manage the FEHB Program effectively."
- **Accreditation organizations** (NCQA, URAC, AAAHC) accredit FEHB health plans;
  accreditation status appears on the brochure cover. NCQA uses **HEDIS** and
  **CAHPS** measures.
- NCQA standards cover: Quality Management & Improvement, Population Health
  Management, Credentialing/Recredentialing, Members' Rights & Responsibilities,
  Member Connections, Network Adequacy.
- **URAC** emphasizes operational compliance: utilization management, network
  adequacy, delegation.
- **HIPAA** governs member privacy/security; breach and access-rights handling.

## 4. High-level tasks & features (to simulate)

### Stage 1 — Regulatory Reporting
- **Feature 1.1 — OPM reporting:** compile required carrier data (membership,
  claims, premium, quality metrics) for OPM.
- **Feature 1.2 — Regulator submissions:** prepare required filings on schedule.

### Stage 2 — Accreditation Monitoring
- **Feature 2.1 — Standard tracking:** track compliance against accreditation
  standards (credentialing, UM, network adequacy, member rights).
- **Feature 2.2 — HEDIS/CAHPS measures:** compile quality/consumer-experience
  measures.

### Stage 3 — Privacy & Security (HIPAA)
- **Feature 3.1 — Privacy monitoring:** log access to protected health info (PHI).
- **Feature 3.2 — Breach handling:** detect/report breaches per HIPAA rules.

### Stage 4 — Audit & Internal Controls
- **Feature 4.1 — Audit evidence:** assemble audit trails from all flows.
- **Feature 4.2 — Compliance findings:** flag non-compliance; track remediation.

### Stage 5 — Status & Outputs
- **Feature 5.1 — Compliance states:** `COMPLIANT`, `FLAGGED`, `REMEDIATION`,
  `BREACH_REPORTED`, `AUDIT_READY`.
- **Feature 5.2 — Audit log** of compliance activities.

## 5. Simulation output

`simulate_compliance.py` reviews compliance across the other flows and produces:

- A **compliance register** (`compliance_register.json`): area, status, findings.
- A **compliance event trail** (`compliance_events.json`).
- A **summary** of compliant / flagged / remediation items.

## 6. Dependencies & hand-offs

- **Reads evidence from all other flows** (audit trails, appeals, credentialing,
  privacy).
- **Feeds back** remediation requirements to the relevant flows.

## 7. Sample data

Reuse the fabricated audit trails and event logs from the other 8 flows. All
data is synthetic.

## 8. Disclaimer

Simulation for education/demo. Compliance rules follow OPM/HIPAA/accreditation
principles but are simplified and fabricated. No real compliance or PHI data is
involved.
