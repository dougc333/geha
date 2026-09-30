import json
from collections import defaultdict
from datetime import datetime


def split_same_day_claims(rows, names, deaths, min_claims: int = 3, min_visits: int = 3, max_visits_listed: int = 15, top_n: int = 25) -> str:
    """Find visits split into several separate claims (possible unbundling or claim splitting).
    A visit is one provider, one patient and one service date. A visit is flagged when it is
    billed as min_claims or more separate claims. Providers need at least min_visits flagged
    visits to be listed. For each provider the tool reports: flagged visits, all visits, the
    flagged share, the flagged share across all other providers (peer rate), the average
    claims per flagged visit, the share of single-line claims and the total paid on flagged
    visits. Each flagged visit lists the patient, date, claim ids (eob), distinct service
    codes, amount paid and the minutes between the first and last start time. Providers are
    ranked by number of flagged visits, then by how far their rate exceeds the peer rate.
    Use this when one encounter (for example a lab draw) may have been billed as several
    same-day claims. find_duplicate_claims misses this because the split claims have
    different codes or amounts."""
    visits = defaultdict(list)
    for r in rows:
        prov = r.get("provider")
        pat = r.get("patient")
        d = r.get("date")
        if not prov or not pat or not d:
            continue
        visits[(prov, pat, d)].append(r)

    prov_visits = defaultdict(int)
    prov_flag = defaultdict(list)
    for key, claims in visits.items():
        prov_visits[key[0]] += 1
        if len(claims) >= min_claims:
            prov_flag[key[0]].append((key, claims))

    total_visits = sum(prov_visits.values())
    total_flag = sum(len(v) for v in prov_flag.values())

    def parse(s):
        if not s or len(s) < 16:
            return None
        return datetime.fromisoformat(s.replace("Z", "+00:00"))

    results = []
    for prov, fl in prov_flag.items():
        if len(fl) < min_visits:
            continue
        n = prov_visits[prov]
        other_n = total_visits - n
        other_f = total_flag - len(fl)
        peer_rate = other_f / other_n if other_n else 0.0
        rate = len(fl) / n if n else 0.0
        n_claims = 0
        single_line = 0
        paid_total = 0.0
        vlist = []
        for (p, pat, d), claims in sorted(fl, key=lambda x: (-len(x[1]), x[0][2])):
            n_claims += len(claims)
            single_line += sum(1 for c in claims if (c.get("lines") or 0) <= 1)
            vpaid = sum(float(c.get("paid") or 0) for c in claims)
            paid_total += vpaid
            starts = [t for t in (parse(c.get("start")) for c in claims) if t is not None]
            span = round((max(starts) - min(starts)).total_seconds() / 60, 1) if starts else None
            if len(vlist) < max_visits_listed:
                vlist.append({
                    "patient": pat,
                    "date": d,
                    "claims": len(claims),
                    "codes": sorted(set(str(c.get("code")) for c in claims)),
                    "eobs": [c.get("eob") for c in claims],
                    "paid": round(vpaid, 2),
                    "start_span_min": span,
                })
        results.append({
            "provider": prov,
            "name": names.get(prov, ""),
            "flagged_visits": len(fl),
            "all_visits": n,
            "flagged_rate": round(rate, 3),
            "peer_rate": round(peer_rate, 4),
            "avg_claims_per_flagged_visit": round(n_claims / len(fl), 2),
            "single_line_share": round(single_line / n_claims, 3) if n_claims else 0.0,
            "paid_on_flagged_visits": round(paid_total, 2),
            "patients": len(set(k[1] for k, c in fl)),
            "visits": vlist,
            "score": rate - peer_rate,
        })

    results.sort(key=lambda x: (-x["flagged_visits"], -x["score"], -x["paid_on_flagged_visits"]))
    results = results[:top_n]
    for r in results:
        r.pop("score", None)
    return json.dumps({"min_claims": min_claims, "providers": results}, separators=(",", ":"))
