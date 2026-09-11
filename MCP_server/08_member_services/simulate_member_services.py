"""
Simulation — Customer / Member Services (Flow 8).

Processes member/provider inquiries through intake -> resolution (360-degree
member view) -> escalation, mirroring functional_spec.md. Deterministic,
rule-based. Emits an inquiry log + service event trail.

Usage:
    python simulate_member_services.py
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).parent

# Pull upstream data if available (from prior flows) for the 360-degree view.
_ROOT = Path(__file__).parent.parent
TRAILS = json.loads((_ROOT / "claims" / "audit_trails.json").read_text()) if \
    (_ROOT / "claims" / "audit_trails.json").exists() else []
MEMBERS = json.loads((_ROOT / "01_membership_benefits" / "members.json").read_text()) if \
    (_ROOT / "01_membership_benefits" / "members.json").exists() else []
AUTHS = json.loads((_ROOT / "03_utilization_management" / "authorizations.json").read_text()) if \
    (_ROOT / "03_utilization_management" / "authorizations.json").exists() else []

# Inquiries: (type, member, ref, caller_verified)
INQUIRIES = [
    ("CLAIM_STATUS", "G1005", "CLM-100005", True),
    ("ELIGIBILITY", "G1005", "G1005", True),
    ("BENEFITS", "G1000", "G1000", True),
    ("PRIOR_AUTH", "G1000", "PA-1000", True),
    ("PREMIUM", "G1005", "G1005", True),
    ("ID_CARD", "G1003", "G1003", True),
    ("CLAIM_STATUS", "G1004", "CLM-100000", False),   # unverified caller
    ("OTHER", "G1001", "G1001", True),
    ("CLAIM_STATUS", "G1009", "CLM-100014", True),
    ("PRIOR_AUTH", "G1001", "PA-1002", True),
]


@dataclass
class InquiryRecord:
    inquiry_id: str
    itype: str
    member: str
    ref: str
    verified: bool
    source: str
    status: str
    resolution: str = ""


@dataclass
class ServiceEvent:
    inquiry_id: str
    stage: str
    status: str
    note: str


@dataclass
class ServiceRun:
    events: list[ServiceEvent] = field(default_factory=list)
    inquiries: list[InquiryRecord] = field(default_factory=list)

    def log(self, iid, stage, status, note=""):
        self.events.append(ServiceEvent(iid, stage, status, note))


def claim_status(cid: str) -> str:
    for t in TRAILS:
        if t.get("claim_id") == cid:
            return t.get("final_status", "UNKNOWN")
    return "NOT_FOUND"


def auth_status(tx: str) -> str:
    for a in AUTHS:
        if a.get("tx_id") == tx:
            return a.get("decision", "UNKNOWN")
    return "NOT_FOUND"


def member_eligibility(mid: str) -> str:
    for m in MEMBERS:
        if m.get("member_id") == mid:
            return m.get("status", "ACTIVE")
    return "NOT_FOUND"


def run():
    run = ServiceRun()
    iid_n = 9000

    for itype, mid, ref, verified in INQUIRIES:
        iid = f"INQ-{iid_n}"; iid_n += 1

        # Stage 1 — Intake + identity verification
        if not verified:
            run.log(iid, "INTAKE", "FAIL", "Identity not verified (member ID/DOB mismatch)")
            run.inquiries.append(InquiryRecord(iid, itype, mid, ref, False, "", "UNRESOLVED",
                                               "Caller identity could not be verified"))
            continue
        run.log(iid, "INTAKE", "OK", f"{itype} inquiry for member {mid}")

        # Stage 2 — Resolution via 360-degree view
        if itype == "CLAIM_STATUS":
            st = claim_status(ref)
            run.inquiries.append(InquiryRecord(iid, itype, mid, ref, True, "Claims (Flow 0)",
                                               "RESOLVED", f"Claim {ref} status: {st}"))
            run.log(iid, "RESOLVE", "RESOLVED", f"Claim {ref} -> {st}")
        elif itype == "ELIGIBILITY":
            st = member_eligibility(mid)
            run.inquiries.append(InquiryRecord(iid, itype, mid, ref, True, "Membership (Flow 1)",
                                               "RESOLVED", f"Eligibility: {st}"))
            run.log(iid, "RESOLVE", "RESOLVED", f"Eligibility -> {st}")
        elif itype == "BENEFITS":
            run.inquiries.append(InquiryRecord(iid, itype, mid, ref, True, "Plan Config (Flow 1)",
                                               "RESOLVED", "Plan cost-sharing provided"))
            run.log(iid, "RESOLVE", "RESOLVED", "Benefits/cost-sharing provided")
        elif itype == "PRIOR_AUTH":
            st = auth_status(ref)
            run.inquiries.append(InquiryRecord(iid, itype, mid, ref, True, "UM (Flow 3)",
                                               "RESOLVED", f"Auth {ref} -> {st}"))
            run.log(iid, "RESOLVE", "RESOLVED", f"Auth status -> {st}")
        elif itype == "PREMIUM":
            run.inquiries.append(InquiryRecord(iid, itype, mid, ref, True, "Premium Billing (Flow 4)",
                                               "RESOLVED", "Premium balance provided"))
            run.log(iid, "RESOLVE", "RESOLVED", "Premium/balance provided")
        elif itype == "ID_CARD":
            run.inquiries.append(InquiryRecord(iid, itype, mid, ref, True, "Membership (Flow 1)",
                                               "RESOLVED", "Replacement ID card ordered"))
            run.log(iid, "RESOLVE", "RESOLVED", "ID card replacement processed")
        else:  # OTHER -> escalate
            run.inquiries.append(InquiryRecord(iid, itype, mid, ref, True, "",
                                               "ESCALATED", "Routed to specialist"))
            run.log(iid, "RESOLVE", "ESCALATED", "Routed to specialist team")

    # Persist
    inquiries = [{"inquiry_id": i.inquiry_id, "type": i.itype, "member": i.member,
                  "ref": i.ref, "verified": i.verified, "source": i.source,
                  "status": i.status, "resolution": i.resolution}
                 for i in run.inquiries]
    (HERE / "inquiries.json").write_text(json.dumps(inquiries, indent=2))
    events = [{"inquiry_id": e.inquiry_id, "stage": e.stage, "status": e.status, "note": e.note}
              for e in run.events]
    (HERE / "service_events.json").write_text(json.dumps(events, indent=2))

    print("=" * 70)
    print("CUSTOMER / MEMBER SERVICES — SIMULATION (Flow 8)")
    print("=" * 70)
    for i in run.inquiries:
        print(f"[{i.inquiry_id}] {i.itype:14} member={i.member} ref={i.ref:12} "
              f"{i.status:12} <- {i.source or '-'}")
    from collections import Counter
    s = Counter(i.status for i in run.inquiries)
    print(f"\nStatus: {dict(s)} | events: {len(run.events)}")
    print(f"Wrote inquiries.json + service_events.json to {HERE.name}/")


if __name__ == "__main__":
    run()
