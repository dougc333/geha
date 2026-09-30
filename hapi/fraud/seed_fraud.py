#!/usr/bin/env python3
"""Plant billing fraud in the local HAPI server at a chosen difficulty (synthetic data only).

Synthea's claims contain no fraud. Each level removes any earlier planting and adds
claims (ExplanationOfBenefit) shaped like Synthea's, unmarked in the FHIR data:

  1  obvious        upcoding at ~6x peers, a 26-hour day, billing after death, exact duplicates
  2  subtle         upcoding at 1.6x on half a provider's claims, a 14-visit day in a 10-hour
                    window, duplicates re-billed one day later, visits 2-3 weeks after death
  3  spread thin    small fraud by six existing Synthea providers: one exact duplicate each
                    (three providers) or three claims at 2.5x their own price (three providers)
  4  unnamed        schemes no analytics tool covers: unbundling (one lab visit split into four
                    claims), excessive frequency (weekly therapy for 26 weeks), phantom patients
                    (new patients with no other history, sharing one address)
  5  clean          nothing planted: tests false accusations

The answer key (guilty providers, schemes, keywords for scoring, planted resource ids) is
written to answer_key.json.

    python seed_fraud.py [--level 1-5]   # plant (removes an earlier planting first)
    python seed_fraud.py --reset         # remove the planted resources only
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
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

FHIR = "http://localhost:8080/fhir"
HERE = Path(__file__).resolve().parent
KEY = HERE / "answer_key.json"
SNOMED = "http://snomed.info/sct"
NPI = "http://hl7.org/fhir/sid/us-npi"
KEYWORDS = {
    "upcoding": ["upcod", "inflat", "peer", "higher than", "overbill", "overpa", "above"],
    "impossible_day": ["hour", "impossible", "overlap", "one day", "single day", "same day"],
    "after_death": ["death", "deceased", "died", "dead"],
    "duplicates": ["duplicat", "twice", "double", "re-bill", "rebill", "resubmit"],
    "unbundling": ["unbundl", "split", "fragment", "separate claim", "separately"],
    "excessive_frequency": ["frequen", "weekly", "excessive", "repeated", "every week", "overutil", "medically"],
    "phantom_patients": ["phantom", "ghost", "fictitious", "no other", "no history", "no prior",
                         "same address", "shared address", "fake"],
}
LEVELS = {
    1: ("Obvious", "Upcoding at ~6x peers, a 26-hour day, billing after death, exact duplicates."),
    2: ("Subtle", "Upcoding at 1.6x on half of one provider's claims, a 14-visit day in a 10-hour window, "
                  "duplicates re-billed one day later, visits 2-3 weeks after death."),
    3: ("Spread thin", "Six existing Synthea providers each add a little fraud: one exact duplicate, or "
                       "three claims at 2.5x their own usual price."),
    4: ("Unnamed schemes", "Schemes no analytics tool covers: unbundling, excessive frequency, phantom patients."),
    5: ("Clean", "No fraud planted; any accusation is a false positive."),
}


def request(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{FHIR}/{path}" if path else FHIR, data=data, method=method,
                                 headers={"Content-Type": "application/fhir+json"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        text = resp.read()
    return json.loads(text) if text else {}


def search_all(query: str) -> list[dict]:
    out, url = [], f"{FHIR}/{query}"
    while url:
        req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            bundle = json.load(resp)
        out += [e["resource"] for e in bundle.get("entry", [])]
        url = next((l["url"] for l in bundle.get("link", []) if l["relation"] == "next"), None)
    return out


def transaction(entries: list[dict]) -> list[str]:
    """POST entries as transactions (in chunks); returns the created references in order."""
    refs = []
    for i in range(0, len(entries), 150):
        result = request("POST", "", {"resourceType": "Bundle", "type": "transaction", "entry": entries[i:i + 150]})
        refs += [e["response"]["location"].split("/_history")[0] for e in result["entry"]]
    return refs


def reset() -> None:
    if not KEY.exists():
        return
    key = json.loads(KEY.read_text())
    # Claims first, then the patients/providers they reference.
    refs = sorted(key["planted_resources"], key=lambda r: not r.startswith("ExplanationOfBenefit/"))
    transaction([{"request": {"method": "DELETE", "url": ref}} for ref in refs])
    KEY.unlink()
    print(f"removed {len(refs)} planted resources (level {key.get('level')})")


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


class Planter:
    """Holds the live data and collects new resources plus the answer key for one level."""

    def __init__(self, level: int):
        self.rng = random.Random(1000 + level)
        self.level = level
        self.eobs = search_all("ExplanationOfBenefit?_count=1000")
        patients = search_all("Patient?_count=1000")
        self.alive = [p for p in patients if "deceasedDateTime" not in p]
        self.dead = sorted((p for p in patients if "deceasedDateTime" in p), key=lambda p: p["id"])
        self.insurer_of = {e["patient"]["reference"]: e["insurer"] for e in self.eobs}
        self.single = [e for e in self.eobs if len(e.get("item", [])) == 1
                       and e.get("payment", {}).get("amount", {}).get("value", 0) > 0]
        counts = Counter(self.code(e) for e in self.single)
        self.visit_code = counts.most_common(1)[0][0]
        peers = [e for e in self.single if self.code(e) == self.visit_code]
        self.visit_display = peers[0]["item"][0]["productOrService"]["coding"][0].get("display", "visit")
        self.peer_median = statistics.median(e["payment"]["amount"]["value"] for e in peers)
        self.template = peers[0]
        self.planted: list[str] = []
        self.guilty: dict[str, dict] = {}

    @staticmethod
    def code(eob: dict) -> str:
        return eob["item"][0]["productOrService"]["coding"][0]["code"]

    def insurer(self, patient: str) -> dict:
        return self.insurer_of.get(patient, self.template["insurer"])

    def provider(self, given: str, family: str, npi: str, org: str, city: str, gender: str) -> tuple[str, str, str]:
        refs = transaction([
            {"fullUrl": f"urn:uuid:prac-{npi}", "request": {"method": "POST", "url": "Practitioner"},
             "resource": {"resourceType": "Practitioner", "active": True, "identifier": [{"system": NPI, "value": npi}],
                          "name": [{"family": family, "given": [given], "prefix": ["Dr."]}], "gender": gender}},
            {"fullUrl": f"urn:uuid:org-{npi}", "request": {"method": "POST", "url": "Organization"},
             "resource": {"resourceType": "Organization", "active": True, "name": org,
                          "type": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/organization-type",
                                                "code": "prov", "display": "Healthcare Provider"}]}],
                          "address": [{"city": city, "state": "MO", "country": "US"}]}},
            {"fullUrl": f"urn:uuid:loc-{npi}", "request": {"method": "POST", "url": "Location"},
             "resource": {"resourceType": "Location", "status": "active", "name": org.upper(),
                          "address": {"city": city, "state": "MO", "country": "US"},
                          "managingOrganization": {"reference": f"urn:uuid:org-{npi}"}}},
        ])
        self.planted += refs
        return refs[0], refs[2], org.upper()

    def eob(self, patient: str, practitioner: str, location: str, facility: str, code: str, display: str,
            start: datetime, minutes: int, paid: float) -> dict:
        """An EOB shaped like Synthea's, with one service line."""
        item0 = self.template["item"][0]
        factor = paid / max(self.template["payment"]["amount"]["value"], 0.01)
        return {
            "resourceType": "ExplanationOfBenefit",
            "identifier": [{"system": "https://bluebutton.cms.gov/resources/variables/clm_id",
                            "value": f"{self.rng.getrandbits(128):032x}"}],
            "status": "active", "type": self.template["type"], "use": "claim",
            "patient": {"reference": patient},
            "billablePeriod": {"start": iso(start), "end": iso(start + timedelta(minutes=minutes))},
            "created": iso(start), "insurer": self.insurer(patient),
            "provider": {"reference": practitioner},
            "facility": {"reference": location, "display": facility},
            "outcome": "complete",
            "careTeam": [{"sequence": 1, "provider": {"reference": practitioner},
                          "role": self.template["careTeam"][0]["role"]}],
            "insurance": self.template.get("insurance", []),
            "item": [{
                "sequence": 1, "category": item0.get("category"),
                "productOrService": {"coding": [{"system": SNOMED, "code": code, "display": display}], "text": display},
                "servicedPeriod": {"start": iso(start), "end": iso(start + timedelta(minutes=minutes))},
                "locationCodeableConcept": item0.get("locationCodeableConcept"),
                "net": {"value": round(paid * 1.25, 2), "currency": "USD"},
                "adjudication": [{**a, "amount": {"value": round(a["amount"]["value"] * factor, 2), "currency": "USD"}}
                                 for a in copy.deepcopy(item0.get("adjudication", [])) if "amount" in a],
            }],
            "total": [{"category": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/adjudication",
                                                "code": "submitted", "display": "Submitted Amount"}],
                                    "text": "Submitted Amount"},
                       "amount": {"value": round(paid * 1.25, 2), "currency": "USD"}}],
            "payment": {"amount": {"value": round(paid, 2), "currency": "USD"}},
        }

    def clone(self, eob: dict, **changes) -> dict:
        """Copy of an existing claim with a new claim id (for duplicates of real claims)."""
        twin = {k: copy.deepcopy(v) for k, v in eob.items() if k not in ("id", "meta")}
        twin["identifier"] = [{"system": "https://bluebutton.cms.gov/resources/variables/clm_id",
                               "value": f"{self.rng.getrandbits(128):032x}"}]
        twin.update(changes)
        return twin

    def commit(self, claims: list[tuple[str, str, dict]]) -> None:
        """claims: (provider ref, scheme, EOB). Posts them and records the answer key."""
        self.rng.shuffle(claims)
        refs = transaction([{"request": {"method": "POST", "url": "ExplanationOfBenefit"}, "resource": c[2]}
                            for c in claims])
        self.planted += refs
        for (prov, scheme, eob), ref in zip(claims, refs):
            s = self.guilty[prov]["schemes"].setdefault(scheme, {"claims": 0, "paid": 0.0, "eobs": [],
                                                                 "keywords": KEYWORDS.get(scheme, [])})
            s["claims"] += 1
            s["paid"] = round(s["paid"] + eob["payment"]["amount"]["value"], 2)
            s["eobs"].append(ref)

    def mark(self, prov: str, name: str, details: dict[str, str]) -> None:
        self.guilty[prov] = {"name": name, "schemes": {}, "details": details}


