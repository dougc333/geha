# GEHA Processing-Flow Simulations

Nine directories, one per major health-payer processing flow. Each follows the
same pattern: a `functional_spec.md` (research-backed tasks/features) plus a
deterministic `simulate_*.py` that runs a simulated flow and emits JSON logs.

| # | Directory | Flow | Simulation | Spec |
|---|-----------|------|-----------|------|
| 1 | `01_membership_benefits/` | Membership & Benefits Admin | `simulate_membership.py` | `functional_spec.md` |
| 2 | `02_provider_operations/` | Provider Operations | `simulate_providers.py` | `functional_spec.md` |
| 3 | `03_utilization_management/` | Utilization Management | `simulate_utilization.py` | `functional_spec.md` |
| 4 | `04_premium_billing/` | Premium Billing & Reconciliation | `simulate_premium_billing.py` | `functional_spec.md` |
| 5 | `05_appeals_disputes/` | Post-Adjudication & Disputes | `simulate_appeals.py` | `functional_spec.md` |
| 6 | `06_payment_integrity/` | Payment Integrity / FWA | `simulate_payment_integrity.py` | `functional_spec.md` |
| 7 | `07_care_case_management/` | Care & Case Management | `simulate_care_management.py` | `functional_spec.md` |
| 8 | `08_member_services/` | Customer / Member Services | `simulate_member_services.py` | `functional_spec.md` |
| 9 | `09_compliance/` | Compliance & Regulatory | `simulate_compliance.py` | `functional_spec.md` |

## Run everything

```bash
bash run_all_flows.sh        # or
for d in 0*/; do (cd "$d" && python simulate_*.py); done
```

## Each flow's outputs

| Flow | JSON outputs |
|------|--------------|
| 1 Membership | `members.json`, `membership_events.json` |
| 2 Provider Ops | `providers.json`, `provider_events.json` |
| 3 Utilization | `authorizations.json`, `um_events.json` |
| 4 Premium Billing | `premium_ledger.json`, `billing_events.json` |
| 5 Appeals | `appeals.json`, `appeals_events.json` |
| 6 Payment Integrity | `screening_log.json`, `integrity_events.json` |
| 7 Care Management | `care_cases.json`, `care_events.json` |
| 8 Member Services | `inquiries.json`, `service_events.json` |
| 9 Compliance | `compliance_register.json`, `compliance_events.json` |

> Several flows read upstream data: **8 (Member Services)** pulls from claims,
> membership, UM, and premium; **9 (Compliance)** checks for audit evidence from
> all other flows. Run them in dependency order (the script does).

## Method

For each flow: web research on GEHA + the processing area → `functional_spec.md`
with high-level tasks/features → deterministic `simulate_*.py` → JSON logs +
console summary. All member/provider/claim data is **fabricated**.
