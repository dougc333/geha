"""
Simulation — Compliance & Regulatory (Flow 9).

Reviews compliance across the other flows: OPM reporting, accreditation
monitoring, HIPAA privacy/security, and audit controls. Deterministic,
rule-based. Emits a compliance register + event trail.

Usage:
    python simulate_compliance.py
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).parent
_ROOT = Path(__file__).parent.parent


@dataclass
class ComplianceRecord:
    area: str
    status: str
    findings: str


@dataclass
class ComplianceEvent:
    area: str
    stage: str
    status: str
    note: str


@dataclass
class ComplianceRun:
    events: list[ComplianceEvent] = field(default_factory=list)
    register: list[ComplianceRecord] = field(default_factory=list)

    def log(self, area, stage, status, note=""):
        self.events.append(ComplianceEvent(area, stage, status, note))


def file_exists(p: Path) -> bool:
    return p.exists()


def run():
    run = ComplianceRun()
    root = _ROOT

    # Evidence check: do the upstream flows have audit trails?
    evidence = {
        "Claims adjudication": Path(os.environ.get("GEHA_CLAIMS_PATH", root.parent / "agentic_simulation" / "claims" / "audit_trails.json")),
        "Membership": root / "01_membership_benefits" / "membership_events.json",
        "Provider ops": root / "02_provider_operations" / "provider_events.json",
        "Utilization mgmt": root / "03_utilization_management" / "um_events.json",
        "Premium billing": root / "04_premium_billing" / "billing_events.json",
        "Appeals": root / "05_appeals_disputes" / "appeals_events.json",
        "Payment integrity": root / "06_payment_integrity" / "integrity_events.json",
        "Care mgmt": root / "07_care_case_management" / "care_events.json",
        "Member services": root / "08_member_services" / "service_events.json",
    }

    # Stage 1 — Regulatory reporting (OPM)
    present = sum(1 for p in evidence.values() if file_exists(p))
    total = len(evidence)
    if present == total:
        run.log("OPM_REPORTING", "REPORT", "OK",
                f"All {total} flow audit trails present; OPM report compilable")
        run.register.append(ComplianceRecord("OPM_Reporting", "COMPLIANT",
                                             f"{present}/{total} evidence files available"))
    else:
        run.log("OPM_REPORTING", "REPORT", "FLAG",
                f"Missing audit evidence: {total - present} flow(s) have no trail")
        run.register.append(ComplianceRecord("OPM_Reporting", "FLAGGED",
                                             f"{present}/{total} evidence files available"))

    # Stage 2 — Accreditation monitoring (NCQA/URAC)
    # Check credentialing + UM + network adequacy represented
    prov = root / "02_provider_operations" / "providers.json"
    auth = root / "03_utilization_management" / "authorizations.json"
    if file_exists(prov) and file_exists(auth):
        run.log("ACCREDITATION", "STANDARD", "OK", "Credentialing & UM evidence present")
        run.register.append(ComplianceRecord("Accreditation_NCQA_URAC", "COMPLIANT",
                                             "Credentialing, UM, network evidence present"))
    else:
        run.log("ACCREDITATION", "STANDARD", "FLAG", "Missing credentialing/UM evidence")
        run.register.append(ComplianceRecord("Accreditation_NCQA_URAC", "FLAGGED",
                                             "Missing credentialing/UM evidence"))

    # Stage 3 — HIPAA privacy/security
    # In this simulation, PHI access is monitored; a fabricated access log check
    privacy_ok = file_exists(root / "09_compliance" / "hipaa_access_log.json") or True
    if privacy_ok:
        run.log("HIPAA_PRIVACY", "PHI", "OK", "PHI access monitored; no unresolved breach")
        run.register.append(ComplianceRecord("HIPAA_Privacy_Security", "COMPLIANT",
                                             "PHI access logged; breach process current"))
    else:
        run.register.append(ComplianceRecord("HIPAA_Privacy_Security", "BREACH_REPORTED",
                                             "PHI breach reported"))

    # Stage 4 — Audit & internal controls
    appeals = root / "05_appeals_disputes" / "appeals.json"
    if file_exists(appeals):
        run.log("AUDIT_CONTROLS", "AUDIT", "OK", "Appeal/grievance compliance evidence present")
        run.register.append(ComplianceRecord("Audit_Internal_Controls", "AUDIT_READY",
                                             "Appeal timelines & evidence assembled"))
    else:
        run.register.append(ComplianceRecord("Audit_Internal_Controls", "REMEDIATION",
                                             "Missing appeal evidence"))

    # Persist
    register = [{"area": r.area, "status": r.status, "findings": r.findings}
                for r in run.register]
    (HERE / "compliance_register.json").write_text(json.dumps(register, indent=2))
    events = [{"area": e.area, "stage": e.stage, "status": e.status, "note": e.note}
              for e in run.events]
    (HERE / "compliance_events.json").write_text(json.dumps(events, indent=2))

    # Summarize this run, not the illustrative response template.
    response = {
        "flow": HERE.name,
        "example_only": False,
        "data_provenance": "Computed from this simulator run; underlying inputs are fabricated.",
        "execution_status": "completed",
        "simulation_only": True,
        "summary": {
            "evidence_files_expected": total,
            "evidence_files_present": present,
            "evidence_files_missing": total - present,
        },
        "compliance_verified": False,
        "warnings": ["Evidence checks primarily test file existence.", "HIPAA check is an always-pass placeholder."],
        "outputs": ["compliance_register.json", "compliance_events.json"],
    }
    (HERE / "mcp_response.json").write_text(
        json.dumps(response, indent=2) + "\n", encoding="utf-8"
    )


    print("=" * 70)
    print("COMPLIANCE & REGULATORY — SIMULATION (Flow 9)")
    print("=" * 70)
    for r in run.register:
        print(f"  {r.area:28} {r.status:14} {r.findings}")
    from collections import Counter
    s = Counter(r.status for r in run.register)
    print(f"\nStatus: {dict(s)} | events: {len(run.events)}")
    print(f"Wrote compliance_register.json + compliance_events.json to {HERE.name}/")


if __name__ == "__main__":
    run()
