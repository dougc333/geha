"""Dependency-free classifier for the 35-category task.

Two levers, which correspond to the two ways teams try to "drive error to 0":

* ``idf`` (default True) — **regularisation**. Tokens appearing in many
  categories are downweighted, so shared confuser words ("insurance", "claim")
  can't drown the category-specific keywords. This is the legitimate, generalising
  improvement; it lowers error *without* memorising.

* ``memorization`` (default 0.0) — **the overfit knob**. When > 0 the model
  additionally stores the exact training texts and, at prediction time,
  memorised exact/nearest matches win. This drives *training* error toward 0
  while doing nothing (or harm) for genuinely unseen inputs. It is the "chase
  the number on data you've already seen" move that does not generalise.

The loop turns up ``memorization`` to reproduce the classic overfit signature:
train error collapses, held-out error does not.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from .categories import CATEGORIES
from .data import Example

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_HIGH_IMPACT = {c.name for c in CATEGORIES if c.high_impact}
_EPS = 1e-9


class OverfitClassifier:
    """IDF-weighted keyword classifier with an optional memorisation bank."""

    def __init__(self, memorization: float = 0.0, idf: bool = True):
        self.memorization = memorization
        self.idf = idf
        self._class_weights: dict[str, Counter] = {}
        self._idf: dict[str, float] = {}
        self._mem_bank: list[tuple[str, str]] = []  # (normalised_text, label)

    # ---- training -------------------------------------------------------
    def fit(self, examples: list[Example]) -> None:
        self._class_weights = {name: Counter() for name in {e.label for e in examples}}
        doc_freq: Counter = Counter()
        for ex in examples:
            tokens = set(self._tokens(ex.text))
            for token in tokens:
                self._class_weights[ex.label][token] += 1
            for token in tokens:
                doc_freq[token] += 1

        # IDF: log( N / df ), so tokens that appear everywhere get ~0 weight.
        n_docs = len(examples) or 1
        self._idf = {
            token: math.log(n_docs / (1.0 + df)) + 1.0
            for token, df in doc_freq.items()
        }

        if self.memorization > 0:
            # Store every training example verbatim (the overfitting bank).
            self._mem_bank = [
                (self._norm(ex.text), ex.label) for ex in examples
            ]

    # ---- prediction -----------------------------------------------------
    def predict(self, text: str) -> str:
        # 1) Memorised exact/strongly-overlapping match (overfit path).
        if self.memorization > 0 and self._mem_bank:
            mem_label = self._memorised_predict(text)
            if mem_label is not None:
                return mem_label
        # 2) IDF-weighted keyword vote (generalising path).
        scores: dict[str, float] = {name: 0.0 for name in self._class_weights}
        tokens = set(self._tokens(text))
        for class_name, weights in self._class_weights.items():
            total = 0.0
            for token in tokens:
                weight = weights[token]
                if weight == 0:
                    continue
                if self.idf:
                    weight *= self._idf.get(token, 1.0)
                total += weight
            scores[class_name] = total
        if not scores:
            return "claim_submission"
        best = "claim_submission"
        best_score = -1.0
        for name, score in scores.items():
            if score > best_score:
                best_score = score
                best = name
        return best

    def predict_high_impact(self, text: str) -> bool:
        """Whether the predicted category is a high-impact (FP-positive) one."""
        return self.predict(text) in _HIGH_IMPACT

    # ---- helpers --------------------------------------------------------
    def _memorised_predict(self, text: str) -> str | None:
        norm = self._norm(text)
        for stored_text, label in self._mem_bank:
            # Exact memorisation: perfect on train, useless on new input.
            if stored_text == norm:
                return label
        # Fuzzy memorisation: score by token overlap with any stored example.
        tokens = set(self._tokens(text))
        best_label = None
        best_overlap = 0.0
        for stored_text, label in self._mem_bank:
            overlap = len(tokens & set(self._tokens(stored_text)))
            if overlap > best_overlap:
                best_overlap = overlap
                best_label = label
        if tokens and best_overlap / len(tokens) >= self.memorization:
            return best_label
        return None

    @staticmethod
    def _norm(text: str) -> str:
        return " ".join(_TOKEN_RE.findall(text.lower()))

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return _TOKEN_RE.findall(text.lower())
