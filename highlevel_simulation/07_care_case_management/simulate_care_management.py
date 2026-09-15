"""
Simulation — Care & Case Management (Flow 7).

Processes candidate members through identification -> enrollment -> care plan
-> monitoring, mirroring functional_spec.md. Deterministic, rule-based. Emits a
care-case roster + care event trail.

Usage:
    python simulate_care_management.py
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

random.seed(29)
HERE = Path(__file__).parent

# Candidate members with a chronic/high-risk diagnosis (reuse fabricated data).
# (member, diagnosis, condition_category)
CANDIDATES = [
    ("G1000", "E11.9", "Diabetes"),
    ("G1001", "I10", "Hypertension"),
    ("G1002", "J45.909", "Asthma"),
    ("G1004", "G47.33", "Sleep Apnea"),
    ("G1005", "D25.9", "High-Risk (Gyn)"),
    ("G1006", "M17.0", "Osteoarthritis"),
    ("G1007", "F41.1", "Behavioral Health"),
    ("G1008", "H25.13", "Cataract"),
    ("G1009", "J18.9", "Pneumonia / High-Risk"),
    ("G1010", "K21.9", "GI Condition"),
]

# Deterministic risk level by index
RISK = {
    0: "HIGH",
    1: "MEDIUM",
    2: "MEDIUM",
    3: "HIGH",
    4: "HIGH",
    5: "LOW",
    6: "MEDIUM",
    7: "LOW",
    8: "HIGH",
    9: "LOW",
}


@dataclass
class CareCase:
    member_id: str
    diagnosis: str
    program: str
    risk: str
    status: str


@dataclass
class CareEvent:
    member_id: str
    stage: str
    status: str
    note: str


@dataclass
class CareRun:
    events: list[CareEvent] = field(default_factory=list)
    cases: list[CareCase] = field(default_factory=list)

    def log(self, mid, stage, status, note=""):
        self.events.append(CareEvent(mid, stage, status, note))


def program_for(condition: str) -> str:
    return {
        "Diabetes": "Disease Management",
        "Hypertension": "Disease Management",
        "Asthma": "Disease Management",
        "Sleep Apnea": "Case Management",
        "High-Risk (Gyn)": "Case Management",
        "Osteoarthritis": "Disease Management",
        "Behavioral Health": "Behavioral Health",
        "Cataract": "Wellness/Education",
        "Pneumonia / High-Risk": "Case Management",
        "GI Condition": "Disease Management",
    }[condition]


def run():
    run = CareRun()
    for i, (mid, dx, cond) in enumerate(CANDIDATES):
        risk = RISK[i]
        program = program_for(cond)

        # Stage 1 — Identification
        run.log(mid, "IDENTIFY", "FLAGGED", f"{cond} ({dx}) -> eligible for {program}")

        # Stage 2 — Enrollment (outreach); some decline
        if risk == "LOW" and random.random() < 0.4:
            run.log(mid, "ENROLL", "DECLINED", "Member declined outreach")
            run.cases.append(CareCase(mid, dx, program, risk, "DECLINED"))
            continue
        run.log(mid, "ENROLL", "ENROLLED", f"Enrolled in {program}; risk {risk}")
        run.cases.append(CareCase(mid, dx, program, risk, "ACTIVE_PLAN"))

        # Stage 3 — Care plan
        run.log(
            mid,
            "CARE_PLAN",
            "OK",
            f"Care plan built (education + follow-up) for {cond}",
        )

        # Stage 4 — Monitoring / outcome
        if risk == "HIGH":
            status = "MONITORING"
        elif random.random() < 0.5:
            status = "COMPLETED"
        else:
            status = "MONITORING"
        # update the record
        run.cases[-1].status = status
        run.log(mid, "MONITORING", status, f"Follow-up complete; case {status.lower()}")

    # Persist
    cases = [
        {
            "member_id": c.member_id,
            "diagnosis": c.diagnosis,
            "program": c.program,
            "risk": c.risk,
            "status": c.status,
        }
        for c in run.cases
    ]
    (HERE / "care_cases.json").write_text(json.dumps(cases, indent=2))
    events = [
        {"member_id": e.member_id, "stage": e.stage, "status": e.status, "note": e.note}
        for e in run.events
    ]
    (HERE / "care_events.json").write_text(json.dumps(events, indent=2))

    # Summarize this run, not the illustrative response template.
    response = {
        "flow": HERE.name,
        "example_only": False,
        "data_provenance": "Computed from this simulator run; underlying inputs are fabricated.",
        "execution_status": "completed",
        "simulation_only": True,
        "summary": {
            "candidates_processed": len(cases),
            "declined": sum(r["status"] == "DECLINED" for r in cases),
            "monitoring": sum(r["status"] == "MONITORING" for r in cases),
            "completed": sum(r["status"] == "COMPLETED" for r in cases),
        },
        "outputs": ["care_cases.json", "care_events.json"],
    }
    (HERE / "mcp_response.json").write_text(
        json.dumps(response, indent=2) + "\n", encoding="utf-8"
    )

    print("=" * 70)
    print("CARE & CASE MANAGEMENT — SIMULATION (Flow 7)")
    print("=" * 70)
    for c in run.cases:
        print(
            f"[{c.member_id}] {c.diagnosis:10} {c.program:22} risk={c.risk:7} {c.status}"
        )
    from collections import Counter

    s = Counter(c.status for c in run.cases)
    print(f"\nStatus: {dict(s)} | events: {len(run.events)}")
    print(f"Wrote care_cases.json + care_events.json to {HERE.name}/")


if __name__ == "__main__":
    run()
