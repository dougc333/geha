"""Deterministic example generator for the 35-category task.

Produces labelled (text, category) examples using each category's keyword
vocabulary plus injected confuser terms. Deterministic (seeded) so runs are
reproducible. The probe agent uses this same generator but with fresh seeds and
held-out phrasings to produce *new* cases not in the seed/train set.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .categories import CATEGORIES, CONFUSER_POOL, CategorySpec


@dataclass(frozen=True)
class Example:
    text: str
    label: str
    source: str = "seed"


_INTROS = (
    "Can you help with",
    "I need to know about",
    "Tell me about",
    "Question regarding",
    "Please explain",
    "Looking for info on",
    "I want to",
    "What about",
    "Need details on",
    "How do I handle",
)
_MIDDLES = ("my", "the", "this", "our", "a", "your")
_OUTROS = ("thanks", "thank you", "please advise", "appreciate it", "", "")


class ExampleGenerator:
    """Deterministic generator with an explicit seed and a version offset.

    `version` shifts the seed so later iterations produce distinct phrasings
    (this is how the probe agent creates genuinely new test cases).
    """

    def __init__(self, seed: int = 0, version: int = 0):
        self._rng = random.Random(seed * 1000003 + version * 7919)

    def _shuffle(self, items):
        items = list(items)
        self._rng.shuffle(items)
        return items

    def one(self, spec: CategorySpec, *, forced_keywords: int = 1) -> Example:
        kws = self._shuffle(spec.keywords)[: max(1, forced_keywords)]
        confusers = self._rng.sample(CONFUSER_POOL, self._rng.randint(1, 3))
        parts = (
            [
                self._rng.choice(_INTROS),
                self._rng.choice(_MIDDLES),
            ]
            + kws
            + confusers
        )
        text = " ".join(parts)
        if self._rng.random() < 0.4:
            text += " " + self._rng.choice(_OUTROS).strip()
        text = " ".join(text.split())
        return Example(text=text, label=spec.name, source="seed")

    def dataset(
        self,
        per_category: int,
        *,
        forced_keywords: int = 1,
        rng: random.Random | None = None,
    ) -> list[Example]:
        """Return `per_category` examples for every category (total = 35*n)."""
        pick = rng or self._rng
        out: list[Example] = []
        for spec in CATEGORIES:
            for _ in range(per_category):
                out.append(self.one(spec, forced_keywords=forced_keywords))
        pick.shuffle(out)
        return out
