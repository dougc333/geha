#!/usr/bin/env python3
"""Find claim insights in the local HAPI server: conflicting reports and new comorbidities.

  Conflicting report  a condition the claimant asserts (Condition.asserter = the patient)
                      that provider records disagree with: the provider recorded it as
                      resolved or inactive, ruled it out (verificationStatus refuted), or
                      has no record of it.
  New comorbidity     an active disorder whose onset is after the claimant's primary
                      condition (the first active one in PRIMARY, or --primary).

Each insight names its source documents: the claimant statement (Condition.evidence) and
the provider note for the condition's encounter (DocumentReference?encounter=...).

    python find_insights.py                       # patients with claimant statements
    python find_insights.py --patient Patient/123 # one patient, with or without statements
    python find_insights.py --since 2015-01-01    # only comorbidities with onset since then
    python find_insights.py --check               # compare conflicts with answer_key.json
    python find_insights.py --json
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path

FHIR = "http://localhost:8080/fhir"
KEY = Path(__file__).resolve().parent / "answer_key.json"
PRIMARY = ["88805009", "414545008", "124171000119105", "195967001", "44054006", "59621000",
           "237602007", "55822004", "40055000"]  # same order as seed_claimant.py
INACTIVE = {"resolved", "inactive", "remission"}
NOT_DISABLING = {"37320007", "196416002"}  # loss of teeth, impacted molars: Synthea dental noise


def search_all(resource: str, **params) -> list[dict]:
    out, url = [], f"{FHIR}/{resource}?" + urllib.parse.urlencode({"_count": 1000, **params})
    while url:
        req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            bundle = json.load(resp)
        out += [e["resource"] for e in bundle.get("entry", [])]
        url = next((l["url"] for l in bundle.get("link", []) if l["relation"] == "next"), None)
    return out


def read(ref: str) -> dict:
    req = urllib.request.Request(f"{FHIR}/{ref}", headers={"Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def status(cond: dict, field: str) -> str:
    return cond.get(field, {}).get("coding", [{}])[0].get("code", "")


def code(cond: dict) -> str:
    return cond["code"]["coding"][0]["code"]


def name(cond: dict) -> str:
    c = cond["code"]["coding"][0]
    return c.get("display", c["code"]).split(" (")[0]


def onset(cond: dict) -> str:
    return (cond.get("onsetDateTime") or cond.get("recordedDate") or "")[:10]


class Patient:
    """One claimant's conditions, split by who asserted them, plus document look-ups."""

    def __init__(self, ref: str):
        self.ref = ref
        conditions = search_all("Condition", subject=ref)
        self.claimant = [c for c in conditions if c.get("asserter", {}).get("reference") == ref]
        self.provider = [c for c in conditions if c not in self.claimant]
        self._notes: dict[str, list[dict]] = {}

    def notes(self, cond: dict) -> list[dict]:
        """Provider notes from the condition's encounter."""
        enc = cond.get("encounter", {}).get("reference")
        if not enc:
            return []
        if enc not in self._notes:
            self._notes[enc] = search_all("DocumentReference", encounter=enc)
        return self._notes[enc]

    def statements(self, cond: dict) -> list[dict]:
        return [read(d["reference"]) for e in cond.get("evidence", []) for d in e.get("detail", [])]

    def primary(self, wanted: str | None) -> dict | None:
        active = [c for c in self.provider if status(c, "clinicalStatus") == "active"]
        order = [wanted] if wanted else PRIMARY
        for want in order:
            matches = sorted((c for c in active if code(c) == want), key=onset)
            if matches:
                return matches[0]
        return None


def doc(d: dict) -> dict:
    author = ", ".join(a.get("display", a.get("reference", "")) for a in d.get("author", []))
    kind = d.get("type", {}).get("text") or d.get("type", {}).get("coding", [{}])[0].get("display", "Document")
    return {"ref": f"DocumentReference/{d['id']}", "date": d.get("date", "")[:10], "type": kind, "author": author}


