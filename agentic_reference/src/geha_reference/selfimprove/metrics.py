"""Evaluation metrics for the 35-category task.

Exposes the three error families the user asked to track:

* **category error rate** — fraction of examples whose predicted category is
  wrong (1 - accuracy, per category and overall).
* **false positive rate** — for the binary high-impact view, fraction of
  non-high-impact examples wrongly predicted as high-impact.
* **misclassification rate** — identical to overall category error for a pure
  classifier, but tracked separately because the loop's "code modifications"
  can trade these off differently (a classifier can cut FPs by over-predicting
  the majority category, which *increases* misclassification).
"""

from __future__ import annotations

from collections import Counter

from .categories import CATEGORIES
from .data import Example

_HIGH_IMPACT = {c.name for c in CATEGORIES if c.high_impact}


def evaluate(predict, examples: list[Example]) -> dict:
    """`predict` is a callable text -> predicted_label."""
    overall_wrong = 0
    fp_wrong = 0
    fn_wrong = 0
    tp = 0
    tn = 0
    category_wrong: Counter = Counter()
    category_total: Counter = Counter()

    for ex in examples:
        predicted = predict(ex.text)
        category_total[ex.label] += 1
        if predicted != ex.label:
            overall_wrong += 1
            category_wrong[ex.label] += 1

        true_hi = ex.label in _HIGH_IMPACT
        pred_hi = predicted in _HIGH_IMPACT
        if true_hi and pred_hi:
            tp += 1
        elif not true_hi and not pred_hi:
            tn += 1
        elif not true_hi and pred_hi:
            fp_wrong += 1
        else:
            fn_wrong += 1

    n = len(examples) or 1
    n_hi = sum(1 for e in examples if e.label in _HIGH_IMPACT) or 1
    n_non_hi = len(examples) - n_hi or 1

    per_category_error = {
        name: category_wrong.get(name, 0) / category_total.get(name, 1)
        for name in category_total
    }
    worst_categories = sorted(
        per_category_error.items(), key=lambda kv: kv[1], reverse=True
    )

    return {
        "n": len(examples),
        "category_error_rate": overall_wrong / n,
        "misclassification_rate": overall_wrong / n,
        "accuracy": 1 - overall_wrong / n,
        "false_positive_rate": fp_wrong / n_non_hi,
        "false_negative_rate": fn_wrong / n_hi,
        "true_positive": tp,
        "true_negative": tn,
        "false_positive": fp_wrong,
        "false_negative": fn_wrong,
        "per_category_error": per_category_error,
        "worst_categories": worst_categories,
    }
