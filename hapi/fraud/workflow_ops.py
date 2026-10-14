"""Code steps of the compiled workflow: mechanical checks over the claims table.

Each op takes the claims table from tools.claims() (rows, practitioner names, death dates)
plus keyword parameters from the workflow spec, and returns

    {"providers": {"Practitioner/<id>": features}, "summary": {...}}

Every provider's features include `name`, `score` (the one number the offline rules
classifier reads; see questions.py), `claims` and `amount` (the claims behind the signal
and what was paid on them, or overpaid for upcoding), and `eobs` (up to 10 claim ids).
The rest are the facts the question step is asked about. Only providers with some
signal are returned; question steps then screen them by `score`.

The checks are the analytics tools in tools.py made per-provider, plus what graded agent
runs showed those tools miss (next-day re-billing, death-certificate claims after death).
None of them knows which claims were planted.
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta


def _days(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def peer_cost(rows, names, deaths, top_codes: int = 15, min_claims: int = 3, high_ratio: float = 1.3) -> dict:
    """Upcoding: for the most billed services, each provider's average paid on single-service
    claims against the median of the OTHER providers (as service_cost_by_provider). Per
    provider, the service with the highest ratio."""
    single = [r for r in rows if r["lines"] == 1 and r["paid"] > 0]
    out: dict[str, dict] = {}
    for code, _ in Counter(r["code"] for r in single).most_common(top_codes):
        rs = [r for r in single if r["code"] == code]
        by = defaultdict(list)
        for r in rs:
            by[r["provider"]].append(r)
        for prov, mine in by.items():
            peers = [r["paid"] for r in rs if r["provider"] != prov]
            if len(mine) < min_claims or not peers:
                continue
            peer_median = statistics.median(peers)
            avg = sum(r["paid"] for r in mine) / len(mine)
            ratio = round(avg / peer_median, 2)
            if ratio <= out.get(prov, {}).get("score", 1.0):
                continue
            high = [r for r in mine if r["paid"] > high_ratio * peer_median]
            out[prov] = {"name": names.get(prov, ""), "score": ratio, "ratio_to_peer_median": ratio,
                         "service_code": code, "service": mine[0]["service"], "claims_on_service": len(mine),
                         "avg_paid": round(avg, 2), "peer_median_paid": round(peer_median, 2),
                         "claims": len(high), "amount": round(sum(r["paid"] - peer_median for r in high), 2),
                         "eobs": [r["eob"] for r in high][:10]}
    return {"providers": out, "summary": {"services_checked": top_codes, "providers_above_peers": len(out)}}


def duplicates(rows, names, deaths, window_days: int = 0, series_gap: int = 7) -> dict:
    """Duplicate billing: claims with the same patient, service, amount and provider on the
    same day (exact), and, if window_days > 0, an isolated pair 1..window_days days apart
    (re-billed). A pair inside a longer run of the same service (another claim within
    series_gap days, e.g. daily home visits or treatments) is counted as routine and left
    out of the score; a re-billed pair counts half as much as an exact duplicate."""
    groups = defaultdict(list)
    for r in rows:
        if r["paid"] > 0:
            groups[(r["patient"], r["code"], r["paid"], r["provider"])].append(r)
    exact, rebilled, routine = defaultdict(list), defaultdict(list), Counter()
    for (_, _, _, prov), rs in groups.items():
        rs.sort(key=lambda r: r["date"])
        for i, (a, b) in enumerate(zip(rs, rs[1:])):
            gap = _days(a["date"], b["date"])
            if gap == 0:
                exact[prov].append((a, b))
            elif window_days and gap <= window_days:
                before = i > 0 and _days(rs[i - 1]["date"], a["date"]) <= series_gap
                after = i + 2 < len(rs) and _days(b["date"], rs[i + 2]["date"]) <= series_gap
                if before or after:
                    routine[prov] += 1
                else:
                    rebilled[prov].append((a, b))
    out = {}
    for prov in set(exact) | set(rebilled) | set(routine):
        pairs = exact[prov] + rebilled[prov]
        extra = [b for _, b in pairs]
        # A same-day copy is stronger evidence than a next-day repeat, which can be a real revisit.
        out[prov] = {"name": names.get(prov, ""), "score": len(exact[prov]) + 0.5 * len(rebilled[prov]),
                     "exact_duplicates": len(exact[prov]),
                     "rebilled_within_window": len(rebilled[prov]), "routine_repeats": routine[prov],
                     "window_days": window_days,
                     "claims": len(extra), "amount": round(sum(r["paid"] for r in extra), 2),
                     "examples": [{"first": a["eob"], "again": b["eob"], "dates": [a["date"], b["date"]],
                                   "service": a["service"], "paid": a["paid"]} for a, b in pairs[:5]],
                     "eobs": [r["eob"] for r in extra][:10]}
    return {"providers": out, "summary": {"providers_with_repeats": len(out), "window_days": window_days}}


def after_death(rows, names, deaths, exclude_services: tuple[str, ...] = ()) -> dict:
    """Billing after death: claims dated after the patient's recorded death. Services in
    exclude_services (e.g. death certification, which follows a death by design) are
    counted but left out of the score."""
    hits, excluded = defaultdict(list), Counter()
    for r in rows:
        if r["patient"] in deaths and r["date"] > deaths[r["patient"]]:
            if r["service"] in exclude_services:
                excluded[r["provider"]] += 1
            else:
                hits[r["provider"]].append(r)
    out = {}
    for prov, rs in hits.items():
        gaps = [_days(deaths[r["patient"]], r["date"]) for r in rs]
        out[prov] = {"name": names.get(prov, ""), "score": len(rs), "patients": len({r["patient"] for r in rs}),
                     "days_after_death_min": min(gaps), "days_after_death_max": max(gaps),
                     "services": dict(Counter(r["service"] for r in rs).most_common(3)),
                     "excluded_routine_claims": excluded[prov],
                     "claims": len(rs), "amount": round(sum(r["paid"] for r in rs), 2), "eobs": [r["eob"] for r in rs][:10]}
    return {"providers": out, "summary": {"providers": len(out), "excluded_routine_claims": sum(excluded.values()),
                                          "excluded_services": list(exclude_services)}}


def daily_load(rows, names, deaths, max_visit_minutes: int = 180, min_visits: int = 5) -> dict:
    """Impossible day: per provider, the day with the most short visits (claims of at most
    max_visit_minutes; long stays are not visits), with the hours they span and how many
    billed minutes overlap."""
    days = defaultdict(list)
    for r in rows:
        if r["start"] and 0 < r["minutes"] <= max_visit_minutes:
            days[(r["provider"], r["date"])].append(r)
    out = {}
    for (prov, day), rs in days.items():
        if len(rs) < min_visits or len(rs) <= out.get(prov, {}).get("score", 0):
            continue
        spans = sorted((datetime.fromisoformat(r["start"]), r["minutes"]) for r in rs)
        billed = sum(m for _, m in spans)
        union, cur_s, cur_e = 0.0, None, None
        for s, m in spans:
            e = s + timedelta(minutes=m)
            if cur_e is None or s > cur_e:
                union += (cur_e - cur_s).total_seconds() / 60 if cur_e else 0
                cur_s, cur_e = s, e
            else:
                cur_e = max(cur_e, e)
        union += (cur_e - cur_s).total_seconds() / 60
        first, last = spans[0][0], max(s + timedelta(minutes=m) for s, m in spans)
        out[prov] = {"name": names.get(prov, ""), "score": len(rs), "date": day, "visits": len(rs),
                     "patients": len({r["patient"] for r in rs}), "billed_minutes": billed,
                     "overlapping_minutes": round(billed - union), "first_start": first.strftime("%H:%M"),
                     "last_end": last.strftime("%H:%M"), "span_hours": round((last - first).total_seconds() / 3600, 1),
                     "claims": len(rs), "amount": round(sum(r["paid"] for r in rs), 2), "eobs": [r["eob"] for r in rs][:10]}
    return {"providers": out, "summary": {"providers_with_busy_days": len(out), "max_visit_minutes": max_visit_minutes}}


def profile(rows, names, deaths, min_claims: int = 10, limits: dict | None = None) -> dict:
    """Coverage check, not a scheme: providers whose billing profile is outside the limits
    on a measure no question covers. A flagged provider that no question explains is
    'unexplained', and the router hands the case to the full agent.

      claims_per_patient_day   claims per (patient, day) seen
      repeat_series            patients billed the same service 10+ times at a median gap of 8 days or less
      exclusive_patient_share  share of the provider's patients (5+) seen by no other provider"""
    limits = limits or {}
    by = defaultdict(list)
    seen_by = defaultdict(set)
    for r in rows:
        by[r["provider"]].append(r)
        seen_by[r["patient"]].add(r["provider"])
    out = {}
    for prov, rs in by.items():
        if len(rs) < min_claims:
            continue
        patients = {r["patient"] for r in rs}
        series = defaultdict(set)
        for r in rs:
            series[(r["patient"], r["code"])].add(r["date"])
        repeat = 0
        for ds in series.values():
            ds = sorted(ds)
            gaps = [_days(a, b) for a, b in zip(ds, ds[1:])]
            repeat += len(gaps) >= 9 and statistics.median(gaps) <= 8
        measures = {"claims_per_patient_day": round(len(rs) / len({(r["patient"], r["date"]) for r in rs}), 2),
                    "repeat_series": repeat,
                    "exclusive_patient_share": round(sum(len(seen_by[p]) == 1 for p in patients) / len(patients), 2)
                    if len(patients) >= 5 else 0.0}
        over = {m: v for m, v in measures.items() if m in limits and v > limits[m]}
        if over:
            out[prov] = {"name": names.get(prov, ""), "score": len(over), "outside_limits": over, **measures,
                         "claims": len(rs), "patients": len(patients),
                         "amount": round(sum(r["paid"] for r in rs), 2), "eobs": [r["eob"] for r in rs][:10]}
    return {"providers": out, "summary": {"providers_checked": sum(len(v) >= min_claims for v in by.values()),
                                          "outside_limits": len(out), "limits": limits}}


OPS = {"peer_cost": peer_cost, "duplicates": duplicates, "after_death": after_death,
       "daily_load": daily_load, "profile": profile}