def practitioner_name(ref: str) -> str:
    p = request("GET", ref)
    n = (p.get("name") or [{}])[0]
    return " ".join(n.get("prefix", []) + n.get("given", []) + [n.get("family", "")]).strip()


def level1(pl: Planter) -> list:
    rng, claims = pl.rng, []
    grayle, gloc, gfac = pl.provider("Vincent", "Grayle", "1932847561", "Summit Ridge Wellness Clinic", "Lee's Summit", "male")
    moravec, mloc, mfac = pl.provider("Lena", "Moravec", "1760394825", "Heartland Home Health", "Independence", "female")
    pl.mark(grayle, "Dr. Vincent Grayle", {"upcoding": f"{pl.visit_display} paid ~5-7x the peer median (${pl.peer_median:.2f})",
                                           "impossible_day": "26 one-hour visits between 07:00 and 20:00 on 2026-03-12"})
    pl.mark(moravec, "Dr. Lena Moravec", {"after_death": "home visits 1-10 months after 3 patients' deaths",
                                          "duplicates": "10 visits each submitted twice"})
    patients = rng.sample(pl.alive, 30)
    for i in range(45):
        patient = f"Patient/{patients[i % 30]['id']}"
        if i < 26:
            start, scheme = datetime(2026, 3, 12, 7, tzinfo=timezone.utc) + timedelta(minutes=30 * i), "impossible_day"
        else:
            start = datetime(2026, 1, 5, 9, tzinfo=timezone.utc) + timedelta(days=rng.randint(0, 230), hours=rng.randint(0, 7))
            if start.date() == datetime(2026, 3, 12).date():
                start += timedelta(days=1)
            scheme = "upcoding"
        claims.append((grayle, scheme, pl.eob(patient, grayle, gloc, gfac, pl.visit_code, pl.visit_display,
                                               start, 60, pl.peer_median * rng.uniform(5, 7))))
    for p in pl.dead[:3]:
        died = datetime.fromisoformat(p["deceasedDateTime"].replace("Z", "+00:00"))
        for _ in range(4):
            start = (died + timedelta(days=rng.randint(30, 300))).replace(hour=rng.randint(8, 16), minute=0, second=0)
            claims.append((moravec, "after_death", pl.eob(f"Patient/{p['id']}", moravec, mloc, mfac, "439708006",
                                                          "Home visit (procedure)", start, 45, pl.peer_median * rng.uniform(0.9, 1.3))))
    for p in rng.sample([p for p in pl.alive if p not in patients], 10):
        start = datetime(2026, 2, 2, tzinfo=timezone.utc) + timedelta(days=rng.randint(0, 200), hours=rng.randint(9, 15))
        eob = pl.eob(f"Patient/{p['id']}", moravec, mloc, mfac, "439708006", "Home visit (procedure)", start, 45,
                     pl.peer_median * rng.uniform(0.9, 1.3))
        claims += [(moravec, "duplicates", eob), (moravec, "duplicates", pl.clone(eob))]
    return claims


