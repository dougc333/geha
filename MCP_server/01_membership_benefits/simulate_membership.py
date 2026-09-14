"""
Simulation — Membership & Benefits Administration (Flow 1).

Processes a batch of enrollment / maintenance events through the membership
lifecycle, mirroring functional_spec.md:
  ENROLL -> ELIGIBILITY VERIFY -> MAINTENANCE (changes) -> ID CARD -> STATE

Deterministic rule-based logic, no ML. Emits a member roster + event audit log.

Usage:
    python simulate_membership.py
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

random.seed(11)
HERE = Path(__file__).parent

# --- Plan config snapshot (deductible/coinsurance read by adjudication) ------
PLAN_CONFIG = {
    "GEHA Elevate (HDHP)": {
        "code": "E-HDHP",
        "deductible": 1300.0,
        "coins": 0.15,
        "premium_monthly": 320.00,
    },
    "GEHA Elevate Plus (HDHP)": {
        "code": "EP-HDHP",
        "deductible": 1500.0,
        "coins": 0.15,
        "premium_monthly": 360.00,
    },
    "GEHA Standard": {
        "code": "314",
        "deductible": 250.0,
        "coins": 0.20,
        "premium_monthly": 187.95,
    },
    "GEHA High": {
        "code": "311",
        "deductible": 150.0,
        "coins": 0.10,
        "premium_monthly": 423.13,
    },
    "GEHA Medical Benefit (PSHB)": {
        "code": "PSHB",
        "deductible": 350.0,
        "coins": 0.20,
        "premium_monthly": 210.00,
    },
}
COVERAGE_LEVELS = ["Self Only", "Self Plus One", "Self and Family"]

# Reuse fabricated member names/plans from the claims dataset where possible.
MEMBERS = [
    {
        "name": "Sanchez, Michael",
        "plan": "GEHA Elevate (HDHP)",
        "coverage": "Self Only",
    },
    {
        "name": "Brown, Joseph",
        "plan": "GEHA Medical Benefit (PSHB)",
        "coverage": "Self Plus One",
    },
    {
        "name": "Lee, Anthony",
        "plan": "GEHA Elevate Plus (HDHP)",
        "coverage": "Self Only",
    },
    {"name": "Moore, Donna", "plan": "GEHA Standard", "coverage": "Self and Family"},
    {"name": "Torres, Elena", "plan": "GEHA Standard", "coverage": "Self Only"},
    {"name": "Hernandez, Rachel", "plan": "GEHA Standard", "coverage": "Self Plus One"},
    {
        "name": "Ramirez, Susan",
        "plan": "GEHA Elevate Plus (HDHP)",
        "coverage": "Self Only",
    },
    {"name": "Clark, David", "plan": "GEHA Standard", "coverage": "Self and Family"},
    {
        "name": "Nguyen, Thomas",
        "plan": "GEHA Elevate Plus (HDHP)",
        "coverage": "Self Only",
    },
    {
        "name": "Walker, William",
        "plan": "GEHA Elevate (HDHP)",
        "coverage": "Self Plus One",
    },
    {"name": "Jones, James", "plan": "GEHA Standard", "coverage": "Self Only"},
    {
        "name": "Wilson, Charles",
        "plan": "GEHA Elevate Plus (HDHP)",
        "coverage": "Self and Family",
    },
    {"name": "Hill, Robert", "plan": "GEHA Standard", "coverage": "Self Only"},
    {"name": "Moore, Donna", "plan": "GEHA Standard", "coverage": "Self and Family"},
]


@dataclass
class MemberRecord:
    member_id: str
    name: str
    plan: str
    coverage: str
    status: str = "ACTIVE"
    effective_date: str = "01/01/2026"
    dependents: int = 0
    card_status: str = "ISSUED"
    plan_config: dict = field(default_factory=dict)


@dataclass
class MembershipEvent:
    member_id: str
    stage: str
    status: str
    note: str


@dataclass
class MembershipRun:
    events: list[MembershipEvent] = field(default_factory=list)
    members: dict[str, MemberRecord] = field(default_factory=dict)

    def log(self, mid, stage, status, note=""):
        self.events.append(MembershipEvent(mid, stage, status, note))


def dependents_for(coverage: str) -> int:
    return {"Self Only": 0, "Self Plus One": 1, "Self and Family": 3}[coverage]


def _validate_eligibility(name: str, plan: str, event: MembershipRun, mid: str) -> bool:
    """Feature 1.1: postal employees are not eligible for the FEHB Benefit Plan."""
    if plan == "GEHA Medical Benefit (PSHB)":
        # PSHB is for postal workers; everyone else uses FEHB plans.
        event.log(mid, "ELIGIBILITY", "OK", "PSHB plan valid for postal employees")
        return True
    # FEHB plans are for federal employees/annuitants (not postal on this plan).
    event.log(mid, "ELIGIBILITY", "OK", "Federal employee/annuitant — FEHB eligible")
    return True


def run():
    run = MembershipRun()
    next_id = 1000

    for m in MEMBERS:
        mid = f"G{next_id:04d}"
        next_id += 1
        rec = MemberRecord(
            member_id=mid,
            name=m["name"],
            plan=m["plan"],
            coverage=m["coverage"],
            dependents=dependents_for(m["coverage"]),
            plan_config=PLAN_CONFIG[m["plan"]],
        )
        run.members[mid] = rec

        # Stage 1 — Enrollment
        _validate_eligibility(m["name"], m["plan"], run, mid)
        run.log(
            mid,
            "ENROLL",
            "OK",
            f"SF-2809 accepted; plan {PLAN_CONFIG[m['plan']]['code']}, {m['coverage']}",
        )

        # Stage 2 — Eligibility verification
        run.log(mid, "ELIGIBILITY_VERIFY", "OK", "Active on plan at date of service")

        # Stage 3 — Maintenance (some members get a change)
        if random.random() < 0.35:
            new_cov = random.choice([c for c in COVERAGE_LEVELS if c != m["coverage"]])
            rec.coverage = new_cov
            rec.dependents = dependents_for(new_cov)
            run.log(
                mid,
                "MAINTENANCE",
                "OK",
                f"Coverage level changed to {new_cov} (qualifying life event)",
            )

        # Stage 4 — ID card issuance
        run.log(mid, "ID_CARD", "OK", f"Health plan ID card issued (card active)")

        # Stage 5 — State
        run.log(mid, "STATE", rec.status, f"Membership {rec.status}")

    # Persist
    roster = []
    for rec in run.members.values():
        roster.append(
            {
                "member_id": rec.member_id,
                "name": rec.name,
                "plan": rec.plan,
                "plan_code": rec.plan_config["code"],
                "coverage": rec.coverage,
                "dependents": rec.dependents,
                "status": rec.status,
                "effective_date": rec.effective_date,
                "card_status": rec.card_status,
                "deductible": rec.plan_config["deductible"],
                "coinsurance": rec.plan_config["coins"],
            }
        )
    (HERE / "members.json").write_text(json.dumps(roster, indent=2))

    events = [
        {"member_id": e.member_id, "stage": e.stage, "status": e.status, "note": e.note}
        for e in run.events
    ]
    (HERE / "membership_events.json").write_text(json.dumps(events, indent=2))

    # Summarize this run, not the illustrative response template.
    response = {
        "flow": HERE.name,
        "example_only": False,
        "data_provenance": "Computed from this simulator run; underlying inputs are fabricated.",
        "execution_status": "completed",
        "simulation_only": True,
        "summary": {
            "members_created": len(roster),
            "active_members": sum(r["status"] == "ACTIVE" for r in roster),
            "coverage_changes": sum(e["stage"] == "MAINTENANCE" for e in events),
        },
        "outputs": ["members.json", "membership_events.json"],
    }
    (HERE / "mcp_response.json").write_text(
        json.dumps(response, indent=2) + "\n", encoding="utf-8"
    )

    # Summary
    print("=" * 70)
    print("MEMBERSHIP & BENEFITS ADMIN — SIMULATION (Flow 1)")
    print("=" * 70)
    for rec in run.members.values():
        print(
            f"[{rec.member_id}] {rec.name:22} {rec.plan:24} {rec.coverage:16} "
            f"{rec.dependents} dep  {rec.status}"
        )
    print(f"\nTotal members: {len(run.members)} | events logged: {len(run.events)}")
    print(f"Wrote members.json + membership_events.json to {HERE.name}/")


if __name__ == "__main__":
    run()
