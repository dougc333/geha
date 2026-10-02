#!/usr/bin/env python3
"""Ragas scores for the agentic RAG, on the same dataset and PDF as evaluate_ragas.py."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from agentic_rag import AgenticRag
from evaluate_ragas import load_jsonl
from rag_client_class import RagClient
from ragas_evaluator import RagasEvaluator, RagasSample


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--evaluator-model", default="gpt-4o-mini")
    parser.add_argument("--reranker-model", default="none", choices=("none", "gpt"))
    args = parser.parse_args()

    agent = AgenticRag(RagClient(files=str(args.pdf)), reranker_model=args.reranker_model)
    samples, steps = [], Counter()
    for record in load_jsonl(args.dataset):
        result = agent.generate(str(record["user_input"]))
        steps.update(line.split(":")[0] for line in result["trace"])
        samples.append(RagasSample(
            user_input=str(record["user_input"]), response=str(result["response"]),
            retrieved_contexts=[str(v) for v in result["retrieved_contexts"]], reference=str(record["reference"]),
            reference_contexts=record.get("reference_contexts")))
    evaluator = RagasEvaluator(evaluator_model=args.evaluator_model)
    report = evaluator.evaluate(samples)
    report.update({"pdf": str(args.pdf.resolve()), "dataset": str(args.dataset.resolve()),
                   "pipeline": "agentic", "agent_steps": dict(steps)})
    evaluator.write_json(args.output, report)
    print(json.dumps({"aggregate": report["aggregate"], "agent_steps": dict(steps)}, indent=2))


if __name__ == "__main__":
    main()
