"""Evaluate dental-policy retrieval and, optionally, live DSPy answers."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from policy_qa import DentalPolicyIndex, DentalPolicyQA, PolicyChunk


PROJECT = Path(__file__).resolve().parents[1]
REPO = PROJECT.parent
DEFAULT_CASES = PROJECT / "data/policy_qa_eval_cases.json"
DEFAULT_PDF = REPO / "crawl_dir/raw/dental/fedvip/2026-geha-dental-benefits-guide.pdf"


def normalize(text: str) -> str:
    text = text.lower().replace("–", "-").replace(",", "")
    return re.sub(r"\s+", " ", text).strip()


def missing_facts(text: str, required_facts: list[list[str]]) -> list[list[str]]:
    normalized = normalize(text)
    return [
        alternatives
        for alternatives in required_facts
        if not any(normalize(alternative) in normalized for alternative in alternatives)
    ]


def evaluate_retrieval(case: dict[str, Any], chunks: list[PolicyChunk]) -> dict[str, Any]:
    expected_page = int(case["expected_page"])
    expected_chunks = [chunk for chunk in chunks if chunk.page == expected_page]
    evidence = "\n".join(chunk.text for chunk in expected_chunks)
    missing = missing_facts(evidence, case["required_facts"])
    return {
        "passed": bool(expected_chunks) and not missing,
        "expected_page": expected_page,
        "retrieved_pages": [chunk.page for chunk in chunks],
        "missing_facts": missing,
    }


def run(cases_path: Path, pdf_path: Path, top_k: int, live: bool) -> dict[str, Any]:
    cases = json.loads(cases_path.read_text())
    index = DentalPolicyIndex.from_pdf(pdf_path)
    qa = None
    if live:
        from dspy_router import configure_lm

        load_dotenv(PROJECT / ".env")
        configure_lm()
        qa = DentalPolicyQA(index)

    results = []
    for case in cases:
        chunks = index.search(case["question"], top_k=top_k)
        retrieval = evaluate_retrieval(case, chunks)
        result: dict[str, Any] = {
            "id": case["id"],
            "question": case["question"],
            "retrieval": retrieval,
        }
        if qa is not None:
            answer, answer_chunks = qa.ask(case["question"], top_k=top_k)
            missing = missing_facts(answer, case["required_facts"])
            citation = f"[p. {case['expected_page']}]"
            result["answer"] = {
                "passed": not missing and citation in answer,
                "text": answer,
                "retrieved_pages": [chunk.page for chunk in answer_chunks],
                "missing_facts": missing,
                "required_citation": citation,
            }
        results.append(result)

    retrieval_passed = sum(item["retrieval"]["passed"] for item in results)
    summary: dict[str, Any] = {
        "cases": len(results),
        "retrieval_passed": retrieval_passed,
        "retrieval_failed": len(results) - retrieval_passed,
        "live_answers_evaluated": live,
    }
    if live:
        answer_passed = sum(item["answer"]["passed"] for item in results)
        summary.update(
            answer_passed=answer_passed,
            answer_failed=len(results) - answer_passed,
        )
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_pdf": str(pdf_path),
        "summary": summary,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--live", action="store_true", help="Also call the configured DSPy model.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = run(args.cases, args.pdf, args.top_k, args.live)
    output = args.output
    if output is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = PROJECT / "runs" / f"policy-qa-eval-{stamp}" / "results.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")

    print(json.dumps(report["summary"], indent=2))
    print(f"Saved: {output}")
    failures = report["summary"]["retrieval_failed"]
    failures += report["summary"].get("answer_failed", 0)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
