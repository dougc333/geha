import json
from collections import defaultdict
from datetime import date


def find_next_day_rebills(rows, names, deaths, max_gap_days: int = 1, min_pairs: int = 2, min_paid: float = 0.01) -> str:
    """Find claims re-billed shortly after an identical claim.

    A match is the same provider, same patient, same service code and same paid amount, with
    service dates 1 to max_gap_days apart. Same-day repeats are excluded, because
    find_duplicate_claims already covers them. Use this to catch duplicate billing that is
    shifted by a day so that exact-date duplicate checks miss it.

    Providers need at least min_pairs such pairs to be listed. They are ranked by the number
    of re-billed claims, then by the amount paid on them. Each provider lists its pairs
    (original eob, re-billed eob, dates, amount), its re-bill rate over all claims, and the
    rate across all other providers for comparison.
    """
    groups = defaultdict(list)
    total_by_provider = defaultdict(int)
    for r in rows:
        prov = r.get("provider")
        if not prov:
            continue
        total_by_provider[prov] += 1
        paid = r.get("paid") or 0
        if paid < min_paid or not r.get("date"):
            continue
        d = date.fromisoformat(str(r["date"])[:10])
        key = (prov, r.get("patient"), r.get("code"), round(float(paid), 2))
        groups[key].append((d, r.get("start") or "", r["eob"], r.get("service", "")))

    pairs_by_provider = defaultdict(list)
    for (prov, patient, code, paid), items in groups.items():
        if len(items) < 2:
            continue
        items.sort()
        for a, b in zip(items, items[1:]):
            gap = (b[0] - a[0]).days
            if 1 <= gap <= max_gap_days:
                pairs_by_provider[prov].append({
                    "patient": patient,
                    "code": code,
                    "service": a[3],
                    "paid": paid,
                    "original_eob": a[2],
                    "original_date": a[0].isoformat(),
                    "rebill_eob": b[2],
                    "rebill_date": b[0].isoformat(),
                    "gap_days": gap,
                })

    all_rebills = sum(len(v) for v in pairs_by_provider.values())
    all_claims = sum(total_by_provider.values())

    results = []
    for prov, pairs in pairs_by_provider.items():
        if len(pairs) < min_pairs:
            continue
        n_claims = total_by_provider[prov]
        other_claims = all_claims - n_claims
        other_rebills = all_rebills - len(pairs)
        results.append({
            "provider": prov,
            "name": names.get(prov, ""),
            "rebilled_claims": len(pairs),
            "rebilled_paid": round(sum(p["paid"] for p in pairs), 2),
            "provider_claims": n_claims,
            "rebill_rate": round(len(pairs) / n_claims, 4) if n_claims else 0,
            "other_providers_rebill_rate": round(other_rebills / other_claims, 4) if other_claims else 0,
            "eobs": [e for p in pairs for e in (p["original_eob"], p["rebill_eob"])],
            "pairs": pairs,
        })

    results.sort(key=lambda x: (-x["rebilled_claims"], -x["rebilled_paid"]))
    return json.dumps({
        "max_gap_days": max_gap_days,
        "providers_flagged": len(results),
        "groups": results[:25],
    }, separators=(",", ":"))
