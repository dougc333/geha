"""
Simulation — Post-Adjudication & Disputes (Appeals) (Flow 5).

Processes disputed determinations through appeal intake -> internal review ->
escalation to external review, mirroring functional_spec.md. Deterministic,
rule-based. Emits an appeals log + dispute event trail.

Usage:
    python simulate_appeals.py
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

random.seed(23)
HERE = Path(__file__).parent

# Disputed determinations (reuse fabricated outcomes from claims + UM flows).
# Each: (claim_id, member, cpt, original_decision, dispute_type)
DISPUTES = [
    ("CLM-100005", "G1005", "D0150", "DENIED", "claim"),      # dental denied under medical plan
    ("CLM-100002", "G1002", "90670", "PARTIAL", "claim"),     # partial (vaccine not covered)
    ("PA-1002",    "G1001", "91034", "DENIED", "authorization"),  # UM denial
    ("PA-1007",    "G1009", "74178", "PENDING_REVIEW", "authorization"),
    ("CLM-100009", "G1009", "D0150", "DENIED", "claim"),
    ("PA-1008",    "G1010", "95782", "PENDING_REVIEW", "authorization"),
    ("CLM-100006", "G1006", "D0150", "DENIED", "claim"),
]

# Deadline: must file within N days of the adverse notice
FILING_DEADLINE_DAYS = 120
# Chance an internal appeal overturns (seeded but deterministic via fixed map)
OVERTURN = {  # dispute index -> overturned?
    0: True, 1: False, 2: True, 3: False, 4: False, 5: True, 6: False,
}


@dataclass
class AppealRecord:
    appeal_id: str
    claim_id: str
    member: str
    dispute_type: str
    original: str
    filed_days_late: bool
    internal_decision: str
    escalated: bool
    final_decision: str


@dataclass
class AppealEvent:
    appeal_id: str
    stage: str
    status: str
    note: str


@dataclass
class AppealRun:
    events: list[AppealEvent] = field(default_factory=list)
    appeals: list[AppealRecord] = field(default_factory=list)

    def log(self, ap, stage, status, note=""):
        self.events.append(AppealEvent(ap, stage, status, note))


def run():
    run = AppealRun()
    ap_n = 5000

    for i, (cid, member, cpt, orig, dtype) in enumerate(DISPUTES):
        ap = f"AP-{ap_n}"; ap_n += 1

        # Stage 1 — Intake + filing deadline
        late = random.random() < 0.10
        if late:
            run.log(ap, "INTAKE", "REJECT", f"Filed after {FILING_DEADLINE_DAYS}-day deadline")
            run.appeals.append(AppealRecord(ap, cid, member, dtype, orig, True,
                                            "REJECTED", False, "REJECTED"))
            continue
        run.log(ap, "INTAKE", "FILED", f"Dispute of {dtype} {orig} for {cpt}")

        # Stage 2 — Internal review
        overturned = OVERTURN.get(i, False)
        if overturned:
            internal = "OVERTURNED"
            run.log(ap, "INTERNAL_REVIEW", "OVERTURNED", "Re-reviewed; decision reversed -> claim adjustment")
            run.appeals.append(AppealRecord(ap, cid, member, dtype, orig, False,
                                            internal, False, "OVERTURNED"))
            continue
        else:
            internal = "UPHELD"
            run.log(ap, "INTERNAL_REVIEW", "UPHELD", "Original determination upheld")

        # Stage 3 — Escalation to external review (OPM)
        if random.random() < 0.5:
            run.log(ap, "ESCALATION", "EXTERNAL", "Escalated to OPM/external reviewer (30-day window)")
            ext = "OVERTURNED" if random.random() < 0.5 else "UPHELD"
            run.log(ap, "EXTERNAL_REVIEW", ext, f"External decision: {ext}; plan must accept")
            run.appeals.append(AppealRecord(ap, cid, member, dtype, orig, False,
                                            internal, True, ext))
        else:
            run.appeals.append(AppealRecord(ap, cid, member, dtype, orig, False,
                                            internal, False, internal))

    # Persist
    appeals = [{"appeal_id": a.appeal_id, "claim_id": a.claim_id, "member": a.member,
                "dispute_type": a.dispute_type, "original": a.original,
                "filed_late": a.filed_days_late, "internal": a.internal_decision,
                "escalated": a.escalated, "final": a.final_decision}
               for a in run.appeals]
    (HERE / "appeals.json").write_text(json.dumps(appeals, indent=2))
    events = [{"appeal_id": e.appeal_id, "stage": e.stage, "status": e.status, "note": e.note}
              for e in run.events]
    (HERE / "appeals_events.json").write_text(json.dumps(events, indent=2))

    print("=" * 70)
    print("POST-ADJUDICATION & DISPUTES (APPEALS) — SIMULATION (Flow 5)")
    print("=" * 70)
    for a in run.appeals:
        print(f"[{a.appeal_id}] {a.claim_id} {a.member} {a.dispute_type:14} "
              f"orig={a.original:14} final={a.final_decision:12} esc={a.escalated}")
    from collections import Counter
    c = Counter(a.final_decision for a in run.appeals)
    print(f"\nFinal decisions: {dict(c)} | events: {len(run.events)}")
    print(f"Wrote appeals.json + appeals_events.json to {HERE.name}/")


if __name__ == "__main__":
    run()
