#!/usr/bin/env python3
"""Run an approved JSONL evaluation set through e2e_RAG and Ragas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rag_client_class import RagClient
from ragas_evaluator import RagasEvaluator, RagasSample


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSON on {path}:{line_number}: {error}") from error
        if not isinstance(record, dict):
            raise ValueError(f"Expected an object on {path}:{line_number}")
        for field in ("user_input", "reference"):
            if not str(record.get(field, "")).strip():
                raise ValueError(f"Missing {field!r} on {path}:{line_number}")
        records.append(record)
    if not records:
        raise ValueError(f"No evaluation records found in {path}")
    return records


def run_evaluation(
    *,
    pdf: Path,
    dataset: Path,
    output: Path,
    evaluator_model: str,
    reranker_model: str,
) -> dict[str, Any]:
    client = RagClient(files=str(pdf))
    samples: list[RagasSample] = []
    for record in load_jsonl(dataset):
        query = str(record["user_input"])
        generation = client.generate(query, reranker_model=reranker_model)
        samples.append(RagasSample(
            user_input=query,
            response=str(generation["response"]),
            retrieved_contexts=[str(value) for value in generation["retrieved_contexts"]],
            reference=str(record["reference"]),
            reference_contexts=(
                [str(value) for value in record["reference_contexts"]]
                if record.get("reference_contexts") is not None
                else None
            ),
        ))
    evaluator = RagasEvaluator(evaluator_model=evaluator_model)
    result = evaluator.evaluate(samples)
    result.update({
        "pdf": str(pdf.resolve()),
        "dataset": str(dataset.resolve()),
        "reranker_model": reranker_model,
    })
    evaluator.write_json(output, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--evaluator-model", default="gpt-4o-mini")
    parser.add_argument("--reranker-model", default="none", choices=("none", "gpt"))
    args = parser.parse_args()
    result = run_evaluation(
        pdf=args.pdf.expanduser().resolve(),
        dataset=args.dataset.expanduser().resolve(),
        output=args.output.expanduser().resolve(),
        evaluator_model=args.evaluator_model,
        reranker_model=args.reranker_model,
    )
    print(json.dumps({"output": str(args.output), "aggregate": result["aggregate"]}, indent=2))


if __name__ == "__main__":
    main()