def level2(pl: Planter) -> list:
    rng, claims = pl.rng, []
    cast, cloc, cfac = pl.provider("Priya", "Castellan", "1497305268", "Lakeview Family Practice", "Blue Springs", "female")
    tread, tloc, tfac = pl.provider("Owen", "Treadwell", "1386027459", "Riverside Home Care", "Liberty", "male")
    pl.mark(cast, "Dr. Priya Castellan", {"upcoding": f"20 of 40 {pl.visit_display} claims paid 1.6x the peer median",
                                          "impossible_day": "14 one-hour visits between 07:00 and 17:00 on 2026-05-06"})
    pl.mark(tread, "Dr. Owen Treadwell", {"duplicates": "6 visits re-billed one day later (same patient, service, amount)",
                                          "after_death": "3 home visits 14-21 days after the patient's death"})
    patients = rng.sample(pl.alive, 35)
    for i in range(40):
        patient = f"Patient/{patients[i % 35]['id']}"
        if i < 14:  # the busy day, at normal prices
            start = datetime(2026, 5, 6, 7, tzinfo=timezone.utc) + timedelta(minutes=43 * i)
            scheme, paid = "impossible_day", pl.peer_median * rng.uniform(0.9, 1.1)
        else:
            start = datetime(2026, 1, 8, 9, tzinfo=timezone.utc) + timedelta(days=rng.randint(0, 230), hours=rng.randint(0, 7))
            if start.date() == datetime(2026, 5, 6).date():
                start += timedelta(days=1)
            upcoded = i < 34  # 20 upcoded, 6 normal
            scheme = "upcoding" if upcoded else "normal"
            paid = pl.peer_median * (rng.uniform(1.5, 1.7) if upcoded else rng.uniform(0.9, 1.1))
        claims.append((cast, scheme, pl.eob(patient, cast, cloc, cfac, pl.visit_code, pl.visit_display, start, 60, paid)))
    others = [p for p in pl.alive if p not in patients]
    for p in rng.sample(others, 10):  # normal home visits
        start = datetime(2026, 1, 12, 10, tzinfo=timezone.utc) + timedelta(days=rng.randint(0, 220))
        claims.append((tread, "normal", pl.eob(f"Patient/{p['id']}", tread, tloc, tfac, "439708006", "Home visit (procedure)",
                                               start, 45, pl.peer_median * rng.uniform(0.9, 1.2))))
    for p in rng.sample(others, 6):  # re-billed the next day
        start = datetime(2026, 2, 3, 11, tzinfo=timezone.utc) + timedelta(days=rng.randint(0, 200))
        eob = pl.eob(f"Patient/{p['id']}", tread, tloc, tfac, "439708006", "Home visit (procedure)", start, 45,
                     pl.peer_median * rng.uniform(0.9, 1.2))
        later = pl.clone(eob)
        for field in ("billablePeriod",):
            later[field] = {k: iso(datetime.fromisoformat(v) + timedelta(days=1)) for k, v in eob[field].items()}
        later["created"] = iso(datetime.fromisoformat(eob["created"]) + timedelta(days=1))
        later["item"][0]["servicedPeriod"] = later["billablePeriod"]
        claims += [(tread, "duplicates", eob), (tread, "duplicates", later)]
    p = pl.dead[3]
    died = datetime.fromisoformat(p["deceasedDateTime"].replace("Z", "+00:00"))
    for days in (14, 17, 21):
        start = (died + timedelta(days=days)).replace(hour=10, minute=0, second=0)
        claims.append((tread, "after_death", pl.eob(f"Patient/{p['id']}", tread, tloc, tfac, "439708006",
                                                    "Home visit (procedure)", start, 45, pl.peer_median)))
    return claims


