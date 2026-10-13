"""Compile the DSPy router against labeled enrollment-language examples."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import dspy

from dspy_router import build_program


def load_examples(path: Path) -> list[dspy.Example]:
    rows = json.loads(path.read_text())
    return [
        dspy.Example(
            question=row["question"],
            options_json=json.dumps(row["options"], sort_keys=True),
            member_answer=row["answer"],
            label=row["label"],
            second_label=row["second_label"],
            ambiguous=row["ambiguous"],
        ).with_inputs("question", "options_json", "member_answer")
        for row in rows
    ]


def metric(example, prediction, trace=None) -> float:
    label = str(getattr(prediction, "label", "")).strip()
    ambiguous = str(getattr(prediction, "ambiguous", False)).lower() in {"true", "1", "yes"}
    label_ok = label == example.label
    ambiguity_ok = ambiguous == bool(example.ambiguous)
    score = 0.8 * label_ok + 0.2 * ambiguity_ok
    return bool(score == 1.0) if trace is not None else score


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path(__file__).parents[1] / "data/router_examples.json")
    parser.add_argument("--output", type=Path, default=Path("compiled_router.json"))
    args = parser.parse_args()

    examples = load_examples(args.data)
    if len(examples) < 5:
        raise ValueError("Provide at least five routing examples")
    split = max(1, int(len(examples) * 0.75))
    trainset, valset = examples[:split], examples[split:]
    optimizer = dspy.MIPROv2(metric=metric, auto="light", num_threads=4)
    compiled = optimizer.compile(build_program(), trainset=trainset, valset=valset)
    compiled.save(str(args.output))
    print(f"Saved optimized DSPy router to {args.output}")


if __name__ == "__main__":
    main()

