#!/usr/bin/env python3
"""Self-improvement loop: the agent investigates, is graded, and a reflector turns the
graded run into general lessons that are added to its prompt for later runs.

    python improve.py --model nous                    # train on variant 1, test on variant 2, levels 1-5
    python improve.py --model claude --train 2:1,4:1 --test 2:2,4:2
    python improve.py --model nous --skip-baseline    # reuse the last baseline for the same test cases

Cases are level:variant (see seed_fraud.py --variant). Three phases:

  baseline  the test cases with no lessons
  train     each train case is run with the lessons so far, scored against the answer key,
            and the reflector rewrites the lessons from what was missed or wrongly accused
  test      the test cases again, with the lessons

The lessons are kept (lessons.md) only if the test score beats the baseline; otherwise
they go to lessons_rejected.md and lessons.md is left as it was. Score = guilty providers
found minus innocent providers accused, so accusing everyone does not pay.

Every run is saved in traces/ like a ladder run; results go to improve_results.json and
improve_results.md. HAPI is left with nothing planted.

Tool writing (--tools, or --toolsmith RUN_ID for one saved run): when a graded run missed
a scheme that no existing tool could have surfaced, the reflector writes one new analytics
function. It is validated, run in isolation against the case it was written for (it must
surface the missed provider), and saved as pending in learned_tools/. The agent cannot use
it until a person approves it: python learned.py show NAME, then approve NAME. Advice to
call an existing tool differently needs no approval; it is a lesson, not code.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

import learned
import seed_fraud
import tools as analytics
from agent import DEFAULT_MODEL, MODELS, as_text, chat_model
from ladder import TRACES, run_level

HERE = Path(__file__).resolve().parent
LESSONS = HERE / "lessons.md"
REJECTED = HERE / "lessons_rejected.md"
RESULTS = HERE / "improve_results.json"
SUMMARY = HERE / "improve_results.md"
MAX_LESSONS = 10
TOP_RANK = 3  # a learned tool must list a missed provider among its first 3 providers

REFLECT_SYSTEM = f"""You maintain the lessons file of a fraud-investigation agent at a health plan.
After each investigation the agent's findings are graded against confirmed outcomes. You
are given the current lessons, what the agent did, and the grading. Return the revised
lessons: what a careful investigator should do differently next time, on different data.

Rules for every lesson:
- General and reusable: a check to perform, a pattern to look for, or a condition under
  which NOT to accuse. One or two sentences.
- No specifics of this case: no provider, patient or clinic names, no ids, no dates, no
  addresses, no dollar amounts or counts taken from this case. The next case has
  different providers and may contain different fraud or none.
- Never state or imply how many providers are guilty, or that fraud is present or absent.
- Keep current lessons that still hold, merge overlapping ones, reword any this case
  shows to be misleading, and drop the least useful if there are more than {MAX_LESSONS}.
- If the agent did well and nothing new was learned, return the current lessons unchanged.

Reply with only this JSON: {{"lessons": ["...", "..."]}}"""


TOOLSMITH_SYSTEM = f"""You extend the toolset of a fraud-investigation agent at a health plan. A graded
investigation missed something. Decide whether a new analytics tool would have made the
miss easy to catch, and if so write it.

Write a tool only if no existing tool, called with any arguments, surfaces the pattern.
If an existing tool would do, or the pattern needs data that is not in the claims table,
reply with one line: NO_TOOL: <reason>.

Otherwise reply with one Python code block containing exactly one function:

    def tool_name(rows, names, deaths, <parameters>) -> str:
        \"\"\"What it finds and when to use it (the agent sees this as the tool description).\"\"\"

- rows: list of claim dicts (fields shown below). names: {{"Practitioner/<id>": name}}.
  deaths: {{"Patient/<id>": "YYYY-MM-DD"}}.
- Every parameter after the first three needs a type (int, float, str or bool) and a default.
  Called with its defaults it must surface the missed pattern.
