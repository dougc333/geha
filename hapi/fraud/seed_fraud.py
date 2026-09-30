#!/usr/bin/env python3
"""Plant billing-fraud schemes in the local HAPI server (synthetic data only).

Synthea's claims contain no fraud, so this adds two made-up providers whose claims
(ExplanationOfBenefit) follow four common fraud patterns, built in the same shape as
Synthea's own EOBs so they aren't obvious from the format:

  A  Dr. Vincent Grayle, Summit Ridge Wellness Clinic
     - upcoding: the most common visit type billed at ~5-7x what peers are paid
     - impossible day: 26 one-hour visits on 2026-03-12 inside a 13-hour window
  B  Dr. Lena Moravec, Heartland Home Health
     - billing after death: home visits for 3 deceased patients, months after death
     - duplicate billing: 10 visits each submitted twice (same patient/day/service/amount)

Nothing in the FHIR data marks these records. The answer key (resource ids, counts,
dollars) is written to answer_key.json next to this file, for scoring the agent.

    python seed_fraud.py            # plant (removes an earlier planting first)
    python seed_fraud.py --reset    # remove the planted resources only
"""

from __future__ import annotations

import argparse
import copy
import json
import random
import statistics
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

FHIR = "http://localhost:8080/fhir"
HERE = Path(__file__).resolve().parent
KEY = HERE / "answer_key.json"
SNOMED = "http://snomed.info/sct"
NPI = "http://hl7.org/fhir/sid/us-npi"
rng = random.Random(7)


def request(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{FHIR}/{path}" if path else FHIR, data=data, method=method,
                                 headers={"Content-Type": "application/fhir+json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        text = resp.read()
    return json.loads(text) if text else {}


def search_all(query: str) -> list[dict]:
    out, url = [], f"{FHIR}/{query}"
    while url:
        with urllib.request.urlopen(url, timeout=120) as resp:
            bundle = json.load(resp)
        out += [e["resource"] for e in bundle.get("entry", [])]
        url = next((l["url"] for l in bundle.get("link", []) if l["relation"] == "next"), None)
    return out


def reset() -> None:
    if not KEY.exists():
        return
    key = json.loads(KEY.read_text())
    entries = [{"request": {"method": "DELETE", "url": ref}} for ref in reversed(key["planted_resources"])]
    for i in range(0, len(entries), 200):
        request("POST", "", {"resourceType": "Bundle", "type": "transaction", "entry": entries[i:i + 200]})
    KEY.unlink()
    print(f"removed {len(entries)} planted resources")


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def provider_resources(name: tuple[str, str], npi: str, org_name: str, city: str) -> list[dict]:
    """Practitioner + Organization + Location, created with temporary ids in a transaction."""
    given, family = name
    return [
        {"fullUrl": f"urn:uuid:prac-{npi}", "request": {"method": "POST", "url": "Practitioner"},
         "resource": {"resourceType": "Practitioner", "active": True,
                      "identifier": [{"system": NPI, "value": npi}],
                      "name": [{"family": family, "given": [given], "prefix": ["Dr."]}],
                      "gender": "male" if given == "Vincent" else "female"}},
        {"fullUrl": f"urn:uuid:org-{npi}", "request": {"method": "POST", "url": "Organization"},
         "resource": {"resourceType": "Organization", "active": True, "name": org_name,
                      "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type",
                                            "code": "prov", "display": "Healthcare Provider"}]}],
                      "address": [{"city": city, "state": "MO", "country": "US"}]}},
        {"fullUrl": f"urn:uuid:loc-{npi}", "request": {"method": "POST", "url": "Location"},
         "resource": {"resourceType": "Location", "status": "active", "name": org_name.upper(),
                      "address": {"city": city, "state": "MO", "country": "US"},
                      "managingOrganization": {"reference": f"urn:uuid:org-{npi}"}}},
    ]


