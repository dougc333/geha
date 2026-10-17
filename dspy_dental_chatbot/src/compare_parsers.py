"""Keyword parser vs. Bedrock extraction on hard free-text answers, one stage at a time.

Each case is (stage, member's message, acceptable results). A result is a label,
"ASK:a+b" for a clarifying question between a and b, or "" for no match.

    python src/compare_parsers.py                       # Jev (needs TYPESAFE_API_KEY)
    python src/compare_parsers.py --extractor bedrock   # Nova (LLM_EXTRACT_MODEL)
"""

from __future__ import annotations

import argparse
import time

from enrollment_graph import Ambiguous, DentalEnrollmentGraph

CASES = [
    ("member_type", "I retired from the Postal Service in 2019", {"federal_retiree"}),
    ("member_type", "my wife works at the VA and I'm on her plan", {"eligible_family"}),
    ("member_type", "my spouse is a federal employee", {"eligible_family", "ASK:active_employee+eligible_family"}),
    ("member_type", "I'm an annuitant", {"federal_retiree"}),
    ("member_type", "I spent 22 years in the Navy and I'm retired now", {"retired_uniformed"}),
    ("member_type", "I'm a contractor at NASA", {"unclear"}),
    ("opportunity", "it's open season right now isn't it", {"open_season"}),
    ("opportunity", "I just got hired by the FAA last week", {"newly_eligible_or_qle"}),
    ("opportunity_detail", "I just started my federal job", {"newly_eligible"}),
    ("opportunity_detail",
     "Qualifying life event, because I started my federal job but my child needs braces which is a qualifying life event",
     {"newly_eligible", "ASK:newly_eligible+qle"}),
    ("opportunity_detail", "we had a baby", {"qle"}),
    ("qle_event", "my husband passed away in August", {"lose_family_member"}),
    ("qle_event", "we're expecting twins next month", {"acquire_family_member"}),
    ("qle_event", "we just adopted our son", {"acquire_family_member"}),
    ("qle_event", "my employer dropped our dental benefits", {"lose_other_coverage"}),
    ("qle_event", "I got called up for active duty and won't be paid by my agency", {"active_military_nonpay"}),
    ("qle_event", "I'm back at work after a year of unpaid leave", {"return_lwop"}),
    ("qle_event", "we got married and had a baby", {"ASK:acquire_family_member+marriage"}),
    ("qle_event", "my kid needs braces", {""}),
    ("need", "my teenager needs braces", {"orthodontia"}),
    ("need", "I think I need a root canal soon", {"major"}),
    ("need", "just cleanings, cheapest possible", {"routine"}),
]


def shown(value) -> str:
    return "ASK:" + "+".join(sorted(value)) if isinstance(value, Ambiguous) else value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extractor", choices=["jev", "bedrock"], default="jev")
    args = parser.parse_args()
    if args.extractor == "jev":
        from jev_router import JevExtractor
        extractor = JevExtractor()
    else:
        from llm_extract import BedrockExtractor
        extractor = BedrockExtractor()
    keyword = DentalEnrollmentGraph(jev=lambda *_: None)
    llm = DentalEnrollmentGraph(jev=lambda *_: None, extractor=extractor)
    parsers = {
        "member_type": __import__("enrollment_graph").parse_member_type,
        "opportunity": __import__("enrollment_graph").parse_opportunity,
        "opportunity_detail": __import__("enrollment_graph").parse_opportunity_detail,
        "qle_event": __import__("enrollment_graph").parse_qle_event,
        "need": __import__("enrollment_graph").parse_need,
    }
    score = {"keyword": 0, "llm": 0}
    seconds = []
    print(f"extractor: {extractor.name} {getattr(extractor, 'model', '')}\n")
    print(f"{'stage':<19} {'keyword':<38} {extractor.name:<38} message")
    for stage, message, ok in CASES:
        k = shown(keyword._parse(stage, message, parsers[stage]))
        started = time.perf_counter()
        m = shown(llm._parse(stage, message, parsers[stage]))
        seconds.append(time.perf_counter() - started)
        score["keyword"] += k in ok
        score["llm"] += m in ok
        mark = lambda v: ("ok  " if v in ok else "BAD ") + (v or "(no match)")
        print(f"{stage:<19} {mark(k):<38} {mark(m):<38} {message[:70]}")
    n = len(CASES)
    print(f"\ncorrect: keyword {score['keyword']}/{n}, {extractor.name} {score['llm']}/{n}; "
          f"{extractor.name} median {sorted(seconds)[n // 2]:.2f}s, max {max(seconds):.2f}s")


if __name__ == "__main__":
    main()