def conflicts(p: Patient) -> list[dict]:
    out = []
    for claim in p.claimant:
        same = [c for c in p.provider if code(c) == code(claim)]
        refuted = [c for c in same if status(c, "verificationStatus") == "refuted"]
        active = [c for c in same if status(c, "clinicalStatus") == "active"
                  and status(c, "verificationStatus") != "refuted"]
        ended = [c for c in same if status(c, "clinicalStatus") in INACTIVE and c not in refuted]
        if active:
            continue  # provider agrees
        if refuted:
            kind, records = "refuted", refuted
            why = f"the provider ruled it out on {onset(refuted[-1])}"
        elif ended:
            kind, records = "status", ended
            last = max(ended, key=lambda c: c.get("abatementDateTime", ""))
            why = f"the provider recorded it as {status(last, 'clinicalStatus')} on {(last.get('abatementDateTime') or '')[:10]}"
        else:
            kind, records = "unrecorded", []
            why = "no provider record mentions it"
        stmts = p.statements(claim)
        provider_docs = [n for r in records for n in p.notes(r)]
        where = "the claimant statement" + (" and provider records" if records else "")
        out.append({
            "insight": "Conflicting Report of Condition Between Claimant and Provider", "patient": p.ref,
            "kind": kind, "condition": name(claim),
            "text": f"There is conflicting information about the claimant's condition {name(claim)} in {where}. "
                    f"The claimant reports it as ongoing ({onset(claim)}), but {why}.",
            "evidence": [f"Condition/{claim['id']}"] + [f"Condition/{r['id']}" for r in records],
            "documents": [doc(d) for d in stmts + provider_docs[-1:]],
        })
    return out


def comorbidities(p: Patient, primary_code: str | None, since: str | None) -> list[dict]:
    primary = p.primary(primary_code)
    if not primary:
        return []
    start = max(onset(primary), since or "")
    seen, out = {code(primary)}, []
    for c in sorted(p.provider, key=onset):
        if code(c) in seen or code(c) in NOT_DISABLING or status(c, "clinicalStatus") != "active" or "(disorder)" not in c["code"]["coding"][0].get("display", "") \
                or onset(c) <= start or status(c, "verificationStatus") == "refuted":
            continue
        seen.add(code(c))
        out.append({
            "insight": "New Comorbidity", "patient": p.ref, "condition": name(c), "primary": name(primary),
            "text": f"A new comorbidity {name(c)} (onset {onset(c)}) has been identified. It could impact the "
                    f"claimant's primary condition, {name(primary)} (onset {onset(primary)}), and may affect return to work.",
            "evidence": [f"Condition/{c['id']}", f"Condition/{primary['id']}"],
            "documents": [doc(d) for d in p.notes(c)],
        })
    return out


def show(card: dict) -> None:
    print(f"\n{card['insight']}  ·  {card['patient']}")
    print(f"  {card['text']}")
    for d in card["documents"]:
        print(f"  [{d['ref']}] {d['type']} {d['date']} | Created by {d['author']}")
    print(f"  evidence: {', '.join(card['evidence'])}")


def check(cards: list[dict]) -> None:
    key = json.loads(KEY.read_text())["expected"]
    found = {(c["patient"], c["kind"]) for c in cards if c["insight"].startswith("Conflicting")}
    want = {(k["patient"], k["kind"]) for k in key if k["kind"] != "agrees"}
    controls = {k["patient"] for k in key if k["kind"] == "agrees"}
    false_pos = {f for f in found if f[0] in controls or f not in want}
    print(f"\nconflicts found {len(found & want)}/{len(want)}; false positives {len(false_pos)}"
          + (f": {sorted(false_pos)}" if false_pos else ""))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--patient", action="append", help="Patient/<id> (repeatable); default: claimants with statements")
    parser.add_argument("--primary", help="SNOMED code of the primary condition (default: first active one in PRIMARY)")
    parser.add_argument("--since", help="only comorbidities with onset after this date (YYYY-MM-DD)")
    parser.add_argument("--json", action="store_true", help="print the insights as JSON")
    parser.add_argument("--check", action="store_true", help="score conflicts against answer_key.json")
    args = parser.parse_args()

    refs = args.patient or sorted({c["asserter"]["reference"] for c in search_all("Condition", **{"asserter:missing": "false"})
                                   if c["asserter"]["reference"].startswith("Patient/")})
    if not refs:
        raise SystemExit("no claimant statements found; run seed_claimant.py first or pass --patient")
    cards = []
    for ref in refs:
        p = Patient(ref)
        cards += conflicts(p) + comorbidities(p, args.primary, args.since)
    if args.json:
        print(json.dumps(cards, indent=2))
    else:
        for card in cards:
            show(card)
        counts = {k: sum(c["insight"].startswith(k) for c in cards) for k in ("Conflicting", "New")}
        print(f"\n{len(refs)} patients: {counts['Conflicting']} conflicting reports, {counts['New']} new comorbidities")
    if args.check:
        check(cards)


if __name__ == "__main__":
    main()
