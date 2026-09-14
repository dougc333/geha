"""Self-improving loop over the 35-category task.

Demonstrates the overfitting signature the user asked to surface:

1. Build a seed training set + a fixed held-out eval set (disjoint from train).
2. For each of N iterations:
   a. Retrain the classifier, turning up the ``memorization`` knob as a stand-in
      for "code modifications that chase error -> 0" (this is the overfit move).
   b. Evaluate on the *training* set and the *held-out* set.
   c. Delegate to the separate ProbeAgent to generate 3 new cases per category,
      write them to ``adv_test_loop_<i>/``, and evaluate on them.
   d. Report category error, false-positive rate, misclassification rate, and
      whether each is increasing or decreasing vs the previous iteration.

Expected result (the whole point): training error collapses toward zero as
memorization rises, but held-out and adversarial-probe error stay high / rise —
the textbook overfitting signature. Chasing 0 on seen data does not generalise.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from .categories import category_names
from .classifier import OverfitClassifier
from .data import Example, ExampleGenerator
from .metrics import evaluate
from .probe import ProbeAgent


@dataclass
class IterResult:
    iteration: int
    memorization: float
    train: dict
    heldout: dict
    probe: dict
    direction: dict[str, str]


def _fmt(rate: float) -> str:
    return f"{rate * 100:.2f}%"


def _direction(prev: float | None, cur: float) -> str:
    if prev is None:
        return "—"
    if cur < prev - 1e-9:
        return "decreasing (good)"
    if cur > prev + 1e-9:
        return "INCREASING (overfit / adversarial)"
    return "flat"


def run_loop(
    *,
    iterations: int = 5,
    per_category_probe: int = 3,
    train_per_category: int = 60,
    heldout_per_category: int = 20,
    output_dir: str | Path = "adv_test_loop",
    seed: int = 7,
) -> list[IterResult]:
    output_dir = Path(output_dir)
    gen = ExampleGenerator(seed=seed)
    rng = __import__("random").Random(seed)

    # Fixed seed train + held-out sets (held-out disjoint from train).
    train = gen.dataset(train_per_category)
    heldout = gen.dataset(heldout_per_category)
    # New disjoint held-out rng so train/heldout phrasings differ too.
    held_rng = __import__("random").Random(seed + 1)
    heldout = ExampleGenerator(seed=seed + 1).dataset(
        heldout_per_category, rng=held_rng
    )

    probe_agent = ProbeAgent(seed=seed + 2)
    results: list[IterResult] = []

    prev: dict[str, float | None] = {"train": None, "heldout": None, "probe": None}

    for i in range(1, iterations + 1):
        # "Code modification" this iteration: raise memorization to chase 0.
        memorization = 0.0 if i == 1 else min(0.5 + 0.1 * i, 1.0)

        model = OverfitClassifier(memorization=memorization)
        model.fit(train)

        train_metrics = evaluate(model.predict, train)
        heldout_metrics = evaluate(model.predict, heldout)

        # Delegate adversarial generation to the separate probe agent.
        probes = probe_agent.write(
            output_dir,
            per_category=per_category_probe,
            iteration=i,
        )
        probe_metrics = evaluate(model.predict, probes)

        direction = {
            "train": _direction(prev["train"], train_metrics["category_error_rate"]),
            "heldout": _direction(
                prev["heldout"], heldout_metrics["category_error_rate"]
            ),
            "probe": _direction(prev["probe"], probe_metrics["category_error_rate"]),
        }
        prev["train"] = train_metrics["category_error_rate"]
        prev["heldout"] = heldout_metrics["category_error_rate"]
        prev["probe"] = probe_metrics["category_error_rate"]

        results.append(
            IterResult(
                iteration=i,
                memorization=memorization,
                train=train_metrics,
                heldout=heldout_metrics,
                probe=probe_metrics,
                direction=direction,
            )
        )

    # Persist summary JSON alongside the probe sets.
    summary = []
    for r in results:
        summary.append(
            {
                "iteration": r.iteration,
                "memorization": r.memorization,
                "train": _slice(r.train),
                "heldout": _slice(r.heldout),
                "probe": _slice(r.probe),
                "direction": r.direction,
            }
        )
    (output_dir / "loop_summary.json").write_text(json.dumps(summary, indent=2))
    return results


def _slice(m: dict) -> dict:
    return {
        "category_error_rate": m["category_error_rate"],
        "misclassification_rate": m["misclassification_rate"],
        "false_positive_rate": m["false_positive_rate"],
        "accuracy": m["accuracy"],
    }


def _print_table(results: list[IterResult]) -> None:
    print("\n" + "=" * 88)
    print("SELF-IMPROVING LOOP — 35-category task  (error rates)")
    print("=" * 88)
    header = (
        f"{'iter':<5}{'memorize':<10}"
        f"{'train_err':<12}{'heldout_err':<14}{'probe_err':<12}"
        f"{'FP_rate':<10}{'misclass':<10}"
    )
    print(header)
    print("-" * 88)
    for r in results:
        print(
            f"{r.iteration:<5}{r.memorization:<10.2f}"
            f"{_fmt(r.train['category_error_rate']):<12}"
            f"{_fmt(r.heldout['category_error_rate']):<14}"
            f"{_fmt(r.probe['category_error_rate']):<12}"
            f"{_fmt(r.probe['false_positive_rate']):<10}"
            f"{_fmt(r.probe['misclassification_rate']):<10}"
        )
    print("-" * 88)
    print("FP_rate & misclass shown are on the adversarial probe set.\n")

    print("Per-iteration direction (is error increasing or decreasing?):")
    for r in results:
        print(
            f"  iter {r.iteration}:  train={r.direction['train']}, "
            f"heldout={r.direction['heldout']}, probe={r.direction['probe']}"
        )

    print("\nWorst categories on the final probe set:")
    for name, err in results[-1].probe["worst_categories"][:6]:
        print(f"  {name:<26} {_fmt(err)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="GEHA 35-category self-improve loop")
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--per-category", type=int, default=3)
    parser.add_argument("--output", default="adv_test_loop")
    args = parser.parse_args()

    results = run_loop(
        iterations=args.iterations,
        per_category_probe=args.per_category,
        output_dir=args.output,
    )
    _print_table(results)
    print(f"\nProbe sets + summary written to: {args.output}/")
    print(f"Categories ({len(category_names())}): {', '.join(category_names())}")


if __name__ == "__main__":
    main()
