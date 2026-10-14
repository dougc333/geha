#!/usr/bin/env python3
"""Agent vs compiled workflow, per ladder level, from the graded runs in runs/traces.jsonl.

    python compare.py                  # markdown table on stdout
    python compare.py --agent-model claude-opus-5-5

For each level: the latest full-agent run (by model), the latest workflow / routed run,
and a leave-one-level-out check that needs no model calls: the question priors are
calibrated (compile_workflow.calibrate) on the workflow runs of the OTHER levels, and the
held-out level's run is replayed with them (workflow.replay --reclassify).
"""

from __future__ import annotations

import argparse
import copy
import json

import compile_workflow
import runs
import workflow


def score_of(trace: dict) -> dict:
    return next((e for e in trace["events"] if e["type"] == "score"), {})


def cell(s: dict) -> str:
    if not s:
        return "–"
    found = f"{s['found']}/{s['guilty']}" if s.get("guilty") else "n/a"
    return f"{found}, {s['false_positive_providers']} accused"


def effort(trace: dict) -> str:
    done = next((e for e in trace["events"] if e["type"] == "done"), {})
    usage = done.get("usage") or {}
    tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
    return f"{done.get('tool_calls', '–')} calls, {tokens:,} tokens, {done.get('seconds', '–')} s"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--agent-model", default="claude-opus-5-5")
    args = parser.parse_args()
    traces = runs.read(runs.TRACES_JSONL)
    # The ladder runs saved before traces carried a model are the default agent ("graph", Opus).
    agent = {t["level"]: t for t in traces if t["mode"] == "agent" and
             (t.get("model") == args.agent_model or (not t.get("model") and t.get("agent") == "graph"))}
    flow = {t["level"]: t for t in traces if t["mode"] in ("workflow", "routed") and score_of(t)}
    spec = workflow.load_spec()
    rows = ["| Level | Agent (" + args.agent_model + ") | Agent effort | Workflow (rules, offline) | Workflow effort | "
            "Router | Workflow, priors fitted on the other levels |", "|---|---|---|---|---|---|---|"]
    for level in sorted(set(agent) | set(flow)):
        a, w = agent.get(level), flow.get(level)
        route, lolo = "–", "–"
        if w:
            r = next((e for e in w["events"] if e.get("kind") == "route"), {})
            route = ("escalate: " + "; ".join(r["reasons"])) if r.get("escalate") else f"workflow (confidence {r.get('confidence')})"
            others = [t for lv, t in flow.items() if lv != level]
            fitted = compile_workflow.calibrate(copy.deepcopy(spec), others)
            lolo = cell(workflow.replay(w, fitted, reclassify=True)["score"])
        title = (a or w).get("level_title", "")
        rows.append(f"| {level} {title} | {cell(score_of(a)) if a else '–'} | {effort(a) if a else '–'} | "
                    f"{cell(score_of(w)) if w else '–'} | {effort(w) if w else '–'} | {route} | {lolo} |")
    print("\n".join(rows))
    print("\nRuns: " + json.dumps({lv: {"agent": agent[lv]["run_id"] if lv in agent else None,
                                         "workflow": flow[lv]["run_id"] if lv in flow else None}
                                    for lv in sorted(set(agent) | set(flow))}))


if __name__ == "__main__":
    main()
