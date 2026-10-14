#!/usr/bin/env python3
"""Compiles graded agent runs into a workflow spec (workflow_spec.json) for workflow.py.

    python runs.py backfill                      # once: graded traces/*.json -> runs/
    python compile_workflow.py                   # runs/ -> workflow_spec.json
    python compile_workflow.py --calibrate       # also fit the rules classifier on graded workflow runs

What it reads (runs/traces.jsonl, runs/notes.jsonl; see runs.py):
  - which analytics tools the agent called, in what order, with what arguments, and whose
    results named a provider that turned out to be guilty (the derived notes);
  - which schemes the agents found or missed, and what their notes say they wished they
    had checked first;
  - what the agents' reports dismissed as routine (e.g. death-certificate claims).

What it writes (the step types are described in workflow.py):
  - a code step for each analytics tool that surfaced a guilty provider in at least
    --min-evidence graded runs, in the order the agents usually called them, with the
    arguments they used; then the profile check, which has no tool behind it and catches
    providers no question covers;
  - one typed yes/no question per scheme those steps cover;
  - a research step (FHIR reads only) for uncertain answers, and the escalate step;
  - the schemes agents found that no step covers (uncovered_schemes), notes for the
    research step (hints), and the statistics behind each choice (compiled).

The question priors are hand-set from the clean Synthea baseline until --calibrate fits
them (a logistic curve per question) on graded workflow runs (ladder.py --mode workflow).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import runs
from workflow import DEFAULT_SPEC, spec_hash, validate_spec

# The step library: the analytics tool an agent used, the code step that does its job per
# provider, and the question asked about each provider the step flags.
LIBRARY = [
    {"tool": "service_cost_by_provider", "op": "peer_cost", "scheme": "upcoding", "label": "upcoding",
     "question": "Is this provider's pay for this service consistent with upcoding (billing a higher-paying "
                 "level of service than was delivered)?",
     "choices": {"yes": "Paid well above other providers for the same service, on a pattern of claims.",
                 "no": "The difference is small, isolated, or explained."},
     "describe": "{service} paid {ratio_to_peer_median}x the peer median (${peer_median_paid}); "
                 "{claims} claims above peer rates (inflated)",
     "screen": 1.15, "prior": {"feature": "score", "center": 1.25, "scale": 0.05}},
    {"tool": "find_duplicate_claims", "op": "duplicates", "scheme": "duplicates", "label": "duplicate billing",
     "question": "Is this consistent with duplicate billing (the same service for the same patient and amount "
                 "billed more than once)?",
     "choices": {"yes": "The same service was billed again with nothing to suggest a second service.",
                 "no": "The repeats are routine (e.g. a daily treatment) or too few to matter."},
     "describe": "{exact_duplicates} exact duplicate claim(s) and {rebilled_within_window} re-billed within "
                 "{window_days} day(s) (same patient, service, amount)",
     "screen": 0.5, "prior": {"feature": "score", "center": 0.75, "scale": 0.25}},
    {"tool": "claims_after_patient_death", "op": "after_death", "scheme": "after_death", "label": "billing after death",
     "question": "Is this consistent with billing for services after the patient's death (beyond routine "
                 "post-death paperwork)?",
     "choices": {"yes": "Services were billed for patients who had already died.",
                 "no": "Routine paperwork, a data-entry slip, or a single isolated claim."},
     "describe": "{claims} claims for {patients} deceased patient(s), {days_after_death_min}-{days_after_death_max} "
                 "days after death",
     "screen": 1, "prior": {"feature": "score", "center": 1.5, "scale": 0.5}},
    {"tool": "provider_daily_load", "op": "daily_load", "scheme": "impossible_day", "label": "impossible day",
     "question": "Is this provider's busiest day consistent with billing more visit time than one clinician "
                 "can deliver in a day?",
     "choices": {"yes": "More visits or billed hours in one day than one person can deliver.",
                 "no": "A busy but plausible day."},
     "describe": "{visits} visits for {patients} patients on {date} between {first_start} and {last_end} "
                 "({billed_minutes} billed minutes in {span_hours} hours, same day)",
     "screen": 8, "prior": {"feature": "score", "center": 10, "scale": 1}},
]
SCHEME_OF_TOOL = {e["tool"]: e["scheme"] for e in LIBRARY}
# Limits for the profile check: just above the largest value among the 164 providers of
# the clean Synthea baseline (claims per patient-day 3.75, repeat series 2, exclusive
# patient share 0).
PROFILE_LIMITS = {"claims_per_patient_day": 3.9, "repeat_series": 2, "exclusive_patient_share": 0.5}
REBILL = re.compile(r"day later|next day|following day|re-?bill|one day apart", re.I)
ROUTINE_AFTER_DEATH = {"Death Certification": re.compile(r"death certif", re.I)}


def tool_stats(traces: list[dict], notes: list[dict]) -> dict:
    derived = {n["run_id"]: n for n in notes if n["source"] == "derived"}
    stats = defaultdict(lambda: {"calls": 0, "runs_used": 0, "evidence_runs": 0, "first_positions": [], "args": Counter()})
    for t in traces:
        calls = [e for e in t["events"] if e["type"] == "tool_call"]
        first = {}
        for i, c in enumerate(calls):
            s = stats[c["name"]]
            s["calls"] += 1
            s["args"][json.dumps(c["args"], sort_keys=True)] += 1
            first.setdefault(c["name"], i)
        for name, pos in first.items():
            stats[name]["runs_used"] += 1
            stats[name]["first_positions"].append(pos)
        for name in derived.get(t["run_id"], {}).get("evidence_tools", {}):
            stats[name]["evidence_runs"] += 1
    return {name: {"calls": s["calls"], "runs_used": s["runs_used"], "evidence_runs": s["evidence_runs"],
                   "median_first_position": statistics.median(s["first_positions"]) if s["first_positions"] else None,
                   "common_args": [json.loads(a) for a, _ in s["args"].most_common(3)]}
            for name, s in sorted(stats.items())}


def scheme_outcomes(traces: list[dict]) -> dict:
    found, missed = Counter(), Counter()
    for t in traces:
        score = next((e for e in t["events"] if e["type"] == "score"), {})
        for p in score.get("providers", []):
            for scheme, described in p["schemes"].items():
                (found if p["found"] and described else missed)[scheme] += 1
    return {s: {"found": found[s], "missed": missed[s]} for s in sorted(set(found) | set(missed))}


def _arg(stats: dict, tool: str, name: str, default):
    for args in stats.get(tool, {}).get("common_args", []):
        if name in args:
            return args[name]
    return default


def compile_spec(traces: list[dict], notes: list[dict], min_evidence: int = 1) -> dict:
    traces = [t for t in traces if t.get("mode") == "agent" and any(e["type"] == "score" for e in t["events"])]
    if not traces:
        raise SystemExit("no graded agent runs in runs/: run ladder.py --learn, or runs.py backfill")
    stats = tool_stats(traces, notes)
    outcomes = scheme_outcomes(traces)
    note_text = " ".join(json.dumps(n) for n in notes)
    reports = " ".join(e.get("text", "") for t in traces for e in t["events"] if e["type"] in ("final", "text"))
    chosen = sorted((e for e in LIBRARY if stats.get(e["tool"], {}).get("evidence_runs", 0) >= min_evidence),
                    key=lambda e: stats[e["tool"]]["median_first_position"])
    params = {
        "peer_cost": {"top_codes": max(15, int(_arg(stats, "top_services", "top_n", 15))),
                      "min_claims": int(_arg(stats, "service_cost_by_provider", "min_claims", 3)), "high_ratio": 1.3},
        "duplicates": {"window_days": 1 if REBILL.search(note_text) else 0, "series_gap": 7},
        "after_death": {"exclude_services": [s for s, pat in ROUTINE_AFTER_DEATH.items() if pat.search(reports)]},
        "daily_load": {"max_visit_minutes": 180, "min_visits": 5},
    }
    nodes = [{"id": e["op"], "type": "code", "op": e["op"], "params": params[e["op"]],
              "why": f"{e['tool']} named a guilty provider in {stats[e['tool']]['evidence_runs']} of {len(traces)} graded runs"}
             for e in chosen]
    nodes.append({"id": "profile", "type": "code", "op": "profile", "params": {"min_claims": 10, "limits": PROFILE_LIMITS},
                  "why": "coverage check: providers outside these limits that no question explains go to the full agent"})
    for e in chosen:
        nodes.append({"id": f"q_{e['scheme']}", "type": "question", "input": e["op"], "scheme": e["scheme"],
                      "label": e["label"], "question": e["question"], "choices": e["choices"], "describe": e["describe"],
                      "screen": e["screen"], "max_candidates": 10, "prior": {**e["prior"], "source": "clean-baseline"}})
    nodes.append({"id": "research", "type": "research", "band": [0.3, 0.7], "tools": ["fhir_search", "fhir_read"],
                  "max_items": 4, "max_calls": 6, "recursion_limit": 16})
    nodes.append({"id": "escalate", "type": "escalate", "min_confidence": 0.7, "on_unexplained": True})
    hints = list(dict.fromkeys(n[k].strip() for n in notes if n["source"] == "agent"
                               for k in ("wish_known_first", "least_sure") if isinstance(n.get(k), str) and n[k].strip()))
    covered = {e["scheme"] for e in chosen}
    spec = {"version": 1, "report_threshold": 0.5, "nodes": nodes, "hints": hints[:8],
            "uncovered_schemes": {s: o for s, o in outcomes.items() if s not in covered},
            "compiled": {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         "from_runs": [t["run_id"] for t in traces], "notes": Counter(n["source"] for n in notes),
                         "scheme_outcomes": outcomes, "tool_stats": stats}}
    return validate_spec(spec)


# ---------------------------------------------------------------- calibration

def fit_logistic(xs: list[float], ys: list[int], ridge: float = 0.01, iters: int = 200) -> tuple[float, float]:
    """1-D logistic regression p = sigmoid(a*x + b) by Newton's method with a small ridge
    penalty (separable data would otherwise diverge). x is standardized for the fit."""
    mu = statistics.mean(xs)
    sd = statistics.pstdev(xs) or 1.0
    zs = [(x - mu) / sd for x in xs]
    a = b = 0.0
    for _ in range(iters):
        ga = gb = haa = hab = hbb = 0.0
        for z, y in zip(zs, ys):
            p = 1 / (1 + math.exp(-(a * z + b)))
            w = p * (1 - p)
            ga += (p - y) * z
            gb += p - y
            haa += w * z * z
            hab += w * z
            hbb += w
        ga += ridge * a
        haa += ridge
        hbb += 1e-6
        det = haa * hbb - hab * hab
        if det <= 0:
            break
        da, db = (hbb * ga - hab * gb) / det, (haa * gb - hab * ga) / det
        a, b = a - da, b - db
        if abs(da) + abs(db) < 1e-8:
            break
    return a / sd, b - a * mu / sd


def log_loss(ps: list[float], ys: list[int]) -> float:
    eps = 1e-6
    return round(-statistics.mean(y * math.log(max(p, eps)) + (1 - y) * math.log(max(1 - p, eps)) for p, y in zip(ps, ys)), 4)


def calibrate(spec: dict, traces: list[dict]) -> dict:
    """Fits each question's prior on graded workflow runs: x = the step's score for each
    provider asked about, y = whether that provider was guilty of that scheme."""
    data = defaultdict(lambda: ([], []))
    for t in traces:
        if t.get("mode") not in ("workflow", "routed"):
            continue
        score = next((e for e in t["events"] if e["type"] == "score"), None)
        if not score:
            continue
        guilty = {p["provider"]: set(p["schemes"]) for p in score["providers"]}
        for rec in t["events"]:
            if rec.get("type") == "workflow_node" and rec.get("kind") == "question":
                xs, ys = data[rec["node"]]
                xs.append(float(rec["evidence"]["score"]))
                ys.append(int(rec["scheme"] in guilty.get(rec["provider"], set())))
    for node in spec["nodes"]:
        if node["type"] != "question" or node["id"] not in data:
            continue
        xs, ys = data[node["id"]]
        prior = node["prior"]
        before = [1 / (1 + math.exp(-(x - prior["center"]) / prior["scale"])) for x in xs]
        info = {"n": len(xs), "positives": sum(ys), "log_loss_before": log_loss(before, ys)}
        if 0 < sum(ys) < len(ys):
            a, b = fit_logistic(xs, ys)
            if a > 0:
                center, scale = -b / a, max(1 / a, 0.01 * max(abs(-b / a), 1))
                after = [1 / (1 + math.exp(-(x - center) / scale)) for x in xs]
                node["prior"] = {"feature": prior.get("feature", "score"), "center": round(center, 4),
                                 "scale": round(scale, 4), "source": "calibrated"}
                info["log_loss_after"] = log_loss(after, ys)
        else:
            info["skipped"] = "needs both guilty and innocent examples"
        node["calibration"] = info
    return validate_spec(spec)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(DEFAULT_SPEC))
    parser.add_argument("--min-evidence", type=int, default=1,
                        help="graded runs in which a tool must have named a guilty provider to become a step")
    parser.add_argument("--calibrate", action="store_true", help="fit question priors on graded workflow runs in runs/")
    args = parser.parse_args()
    traces, notes = runs.read(runs.TRACES_JSONL), runs.read(runs.NOTES_JSONL)
    spec = compile_spec(traces, notes, args.min_evidence)
    if args.calibrate:
        spec = calibrate(spec, traces)
    Path(args.out).write_text(json.dumps(spec, indent=1, default=str) + "\n")
    steps = ", ".join(f"{n['id']}({n['type']})" for n in spec["nodes"])
    print(f"wrote {args.out} (spec {spec_hash(spec)}) from {len(spec['compiled']['from_runs'])} graded runs: {steps}")
    if spec["uncovered_schemes"]:
        print("schemes no step covers (left to the full agent): " + ", ".join(spec["uncovered_schemes"]))


if __name__ == "__main__":
    sys.exit(main())
