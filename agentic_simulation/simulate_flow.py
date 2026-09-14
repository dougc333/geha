"""
Agentic simulation of the GEHA medical claims adjudication data flow.

Each claim (from claims/claims.json) is pushed through a state machine that
mirrors the real pipeline described in process.md:

    SUBMIT -> RECEIVE -> INTAKE/EDIT -> ELIGIBILITY -> CODING/VALIDATION
           -> [MEDICAL NECESSITY / MANUAL REVIEW] -> ADJUDICATION
           -> PAY (ERA + EOB) | PARTIAL | PENDING_REVIEW | DENIED

Each stage is a "step" object with deterministic rule-based logic (no ML, so
the simulation is reproducible). The pipeline emits a per-claim audit trail
and a summary report.

Usage:
    python simulate_flow.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CLAIMS_PATH = Path(__file__).parent / "claims" / "claims.json"

# Valid ICD-10 / CPT lookup tables (subset used by the sample claims)
VALID_ICD10 = {
    "J06.9",
    "M54.5",
    "E11.9",
    "I10",
    "K21.9",
    "F41.1",
    "S93.401A",
    "Z23",
    "N39.0",
    "J45.909",
    "H25.13",
    "K08.101",
    "G47.33",
    "M17.0",
    "Z01.810",
    "L20.9",
    "K35.80",
    "Z00.00",
    "D25.9",
    "J18.9",
}
VALID_CPT = {
    "99213",
    "99214",
    "99215",
    "99204",
    "99283",
    "90834",
    "97140",
    "83036",
    "91034",
    "73630",
    "90670",
    "90471",
    "81003",
    "94010",
    "92004",
    "D0150",
    "95782",
    "73564",
    "74178",
    "76830",
    "71045",
    "99396",
}
# Services that tend to require prior authorization / manual review
AUTH_REQUIRED = {"95782", "74178", "91034", "76830"}
# Services not covered under these medical plans -> genuine DENIED outcomes
NOT_COVERED = {"D0150", "90670"}  # dental eval under a medical plan; certain vaccines

# Per-plan out-of-pocket model: (deductible_remaining_midyear, coinsurance_rate)
# Mid-year: assume members have already satisfied part of their annual deductible.
PLAN_MODEL = {
    "GEHA Elevate Plus (HDHP)": (500.0, 0.15),
    "GEHA Elevate (HDHP)": (400.0, 0.15),
    "GEHA Standard": (150.0, 0.20),
    "GEHA High": (80.0, 0.10),
    "GEHA Medical Benefit (PSHB)": (200.0, 0.20),
}


@dataclass
class Stage:
    name: str
    status: str  # PASS | FLAG | DENY
    note: str = ""


@dataclass
class AuditTrail:
    claim_id: str
    stages: list[Stage] = field(default_factory=list)
    allowed_amount: float = 0.0
    member_responsibility: float = 0.0
    final_status: str = ""

    def log(self, name: str, status: str, note: str = ""):
        self.stages.append(Stage(name, status, note))


def _stage_1_intake(claim: dict, trail: AuditTrail) -> bool:
    """Initial edit check: member id, required fields, duplicates."""
    member_id = claim.get("insured_id", "")
    if not member_id or not member_id.startswith("G"):
        trail.log("INTAKE/EDIT", "DENY", "Invalid or missing member ID")
        return False
    if not claim.get("diagnosis", {}).get("code"):
        trail.log("INTAKE/EDIT", "DENY", "Missing diagnosis (Box 21)")
        return False
    lines = claim.get("service_lines", [])
    if not lines:
        trail.log("INTAKE/EDIT", "DENY", "No service lines (Box 24)")
        return False
    if any(not sl.get("charge") for sl in lines):
        trail.log("INTAKE/EDIT", "FLAG", "Service line with $0/missing charge")
        return False
    trail.log("INTAKE/EDIT", "PASS", "Required boxes populated; member ID valid")
    return True


def _stage_2_eligibility(claim: dict, trail: AuditTrail) -> bool:
    """Member active on the plan; benefits in force."""
    if claim.get("plan") not in PLAN_MODEL:
        trail.log("ELIGIBILITY", "DENY", f"Unknown plan: {claim.get('plan')}")
        return False
    # All members in the sample are active FEHB/PSHB enrollees.
    trail.log("ELIGIBILITY", "PASS", "Member active on plan at date of service")
    return True


def _stage_3_coding(claim: dict, trail: AuditTrail) -> bool:
    """Validate ICD-10 + CPT codes and the diagnosis pointer.

    Determines coverage per service line: a claim is DENIED outright only if a
    code is invalid or EVERY line is non-covered. Mixed covered/non-covered
    lines are left to adjudication (PARTIAL).
    """
    dx = claim.get("diagnosis", {}).get("code", "")
    if dx not in VALID_ICD10:
        trail.log("CODING/VALIDATION", "DENY", f"Invalid ICD-10 code: {dx}")
        return False
    for sl in claim.get("service_lines", []):
        cpt = sl.get("cpt", "")
        if cpt not in VALID_CPT:
            trail.log("CODING/VALIDATION", "DENY", f"Invalid CPT/HCPCS: {cpt}")
            return False
        if sl.get("dx_pointer", "A") not in ("A",):
            trail.log("CODING/VALIDATION", "FLAG", f"Unlinked dx pointer on {cpt}")
            return False
    # If every line is non-covered, deny outright; else let adjudication decide.
    if claim.get("service_lines") and all(
        sl.get("cpt") in NOT_COVERED for sl in claim["service_lines"]
    ):
        trail.log(
            "CODING/VALIDATION",
            "DENY",
            "No service line is a covered benefit under this medical plan",
        )
        return False
    trail.log(
        "CODING/VALIDATION", "PASS", "ICD-10 and CPT codes valid; pointers linked"
    )
    return True


def _stage_4_manual_review(claim: dict, trail: AuditTrail) -> bool:
    """Route to manual review if prior auth required / high cost."""
    for sl in claim.get("service_lines", []):
        if sl.get("cpt") in AUTH_REQUIRED:
            trail.log(
                "MANUAL REVIEW",
                "PENDING",
                f"{sl['cpt']} requires prior auth — manual review",
            )
            return False
    if claim.get("total_charge", 0) > 1500:
        trail.log(
            "MANUAL REVIEW",
            "PENDING",
            f"Charge ${claim['total_charge']:.2f} exceeds auto-adjudication threshold",
        )
        return False
    trail.log(
        "MANUAL REVIEW", "PASS", "No prior-auth requirement; within auto threshold"
    )
    return True


# Per-member out-of-pocket accumulator: deductible gets satisfied across the
# year as the member's claims are processed (realistic claims data flow).
_OOP_ACCUM: dict[str, float] = {}


def _stage_5_adjudicate(claim: dict, trail: AuditTrail) -> str:
    """Apply plan benefits -> allowed amount, member responsibility, status.

    Tracks a per-member deductible accumulator so an HDHP deductible is
    satisfied progressively across the member's claims (not re-applied in
    full on every claim).
    """
    plan = claim.get("plan")
    deduct_limit, coins = PLAN_MODEL.get(plan, (0.0, 0.0))
    total = claim.get("total_charge", 0.0)
    member_id = claim.get("insured_id", claim.get("member_id", "?"))

    # Allowed amount: for this simulation, assume GEHA allowed = 85% of billed.
    allowed = round(total * 0.85, 2)

    # Remaining deductible for this member, given what's already been satisfied.
    paid_so_far = _OOP_ACCUM.get(member_id, 0.0)
    deduct_remaining = max(0.0, deduct_limit - paid_so_far)

    # Apply remaining deductible then coinsurance.
    applied_to_ded = min(deduct_remaining, allowed)
    after_ded = max(0.0, allowed - applied_to_ded)
    member_owed = round(applied_to_ded + after_ded * coins, 2)
    geha_pays = round(allowed - member_owed, 2)

    # Track member's satisfied deductible across claims.
    _OOP_ACCUM[member_id] = paid_so_far + applied_to_ded

    # Determine coverage status from the service lines.
    lines = claim.get("service_lines", [])
    any_not_covered = any(sl.get("cpt") in NOT_COVERED for sl in lines)
    all_covered = lines and not any_not_covered

    if all_covered:
        status = "PAID"
        note = "All service lines approved; benefits applied"
    else:
        # Some (not all) lines are non-covered -> partial payment.
        covered_charge = sum(
            sl["charge"] for sl in lines if sl.get("cpt") not in NOT_COVERED
        )
        status = "PARTIAL"
        note = (
            f"Covered ${covered_charge:.2f} of ${total:.2f} billed; "
            f"non-covered line(s) not payable"
        )

    trail.allowed_amount = allowed
    trail.member_responsibility = member_owed
    trail.log("ADJUDICATION", status, note)
    trail.log(
        "PAYMENT",
        "PASS" if status in ("PAID", "PARTIAL") else "DENY",
        f"GEHA pays ${geha_pays:.2f}; ERA to provider + EOB to member",
    )
    return status


def process_claim(claim: dict) -> AuditTrail:
    trail = AuditTrail(claim["claim_id"])

    trail.log("SUBMIT", "PASS", f"Received via EDI 39026 / {claim.get('plan')}")

    if not _stage_1_intake(claim, trail):
        trail.final_status = "DENIED"
        return trail
    if not _stage_2_eligibility(claim, trail):
        trail.final_status = "DENIED"
        return trail
    if not _stage_3_coding(claim, trail):
        trail.final_status = "DENIED"
        return trail

    if not _stage_4_manual_review(claim, trail):
        trail.final_status = "PENDING_REVIEW"
        return trail

    trail.final_status = _stage_5_adjudicate(claim, trail)
    return trail


def summarize(trails: list[AuditTrail], claims: list[dict]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for t in trails:
        counts[t.final_status] = counts.get(t.final_status, 0) + 1
    total_billed = sum(c["total_charge"] for c in claims)
    total_allowed = sum(
        t.allowed_amount for t in trails if t.final_status in ("PAID", "PARTIAL")
    )
    return {
        "status_counts": counts,
        "total_billed": round(total_billed, 2),
        "total_allowed": round(total_allowed, 2),
    }


def main():
    global _OOP_ACCUM
    _OOP_ACCUM = {}  # reset per-member deductible tracking each run
    claims = json.loads(CLAIMS_PATH.read_text())
    trails = [process_claim(c) for c in claims]

    print("=" * 72)
    print("GEHA CLAIMS ADJUDICATION SIMULATION")
    print("=" * 72)
    for c, t in zip(claims, trails):
        print(
            f"\n[{c['claim_id']}] {c['patient_name']}  |  "
            f"{c['diagnosis']['code']} {c['diagnosis']['description'][:35]}"
        )
        print(
            f"    Plan: {c['plan']} | Billed: ${c['total_charge']:.2f} | "
            f"Final: {t.final_status}"
        )
        for s in t.stages:
            flag = {"PASS": "OK ", "DENY": "X  ", "PENDING": "…  "}.get(
                s.status, s.status
            )
            print(f"    {flag} {s.name:22} {s.note}")

    s = summarize(trails, claims)
    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    for k, v in s["status_counts"].items():
        print(f"  {k:16} {v}")
    print(f"  Total billed : ${s['total_billed']:,.2f}")
    print(f"  Total allowed: ${s['total_allowed']:,.2f}")

    # Persist the audit trails
    out = []
    for c, t in zip(claims, trails):
        out.append(
            {
                "claim_id": c["claim_id"],
                "final_status": t.final_status,
                "allowed_amount": t.allowed_amount,
                "member_responsibility": t.member_responsibility,
                "stages": [
                    {"name": s.name, "status": s.status, "note": s.note}
                    for s in t.stages
                ],
            }
        )
    (Path(__file__).parent / "claims" / "audit_trails.json").write_text(
        json.dumps(out, indent=2)
    )
    print(f"\nWrote claims/audit_trails.json ({len(out)} trails)")


if __name__ == "__main__":
    main()