def level3(pl: Planter) -> list:
    rng, claims = pl.rng, []
    by_provider = defaultdict(list)
    for e in pl.single:
        by_provider[e["provider"]["reference"]].append(e)
    # Synthea spreads claims thinly: only ~12 providers have 6+ paid single-service claims.
    busy = sorted((p for p, es in by_provider.items() if len(es) >= 6), key=lambda p: -len(by_provider[p]))
    chosen = rng.sample(busy, 6)
    for i, prov in enumerate(chosen):
        name = practitioner_name(prov)
        mine = by_provider[prov]
        if i < 3:  # one exact duplicate of a real claim
            original = rng.choice(mine)
            pl.mark(prov, name, {"duplicates": "one real claim submitted a second time (same patient, day, service, amount)"})
            claims.append((prov, "duplicates", pl.clone(original)))
        else:  # three claims at 2.5x the provider's own median for their most common service
            code = Counter(pl.code(e) for e in mine).most_common(1)[0][0]
            same = [e for e in mine if pl.code(e) == code]
            own_median = statistics.median(e["payment"]["amount"]["value"] for e in same)
            pl.mark(prov, name, {"upcoding": f"three claims billed at 2.5x the provider's usual price for service {code}"})
            for _ in range(3):
                base = rng.choice(same)
                start = datetime(2026, 1, 15, tzinfo=timezone.utc) + timedelta(days=rng.randint(0, 220), hours=rng.randint(8, 16))
                twin = pl.clone(base, created=iso(start),
                                billablePeriod={"start": iso(start), "end": iso(start + timedelta(minutes=30))})
                paid = own_median * 2.5
                factor = paid / max(base["payment"]["amount"]["value"], 0.01)
                twin["payment"] = {"amount": {"value": round(paid, 2), "currency": "USD"}}
                twin["item"][0]["servicedPeriod"] = twin["billablePeriod"]
                for adj in twin["item"][0].get("adjudication", []):
                    if "amount" in adj:
                        adj["amount"]["value"] = round(adj["amount"]["value"] * factor, 2)
                twin.pop("contained", None)
                twin.pop("referral", None)
                twin.pop("claim", None)
                for item in twin["item"]:
                    item.pop("encounter", None)
                claims.append((prov, "upcoding", twin))
    for prov_claims in claims:
        eob = prov_claims[2]
        for item in eob.get("item", []):
            item.pop("encounter", None)
        eob.pop("claim", None)
    return claims


