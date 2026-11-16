#!/usr/bin/env python3
"""Compare one-shot and one-correction AWS RAG on the same gold questions."""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from agentic_rag import NOT_FOUND, AgenticRag  # noqa: E402
from aws_retriever import AwsAgentClient, AwsRagRetriever, BedrockNova  # noqa: E402


def load_questions(path: Path, limit: int | None) -> list[dict[str, Any]]:
    questions = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return questions if limit is None else questions[:limit]


def canonical_source(source: str) -> str:
    """Normalize arXiv versioned filenames (1706.03762v7.pdf -> 1706.03762.pdf)."""
    return re.sub(r"v\d+(?=\.pdf$)", "", Path(source).name)


def document_ids(base_url: str, api_key: str) -> dict[str, str]:
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/documents", headers={"X-API-Key": api_key}
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        rows = json.loads(response.read()).get("documents", [])
    mapping: dict[str, str] = {}
    for row in rows:
        source = str(row.get("source") or "").removeprefix("docling:")
        if source:
            mapping[Path(source).name] = str(row["id"])
            mapping[canonical_source(source)] = str(row["id"])
        if row.get("arxiv_id"):
            mapping[f"{row['arxiv_id']}.pdf"] = str(row["id"])
    return mapping


def percentile_95(values: list[float]) -> float:
    if not values:
        return 0.0
    return sorted(values)[max(0, (95 * len(values) + 99) // 100 - 1)]


def summarize(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    answerable = [row for row in rows if row["fact_total"]]
    unanswerable = [row for row in rows if not row["fact_total"]]
    latencies = [row["latency_ms"] for row in rows]

    def mean(field: str, selected: list[dict[str, Any]] = rows) -> float:
        return statistics.fmean(row[field] for row in selected) if selected else 0.0

    return {
        "questions": len(rows),
        "fact_recall": mean("fact_recall", answerable),
        "source_recall": mean("source_recall", answerable),
        "complete_rate": mean("complete"),
        "grounded_rate": mean("grounded"),
        "correct_abstention_rate": mean("correct_abstention", unanswerable),
        "mean_retrieval_rounds": mean("retrieval_rounds"),
        "followup_rate": mean("used_followup"),
        "mean_generation_attempts": mean("generation_attempts"),
        "median_latency_ms": statistics.median(latencies) if latencies else 0.0,
        "p95_latency_ms": percentile_95(latencies),
    }


def run_mode(
    mode: str,
    max_rewrites: int,
    questions: list[dict[str, Any]],
    source_to_id: dict[str, str],
    base_url: str,
    api_key: str,
    region: str,
    model: str,
    top_k: int,
    judge_facts: bool,
) -> list[dict[str, Any]]:
    nova = BedrockNova(region=region, model_id=model)
    client = AwsAgentClient(AwsRagRetriever(base_url, api_key, top_k=top_k), nova)
    agent = AgenticRag(
        client, assess=nova.assess, check=nova.grounded, max_rewrites=max_rewrites
    )
    rows = []
    for number, item in enumerate(questions, 1):
        started = time.perf_counter()
        result = agent.generate(item["question"])
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        facts = item.get("facts", [])
        supported = nova.score_facts(item["question"], result["response"], facts) if judge_facts else []
        expected_ids = {
            source_to_id[canonical_source(source)]
            for source in item.get("relevant_sources", [])
            if canonical_source(source) in source_to_id
        }
        retrieved_ids = {
            citation.get("document_id") for citation in result.get("citations", [])
            if citation.get("document_id")
        }
        source_recall = len(expected_ids & retrieved_ids) / len(expected_ids) if expected_ids else 0.0
        fact_recall = len(supported) / len(facts) if facts and judge_facts else 0.0
        row = {
            "id": item.get("id", str(number)),
            "category": item.get("category", "uncategorized"),
            "question": item["question"],
            "mode": mode,
            "answer": result["response"],
            "fact_total": len(facts),
            "supported_fact_indices": supported,
            "fact_recall": fact_recall,
            "source_recall": source_recall,
            "complete": bool(result.get("complete")),
            "grounded": bool(result.get("grounded")),
            "correct_abstention": not facts and result["response"].startswith(NOT_FOUND),
            "retrieval_rounds": result["retrieval_rounds"],
            "used_followup": result["retrieval_rounds"] > 1,
            "generation_attempts": result["generation_attempts"],
            "latency_ms": latency_ms,
            "searches": result["searches"],
            "citations": result.get("citations", []),
            "trace": result["trace"],
        }
        rows.append(row)
        print(
            f"[{mode} {number}/{len(questions)}] {row['id']}: "
            f"facts={fact_recall:.0%} sources={source_recall:.0%} "
            f"rounds={row['retrieval_rounds']} grounded={row['grounded']} {latency_ms:.0f}ms",
            flush=True,
        )
    return rows


def markdown_report(summaries: dict[str, dict[str, float | int]]) -> str:
    baseline, corrective = summaries["single_search"], summaries["corrective"]
    metrics = [
        ("Fact recall", "fact_recall", "rate"),
        ("Source recall", "source_recall", "rate"),
        ("Complete-answer rate", "complete_rate", "rate"),
        ("Grounded-answer rate", "grounded_rate", "rate"),
        ("Correct abstention rate", "correct_abstention_rate", "rate"),
        ("Follow-up-search rate", "followup_rate", "rate"),
        ("Mean retrieval rounds", "mean_retrieval_rounds", "number"),
        ("Mean generation attempts", "mean_generation_attempts", "number"),
        ("Median latency", "median_latency_ms", "latency"),
        ("p95 latency", "p95_latency_ms", "latency"),
    ]
    lines = [
        "# AWS corrective RAG A/B evaluation",
        "",
        f"Questions: {baseline['questions']}",
        "",
        "| Metric | Single search | Corrective | Change |",
        "| --- | ---: | ---: | ---: |",
    ]
    for label, key, kind in metrics:
        left, right = float(baseline[key]), float(corrective[key])
        if kind == "rate":
            cells = (f"{left:.1%}", f"{right:.1%}", f"{(right-left)*100:+.1f} pp")
        elif kind == "latency":
            cells = (f"{left:.0f} ms", f"{right:.0f} ms", f"{right-left:+.0f} ms")
        else:
            cells = (f"{left:.2f}", f"{right:.2f}", f"{right-left:+.2f}")
        lines.append(f"| {label} | {cells[0]} | {cells[1]} | {cells[2]} |")
    lines += [
        "",
        "Fact recall is judged in one batched Nova call per answer against the checked-in rubric facts. ",
        "Source recall is calculated from retrieved document IDs. Report numerators and inspect the JSON ",
        "records before making quality claims; this evaluation set is small.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=ROOT / "evals" / "answer_questions.jsonl")
    parser.add_argument("--output-json", type=Path, default=ROOT / "evals" / "aws_agentic_ab_results.json")
    parser.add_argument("--output-md", type=Path, default=ROOT / "evals" / "aws_agentic_ab_results.md")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--skip-fact-judge", action="store_true")
    parser.add_argument("--aws-url", default=os.getenv("AWS_RAG_URL") or os.getenv("CHATBOT_URL"))
    parser.add_argument("--api-key", default=os.getenv("CHATBOT_API_KEY"))
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-west-2"))
    parser.add_argument("--nova-model", default=os.getenv("AGENTIC_NOVA_MODEL", "amazon.nova-lite-v1:0"))
    args = parser.parse_args()
    if not args.aws_url or not args.api_key:
        parser.error("Set AWS_RAG_URL and CHATBOT_API_KEY (the launcher does this automatically)")

    questions = load_questions(args.questions, args.limit)
    ids = document_ids(args.aws_url, args.api_key)
    records: dict[str, list[dict[str, Any]]] = {}
    records["single_search"] = run_mode(
        "single_search", 0, questions, ids, args.aws_url, args.api_key, args.region,
        args.nova_model, args.top_k, not args.skip_fact_judge,
    )
    records["corrective"] = run_mode(
        "corrective", 1, questions, ids, args.aws_url, args.api_key, args.region,
        args.nova_model, args.top_k, not args.skip_fact_judge,
    )
    summaries = {mode: summarize(rows) for mode, rows in records.items()}
    payload = {"configuration": vars(args), "summaries": summaries, "records": records}
    payload["configuration"] = {
        key: str(value) if isinstance(value, Path) else value
        for key, value in payload["configuration"].items()
        if key != "api_key"
    }
    args.output_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    args.output_md.write_text(markdown_report(summaries))
    print(f"\nWrote {args.output_json}\nWrote {args.output_md}")


if __name__ == "__main__":
    main()
