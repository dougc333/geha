#!/usr/bin/env python3
"""Score the dental + medical chatbot on the conversation test set.

Each conversation in benefits_conversations.jsonl lists a member's messages and the slots
a careful human would fill from them. The runner plays the messages through a fresh
BenefitsBot thread and reports:

- joint goal accuracy: conversations where every expected slot is right (one wrong slot
  means a wrong premium)
- per-slot accuracy
- quote accuracy: the last reply contains every premium the expected slots imply, read
  from the same PDF tables
- expected phrases in the replies (benefit answers mid-flow)

    cd /Users/dc/geha
    PYTHONPATH=e2e_RAG/src .venv/bin/python e2e_RAG/evals/run_benefits_conversations.py
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from benefits_bot import BenefitsBot
from medical_tables import PLANS as MEDICAL_PLANS

HERE = Path(__file__).resolve().parent
SLOTS = ("line", "zip", "rate_code", "status", "enrollment", "dental_plan", "medical_plan")


def expected_amounts(bot: BenefitsBot, e: dict) -> list[str]:
    """Premiums the expected slots imply, as the bot prints them."""
    out = []
    if e["line"] in ("dental", "both"):
        plans = ["HIGH", "STANDARD"] if e["dental_plan"] == "BOTH" else [e["dental_plan"]]
        for p in plans:
            out.append(f"${bot.dental.premiums[(p, e['status'], e['enrollment'], e['rate_code'])]:,.2f}")
    if e["line"] in ("medical", "both"):
        plans = list(MEDICAL_PLANS) if e["medical_plan"] == "ALL" else [e["medical_plan"]]
        for p in plans:
            out.append(f"${bot.medical.premium(p, e['status'], e['enrollment'])['value']:,.2f}")
    return out


def run(dataset: Path) -> dict:
    bot = BenefitsBot()
    results = []
    for line in dataset.read_text().splitlines():
        if not line.strip():
            continue
        case = json.loads(line)
        replies = [bot.reply(turn, case["id"]) for turn in case["turns"]]
        got = bot.state(case["id"])
        slots = {k: (got.get(k) == v) for k, v in case["expect"].items()}
        amounts = expected_amounts(bot, case["expect"])
        quote_ok = "2026 premiums" in replies[-1] and all(a in replies[-1] for a in amounts)
        phrases = {p: any(p in r for r in replies) for p in case.get("expect_in_replies", [])}
        results.append({
            "id": case["id"], "category": case["category"], "joint": all(slots.values()),
            "quote": quote_ok, "phrases": all(phrases.values()) if phrases else True,
            "wrong": {k: {"expected": case["expect"][k], "got": got.get(k)} for k, ok in slots.items() if not ok},
            "missing_phrases": [p for p, ok in phrases.items() if not ok],
            "transcript": [{"member": t, "bot": r} for t, r in zip(case["turns"], replies)],
        })
    n = len(results)
    per_slot = defaultdict(lambda: [0, 0])
    for r, case in zip(results, (json.loads(l) for l in dataset.read_text().splitlines() if l.strip())):
        for k in case["expect"]:
            per_slot[k][1] += 1
            per_slot[k][0] += k not in r["wrong"]
    by_cat = defaultdict(lambda: [0, 0])
    for r in results:
        by_cat[r["category"]][1] += 1
        by_cat[r["category"]][0] += r["joint"] and r["quote"] and r["phrases"]
    return {
        "conversations": n,
        "joint_goal_accuracy": sum(r["joint"] for r in results) / n,
        "quote_accuracy": sum(r["quote"] for r in results) / n,
        "phrase_accuracy": sum(r["phrases"] for r in results) / n,
        "all_correct": sum(r["joint"] and r["quote"] and r["phrases"] for r in results) / n,
        "per_slot": {k: {"correct": c, "total": t, "accuracy": c / t} for k, (c, t) in per_slot.items()},
        "by_category": {k: {"correct": c, "total": t} for k, (c, t) in sorted(by_cat.items())},
        "wrong_slots": dict(Counter(k for r in results for k in r["wrong"])),
        "results": results,
    }


def markdown(report: dict) -> str:
    lines = ["# Benefits chatbot conversation test set", "",
             f"{report['conversations']} conversations. All correct (every slot, the quote and expected phrases): "
             f"**{report['all_correct']:.0%}**", "",
             "| Metric | Score |", "|---|---:|",
             f"| Joint goal accuracy (every slot right) | {report['joint_goal_accuracy']:.0%} |",
             f"| Quote accuracy (last reply has the expected premiums) | {report['quote_accuracy']:.0%} |",
             f"| Expected phrases found | {report['phrase_accuracy']:.0%} |", "",
             "| Slot | Correct | Accuracy |", "|---|---:|---:|"]
    lines += [f"| {k} | {v['correct']}/{v['total']} | {v['accuracy']:.0%} |" for k, v in report["per_slot"].items()]
    lines += ["", "| Category | All correct |", "|---|---:|"]
    lines += [f"| {k} | {v['correct']}/{v['total']} |" for k, v in report["by_category"].items()]
    lines += ["", "## Failures", ""]
    for r in report["results"]:
        if r["joint"] and r["quote"] and r["phrases"]:
            continue
        wrong = "; ".join(f"{k}: expected {v['expected']}, got {v['got']}" for k, v in r["wrong"].items())
        extra = f"; missing phrases {r['missing_phrases']}" if r["missing_phrases"] else ""
        quote = "" if r["quote"] else "; quote wrong or missing"
        lines.append(f"- **{r['id']}** ({r['category']}): {wrong or 'slots right'}{quote}{extra}")
        lines.append(f"  - member said: {' / '.join(t['member'] for t in r['transcript'])}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", type=Path, default=HERE / "benefits_conversations.jsonl")
    parser.add_argument("--out", type=Path, default=HERE / "benefits_conversations_results")
    args = parser.parse_args()
    report = run(args.dataset)
    args.out.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
    args.out.with_suffix(".md").write_text(markdown(report))
    print(markdown(report))


if __name__ == "__main__":
    main()