- General: it detects the pattern for any provider on any data. No names, ids, dates or
  amounts from this case in the code.
- Return compact JSON text: the suspicious groups with provider reference and name, the
  claim ids (eob), and the numbers behind the suspicion. Rank providers, most suspicious
  first, and return at most 25 groups.
- Imports only from: {", ".join(sorted(learned.ALLOWED_IMPORTS))}, at the top. No files, network, classes, try,
  while, or names or attributes starting with an underscore."""


def misses(trace: dict, key: dict) -> list[dict]:
    score = next(e for e in trace["events"] if e["type"] == "score")
    return [{"provider": p["provider"], "name": p["name"], "scheme": scheme,
             "detail": key["guilty"][p["provider"]]["details"].get(scheme, scheme)}
            for p in score["providers"] for scheme, described in p["schemes"].items() if not (p["found"] and described)]


def check_tool(code: str, spec: dict, key: dict, missed: list[dict]) -> dict:
    """Runs the tool with its defaults on the planted case: it must surface a missed provider.
    Also counts the providers it lists when the planted claims are left out (a noisy tool
    would mislead the agent)."""
    rows, names, deaths = analytics.claims()
    try:
        out = learned.run(code, spec["name"], rows, names, deaths)
    except RuntimeError as exc:
        return {"passed": False, "error": str(exc)}
    # The missed provider must be near the top, not merely somewhere in the output: the first
    # next-day tool listed its target 5th of 6, behind daily treatments, and the agent
    # dismissed the whole list.
    ranked = list(dict.fromkeys(re.findall(r"Practitioner/\d+", out)))[:TOP_RANK]
    hit = sorted({m["name"] for m in missed if m["provider"] in ranked})
    planted = set(key["planted_resources"])
    try:
        clean = learned.run(code, spec["name"], [r for r in rows if r["eob"] not in planted], names, deaths)
        flagged_clean = len(set(re.findall(r"Practitioner/\d+", clean)))
    except RuntimeError:
        flagged_clean = None
    return {"passed": bool(hit), "surfaced_missed_providers": len(hit), "required_rank": TOP_RANK, "missed_providers": len({m["provider"] for m in missed}),
            "providers_listed_with_planted_claims_removed": flagged_clean, "output_chars": len(out)}


async def write_tool(trace: dict, key: dict, reflector: str, feedback: str = "") -> str | None:
    """Asks the reflector for a tool covering what this run missed. Returns the name of the
    pending tool, or None. HAPI must still hold the planting the run was made on."""
    missed = misses(trace, key)
    if not missed:
        return None
    rows, _, _ = analytics.claims()
    existing = [(t.name, (t.description or "").strip()) for t in analytics.ANALYTIC_TOOLS]
    existing += [(n, e["description"]) for n, e in learned.registry().items() if e["status"] != "rejected"]
    human = ("WHAT THE AGENT MISSED\n" + "\n".join(f"- {m['detail']}" for m in missed)
             + "\n\nEXISTING TOOLS\n" + "\n".join(f"- {n}: {' '.join(d.split())}" for n, d in existing)
             + "\n\nCLAIM ROW FIELDS (two sample rows)\n" + json.dumps(rows[:2], indent=1)
             + (f"\n\nFEEDBACK ON AN EARLIER TOOL FOR THIS MISS\n{feedback}" if feedback else "")
             + "\n\nTOOL CALLS THE AGENT MADE\n"
             + "\n".join(f"{e['step']}. {e['name']} {json.dumps(e['args'])[:160]}" for e in trace["events"] if e["type"] == "tool_call")[:6000])
    messages = [SystemMessage(TOOLSMITH_SYSTEM), HumanMessage(human)]
    for attempt in range(2):
        reply = await chat_model(reflector).ainvoke(messages)
        text = as_text(reply.content)
        block = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.S)
        if not block:
            print(f"    no tool written: {' '.join(text.split())[:160]}", flush=True)
            return None
        code = block.group(1)
        try:
            spec = learned.validate(code)
            break
        except learned.Rejected as exc:
            print(f"    tool rejected by validation: {exc}", flush=True)
            messages += [reply, HumanMessage(f"That code was rejected: {exc}. Send a corrected code block.")]
    else:
        return None
    if spec["name"] in {n for n, _ in existing}:
        print(f"    tool {spec['name']} already exists; not replaced", flush=True)
        return None
    if spec["name"] in learned.registry():  # a rejected tool of that name: keep its record, rename this one
        new = next(f"{spec['name']}_v{i}" for i in range(2, 100) if f"{spec['name']}_v{i}" not in learned.registry())
        code = re.sub(rf"\bdef {spec['name']}\(", f"def {new}(", code, count=1)
        spec = learned.validate(code)
    check = check_tool(code, spec, key, missed)
    if not check["passed"]:
        print(f"    tool {spec['name']} did not surface the missed provider; discarded ({check})", flush=True)
        return None
    learned.save(code, spec, "; ".join(m["detail"] for m in missed), check)
    print(f"    wrote tool {spec['name']} (pending approval): {check}", flush=True)
    return spec["name"]


async def toolsmith(run_id: str, reflector: str, feedback: str = "") -> None:
    """Writes a tool from one saved run: re-plants its case, asks the reflector, checks the tool."""
    trace = json.loads((TRACES / f"{run_id}.json").read_text())
    try:
        key = seed_fraud.plant(trace["level"], trace.get("variant", 0))
        analytics.claims.cache_clear()
        # Re-planting creates new Practitioner resources: point the run's score at the new
        # references (same names, since a variant always draws the same identities).
        by_name = {g["name"]: ref for ref, g in key["guilty"].items()}
        for p in next(e for e in trace["events"] if e["type"] == "score")["providers"]:
            p["provider"] = p["provider"] if p["provider"] in key["guilty"] else by_name.get(p["name"], p["provider"])
        name = await write_tool(trace, key, reflector, feedback)
    finally:
        seed_fraud.reset()
    print(f"pending tool: {name}. Read it with: python learned.py show {name}" if name else "no tool was written")


def read_lessons(path: Path = LESSONS) -> list[str]:
    if not path.exists():
        return []
    return [line[2:].strip() for line in path.read_text().splitlines() if line.startswith("- ")]


def write_lessons(lessons: list[str], path: Path, note: str) -> None:
    path.write_text(f"# Lessons\n\n{note}\n\n" + "".join(f"- {lesson}\n" for lesson in lessons))


def as_prompt(lessons: list[str]) -> str:
    return "\n".join(f"- {lesson}" for lesson in lessons)


def feedback(trace: dict, key: dict) -> str:
    """What the agent did and how it was graded, for the reflector."""
    events = trace["events"]
    score = next(e for e in events if e["type"] == "score")
    final = next((e for e in events if e["type"] == "final"), {})
    lines = ["GRADING"]
    if not key["guilty"]:
        lines.append("No fraud was present in this data. Every accusation below is wrong.")
    for p in score["providers"]:
        details = key["guilty"][p["provider"]]["details"]
        for scheme, described in p["schemes"].items():
            outcome = ("found and described" if p["found"] and described
                       else "provider accused, but this scheme was not described" if p["found"] else "MISSED")
            lines.append(f"- {outcome}: {p['name']}: {details.get(scheme, scheme)}")
    for f in score["false_positives"]:
        lines.append(f"- WRONGLY ACCUSED (innocent): {f['name'] or f['provider']} for \"{f['scheme'][:200]}\" "
                     f"(the agent's confidence: {f['confidence']})")
    lines += ["", "TOOL CALLS THE AGENT MADE, IN ORDER"]
    lines += [f"{e['step']}. {e['name']} {json.dumps(e['args'])[:200]}" for e in events if e["type"] == "tool_call"][:120]
    lines += ["", "THE AGENT'S FINAL REPORT", (final.get("text") or "(no report)")[:8000]]
    return "\n".join(lines)


def sanitize(lessons: list, key: dict) -> list[str]:
    """Drop lessons that carry case specifics (a guilty provider's name, a resource id)."""
    names = {part.lower() for g in key["guilty"].values() for part in g["name"].replace("Dr.", "").split()}
    kept = []
    for lesson in lessons:
        if not isinstance(lesson, str) or not lesson.strip():
            continue
        words = set(re.findall(r"[a-z']+", lesson.lower()))
        if names & words or re.search(r"(Practitioner|Patient|ExplanationOfBenefit)/\d|\d{5,}|20\d\d-\d\d", lesson):
            print(f"    dropped a lesson with case specifics: {lesson[:80]}", flush=True)
            continue
        kept.append(" ".join(lesson.split()))
    return kept[:MAX_LESSONS]


async def reflect(trace: dict, key: dict, lessons: list[str], reflector: str) -> list[str]:
    human = ("CURRENT LESSONS\n" + (as_prompt(lessons) or "(none yet)") + "\n\n" + feedback(trace, key))
    reply = await chat_model(reflector).ainvoke([SystemMessage(REFLECT_SYSTEM), HumanMessage(human)])
    text = as_text(reply.content)
    match = re.search(r"\{.*\}", text, re.S)
    try:
        revised = json.loads(match.group(0))["lessons"] if match else None
    except (json.JSONDecodeError, KeyError):
        revised = None
    if not isinstance(revised, list):
        print("    reflector reply was not the expected JSON; lessons unchanged", flush=True)
        return lessons
    return sanitize(revised, key)


def net(rows: list[dict]) -> int:
    return sum(r["found"] - r["false_positive_providers"] for r in rows if not r["error"])


def describe(row: dict) -> str:
    return (f"found {row['found']}/{row['guilty']}, {row['false_positive_providers']} innocent accused, "
            f"{row['tool_calls']} calls, {row['seconds']}s" + (f"  ERROR {row['error'][:120]}" if row["error"] else ""))


async def run_cases(cases: list[tuple[int, int]], phase: str, model: str, lessons: list[str],
                    reflector: str | None = None, write_tools: bool = False) -> tuple[list[dict], list[str]]:
    """Runs each case with the lessons; with a reflector, the lessons are revised after each run."""
    rows = []
    for level, variant in cases:
        print(f"{phase}: level {level} variant {variant} ({len(lessons)} lessons)", flush=True)
        row = await run_level(level, f"improve/{phase}/{MODELS[model]['model']}", model, variant, as_prompt(lessons))
        row.update(phase=phase, lessons_in=len(lessons))
        print(f"  -> {describe(row)}", flush=True)
        if reflector and not row["error"]:
            trace = json.loads((TRACES / f"{row['run_id']}.json").read_text())
            key = json.loads(seed_fraud.KEY.read_text())
            lessons = await reflect(trace, key, lessons, reflector)
            print(f"  reflected: {len(lessons)} lessons", flush=True)
            if write_tools:
                row["tool_written"] = await write_tool(trace, key, reflector)
        row["lessons_out"] = list(lessons)
        rows.append(row)
    return rows, lessons


def parse_cases(text: str) -> list[tuple[int, int]]:
    return [(int(level), int(variant)) for level, variant in (case.split(":") for case in text.split(","))]


def write_summary(experiments: list[dict]) -> None:
    lines = ["# Self-improvement results", ""]
    for x in experiments:
        lines += [f"## {x['started'][:16]}Z, agent `{x['model']}`, reflector `{x['reflector']}`", "",
                  f"Train cases (level:variant): {x['train']}. Test cases: {x['test']}.", "",
                  "| Test case | Baseline: found | Baseline: innocent accused | With lessons: found | With lessons: innocent accused |",
                  "|---|---:|---:|---:|---:|"]
        for b, t in zip(x["baseline"], x["tested"]):
            cells = [f"{r['found']}/{r['guilty']}" if not r["error"] else "error" for r in (b, t)]
            lines.append(f"| level {b['level']} variant {b['variant']} | {cells[0]} | {b['false_positive_providers']} | "
                         f"{cells[1]} | {t['false_positive_providers']} |")
        lines += ["", f"Score (found minus innocent accused): baseline **{x['baseline_net']}**, with lessons "
                      f"**{x['tested_net']}**. Lessons **{x['decision']}**.", "", "Lessons after training:", ""]
        lines += [f"- {lesson}" for lesson in x["lessons"]] or ["(none)"]
        lines.append("")
    SUMMARY.write_text("\n".join(lines))


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default=DEFAULT_MODEL, choices=sorted(MODELS), help="the agent being improved")
    parser.add_argument("--reflector", default=DEFAULT_MODEL, choices=sorted(MODELS), help="the model that writes the lessons")
    parser.add_argument("--train", default="1:1,2:1,3:1,4:1,5:1", help="level:variant cases to learn from")
    parser.add_argument("--test", default="1:2,2:2,3:2,4:2,5:2", help="level:variant cases to measure on")
    parser.add_argument("--fresh", action="store_true", help="start from no lessons instead of lessons.md")
    parser.add_argument("--skip-baseline", action="store_true", help="reuse the last baseline with the same model and test cases")
    parser.add_argument("--tools", action="store_true", help="also let the reflector write new tools during training (saved as pending)")
    parser.add_argument("--toolsmith", metavar="RUN_ID", help="only write a tool from one saved run in traces/, then stop")
    parser.add_argument("--feedback", default="", help="with --toolsmith: what went wrong with an earlier tool for this miss")
    args = parser.parse_args()
    if args.toolsmith:
        await toolsmith(args.toolsmith, args.reflector, args.feedback)
        return
    train, test = parse_cases(args.train), parse_cases(args.test)
    if set(train) & set(test):
        parser.error("train and test cases overlap")
    experiments = json.loads(RESULTS.read_text()) if RESULTS.exists() else []
    start = [] if args.fresh else read_lessons()
    started = datetime.now(timezone.utc).isoformat()
    try:
        previous = next((x for x in reversed(experiments) if x["model"] == MODELS[args.model]["model"]
                         and x["test"] == args.test), None) if args.skip_baseline else None
        baseline = previous["baseline"] if previous else (await run_cases(test, "baseline", args.model, []))[0]
        _, lessons = await run_cases(train, "train", args.model, start, args.reflector, args.tools)
        tested, _ = await run_cases(test, "test", args.model, lessons)
    finally:
        seed_fraud.reset()
        print("HAPI left with nothing planted (restore the original demo with ../fraud/seed_fraud.py --level 1)")
    better = net(tested) > net(baseline)
    note = (f"Written by improve.py on {started[:10]} (agent {MODELS[args.model]['model']}, reflector "
            f"{MODELS[args.reflector]['model']}). Test score {net(baseline)} -> {net(tested)}.")
    write_lessons(lessons, LESSONS if better else REJECTED, note)
    experiments.append({"started": started, "model": MODELS[args.model]["model"], "reflector": MODELS[args.reflector]["model"],
                        "train": args.train, "test": args.test, "baseline": baseline, "tested": tested,
                        "baseline_net": net(baseline), "tested_net": net(tested),
                        "decision": "kept" if better else "rejected", "lessons": lessons})
    RESULTS.write_text(json.dumps(experiments, indent=1))
    write_summary(experiments)
    print(f"baseline {net(baseline)} -> with lessons {net(tested)}: lessons {'kept in' if better else 'rejected, see'} "
          f"{(LESSONS if better else REJECTED).name}")


if __name__ == "__main__":
    asyncio.run(main())
