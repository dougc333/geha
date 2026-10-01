import json
from collections import defaultdict
from datetime import date


def isolated_next_day_rebills(rows, names, deaths, max_gap_days: int = 1, isolation_days: int = 7, min_pairs: int = 2, min_series_len: int = 3) -> str:
    """Find likely re-billed visits: a claim copied onto the following day (same provider, patient, service code
    and amount paid) as an ISOLATED pair. Neither claim may have another identical claim within isolation_days
    before or after it, so daily treatment series (radiation, home health, telemedicine runs) are not counted.
    Ranks providers by number of isolated re-bill pairs, then by the share of their claims involved.
    long_series_claims shows how much of the provider's billing sits in runs of min_series_len or more
    consecutive-day identical claims, which is context for legitimate daily care.
    Use this to catch duplicate billing shifted by a day, which same-date duplicate checks miss."""
    groups = defaultdict(list)
    prov_claims = defaultdict(int)
    for r in rows:
        prov = r.get("provider")
        d = r.get("date")
        if not prov or not d:
            continue
        prov_claims[prov] += 1
        paid = r.get("paid")
        if paid is None:
            continue
        key = (prov, r.get("patient"), r.get("code"), round(float(paid), 2))
        groups[key].append((date.fromisoformat(d[:10]), r.get("eob"), r.get("service"), r.get("start")))

    flagged = defaultdict(list)
    series_claims = defaultdict(int)
    for key, items in groups.items():
        items.sort(key=lambda x: (x[0], x[1] or ""))
        n = len(items)
        # long consecutive-day runs (context: daily care)
        run = 1
        for i in range(1, n + 1):
            if i < n and (items[i][0] - items[i - 1][0]).days == 1:
                run += 1
            else:
                if run >= min_series_len:
                    series_claims[key[0]] += run
                run = 1
        # isolated next-day pairs
        for i in range(n - 1):
            gap = (items[i + 1][0] - items[i][0]).days
            if gap < 1 or gap > max_gap_days:
                continue
            if i > 0 and (items[i][0] - items[i - 1][0]).days < isolation_days:
                continue
            if i + 2 < n and (items[i + 2][0] - items[i + 1][0]).days < isolation_days:
                continue
            flagged[key[0]].append({
                "patient": key[1],
                "code": key[2],
                "service": items[i][2],
                "paid": key[3],
                "first_eob": items[i][1],
                "first_date": items[i][0].isoformat(),
                "first_start": items[i][3],
                "rebill_eob": items[i + 1][1],
                "rebill_date": items[i + 1][0].isoformat(),
                "rebill_start": items[i + 1][3],
            })

    out = []
    for prov, pairs in flagged.items():
        if len(pairs) < min_pairs:
            continue
        total = prov_claims[prov]
        share = round(2 * len(pairs) / total, 3) if total else 0.0
        out.append({
            "provider": prov,
            "name": names.get(prov, ""),
            "isolated_rebill_pairs": len(pairs),
            "provider_claims": total,
            "share_of_claims_in_pairs": share,
            "rebilled_amount": round(sum(p["paid"] for p in pairs), 2),
            "long_series_claims": series_claims.get(prov, 0),
            "pairs": pairs[:40],
        })
    out.sort(key=lambda g: (-g["isolated_rebill_pairs"], -g["share_of_claims_in_pairs"], g["long_series_claims"]))
    return json.dumps({"providers_flagged": len(out), "groups": out[:25]}, separators=(",", ":"))
