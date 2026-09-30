"""Claims-analytics tools for the fraud agent, next to the raw FHIR MCP tools.

These give the agent a choice: pull raw resources with fhir_search/fhir_read, or ask
for an aggregate view. Each tool computes from the live HAPI data (loaded once and
cached) and returns compact JSON. None of them knows which claims were planted.
"""

from __future__ import annotations

import json
import statistics
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime
from functools import lru_cache

from langchain_core.tools import tool

FHIR = "http://localhost:8080/fhir"


def _search_all(query: str) -> list[dict]:
    out, url = [], f"{FHIR}/{query}"
    while url:
        # no-cache: HAPI otherwise reuses a search result for 60 s, which hid newly planted claims
        req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            bundle = json.load(resp)
        out += [e["resource"] for e in bundle.get("entry", [])]
        url = next((l["url"] for l in bundle.get("link", []) if l["relation"] == "next"), None)
    return out


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@lru_cache(maxsize=1)
def claims() -> tuple[list[dict], dict, dict]:
    """(claim rows, practitioner names, patient death dates), loaded once per process."""
    names = {}
    for p in _search_all("Practitioner?_count=1000"):
        n = (p.get("name") or [{}])[0]
        names[f"Practitioner/{p['id']}"] = " ".join(n.get("prefix", []) + n.get("given", []) + [n.get("family", "")]).strip()
    deaths = {f"Patient/{p['id']}": p["deceasedDateTime"][:10]
              for p in _search_all("Patient?_count=1000&_elements=deceased") if "deceasedDateTime" in p}
    rows = []
    for e in _search_all("ExplanationOfBenefit?_count=1000&_elements=patient,provider,facility,item,payment,created"):
        items = e.get("item", [])
        coding = items[0]["productOrService"]["coding"][0] if items else {}
        period = items[0].get("servicedPeriod", {}) if items else {}
        minutes = 0
        if period.get("start") and period.get("end"):
            minutes = max(0, int((_dt(period["end"]) - _dt(period["start"])).total_seconds() // 60))
        rows.append({
            "eob": f"ExplanationOfBenefit/{e['id']}", "patient": e["patient"]["reference"],
            "provider": e.get("provider", {}).get("reference", ""),
            "facility": e.get("facility", {}).get("display", ""),
            "date": (period.get("start") or e.get("created", ""))[:10],
            "start": period.get("start", ""), "minutes": minutes,
            "code": coding.get("code", ""), "service": coding.get("display", ""),
            "lines": len(items), "paid": round(e.get("payment", {}).get("amount", {}).get("value", 0.0), 2),
        })
    return rows, names, deaths


def _j(value) -> str:
    return json.dumps(value, separators=(",", ":"))


@tool
def provider_billing_summary(sort_by: str = "total_paid", top_n: int = 15, min_claims: int = 10) -> str:
    """Rank billing providers (Practitioner) with at least min_claims claims. For each:
    claims, distinct patients, total paid, average paid per claim, and the share of the
    provider's claims that is their single most common service.
    sort_by: total_paid | claims | avg_paid."""
    rows, names, _ = claims()
    by = defaultdict(list)
    for r in rows:
        by[r["provider"]].append(r)
    out = []
    for prov, rs in by.items():
        if len(rs) < min_claims:
            continue
        top_code, top_n_code = Counter(r["code"] for r in rs).most_common(1)[0]
        out.append({"provider": prov, "name": names.get(prov, ""), "claims": len(rs),
                    "patients": len({r["patient"] for r in rs}),
                    "total_paid": round(sum(r["paid"] for r in rs), 2),
                    "avg_paid": round(sum(r["paid"] for r in rs) / len(rs), 2),
                    "top_service_code": top_code, "top_service_share": round(top_n_code / len(rs), 2)})
    key = {"claims": "claims", "avg_paid": "avg_paid"}.get(sort_by, "total_paid")
    out.sort(key=lambda x: x[key], reverse=True)
    return _j({"providers_total": len(out), "sorted_by": key, "rows": out[:top_n]})


@tool
def top_services(top_n: int = 15) -> str:
    """Most frequently billed services (SNOMED codes) across all claims, with claim count,
    number of providers billing it, and the median / 90th-percentile amount paid."""
    rows, _, _ = claims()
    by = defaultdict(list)
    for r in rows:
        by[(r["code"], r["service"])].append(r)
    out = []
    for (code, service), rs in sorted(by.items(), key=lambda kv: -len(kv[1]))[:top_n]:
        paid = sorted(r["paid"] for r in rs)
        out.append({"code": code, "service": service, "claims": len(rs),
                    "providers": len({r["provider"] for r in rs}),
                    "median_paid": round(statistics.median(paid), 2),
                    "p90_paid": round(paid[int(0.9 * (len(paid) - 1))], 2)})
    return _j(out)


@tool
def service_cost_by_provider(service_code: str, min_claims: int = 3) -> str:
    """For one service (SNOMED code), compare what each provider is paid for it with what
    the OTHER providers are paid (peer median, excluding the provider's own claims), using
    paid single-service claims so multi-service claims don't distort the comparison.
    Returns providers sorted by ratio to their peer median."""
    rows, names, _ = claims()
    rs = [r for r in rows if r["code"] == service_code and r["lines"] == 1 and r["paid"] > 0]
    if not rs:
        return _j({"error": f"no paid single-service claims with service code {service_code}"})
    by = defaultdict(list)
    for r in rs:
        by[r["provider"]].append(r["paid"])
    out = []
    for p, v in by.items():
        peers = [r["paid"] for r in rs if r["provider"] != p]
        if len(v) < min_claims or not peers:
            continue
        peer_median = statistics.median(peers)
        out.append({"provider": p, "name": names.get(p, ""), "claims": len(v),
                    "avg_paid": round(sum(v) / len(v), 2), "peer_median_paid": round(peer_median, 2),
                    "ratio_to_peer_median": round((sum(v) / len(v)) / peer_median, 2)})
    out.sort(key=lambda x: x["ratio_to_peer_median"], reverse=True)
    return _j({"service_code": service_code, "service": rs[0]["service"],
               "single_service_paid_claims": len(rs), "providers": out[:20]})


@tool
def find_duplicate_claims(provider: str = "") -> str:
    """Find groups of claims with the same patient, service date, service code and amount
    paid (possible duplicate billing). Optionally limit to one provider (Practitioner/<id>)."""
    rows, names, _ = claims()
    groups = defaultdict(list)
    for r in rows:
        if provider and r["provider"] != provider:
            continue
        groups[(r["patient"], r["date"], r["code"], r["paid"], r["provider"])].append(r["eob"])
    dups = [{"patient": k[0], "date": k[1], "service_code": k[2], "paid": k[3], "provider": k[4],
             "provider_name": names.get(k[4], ""), "claims": v}
            for k, v in groups.items() if len(v) > 1 and k[3] > 0]
    by_provider = Counter(d["provider"] for d in dups)
    return _j({"duplicate_groups": len(dups), "by_provider": dict(by_provider.most_common(10)),
               "examples": dups[:12]})


@tool
def claims_after_patient_death(provider: str = "") -> str:
    """Find claims whose service date is after the patient's recorded date of death.
    Optionally limit to one provider (Practitioner/<id>)."""
    rows, names, deaths = claims()
    hits = [{"eob": r["eob"], "patient": r["patient"], "died": deaths[r["patient"]], "service_date": r["date"],
             "provider": r["provider"], "provider_name": names.get(r["provider"], ""), "service": r["service"],
             "paid": r["paid"]}
            for r in rows if r["patient"] in deaths and r["date"] > deaths[r["patient"]]
            and (not provider or r["provider"] == provider)]
    return _j({"claims_after_death": len(hits), "total_paid": round(sum(h["paid"] for h in hits), 2),
               "by_provider": dict(Counter(h["provider"] for h in hits).most_common(10)), "claims": hits[:20]})


@tool
def provider_daily_load(provider: str, top_n: int = 5) -> str:
    """For one provider (Practitioner/<id>), the busiest service days: number of claims,
    distinct patients, total billed service minutes, and the first and last start times."""
    rows, names, _ = claims()
    by = defaultdict(list)
    for r in rows:
        if r["provider"] == provider:
            by[r["date"]].append(r)
    days = [{"date": d, "claims": len(rs), "patients": len({r["patient"] for r in rs}),
             "billed_minutes": sum(r["minutes"] for r in rs),
             "first_start": min(r["start"] for r in rs)[11:16] if rs[0]["start"] else "",
             "last_start": max(r["start"] for r in rs)[11:16] if rs[0]["start"] else ""}
            for d, rs in by.items()]
    days.sort(key=lambda x: x["billed_minutes"], reverse=True)
    return _j({"provider": provider, "name": names.get(provider, ""), "days_with_claims": len(days),
               "busiest_days": days[:top_n]})


ANALYTIC_TOOLS = [provider_billing_summary, top_services, service_cost_by_provider,
                  find_duplicate_claims, claims_after_patient_death, provider_daily_load]
