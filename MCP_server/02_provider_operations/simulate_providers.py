"""
Simulation — Provider Operations (Flow 2).

Processes provider applications through enrollment -> credentialing ->
contracting -> directory, mirroring functional_spec.md. Deterministic,
rule-based. Emits a provider roster + credentialing event log.

Usage:
    python simulate_providers.py
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

random.seed(13)
HERE = Path(__file__).parent

# OIG / state Medicaid exclusion lists (fabricated identifiers to screen)
EXCLUDED_NPIS = {"9999999999", "8888888888", "1234567890"}

# Provider applications: name, NPI, state license present?, board cert?, malprac?
PROVIDERS = [
    {"name": "Dr. A. Bennett", "npi": "1982635411", "license": True, "board": True, "malpractice": True},
    {"name": "Dr. S. Chen", "npi": "1674892022", "license": True, "board": True, "malpractice": True},
    {"name": "Dr. R. Gupta", "npi": "1325478890", "license": True, "board": True, "malpractice": True},
    {"name": "Dr. L. Okafor", "npi": "1452378901", "license": True, "board": False, "malpractice": True},
    {"name": "Dr. J. Miller", "npi": "1098723456", "license": True, "board": True, "malpractice": True},
    {"name": "Dr. T. Alvarez", "npi": "1554981234", "license": True, "board": True, "malpractice": False},
    {"name": "Dr. M. Park", "npi": "1876543290", "license": False, "board": True, "malpractice": True},
    {"name": "Dr. K. Singh", "npi": "1432569871", "license": True, "board": True, "malpractice": True},
    # A sanctioned provider (should be rejected)
    {"name": "Dr. X. Fraud", "npi": "8888888888", "license": True, "board": True, "malpractice": True},
    # An out-of-network-only provider (credentialed but not contracted)
    {"name": "Dr. Y. Solo", "npi": "1765432190", "license": True, "board": True, "malpractice": True},
]

FACILITIES = [
    "St. Mary's Medical Center", "Community Health Clinic", "Capital Physician Group",
    "Fairfax Family Practice", "Apex Orthopedic Associates", "Midwest Cardiology Clinic",
]


@dataclass
class ProviderRecord:
    npi: str
    name: str
    status: str
    network: str = "OUT_OF_NETWORK"
    allowed_factor: float = 0.85      # participates at 85% of billed
    facility: str = ""


@dataclass
class ProviderEvent:
    npi: str
    stage: str
    status: str
    note: str


@dataclass
class ProviderRun:
    events: list[ProviderEvent] = field(default_factory=list)
    providers: dict[str, ProviderRecord] = field(default_factory=dict)

    def log(self, npi, stage, status, note=""):
        self.events.append(ProviderEvent(npi, stage, status, note))


def run():
    run = ProviderRun()

    for p in PROVIDERS:
        npi = p["npi"]
        rec = ProviderRecord(npi=npi, name=p["name"], status="PENDING",
                             facility=random.choice(FACILITIES))
        run.providers[npi] = rec

        # Stage 1 — Enrollment + exclusion screening
        if npi in EXCLUDED_NPIS:
            rec.status = "REJECTED"
            run.log(npi, "ENROLLMENT", "REJECT", "Sanctions/exclusion-list hit (OIG)")
            continue
        run.log(npi, "ENROLLMENT", "OK", "Application complete; no exclusion hit")

        # Stage 2 — Credentialing
        ok = True
        if not p["license"]:
            run.log(npi, "CREDENTIALING", "FAIL", "State license not verified")
            ok = False
        if not p["board"]:
            run.log(npi, "CREDENTIALING", "FLAG", "Board certification missing (non-fatal)")
        if not p["malpractice"]:
            run.log(npi, "CREDENTIALING", "FAIL", "Insufficient malpractice coverage")
            ok = False
        if ok:
            run.log(npi, "CREDENTIALING", "OK", "License, board, malpractice verified")
            rec.status = "CREDENTIALED"
        else:
            rec.status = "REJECTED"
            continue

        # Stage 3 — Network contracting
        if p["name"].startswith("Dr. Y."):
            rec.network = "OUT_OF_NETWORK"
            run.log(npi, "CONTRACTING", "OK", "Credentialed but practicing out-of-network")
        else:
            rec.network = "IN_NETWORK"
            rec.allowed_factor = 0.85
            run.log(npi, "CONTRACTING", "OK", f"Participating contract; allowed = 85% of billed")

        # Stage 4 — Directory
        run.log(npi, "DIRECTORY", "OK", f"Directory entry active at {rec.facility}")

        # Stage 5 — State
        run.log(npi, "STATE", rec.status, f"Provider {rec.status}")

    # Persist
    roster = []
    for r in run.providers.values():
        roster.append({"npi": r.npi, "name": r.name, "status": r.status,
                       "network": r.network, "allowed_factor": r.allowed_factor,
                       "facility": r.facility})
    (HERE / "providers.json").write_text(json.dumps(roster, indent=2))
    events = [{"npi": e.npi, "stage": e.stage, "status": e.status, "note": e.note}
              for e in run.events]
    (HERE / "provider_events.json").write_text(json.dumps(events, indent=2))

    # Summarize this run, not the illustrative response template.
    response = {
        "flow": HERE.name,
        "example_only": False,
        "data_provenance": "Computed from this simulator run; underlying inputs are fabricated.",
        "execution_status": "completed",
        "simulation_only": True,
        "summary": {
            "providers_processed": len(roster),
            "credentialed": sum(r["status"] == "CREDENTIALED" for r in roster),
            "rejected": sum(r["status"] == "REJECTED" for r in roster),
            "in_network": sum(r["status"] == "CREDENTIALED" and r["network"] == "IN_NETWORK" for r in roster),
            "out_of_network": sum(r["status"] == "CREDENTIALED" and r["network"] == "OUT_OF_NETWORK" for r in roster),
        },
        "outputs": ["providers.json", "provider_events.json"],
    }
    (HERE / "mcp_response.json").write_text(
        json.dumps(response, indent=2) + "\n", encoding="utf-8"
    )


    print("=" * 70)
    print("PROVIDER OPERATIONS — SIMULATION (Flow 2)")
    print("=" * 70)
    for r in run.providers.values():
        print(f"[{r.npi}] {r.name:18} {r.status:14} {r.network:16} "
              f"allowed={r.allowed_factor:.0%}  {r.facility[:28]}")
    in_net = sum(1 for r in run.providers.values() if r.network == "IN_NETWORK")
    cred = sum(1 for r in run.providers.values() if r.status == "CREDENTIALED")
    rej = sum(1 for r in run.providers.values() if r.status == "REJECTED")
    print(f"\nCredentialed: {cred} | In-network: {in_net} | Rejected: {rej} | "
          f"events: {len(run.events)}")
    print(f"Wrote providers.json + provider_events.json to {HERE.name}/")


if __name__ == "__main__":
    run()
