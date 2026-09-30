import json
import statistics
from collections import defaultdict


def provider_price_outliers(rows, names, deaths, ratio: float = 2.0, min_claims: int = 4, min_flagged: int = 1, same_line_count: bool = False) -> str:
    """Find claims paid far above the SAME provider's usual price for the same service.

    For every (provider, service code) pair with at least min_claims paid claims, the
    provider's own median paid amount is the baseline. Claims paid at ratio times that
    median or more are flagged. This catches a provider who occasionally inflates the
    price of a service they normally bill at a normal rate. Such claims hide in averages
    and in peer comparisons. The tool scans all services at once, so no service code is
    needed.

    Use same_line_count=True to build baselines only from claims with the same number of
    lines, so multi-service claims don't distort the comparison.

    Results are grouped by provider and service. They are ranked by number of flagged
    claims, then by excess paid over the baseline. Each group lists the claim ids, the
    amounts paid, the baseline median and the ratios.
    """
    groups = defaultdict(list)
    for r in rows:
        paid = r.get("paid")
        prov = r.get("provider")
        code = r.get("code")
        if not prov or not code or paid is None or paid <= 0:
            continue
        key = (prov, code, r.get("lines") if same_line_count else None)
        groups[key].append(r)

    results = []
    for (prov, code, lines), claims in groups.items():
        if len(claims) < min_claims:
            continue
        med = statistics.median([c["paid"] for c in claims])
        if med <= 0:
            continue
        flagged = [c for c in claims if c["paid"] >= ratio * med]
        if len(flagged) < min_flagged:
            continue
        flagged.sort(key=lambda c: -c["paid"])
        excess = sum(c["paid"] - med for c in flagged)
        entry = {
            "provider": prov,
            "name": names.get(prov, ""),
            "code": code,
            "service": claims[0].get("service", ""),
            "provider_claims_for_service": len(claims),
            "provider_median_paid": round(med, 2),
            "flagged_count": len(flagged),
            "excess_paid": round(excess, 2),
            "max_ratio": round(flagged[0]["paid"] / med, 2),
            "claims": [
                {
                    "eob": c.get("eob"),
                    "date": c.get("date"),
                    "patient": c.get("patient"),
                    "lines": c.get("lines"),
                    "paid": c["paid"],
                    "ratio": round(c["paid"] / med, 2),
                }
                for c in flagged[:20]
            ],
        }
        if same_line_count:
            entry["lines"] = lines
        results.append(entry)

    results.sort(key=lambda e: (-e["flagged_count"], -e["excess_paid"], -e["max_ratio"]))
    return json.dumps({"ratio_threshold": ratio, "groups": results[:25]}, separators=(",", ":"))
