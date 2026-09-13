# GEHA Medical Claims Data Flow — Simulation

## What this directory does

DO NOT DELETE needed for langgraph demo

This is a **synthetic insurance-claim processing demo**. Despite “agentic” in the name, its processing engine is a rule-based Python state machine, not an LLM agent. It applies hardcoded rules to fabricated claims; payments, denials, and manual-review actions are simulated, not sent to real systems. Its rules and amounts must not be treated as actual GEHA coverage policy.

| File | What it does |
| --- | --- |
| `generate_claims.py` | Creates 20 fabricated claims as JSON and CSV. |
| `simulate_flow.py` | Applies hardcoded intake, eligibility, coding, review, and payment rules; writes per-claim audit trails. |
| `render_forms.py` | Creates claim-form PNG images. |
| `forms/codes/ocr_forms.py` | Uses Tesseract to extract text and structured fields from those images and flag discrepancies against the synthetic reference records. |
| `process.md` | Explains the simulated workflow. |

### Relationship to `agentic_reference`

`agentic_simulation` generates and processes fake claims. The separate sibling project, [`agentic_reference`](../agentic_reference/README.md), provides administrative guidance and synthetic claim lookup with reference citations and human-review flags. Neither is a production claims adjudication system.

An agentic simulation of a medical-claims data flow for **GEHA** (Government
Employees Health Association), a health plan for US federal employees under the
FEHB and PSHB programs.

It produces:
- **20 sample insurance claims** (structured + CSV),
- a **process document** explaining the adjudication workflow,
- an **agentic adjudication engine** that pushes each claim through the
  pipeline and emits an audit trail,
- **CMS-1500 claim-form images** (PNG) for all 20 claims, stamped with their
  simulated adjudication status.

> ⚠️ **Simulation only.** All members, providers, diagnoses, NPIs, and amounts
> are fabricated. No real patient data is involved.

## Contents

| File / dir | Purpose |
|------------|---------|
| `process.md` | The claims workflow & CMS-1500 field reference |
| `generate_claims.py` | Builds `claims/claims.json` + `claims/claims.csv` |
| `simulate_flow.py` | Adjudication state machine → `claims/audit_trails.json` |
| `render_forms.py` | Draws CMS-1500 PNG forms into `forms/` |
| `claims/` | `claims.json`, `claims.csv`, `audit_trails.json` |
| `forms/` | `CLM-100000.png` … `CLM-100019.png` (20 rendered claim forms) |

## Run everything

```bash
python generate_claims.py   # rebuild the 20 claims
python simulate_flow.py     # run the adjudication pipeline
python render_forms.py      # render the 20 CMS-1500 form images
```

## The simulated pipeline

```
SUBMIT → RECEIVE → INTAKE/EDIT → ELIGIBILITY → CODING/VALIDATION
       → [MANUAL REVIEW] → ADJUDICATION → PAY (ERA + EOB)
```

Outcomes (this seed): **PAID 10 · PENDING_REVIEW 5 · PARTIAL 2 · DENIED 3**.

## Requirements

- Python 3.9+
- `Pillow` (for form rendering)
