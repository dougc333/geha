#!/usr/bin/env python3
"""Plant claimant statements in the local HAPI server so claim insights have something to find.

Synthea writes only the provider side of a medical history: no condition is asserted by
the patient, and there is no claimant correspondence. This adds, for four patients with
an active chronic condition, a claimant statement (a DocumentReference authored by the
patient) and the condition it reports (a Condition with asserter = the patient):

  status      the claimant reports as ongoing a condition the provider recorded as resolved
  refuted     the provider ruled the condition out (a planted provider Condition with
              verificationStatus refuted), the claimant reports it as confirmed
  unrecorded  the claimant reports a condition with no provider record at all
  agrees      the claimant reports the primary condition the provider also has active
              (a control: it must not be flagged)

Every planted resource carries the tag urn:geha:claim-insights|seed. The expected
conflicts are written to answer_key.json.

    python seed_claimant.py           # plant (removes an earlier planting first)
    python seed_claimant.py --reset   # remove the planted resources only
"""

from __future__ import annotations

import argparse
import base64
import json
import random
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

FHIR = "http://localhost:8080/fhir"
HERE = Path(__file__).resolve().parent
KEY = HERE / "answer_key.json"
SNOMED = "http://snomed.info/sct"
TAG = {"system": "urn:geha:claim-insights", "code": "seed"}
CLINICAL = "http://terminology.hl7.org/CodeSystem/condition-clinical"
VERIFICATION = "http://terminology.hl7.org/CodeSystem/condition-ver-status"
# Chronic conditions that can be a disability claim's primary condition, most likely first.
PRIMARY = ["88805009", "414545008", "124171000119105", "195967001", "44054006", "59621000",
           "237602007", "55822004", "40055000"]
REFUTED = ("278860009", "Chronic low back pain (finding)")
UNRECORDED = ("203082005", "Fibromyalgia (disorder)")


def request(method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{FHIR}/{path}" if path else FHIR, data=data, method=method,
                                 headers={"Content-Type": "application/fhir+json", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        text = resp.read()
    return json.loads(text) if text else {}


def search_all(resource: str, **params) -> list[dict]:
    out, url = [], f"{FHIR}/{resource}?" + urllib.parse.urlencode({"_count": 1000, **params})
    while url:
        req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            bundle = json.load(resp)
        out += [e["resource"] for e in bundle.get("entry", [])]
        url = next((l["url"] for l in bundle.get("link", []) if l["relation"] == "next"), None)
    return out


def transaction(entries: list[dict]) -> list[str]:
    result = request("POST", "", {"resourceType": "Bundle", "type": "transaction", "entry": entries})
    return [e["response"]["location"].split("/_history")[0] for e in result["entry"]]


def reset() -> None:
    tag = f"{TAG['system']}|{TAG['code']}"
    # Conditions point at the statements (Condition.evidence), so they go first.
    for resource in ("Condition", "DocumentReference"):
        refs = [f"{resource}/{r['id']}" for r in search_all(resource, _tag=tag, _elements="id")]
        if refs:
            transaction([{"request": {"method": "DELETE", "url": ref}} for ref in refs])
            print(f"removed {len(refs)} planted {resource}")
    KEY.unlink(missing_ok=True)


def status_of(cond: dict, field: str) -> str:
    return cond.get(field, {}).get("coding", [{}])[0].get("code", "")


def code_of(cond: dict) -> tuple[str, str]:
    c = cond["code"]["coding"][0]
    return c["code"], c.get("display", c["code"])


def concept(code: str, display: str) -> dict:
    return {"coding": [{"system": SNOMED, "code": code, "display": display}], "text": display}


def statement(n: int, patient: dict, date: datetime, text: str) -> dict:
    """A claimant statement: correspondence authored by the patient, text inline."""
    name = patient["name"][0]
    return {
        "fullUrl": f"urn:uuid:statement-{n}", "request": {"method": "POST", "url": "DocumentReference"},
        "resource": {
            "resourceType": "DocumentReference", "meta": {"tag": [TAG]}, "status": "current",
            "type": {"coding": [{"system": "http://loinc.org", "code": "34109-9", "display": "Note"}],
                     "text": "Claimant correspondence"},
            "subject": {"reference": f"Patient/{patient['id']}"}, "date": date.isoformat(),
            "author": [{"reference": f"Patient/{patient['id']}",
                        "display": f"{' '.join(name.get('given', []))} {name.get('family', '')}".strip()}],
            "description": "Claimant statement",
            "content": [{"attachment": {"contentType": "text/plain", "title": f"Claimant statement {date:%b %d, %Y}",
                                        "data": base64.b64encode(text.encode()).decode()}}],
        },
    }


def claimant_condition(n: int, patient: dict, code: str, display: str, date: datetime, note: str) -> dict:
    return {
        "request": {"method": "POST", "url": "Condition"},
        "resource": {
            "resourceType": "Condition", "meta": {"tag": [TAG]},
            "clinicalStatus": {"coding": [{"system": CLINICAL, "code": "active"}]},
            "verificationStatus": {"coding": [{"system": VERIFICATION, "code": "confirmed"}]},
            "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-category",
                                      "code": "problem-list-item", "display": "Problem List Item"}]}],
            "code": concept(code, display), "subject": {"reference": f"Patient/{patient['id']}"},
            "asserter": {"reference": f"Patient/{patient['id']}"}, "recordedDate": date.isoformat(),
            "evidence": [{"detail": [{"reference": f"urn:uuid:statement-{n}"}]}], "note": [{"text": note}],
        },
    }