def level4(pl: Planter) -> list:
    rng, claims = pl.rng, []
    ferrant, floc, ffac = pl.provider("Marcus", "Ferrant", "1245893016", "Crestline Diagnostics", "Grandview", "male")
    voss, vloc, vfac = pl.provider("Helena", "Voss", "1578204391", "Northgate Physical Therapy", "Raytown", "female")
    brandt, bloc, bfac = pl.provider("Silas", "Brandt", "1669137502", "Westport Wellness Group", "Kansas City", "male")
    pl.mark(ferrant, "Dr. Marcus Ferrant", {"unbundling": "12 lab visits each billed as 4 separate same-day claims"})
    pl.mark(voss, "Dr. Helena Voss", {"excessive_frequency": "5 patients billed physical therapy every week for 26 weeks"})
    pl.mark(brandt, "Dr. Silas Brandt", {"phantom_patients": "12 patients with no other history, all at one address, 3 visits each"})
    components = [("104485008", "Hemoglobin measurement"), ("167209002", "Platelet count"),
                  ("767002", "White blood cell count"), ("14089001", "Red blood cell count")]
    for p in rng.sample(pl.alive, 12):
        start = datetime(2026, 1, 20, 8, tzinfo=timezone.utc) + timedelta(days=rng.randint(0, 210), minutes=15 * rng.randint(0, 30))
        for code, display in components:
            claims.append((ferrant, "unbundling", pl.eob(f"Patient/{p['id']}", ferrant, floc, ffac, code, display,
                                                         start, 15, pl.peer_median * rng.uniform(0.35, 0.45))))
    for p in rng.sample(pl.alive, 5):
        first = datetime(2026, 1, 6, 9, tzinfo=timezone.utc) + timedelta(hours=rng.randint(0, 6))
        for week in range(26):
            claims.append((voss, "excessive_frequency", pl.eob(f"Patient/{p['id']}", voss, vloc, vfac, "91251008",
                                                               "Physical therapy procedure", first + timedelta(weeks=week),
                                                               45, pl.peer_median * rng.uniform(0.8, 1.0))))
    # Phantom patients: new Patient resources sharing one address, with no other records.
    given = ["Aaron", "Bella", "Carlos", "Diane", "Elijah", "Fiona", "Gavin", "Hana", "Isaac", "Joy", "Kyle", "Lena"]
    family = ["Porter", "Reyes", "Hale", "Moss", "Quinn", "Ward", "Stone", "Blake", "Frost", "Lane", "Pike", "Cole"]
    phantom_refs = transaction([
        {"request": {"method": "POST", "url": "Patient"}, "resource": {
            "resourceType": "Patient", "name": [{"given": [g], "family": f}],
            "gender": rng.choice(["male", "female"]), "birthDate": f"{rng.randint(1950, 2000)}-0{rng.randint(1, 9)}-1{rng.randint(0, 9)}",
            "address": [{"line": ["1400 Commerce Dr Suite 210"], "city": "Kansas City", "state": "MO", "postalCode": "64108"}]}}
        for g, f in zip(given, family)])
    pl.planted += phantom_refs
    for ref in phantom_refs:
        for _ in range(3):
            start = datetime(2026, 2, 1, 9, tzinfo=timezone.utc) + timedelta(days=rng.randint(0, 200), hours=rng.randint(0, 7))
            claims.append((brandt, "phantom_patients", pl.eob(ref, brandt, bloc, bfac, pl.visit_code, pl.visit_display,
                                                              start, 30, pl.peer_median * rng.uniform(0.9, 1.1))))
    return claims


