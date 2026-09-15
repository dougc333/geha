"""
Simulation — Premium Billing & Reconciliation (Flow 4).

Processes a premium billing cycle: calculate premium -> collect (withhold/pay)
-> delinquency/grace -> reconcile. Deterministic, rule-based. Emits a premium
ledger + billing event log.

Usage:
    python simulate_premium_billing.py
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

random.seed(19)
HERE = Path(__file__).parent

# Load the fabricated member roster produced by Flow 1 (if present), else defaults.
_ROSTER_PATH = Path(__file__).parent.parent / "01_membership_benefits" / "members.json"

# plan -> (monthly_premium, govt_share_pct)
PLAN_PREMIUM = {
    "GEHA Elevate (HDHP)": (320.00, 0.75),
    "GEHA Elevate Plus (HDHP)": (360.00, 0.75),
    "GEHA Standard": (187.95, 0.75),
    "GEHA High": (423.13, 0.75),
    "GEHA Medical Benefit (PSHB)": (210.00, 0.75),
}

GRACE_PERIODS = 2  # months before lapse


@dataclass
class BillingRecord:
    member_id: str
    name: str
    plan: str
    monthly: float
    govt_share: float
    enrollee_share: float
    paid: float
    months_due: int
    status: str


@dataclass
class BillingEvent:
    member_id: str
    stage: str
    status: str
    note: str


@dataclass
class BillingRun:
    events: list[BillingEvent] = field(default_factory=list)
    ledger: list[BillingRecord] = field(default_factory=list)

    def log(self, mid, stage, status, note=""):
        self.events.append(BillingEvent(mid, stage, status, note))


def load_members():
    if _ROSTER_PATH.exists():
        return json.loads(_ROSTER_PATH.read_text())
    # Fallback fabricated members
    return [
        {
            "member_id": "G1000",
            "name": "Sanchez, Michael",
            "plan": "GEHA Elevate (HDHP)",
        },
        {
            "member_id": "G1001",
            "name": "Brown, Joseph",
            "plan": "GEHA Medical Benefit (PSHB)",
        },
        {"member_id": "G1004", "name": "Torres, Elena", "plan": "GEHA Standard"},
        {
            "member_id": "G1006",
            "name": "Ramirez, Susan",
            "plan": "GEHA Elevate Plus (HDHP)",
        },
        {"member_id": "G1010", "name": "Jones, James", "plan": "GEHA Standard"},
    ]


def run():
    run = BillingRun()
    members = load_members()

    for m in members:
        mid = m["member_id"]
        plan = m.get("plan", "GEHA Standard")
        monthly = PLAN_PREMIUM[plan][0]
        govt_pct = PLAN_PREMIUM[plan][1]
        govt = round(monthly * govt_pct, 2)
        enrollee = round(monthly - govt, 2)

        # Simulate payment behavior: most pay, some go past due, one lapses.
        r = random.random()
        if r < 0.75:
            paid = monthly
            months_due = 0
            status = "CURRENT"
            run.log(
                mid,
                "CALCULATE",
                "OK",
                f"Premium ${monthly:.2f} (govt ${govt:.2f} / enrollee ${enrollee:.2f})",
            )
            run.log(
                mid,
                "COLLECT",
                "OK",
                "Enrollee share withheld (pre-tax premium conversion)",
            )
            run.log(mid, "RECONCILE", "OK", "Payment received; ledger current")
        elif r < 0.9:
            paid = monthly * 0.5
            months_due = 1
            status = "PAST_DUE"
            run.log(mid, "CALCULATE", "OK", f"Premium ${monthly:.2f}")
            run.log(mid, "COLLECT", "PARTIAL", "Partial payment received")
            run.log(
                mid, "DELINQUENCY", "FLAG", f"Past due 1 month (grace {GRACE_PERIODS})"
            )
        else:
            paid = 0.0
            months_due = GRACE_PERIODS + 1
            status = "LAPSED"
            run.log(mid, "CALCULATE", "OK", f"Premium ${monthly:.2f}")
            run.log(mid, "COLLECT", "NONE", "No payment received")
            run.log(
                mid,
                "DELINQUENCY",
                "LAPSE",
                "Grace period expired; coverage lapsed -> feeds eligibility",
            )

        rec = BillingRecord(
            mid,
            m.get("name", ""),
            plan,
            monthly,
            govt,
            enrollee,
            paid,
            months_due,
            status,
        )
        run.ledger.append(rec)

    # Persist
    ledger = [
        {
            "member_id": r.member_id,
            "name": r.name,
            "plan": r.plan,
            "monthly_premium": r.monthly,
            "govt_share": r.govt_share,
            "enrollee_share": r.enrollee_share,
            "paid": r.paid,
            "months_due": r.months_due,
            "status": r.status,
        }
        for r in run.ledger
    ]
    (HERE / "premium_ledger.json").write_text(json.dumps(ledger, indent=2))
    events = [
        {"member_id": e.member_id, "stage": e.stage, "status": e.status, "note": e.note}
        for e in run.events
    ]
    (HERE / "billing_events.json").write_text(json.dumps(events, indent=2))

    # Summarize this run, not the illustrative response template.
    response = {
        "flow": HERE.name,
        "example_only": False,
        "data_provenance": "Computed from this simulator run; underlying inputs are fabricated.",
        "execution_status": "completed",
        "simulation_only": True,
        "summary": {
            "members_processed": len(ledger),
            "current": sum(r["status"] == "CURRENT" for r in ledger),
            "past_due": sum(r["status"] == "PAST_DUE" for r in ledger),
            "lapsed": sum(r["status"] == "LAPSED" for r in ledger),
        },
        "outputs": ["premium_ledger.json", "billing_events.json"],
    }
    (HERE / "mcp_response.json").write_text(
        json.dumps(response, indent=2) + "\n", encoding="utf-8"
    )

    print("=" * 70)
    print("PREMIUM BILLING & RECONCILIATION — SIMULATION (Flow 4)")
    print("=" * 70)
    for r in run.ledger:
        print(
            f"[{r.member_id}] {r.name:18} {r.plan:24} ${r.monthly:7.2f}/mo "
            f"enrollee ${r.enrollee_share:6.2f}  {r.status}"
        )
    from collections import Counter

    c = Counter(r.status for r in run.ledger)
    print(f"\nStatus: {dict(c)} | events: {len(run.events)}")
    print(f"Wrote premium_ledger.json + billing_events.json to {HERE.name}/")


if __name__ == "__main__":
    run()
