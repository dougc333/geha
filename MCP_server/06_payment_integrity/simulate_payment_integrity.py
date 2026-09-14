"""
Simulation — Payment Integrity / Fraud, Waste & Abuse (Flow 6).

Screens claims for improper-payment red flags before/after payment, mirroring
functional_spec.md. Deterministic, rule-based. Emits a screening log + integrity
event trail.

Usage:
    python simulate_payment_integrity.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).parent

# Claims to screen (reuse fabricated claims; inject seeded red flags).
# Red-flag key: none | duplicate | upcode | unbundle | illogical_pair
CLAIMS_TO_SCREEN = [
    {
        "claim_id": "CLM-100000",
        "cpt": "99204",
        "dx": "H25.13",
        "charge": 310.0,
        "flag": "none",
    },
    {
        "claim_id": "CLM-100002",
        "cpt": "90670",
        "dx": "Z23",
        "charge": 250.0,
        "flag": "duplicate",
    },
    {
        "claim_id": "CLM-100004",
        "cpt": "95782",
        "dx": "G47.33",
        "charge": 1450.0,
        "flag": "none",
    },
    {
        "claim_id": "CLM-100007",
        "cpt": "99215",
        "dx": "I10",
        "charge": 265.0,
        "flag": "upcode",
    },
    {
        "claim_id": "CLM-100012",
        "cpt": "99214",
        "dx": "J45.909",
        "charge": 230.0,
        "flag": "unbundle",
    },
    {
        "claim_id": "CLM-100014",
        "cpt": "74178",
        "dx": "J18.9",
        "charge": 950.0,
        "flag": "illogical_pair",
    },
    {
        "claim_id": "CLM-100016",
        "cpt": "90670",
        "dx": "Z23",
        "charge": 250.0,
        "flag": "duplicate",
    },
    {
        "claim_id": "CLM-100017",
        "cpt": "99214",
        "dx": "M54.5",
        "charge": 210.0,
        "flag": "none",
    },
    {
        "claim_id": "CLM-100019",
        "cpt": "99213",
        "dx": "N39.0",
        "charge": 158.0,
        "flag": "none",
    },
]

# Illogical dx/procedure pairings (seeded)
ILLOGICAL = {("74178", "J18.9"), ("91034", "I10")}  # CT for dx that doesn't match


@dataclass
class ScreenRecord:
    claim_id: str
    cpt: str
    dx: str
    charge: float
    flags: list[str]
    risk: float
    decision: str


@dataclass
class IntegrityEvent:
    claim_id: str
    stage: str
    status: str
    note: str


@dataclass
class IntegrityRun:
    events: list[IntegrityEvent] = field(default_factory=list)
    screens: list[ScreenRecord] = field(default_factory=list)

    def log(self, cid, stage, status, note=""):
        self.events.append(IntegrityEvent(cid, stage, status, note))


def run():
    run = IntegrityRun()

    for c in CLAIMS_TO_SCREEN:
        cid = c["claim_id"]
        flags = []
        risk = 0.0

        # Stage 1 — Pre-payment rules screening
        if c["flag"] == "duplicate":
            flags.append("DUPLICATE_BILLING")
            risk += 0.9
        if c["flag"] == "upcode":
            flags.append("UPCODING")
            risk += 0.7
        if c["flag"] == "unbundle":
            flags.append("UNBUNDLING")
            risk += 0.6
        if (c["cpt"], c["dx"]) in ILLOGICAL:
            flags.append("ILLOGICAL_DX_PROC_PAIR")
            risk += 0.8
        if c["charge"] > 1200:
            flags.append("HIGH_CHARGE")
            risk += 0.3

        if not flags:
            risk = 0.1
            run.log(cid, "PREPAY_SCREEN", "CLEAN", "No red flags; auto-pass")
            run.screens.append(
                ScreenRecord(cid, c["cpt"], c["dx"], c["charge"], [], 0.1, "CLEAN")
            )
            continue

        run.log(
            cid,
            "PREPAY_SCREEN",
            "HELD",
            f"Risk {risk:.0%}; held for review ({', '.join(flags)})",
        )

        # Stage 2 — Investigation / classification
        if risk >= 0.8:
            cls = "FRAUD_REFERRED"
            run.log(
                cid, "INVESTIGATION", cls, "SIU review; suspected fraud -> FCA referral"
            )
        elif risk >= 0.5:
            cls = "OVERPAYMENT_RECOVERED" if c["charge"] > 600 else "ADJUSTED"
            if cls == "ADJUSTED":
                run.log(cid, "CORRECTION", "ADJUSTED", "Charges adjusted pre-payment")
            else:
                run.log(
                    cid,
                    "CORRECTION",
                    "RECOVERED",
                    "Post-payment overpayment recovery initiated",
                )
        else:
            cls = "ERROR_CORRECTED"
            run.log(cid, "CORRECTION", "ERROR_CORRECTED", "Billing error corrected")

        run.screens.append(
            ScreenRecord(cid, c["cpt"], c["dx"], c["charge"], flags, risk, cls)
        )

    # Persist
    screens = [
        {
            "claim_id": s.claim_id,
            "cpt": s.cpt,
            "dx": s.dx,
            "charge": s.charge,
            "flags": s.flags,
            "risk": round(s.risk, 2),
            "decision": s.decision,
        }
        for s in run.screens
    ]
    (HERE / "screening_log.json").write_text(json.dumps(screens, indent=2))
    events = [
        {"claim_id": e.claim_id, "stage": e.stage, "status": e.status, "note": e.note}
        for e in run.events
    ]
    (HERE / "integrity_events.json").write_text(json.dumps(events, indent=2))

    # Summarize this run, not the illustrative response template.
    response = {
        "flow": HERE.name,
        "example_only": False,
        "data_provenance": "Computed from this simulator run; underlying inputs are fabricated.",
        "execution_status": "completed",
        "simulation_only": True,
        "summary": {
            "claims_screened": len(screens),
            "clean": sum(r["decision"] == "CLEAN" for r in screens),
            "fraud_referred": sum(r["decision"] == "FRAUD_REFERRED" for r in screens),
            "adjusted": sum(r["decision"] == "ADJUSTED" for r in screens),
            "overpayment_recovered": sum(
                r["decision"] == "OVERPAYMENT_RECOVERED" for r in screens
            ),
            "error_corrected": sum(r["decision"] == "ERROR_CORRECTED" for r in screens),
        },
        "outputs": ["screening_log.json", "integrity_events.json"],
    }
    (HERE / "mcp_response.json").write_text(
        json.dumps(response, indent=2) + "\n", encoding="utf-8"
    )

    print("=" * 72)
    print("PAYMENT INTEGRITY / FRAUD, WASTE & ABUSE — SIMULATION (Flow 6)")
    print("=" * 72)
    for s in run.screens:
        fl = ",".join(s.flags) if s.flags else "-"
        print(
            f"[{s.claim_id}] {s.cpt:6} {s.dx:10} ${s.charge:7.2f} risk={s.risk:.2f} "
            f"{s.decision:20} ({fl})"
        )
    from collections import Counter

    c = Counter(s.decision for s in run.screens)
    print(f"\nDecisions: {dict(c)} | events: {len(run.events)}")
    print(f"Wrote screening_log.json + integrity_events.json to {HERE.name}/")


if __name__ == "__main__":
    run()