def make_eob(template: dict, patient: str, practitioner: str, location: str, facility_name: str,
             code: str, display: str, start: datetime, minutes: int, paid: float, insurer: dict) -> dict:
    """An EOB shaped like Synthea's, with one service line."""
    item0 = template["item"][0]
    factor = paid / max(template["payment"]["amount"]["value"], 0.01)
    item = {
        "sequence": 1,
        "category": item0.get("category"),
        "productOrService": {"coding": [{"system": SNOMED, "code": code, "display": display}], "text": display},
        "servicedPeriod": {"start": iso(start), "end": iso(start + timedelta(minutes=minutes))},
        "locationCodeableConcept": item0.get("locationCodeableConcept"),
        "net": {"value": round(paid * 1.25, 2), "currency": "USD"},
        "adjudication": [
            {**adj, "amount": {"value": round(adj["amount"]["value"] * factor, 2), "currency": "USD"}}
            for adj in copy.deepcopy(item0.get("adjudication", [])) if "amount" in adj
        ],
    }
    return {
        "resourceType": "ExplanationOfBenefit",
        "identifier": [{"system": "https://bluebutton.cms.gov/resources/variables/clm_id",
                        "value": f"{rng.getrandbits(128):032x}"}],
        "status": "active", "type": template["type"], "use": "claim",
        "patient": {"reference": patient},
        "billablePeriod": {"start": iso(start), "end": iso(start + timedelta(minutes=minutes))},
        "created": iso(start), "insurer": insurer,
        "provider": {"reference": practitioner},
        "facility": {"reference": location, "display": facility_name},
        "outcome": "complete",
        "careTeam": [{"sequence": 1, "provider": {"reference": practitioner},
                      "role": template["careTeam"][0]["role"]}],
        "insurance": template.get("insurance", []),
        "item": [item],
        "total": [{"category": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/adjudication",
                                            "code": "submitted", "display": "Submitted Amount"}],
                                "text": "Submitted Amount"},
                   "amount": {"value": round(paid * 1.25, 2), "currency": "USD"}}],
        "payment": {"amount": {"value": round(paid, 2), "currency": "USD"}},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    reset()
    if args.reset:
        return

    eobs = search_all("ExplanationOfBenefit?_count=1000")
    patients = search_all("Patient?_count=1000")
    alive = [p for p in patients if "deceasedDateTime" not in p]
    dead = sorted((p for p in patients if "deceasedDateTime" in p), key=lambda p: p["id"])
    insurer_of = {e["patient"]["reference"]: e["insurer"] for e in eobs}

    # The most common single-service visit type, and what peers are paid for it.
    single = [e for e in eobs if len(e.get("item", [])) == 1
              and e.get("payment", {}).get("amount", {}).get("value", 0) > 0]
    code_counts = Counter(e["item"][0]["productOrService"]["coding"][0]["code"] for e in single)
    visit_code, _ = code_counts.most_common(1)[0]
    peer = [e for e in single if e["item"][0]["productOrService"]["coding"][0]["code"] == visit_code]
    visit_display = peer[0]["item"][0]["productOrService"]["coding"][0].get("display", "visit")
    peer_median = statistics.median(e["payment"]["amount"]["value"] for e in peer)
    template = peer[0]

    # Providers
    created = request("POST", "", {"resourceType": "Bundle", "type": "transaction", "entry":
                      provider_resources(("Vincent", "Grayle"), "1932847561", "Summit Ridge Wellness Clinic", "Lee's Summit")
                      + provider_resources(("Lena", "Moravec"), "1760394825", "Heartland Home Health", "Independence")})
    refs = [e["response"]["location"].split("/_history")[0] for e in created["entry"]]
    grayle, _grayle_org, grayle_loc, moravec, _moravec_org, moravec_loc = refs
    planted = list(refs)

    entries, key_claims = [], {"upcoding": [], "impossible_day": [], "after_death": [], "duplicates": []}

    def add(eob: dict, scheme: str) -> None:
        entries.append({"request": {"method": "POST", "url": "ExplanationOfBenefit"}, "resource": eob,
                        "scheme": scheme})

    # A. Grayle: 45 upcoded visits; 26 of them on 2026-03-12 in a 07:00-20:00 window.
    grayle_patients = rng.sample(alive, 30)
    for i in range(45):
        patient = f"Patient/{grayle_patients[i % 30]['id']}"
        if i < 26:
            start = datetime(2026, 3, 12, 7, 0, tzinfo=timezone.utc) + timedelta(minutes=30 * i)
            scheme = "impossible_day"
        else:
            start = datetime(2026, 1, 5, 9, tzinfo=timezone.utc) + timedelta(days=rng.randint(0, 230), hours=rng.randint(0, 7))
            if start.date() == datetime(2026, 3, 12).date():  # keep the impossible day at exactly 26
                start += timedelta(days=1)
            scheme = "upcoding"
        paid = peer_median * rng.uniform(5, 7)
        add(make_eob(template, patient, grayle, grayle_loc, "SUMMIT RIDGE WELLNESS CLINIC", visit_code,
                     visit_display, start, 60, paid, insurer_of.get(patient, template["insurer"])), scheme)

    # B1. Moravec: home visits for 3 deceased patients, 1-10 months after death.
    for p in dead[:3]:
        died = datetime.fromisoformat(p["deceasedDateTime"].replace("Z", "+00:00"))
        for _ in range(4):
            start = (died + timedelta(days=rng.randint(30, 300))).replace(hour=rng.randint(8, 16), minute=0, second=0)
            add(make_eob(template, f"Patient/{p['id']}", moravec, moravec_loc, "HEARTLAND HOME HEALTH",
                         "439708006", "Home visit (procedure)", start, 45, peer_median * rng.uniform(0.9, 1.3),
                         insurer_of.get(f"Patient/{p['id']}", template["insurer"])), "after_death")

    # B2. Moravec: 10 home visits for living patients, each submitted twice.
    for p in rng.sample([p for p in alive if p not in grayle_patients], 10):
        start = datetime(2026, 2, 2, tzinfo=timezone.utc) + timedelta(days=rng.randint(0, 200), hours=rng.randint(9, 15))
        eob = make_eob(template, f"Patient/{p['id']}", moravec, moravec_loc, "HEARTLAND HOME HEALTH",
                       "439708006", "Home visit (procedure)", start, 45, peer_median * rng.uniform(0.9, 1.3),
                       insurer_of.get(f"Patient/{p['id']}", template["insurer"]))
        twin = copy.deepcopy(eob)
        twin["identifier"][0]["value"] = f"{rng.getrandbits(128):032x}"
        add(eob, "duplicates")
        add(twin, "duplicates")

    rng.shuffle(entries)
    schemes = [e.pop("scheme") for e in entries]
    result = request("POST", "", {"resourceType": "Bundle", "type": "transaction", "entry": entries})
    for scheme, entry, e in zip(schemes, result["entry"], entries):
        ref = entry["response"]["location"].split("/_history")[0]
        planted.append(ref)
        key_claims[scheme].append({"eob": ref, "patient": e["resource"]["patient"]["reference"],
                                   "date": e["resource"]["created"][:10],
                                   "paid": e["resource"]["payment"]["amount"]["value"]})

    total = lambda xs: round(sum(x["paid"] for x in xs), 2)  # noqa: E731
    key = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "peer_median_paid_for_visit": round(peer_median, 2),
        "visit_code": visit_code, "visit_display": visit_display,
        "providers": {
            grayle: {"name": "Dr. Vincent Grayle", "npi": "1932847561", "facility": "Summit Ridge Wellness Clinic",
                     "location": grayle_loc, "schemes": ["upcoding", "impossible_day"]},
            moravec: {"name": "Dr. Lena Moravec", "npi": "1760394825", "facility": "Heartland Home Health",
                      "location": moravec_loc, "schemes": ["after_death", "duplicates"]},
        },
        "schemes": {
            "upcoding": {"provider": grayle, "claims": 45, "paid": total(key_claims["upcoding"] + key_claims["impossible_day"]),
                         "detail": f"{visit_display} ({visit_code}) paid ~5-7x the peer median of ${peer_median:.2f}"},
            "impossible_day": {"provider": grayle, "claims": 26, "date": "2026-03-12", "billed_hours": 26,
                               "detail": "26 one-hour visits between 07:00 and 20:00 on 2026-03-12"},
            "after_death": {"provider": moravec, "claims": 12, "paid": total(key_claims["after_death"]),
                            "patients": sorted({c["patient"] for c in key_claims["after_death"]}),
                            "detail": "home visits 1-10 months after each patient's death"},
            "duplicates": {"provider": moravec, "pairs": 10, "claims": 20, "overpaid": round(total(key_claims["duplicates"]) / 2, 2),
                           "detail": "10 visits each submitted twice: same patient, day, service and amount"},
        },
        "claims": key_claims,
        "planted_resources": planted,
    }
    KEY.write_text(json.dumps(key, indent=2) + "\n")
    print(f"planted {len(entries)} claims for 2 providers ({grayle}, {moravec}); answer key: {KEY.name}")
    for name, s in key["schemes"].items():
        print(f"  {name}: {s['detail']}")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as exc:
        sys.exit(f"HAPI not reachable at {FHIR}: {exc}")
