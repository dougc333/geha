"""The probe agent — an independent adversarial test generator.

This is intentionally a *separate* component from the classifier and the loop.
Its job is to manufacture `per_category` brand-new test cases per category each
iteration, distinct from both the seed training set and any previous iteration's
probes. It does this by:

* rotating its own generator version/seed (fresh phrasings every call), and
* forcing different numbers of keyword signals, so cases range from "easy"
  (several keywords, one obvious category) to "hard" (a single keyword and lots
  of confusers, ambiguous against near-miss neighbours).

Because it always produces genuinely new inputs, a classifier that merely
memorises the training set cannot reach zero error on the probes — this is what
exposes overfitting.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from .categories import CATEGORIES
from .data import Example, ExampleGenerator

# How many probes the agent emits per category per iteration.
DEFAULT_PER_CATEGORY = 3


class ProbeAgent:
    """Adversarial example generator writing JSONL test sets to disk."""

    def __init__(self, seed: int = 999):
        self._seed = seed

    def generate(
        self,
        *,
        per_category: int = DEFAULT_PER_CATEGORY,
        iteration: int = 1,
        rng: random.Random | None = None,
    ) -> list[Example]:
        pick = rng or random.Random(self._seed + iteration * 12345)
        examples: list[Example] = []
        for cat_index, spec in enumerate(CATEGORIES):
            # Rotate generator so phrasing differs every iteration.
            gen = ExampleGenerator(
                seed=self._seed + cat_index,
                version=iteration * 10 + cat_index,
            )
            for j in range(per_category):
                # Vary difficulty: 1..2 keyword signals.
                forced = 1 + (pick.random() < 0.5)
                ex = gen.one(spec, forced_keywords=forced)
                examples.append(
                    Example(
                        text=ex.text,
                        label=ex.label,
                        source=f"probe_i{iteration}",
                    )
                )
        pick.shuffle(examples)
        return examples

    def write(
        self,
        output_dir: Path,
        *,
        per_category: int = DEFAULT_PER_CATEGORY,
        iteration: int = 1,
    ) -> list[Example]:
        examples = self.generate(per_category=per_category, iteration=iteration)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"probes_iter{iteration}.jsonl"
        with open(path, "w") as handle:
            for ex in examples:
                handle.write(
                    json.dumps(
                        {"text": ex.text, "label": ex.label, "source": ex.source}
                    )
                    + "\n"
                )
        return examples