def plant() -> None:
    reset()
    rng = random.Random(42)
    patients = {p["id"]: p for p in search_all("Patient") if "deceasedDateTime" not in p}
    conditions: dict[str, list[dict]] = {}
    for c in search_all("Condition"):
        conditions.setdefault(c["subject"]["reference"].split("/")[1], []).append(c)

    candidates = []  # (patient id, primary condition), alive patients with an active chronic condition
    for pid in sorted(patients):
        active = {code_of(c)[0]: c for c in conditions.get(pid, []) if status_of(c, "clinicalStatus") == "active"}
        primary = next((active[code] for code in PRIMARY if code in active), None)
        if primary:
            candidates.append((pid, primary))
    rng.shuffle(candidates)

    def codes(pid: str) -> set[str]:
        return {code_of(c)[0] for c in conditions.get(pid, [])}

    def resolved_disorder(pid: str) -> dict | None:
        """The latest resolved disorder the provider has not also recorded as active (recurrences)."""
        active = {code_of(c)[0] for c in conditions.get(pid, []) if status_of(c, "clinicalStatus") == "active"}
        done = [c for c in conditions.get(pid, []) if status_of(c, "clinicalStatus") == "resolved"
                and "(disorder)" in code_of(c)[1] and code_of(c)[0] not in active]
        return max(done, key=lambda c: c.get("abatementDateTime", ""), default=None)

    plan, used = [], set()
    for kind in ("status", "refuted", "unrecorded", "agrees"):
        for pid, primary in candidates:
            if pid in used or (kind == "status" and not resolved_disorder(pid)) \
                    or (kind == "refuted" and REFUTED[0] in codes(pid)) \
                    or (kind == "unrecorded" and UNRECORDED[0] in codes(pid)):
                continue
            plan.append((kind, pid, primary))
            used.add(pid)
            break
    if len(plan) < 4:
        raise SystemExit("not enough living patients with an active chronic condition; load more with load_synthea.sh")

    entries, key = [], []
    for n, (kind, pid, primary) in enumerate(plan):
        patient = patients[pid]
        pcode, pname = code_of(primary)
        encounters = sorted(search_all("Encounter", subject=f"Patient/{pid}", _elements="period,participant"),
                            key=lambda e: e["period"]["start"])
        last = encounters[-1]
        date = datetime.fromisoformat(last["period"]["start"]) + timedelta(days=rng.randint(10, 40))
        expect = {"patient": f"Patient/{pid}", "kind": kind, "primary": pname}
        if kind == "status":
            gone = resolved_disorder(pid)
            code, name = code_of(gone)
            text = f"I still have {name.split(' (')[0].lower()}. It never went away and it stops me working."
            expect.update(condition=name, provider_record=f"Condition/{gone['id']}")
        elif kind == "refuted":
            code, name = REFUTED
            practitioner = last["participant"][0]["individual"]
            entries.append({"request": {"method": "POST", "url": "Condition"}, "resource": {
                "resourceType": "Condition", "meta": {"tag": [TAG]},
                "clinicalStatus": {"coding": [{"system": CLINICAL, "code": "inactive"}]},
                "verificationStatus": {"coding": [{"system": VERIFICATION, "code": "refuted"}]},
                "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-category",
                                          "code": "encounter-diagnosis", "display": "Encounter Diagnosis"}]}],
                "code": concept(code, name), "subject": {"reference": f"Patient/{pid}"},
                "encounter": {"reference": f"Encounter/{last['id']}"},
                "recorder": {"reference": practitioner["reference"], "display": practitioner.get("display", "")},
                "recordedDate": last["period"]["start"],
                "note": [{"text": "Back exam normal, full range of motion; chronic back pain ruled out."}]}})
            text = "My back pain is constant and I cannot sit or stand for more than twenty minutes."
            expect.update(condition=name)
        elif kind == "unrecorded":
            code, name = UNRECORDED
            text = "I was told I have fibromyalgia. The pain all over my body keeps me from working."
            expect.update(condition=name)
        else:
            code, name = pcode, pname
            text = f"My {name.split(' (')[0].lower()} is the reason I cannot work right now."
            expect.update(condition=name)
        entries.append(statement(n, patient, date, text))
        entries.append(claimant_condition(n, patient, code, name, date, text))
        key.append(expect)

    refs = transaction(entries)
    KEY.write_text(json.dumps({"expected": key, "planted_resources": refs}, indent=2) + "\n")
    for k in key:
        print(f"{k['kind']:<10} {k['patient']:<15} {k['condition']}   (primary: {k['primary']})")
    print(f"planted {len(refs)} resources; answer key in {KEY.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="remove the planted resources only")
    args = parser.parse_args()
    reset() if args.reset else plant()


if __name__ == "__main__":
    main()
