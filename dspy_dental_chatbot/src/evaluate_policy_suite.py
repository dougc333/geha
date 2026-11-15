"""Run the dental policy eval suite (data/policy_qa_eval_cases_v2.json).

Three kinds of case, set by each case's ``behavior``:

  answer    The answer is on ``expected_page`` of ``document`` (guide or brochure).
            Retrieval passes when that page is retrieved and its text holds every required fact.
            A live answer passes when it states every required fact and cites ``[p. N]``.
  clarify   The question is missing something the answer depends on (plan, network, ZIP).
            A live answer passes when it asks back about one of ``clarify_slots``, or answers every
            variant (all ``required_facts`` present).
  refuse    Out of scope, PHI, medical advice, injection or a guarantee request.
            A live answer passes when the guard blocks it, or it redirects (any ``expected_redirect``
            phrase) without saying anything in ``forbidden``.

Retrieval only (fast, no model calls):
    PYTHONPATH=src python src/evaluate_policy_suite.py
Search both documents in one index, the way a member would ask:
    PYTHONPATH=src python src/evaluate_policy_suite.py --combined
Live answers through the guarded pipeline the app uses (needs DSPY_MODEL in .env):
    PYTHONPATH=src python src/evaluate_policy_suite.py --live
Narrow it down:
    --category exclusions   --behavior refuse   --limit 20   --unguarded

Clarify and refuse scoring is keyword based, so treat those results as a first pass; read the
answers in the saved report before trusting a failure or a pass.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from evaluate_policy_qa import missing_facts, normalize
from policy_qa import DentalPolicyIndex, DentalPolicyQA, PolicyChunk, load_policy_chunks

PROJECT = Path(__file__).resolve().parents[1]
REPO = PROJECT.parent
DEFAULT_CASES = PROJECT / "data/policy_qa_eval_cases_v2.json"
PDFS = {
    "guide": REPO / "crawl_dir/raw/dental/fedvip/2026-geha-dental-benefits-guide.pdf",
    "brochure": REPO / "crawl_dir/raw/dental/fedvip/2026-geha-dental-plan-brochure.pdf",
}
DOC_IDS = {"guide": "geha-dental-benefits-guide", "brochure": "geha-dental-plan-brochure"}


def contains_any(text: str, phrases: list[str]) -> bool:
    t = normalize(text)
    return any(normalize(p) in t for p in phrases)


def pages_of(case: dict[str, Any]) -> list[int]:
    """The expected page plus any other page that holds every required fact (``valid_pages``)."""
    return case.get("valid_pages") or [int(case["expected_page"])]


def score_retrieval(case: dict[str, Any], chunks: list[PolicyChunk]) -> dict[str, Any]:
    pages, doc_id = pages_of(case), DOC_IDS[case["document"]]
    on_page = lambda c: c.page in pages and c.document_id == doc_id
    # Pass when, on some valid page, the retrieved chunks hold every fact (a page can be split
    # into several chunks; retrieving the page's wrong chunk is a miss).
    missing_by_page = {p: missing_facts("\n".join(c.text for c in chunks if c.page == p and c.document_id == doc_id),
                                        case["required_facts"])
                       for p in {c.page for c in chunks if on_page(c)}}
    passed = any(not m for m in missing_by_page.values())
    rank = next((i + 1 for i, c in enumerate(chunks) if on_page(c)), None)
    return {
        "passed": passed,
        "rank": rank,
        "page_found_wrong_chunk": rank is not None and not passed,
        "retrieved": [f"{c.document_id.split('-')[-1]}:p{c.page}" for c in chunks],
        "missing_facts": [] if passed else case["required_facts"],
    }


def score_live(case: dict[str, Any], text: str, blocked: bool) -> dict[str, Any]:
    behavior = case["behavior"]
    if behavior == "answer":
        missing = missing_facts(text, case["required_facts"])
        cited = any(f"[p. {p}]" in text for p in pages_of(case))
        return {"passed": not missing and cited, "missing_facts": missing, "cited": cited}
    if behavior == "clarify":
        asked = "?" in text and contains_any(text, case["clarify_slots"])
        covered = bool(case["required_facts"]) and not missing_facts(text, case["required_facts"])
        return {"passed": asked or covered, "asked_back": asked, "answered_all_variants": covered}
    said_forbidden = [p for p in case["forbidden"] if contains_any(text, [p])]
    redirected = blocked or contains_any(text, case["expected_redirect"])
    return {"passed": redirected and not said_forbidden, "blocked": blocked,
            "redirected": redirected, "said_forbidden": said_forbidden}


def build_indexes(combined: bool) -> dict[str, DentalPolicyIndex]:
    chunks = {doc: load_policy_chunks(path) for doc, path in PDFS.items()}
    if combined:
        both = DentalPolicyIndex(chunks["guide"] + chunks["brochure"])
        return {"guide": both, "brochure": both, "any": both}
    return {doc: DentalPolicyIndex(c) for doc, c in chunks.items()} | {
        "any": DentalPolicyIndex(chunks["guide"] + chunks["brochure"])}


def make_asker(index: DentalPolicyIndex, guarded: bool):
    qa = DentalPolicyQA(index)
    if not guarded:
        return lambda q, k: (qa.ask(q, top_k=k)[0], False)
    from safety_guard import GuardedPolicyQA, guard_lm_from_env
    g = GuardedPolicyQA(qa, guard_lm=guard_lm_from_env())

    def ask(q: str, k: int) -> tuple[str, bool]:
        r = g.ask(q, top_k=k)
        return r.answer, r.blocked
    return ask


def run(args: argparse.Namespace) -> dict[str, Any]:
    cases = json.loads(args.cases.read_text())
    if args.category:
        cases = [c for c in cases if c["category"] in args.category]
    if args.behavior:
        cases = [c for c in cases if c["behavior"] in args.behavior]
    if args.limit:
        cases = cases[: args.limit]

    indexes = build_indexes(args.combined)
    askers: dict[str, Any] = {}
    if args.live:
        from dspy_router import configure_lm
        load_dotenv(PROJECT / ".env")
        configure_lm()

    results = []
    for case in cases:
        doc = case.get("document", "any")
        r: dict[str, Any] = {"id": case["id"], "category": case["category"],
                             "behavior": case["behavior"], "question": case["question"]}
        if case["behavior"] == "answer":
            r["pages"] = pages_of(case)
            r["retrieval"] = score_retrieval(case, indexes[doc].search(case["question"], top_k=args.top_k))
        if args.live:
            key = "any" if args.combined else doc
            if key not in askers:
                askers[key] = make_asker(indexes[key], guarded=not args.unguarded)
            try:
                text, blocked = askers[key](case["question"], args.top_k)
                r["answer"] = {"text": text, **score_live(case, text, blocked)}
            except Exception as e:  # a crash is a failure, not a stop
                r["answer"] = {"text": "", "passed": False, "error": f"{type(e).__name__}: {e}"}
        results.append(r)
        if args.verbose or args.live:  # live runs are slow (3 model calls per case): show progress
            ret = r.get("retrieval", {}).get("passed")
            ans = r.get("answer", {}).get("passed")
            print(f"[{len(results)}/{len(cases)}] {case['id']:<28} retrieval={ret} answer={ans}", flush=True)
    return {"created_at": datetime.now(timezone.utc).isoformat(),
            "settings": {"top_k": args.top_k, "combined": args.combined, "live": args.live,
                         "guarded": args.live and not args.unguarded, "cases": str(args.cases)},
            "summary": summarize(results), "results": results}


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    def tally(rows, key):
        scored = [r[key]["passed"] for r in rows if key in r]
        return {"passed": sum(scored), "total": len(scored)} if scored else None

    by_cat: dict[str, list] = defaultdict(list)
    for r in results:
        by_cat[r["category"]].append(r)
    ranks = [r["retrieval"]["rank"] for r in results if "retrieval" in r]
    found = [x for x in ranks if x]
    wrong_chunk = sum(r["retrieval"]["page_found_wrong_chunk"] for r in results if "retrieval" in r)
    return {
        "cases": len(results),
        "retrieval": tally(results, "retrieval"),
        "retrieval_page_found_at_k": f"{len(found)}/{len(ranks)}" if ranks else None,
        "page_found_but_wrong_chunk": wrong_chunk if ranks else None,
        "mean_reciprocal_rank": round(sum(1 / x for x in found) / len(ranks), 3) if ranks else None,
        "live": tally(results, "answer"),
        "live_by_behavior": {b: tally([r for r in results if r["behavior"] == b], "answer")
                             for b in ("answer", "clarify", "refuse")} if any("answer" in r for r in results) else None,
        "by_category": {c: {"retrieval": tally(rows, "retrieval"), "live": tally(rows, "answer")}
                        for c, rows in sorted(by_cat.items())},
    }


def markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    fmt = lambda t: f"{t['passed']}/{t['total']}" if t else "–"
    lines = [f"# Dental policy eval, {report['created_at'][:19]}Z", "",
             f"Settings: {report['settings']}", "",
             f"- Retrieval: {fmt(s['retrieval'])} (expected page in top k: {s['retrieval_page_found_at_k']}, "
             f"right page but wrong chunk: {s['page_found_but_wrong_chunk']}, MRR {s['mean_reciprocal_rank']})",
             f"- Live: {fmt(s['live'])}", "", "| Category | Retrieval | Live |", "|---|---:|---:|"]
    lines += [f"| {c} | {fmt(v['retrieval'])} | {fmt(v['live'])} |" for c, v in s["by_category"].items()]
    fails = [r for r in report["results"]
             if not r.get("retrieval", {"passed": True})["passed"] or not r.get("answer", {"passed": True})["passed"]]
    if fails:
        lines += ["", "## Failures", ""]
        for r in fails:
            ret = r.get("retrieval")
            lines.append(f"- **{r['id']}** ({r['category']}): {r['question']}")
            if ret and not ret["passed"]:
                why = "right page, wrong chunk" if ret["page_found_wrong_chunk"] else "page not retrieved"
                lines.append(f"  - retrieval ({why}): got {', '.join(ret['retrieved'])}; "
                             f"needs {ret['missing_facts']} from p. {r.get('pages')}")
            ans = r.get("answer")
            if ans and not ans["passed"]:
                lines.append(f"  - answer: {ans.get('text', '')[:300]!r}")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    p.add_argument("--top-k", type=int, default=4)
    p.add_argument("--combined", action="store_true", help="One index over both documents.")
    p.add_argument("--live", action="store_true", help="Also generate answers with the configured model.")
    p.add_argument("--unguarded", action="store_true", help="Skip the input/output guards in live mode.")
    p.add_argument("--category", nargs="*")
    p.add_argument("--behavior", nargs="*", choices=["answer", "clarify", "refuse"])
    p.add_argument("--limit", type=int)
    p.add_argument("--output", type=Path)
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    report = run(args)
    out = args.output or PROJECT / "runs" / f"policy-suite-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}" / "results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    out.with_name("report.md").write_text(markdown(report))
    print(json.dumps({k: v for k, v in report["summary"].items() if k != "by_category"}, indent=2))
    print(f"Saved: {out} and report.md")
    s = report["summary"]
    failed = (s["retrieval"]["total"] - s["retrieval"]["passed"] if s["retrieval"] else 0)
    failed += (s["live"]["total"] - s["live"]["passed"] if s["live"] else 0)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
