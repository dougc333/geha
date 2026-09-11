"""
Simulation — Utilization Management (Flow 3).

Processes prior-authorization / medical-necessity requests through
requirement -> clinical review -> decision, mirroring functional_spec.md.
Deterministic, rule-based. Emits an authorization log + UM event trail.

Usage:
    python simulate_utilization.py
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

random.seed(17)
HERE = Path(__file__).parent

# CPT -> (PA required?, medical-necessity review?, covered?)
# Mirrors the requirement-search tool's code-based & conditional results.
CPT_REQUIREMENTS = {
    "95782": (True, True, True),      # sleep study -> PA required
    "74178": (True, True, True),      # CT abdomen/pelvis -> PA required (EviCore)
    "91034": (True, True, True),      # esophageal pH -> medical necessity review
    "76830": (True, True, True),      # transvaginal US -> medical necessity
    "97140": (False, False, True),    # manual therapy -> no requirements
    "99214": (False, False, True),    # office visit -> no requirements
    "D0150": (False, False, False),   # dental eval -> NO coverage under medical plan
    "90670": (False, False, False),   # certain vaccine -> NO coverage
}

# Fabricated member IDs (reuse claim members) + a request each
REQUESTS = [
    {"member": "G1000", "cpt": "95782", "diag": "G47.33", "length_days": 1, "provider": "Dr. S. Chen"},
    {"member": "G1004", "cpt": "74178", "diag": "K35.80", "length_days": 1, "provider": "Dr. R. Gupta"},
    {"member": "G1001", "cpt": "91034", "diag": "K21.9", "length_days": 1, "provider": "Dr. A. Bennett"},
    {"member": "G1005", "cpt": "76830", "diag": "D25.9", "length_days": 1, "provider": "Dr. J. Miller"},
    {"member": "G1007", "cpt": "97140", "diag": "M54.5", "length_days": 1, "provider": "Dr. K. Singh"},
    {"member": "G1002", "cpt": "99214", "diag": "J45.909", "length_days": 1, "provider": "Dr. M. Park"},
    {"member": "G1006", "cpt": "D0150", "diag": "K08.101", "length_days": 1, "provider": "Dr. L. Okafor"},
    {"member": "G1009", "cpt": "74178", "diag": "J18.9", "length_days": 1, "provider": "Dr. T. Alvarez"},
    {"member": "G1010", "cpt": "95782", "diag": "G47.33", "length_days": 1, "provider": "Dr. S. Chen"},
]

# Simple medical-necessity score (fake): some requests fail criteria
NECESSITY_SCORE = {  # member -> 0..1 (probability-like proxy of criteria met)
    "G1000": 0.9, "G1004": 0.8, "G1001": 0.6, "G1005": 0.7, "G1007": 1.0,
    "G1002": 1.0, "G1006": 0.0, "G1009": 0.4, "G1010": 0.2,
}


@dataclass
class AuthRecord:
    tx_id: str
    member: str
    cpt: str
    decision: str
    auth_number: str = ""


@dataclass
class UMEvent:
    tx_id: str
    stage: str
    status: str
    note: str


@dataclass
class UMRun:
    events: list[UMEvent] = field(default_factory=list)
    auths: list[AuthRecord] = field(default_factory=list)

    def log(self, tx, stage, status, note=""):
        self.events.append(UMEvent(tx, stage, status, note))


def run():
    run = UMRun()
    tx_n = 1000

    for req in REQUESTS:
        tx = f"PA-{tx_n}"; tx_n += 1
        cpt = req["cpt"]
        pa_req, mn_req, covered = CPT_REQUIREMENTS.get(cpt, (False, False, True))

        # Stage 1 — Requirement + coverage determination
        if not covered:
            run.log(tx, "REQUIREMENT", "NOT_COVERED", f"{cpt} not covered under plan")
            run.auths.append(AuthRecord(tx, req["member"], cpt, "NOT_COVERED"))
            continue
        if pa_req:
            run.log(tx, "REQUIREMENT", "PA_REQUIRED", f"{cpt} requires prior authorization")
        elif mn_req:
            run.log(tx, "REQUIREMENT", "MN_REVIEW", f"{cpt} requires medical-necessity review")
        else:
            run.log(tx, "REQUIREMENT", "NONE", f"{cpt} no requirements")
            run.auths.append(AuthRecord(tx, req["member"], cpt, "NO_AUTH_NEEDED"))
            continue

        # Stage 2 — Request intake
        run.log(tx, "REQUEST", "SUBMITTED", f"Auth requested for {cpt} ({req['diag']})")

        # Stage 3 — Clinical review
        score = NECESSITY_SCORE.get(req["member"], 0.5)
        if pa_req and score < 0.5:
            run.log(tx, "CLINICAL_REVIEW", "PENDING", "Flagged for manual medical review")
            run.auths.append(AuthRecord(tx, req["member"], cpt, "PENDING_REVIEW"))
            continue
        if score >= 0.7:
            auth_num = f"AU-{random.randint(10000, 99999)}"
            run.log(tx, "CLINICAL_REVIEW", "APPROVED", f"Meets criteria; auth {auth_num}")
            run.auths.append(AuthRecord(tx, req["member"], cpt, "APPROVED", auth_num))
        else:
            run.log(tx, "CLINICAL_REVIEW", "DENIED", "Does not meet medical-necessity criteria")
            run.auths.append(AuthRecord(tx, req["member"], cpt, "DENIED"))

    # Persist
    auths = [{"tx_id": a.tx_id, "member": a.member, "cpt": a.cpt,
              "decision": a.decision, "auth_number": a.auth_number} for a in run.auths]
    (HERE / "authorizations.json").write_text(json.dumps(auths, indent=2))
    events = [{"tx_id": e.tx_id, "stage": e.stage, "status": e.status, "note": e.note}
              for e in run.events]
    (HERE / "um_events.json").write_text(json.dumps(events, indent=2))

    # Summarize this run, not the illustrative response template.
    response = {
        "flow": HERE.name,
        "example_only": False,
        "data_provenance": "Computed from this simulator run; underlying inputs are fabricated.",
        "execution_status": "completed",
        "simulation_only": True,
        "summary": {
            "requests_processed": len(auths),
            "approved": sum(r["decision"] == "APPROVED" for r in auths),
            "denied": sum(r["decision"] == "DENIED" for r in auths),
            "pending_review": sum(r["decision"] == "PENDING_REVIEW" for r in auths),
            "no_auth_needed": sum(r["decision"] == "NO_AUTH_NEEDED" for r in auths),
            "not_covered": sum(r["decision"] == "NOT_COVERED" for r in auths),
        },
        "outputs": ["authorizations.json", "um_events.json"],
    }
    (HERE / "mcp_response.json").write_text(
        json.dumps(response, indent=2) + "\n", encoding="utf-8"
    )


    print("=" * 70)
    print("UTILIZATION MANAGEMENT — SIMULATION (Flow 3)")
    print("=" * 70)
    for a in run.auths:
        print(f"[{a.tx_id}] member {a.member}  {a.cpt:6}  {a.decision:14} {a.auth_number}")
    from collections import Counter
    c = Counter(a.decision for a in run.auths)
    print(f"\nDecisions: {dict(c)} | events: {len(run.events)}")
    print(f"Wrote authorizations.json + um_events.json to {HERE.name}/")


if __name__ == "__main__":
    run()