def plant(level: int) -> dict:
    reset()
    pl = Planter(level)
    claims = {1: level1, 2: level2, 3: level3, 4: level4, 5: lambda _: []}[level](pl)
    # Scheme "normal" claims are cover for the guilty provider, not fraud themselves.
    real = [(p, s, e) for p, s, e in claims if s != "normal"]
    cover = [(p, s, e) for p, s, e in claims if s == "normal"]
    for p in {p for p, _, _ in cover}:
        pl.guilty[p]["schemes"].setdefault("normal", {"claims": 0, "paid": 0.0, "eobs": [], "keywords": []})
    if claims:
        pl.commit(real + cover)
        for p in pl.guilty.values():
            p["schemes"].pop("normal", None)
    title, description = LEVELS[level]
    key = {"level": level, "title": title, "description": description,
           "created_utc": datetime.now(timezone.utc).isoformat(),
           "peer_median_paid_for_visit": round(pl.peer_median, 2), "visit_code": pl.visit_code,
           "guilty": pl.guilty, "planted_resources": pl.planted}
    KEY.write_text(json.dumps(key, indent=2) + "\n")
    return key


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--level", type=int, choices=range(1, 6), default=1)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    if args.reset:
        reset()
        return
    key = plant(args.level)
    n = sum(1 for r in key["planted_resources"] if r.startswith("ExplanationOfBenefit/"))
    print(f"level {key['level']} ({key['title']}): planted {n} claims; guilty providers: {len(key['guilty'])}")
    for prov, g in key["guilty"].items():
        for scheme, s in g["schemes"].items():
            print(f"  {g['name']} ({prov}) {scheme}: {s['claims']} claims, ${s['paid']:,.2f}")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as exc:
        sys.exit(f"HAPI not reachable at {FHIR}: {exc}")
