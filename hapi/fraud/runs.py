#!/usr/bin/env python3
"""Learning-mode records: graded runs and their notes, as JSONL under runs/ (git-ignored).

    runs/traces.jsonl   one graded run per line: run_id, mode (agent | workflow | routed),
                        level, agent, model, events (ending with the score event)
    runs/notes.jsonl    one note per line: run_id, source, and what the run teaches
                          source "agent"    the agent's own note (ladder.py --learn): evidence_tools,
                                            wasted, wish_known_first, least_sure
                          source "derived"  computed from the graded trace, no model: which tools'
                                            results named a guilty provider, repeated / failed /
                                            truncated calls, what was missed, who was wrongly accused

ladder.py appends both after each run. To learn from runs saved before learning mode
existed (traces/*.json from the app or the ladder):

    python runs.py backfill [TRACES_DIR]     # graded agent traces -> runs/, with derived notes
    python runs.py list
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
TRACES_JSONL = RUNS / "traces.jsonl"
NOTES_JSONL = RUNS / "notes.jsonl"


def append(path: Path, record: dict) -> None:
    path.parent.mkdir(exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def known_ids() -> set[str]:
    return {r["run_id"] for r in read(TRACES_JSONL)}


def _refs(text: str) -> set[str]:
    return set(re.findall(r"Practitioner/\d+", text or ""))


def derive_note(trace: dict, level_description: str = "") -> dict:
    """What a graded trace teaches, computed without a model."""
    events = trace["events"]
    score = next((e for e in events if e["type"] == "score"), None) or {}
    guilty = {p["provider"]: p for p in score.get("providers", [])}
    calls = {e["call_id"]: e for e in events if e["type"] == "tool_call"}
    results = {e["call_id"]: e for e in events if e["type"] == "tool_result"}
    evidence, first_hit, wasted, seen = Counter(), {}, [], set()
    for cid, call in calls.items():
        res = results.get(cid, {})
        named = _refs(res.get("preview", "")) & set(guilty)
        named |= {ref for ref, p in guilty.items() if p.get("name") and p["name"] in res.get("preview", "")}
        if named:
            evidence[call["name"]] += 1
            for ref in named:
                first_hit.setdefault(ref, {"step": call["step"], "tool": call["name"]})
        signature = (call["name"], json.dumps(call["args"], sort_keys=True))
        why = ("repeated an earlier call" if signature in seen else "error" if res.get("is_error")
               else "result truncated" if res.get("truncated") else None)
        seen.add(signature)
        if why:
            wasted.append(f"{call['step']}. {call['name']}: {why}")
    missed = [f"{p['name'] or ref}: {scheme}" for ref, p in guilty.items()
              for scheme, described in p.get("schemes", {}).items() if not (p.get("found") and described)]
    return {"run_id": trace["run_id"], "source": "derived", "level": trace.get("level"),
            "evidence_tools": dict(evidence.most_common()), "first_hit": first_hit, "wasted": wasted,
            "missed": missed, "false_positives": [f.get("name") or f.get("provider") for f in score.get("false_positives", [])],
            "wish_known_first": (f"Missed {'; '.join(missed)}. The level was: {level_description}"
                                 if missed and level_description else ""),
            "tool_calls": len(calls)}


def record_run(trace: dict, mode: str, agent_note: dict | None = None, level_description: str = "") -> None:
    """Appends a graded run, its derived note and (learning mode) the agent's own note."""
    append(TRACES_JSONL, {**trace, "mode": mode})
    if mode == "agent":
        append(NOTES_JSONL, derive_note(trace, level_description))
        if agent_note:
            append(NOTES_JSONL, {"run_id": trace["run_id"], "source": "agent", "level": trace.get("level"),
                                 **{k: v for k, v in agent_note.items() if k not in ("type", "t")}})


def backfill(directory: Path) -> int:
    import seed_fraud
    have, added = known_ids(), 0
    for path in sorted(directory.glob("*.json")):
        trace = json.loads(path.read_text())
        if trace["run_id"] in have or not any(e["type"] == "score" for e in trace["events"]):
            continue  # already imported, or never graded
        level = trace.get("level")
        description = seed_fraud.LEVELS.get(level, ("", ""))[1] if level else ""
        note = next((e for e in trace["events"] if e["type"] == "note"), None)
        record_run(trace, "agent", note, description)
        added += 1
    return added


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("backfill")
    b.add_argument("directory", nargs="?", default=str(HERE / "traces"))
    sub.add_parser("list")
    args = parser.parse_args()
    if args.command == "backfill":
        print(f"imported {backfill(Path(args.directory))} graded runs into {TRACES_JSONL}")
    else:
        notes = Counter((n["run_id"], n["source"]) for n in read(NOTES_JSONL))
        for r in read(TRACES_JSONL):
            score = next((e for e in r["events"] if e["type"] == "score"), {})
            print(f"{r['run_id']}  {r['mode']:8} level {r.get('level')}  {r.get('model')}  found {score.get('found')}/"
                  f"{score.get('guilty')}  accused {score.get('false_positive_providers')}  notes: "
                  + ", ".join(s for (rid, s) in notes if rid == r["run_id"]))


if __name__ == "__main__":
    sys.exit(main())
