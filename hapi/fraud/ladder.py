#!/usr/bin/env python3
"""Difficulty ladder: plant each fraud level, run the agent, score it, save the trace.

    python ladder.py                    # levels 1-5 once each, then restore level 1
    python ladder.py --levels 2,4 --repeat 2

Each run is saved to traces/<run id>.json (with its level and score, so it appears in
the app's Run history), and a row is appended to ladder_results.json;
ladder_results.md is rewritten as a summary table. About $1 of Claude usage per run.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import seed_fraud
import tools
from agent import QUESTION, investigate
from scoring import score

HERE = Path(__file__).resolve().parent
TRACES = HERE / "traces"
RESULTS = HERE / "ladder_results.json"
SUMMARY = HERE / "ladder_results.md"


async def run_level(level: int, agent_name: str) -> dict:
    key = seed_fraud.plant(level)
    tools.claims.cache_clear()  # the analytics tools cache the claims; reload with the new planting
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    started = datetime.now(timezone.utc)
    events: list[dict] = []

    async def emit(event: dict) -> None:
        events.append({"t": round((datetime.now(timezone.utc) - started).total_seconds(), 2), **event})
        if event["type"] == "tool_call":
            print(f"    [{event['step']}] {event['name']}", flush=True)

    error = None
    try:
        await investigate(QUESTION, emit)
    except Exception as exc:  # recorded as a failed run
        error = f"{type(exc).__name__}: {exc}"
        events.append({"t": round((datetime.now(timezone.utc) - started).total_seconds(), 2), "type": "error", "message": error})
    final = next((e for e in events if e["type"] == "final"), None)
    result = score(final["findings"] if final else [], key)
    events.append({"t": events[-1]["t"] if events else 0, "type": "score", **result})
    TRACES.mkdir(exist_ok=True)
    (TRACES / f"{run_id}.json").write_text(json.dumps({
        "run_id": run_id, "question": QUESTION, "started": started.isoformat(), "level": level,
        "level_title": key["title"], "agent": agent_name, "events": events}, indent=1, default=str))
    done = next((e for e in events if e["type"] == "done"), {})
    return {"run_id": run_id, "level": level, "title": key["title"], "agent": agent_name, "error": error,
            "guilty": result["guilty"], "found": result["found"],
            "schemes_total": result["schemes_total"], "schemes_described": result["schemes_described"],
            "false_positive_providers": result["false_positive_providers"],
            "tool_calls": done.get("tool_calls"), "seconds": done.get("seconds"),
            "input_tokens": (done.get("usage") or {}).get("input_tokens"),
            "output_tokens": (done.get("usage") or {}).get("output_tokens")}


def write_summary(rows: list[dict]) -> None:
    lines = ["# Difficulty ladder results", "",
             "| Run | Agent | Level | Guilty found | Schemes described | False-positive providers | Tool calls | Time | Tokens in / out |",
             "|---|---|---|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        found = f"{r['found']}/{r['guilty']}" if r["guilty"] else "n/a (none planted)"
        schemes = f"{r['schemes_described']}/{r['schemes_total']}" if r["schemes_total"] else "n/a"
        tokens = f"{r['input_tokens']:,} / {r['output_tokens']:,}" if r.get("input_tokens") else "–"
        lines.append(f"| `{r['run_id']}` | {r['agent']} | {r['level']} {r['title']} | {found} | {schemes} | "
                     f"{r['false_positive_providers']} | {r['tool_calls'] or '–'} | {r['seconds'] or '–'}s | {tokens} |"
                     + (f" error: {r['error'][:80]} |" if r["error"] else ""))
    SUMMARY.write_text("\n".join(lines) + "\n")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--levels", default="1,2,3,4,5")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--agent", default="graph", help="label stored with the results")
    args = parser.parse_args()
    rows = json.loads(RESULTS.read_text()) if RESULTS.exists() else []
    try:
        for level in [int(x) for x in args.levels.split(",")]:
            for i in range(args.repeat):
                print(f"level {level} run {i + 1}/{args.repeat}", flush=True)
                row = await run_level(level, args.agent)
                rows.append(row)
                RESULTS.write_text(json.dumps(rows, indent=1))
                write_summary(rows)
                print(f"  -> found {row['found']}/{row['guilty']} guilty, {row['schemes_described']}/{row['schemes_total']} "
                      f"schemes described, {row['false_positive_providers']} false-positive providers, "
                      f"{row['tool_calls']} calls, {row['seconds']}s{'  ERROR ' + row['error'] if row['error'] else ''}", flush=True)
    finally:
        seed_fraud.plant(1)
        print("restored level 1")


if __name__ == "__main__":
    asyncio.run(main())
