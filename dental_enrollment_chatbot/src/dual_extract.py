"""Run two extractors on every free-text answer and report when they disagree.

The primary's reading is used; the secondary is a cross-check. If the primary
fails (e.g. no Jev key) the secondary's reading is used instead. Both calls run
in parallel, so a turn takes about as long as the slower one.
"""

from __future__ import annotations

import contextvars
import logging
from concurrent.futures import ThreadPoolExecutor


def _same(a: dict, b: dict) -> bool:
    return ((a["decision"], a["label"], sorted(a["candidates"]))
            == (b["decision"], b["label"], sorted(b["candidates"])))


def describe(result: dict) -> str:
    if result["decision"] == "one":
        return result["label"]
    if result["decision"] == "ambiguous":
        return "ask: " + " or ".join(result["candidates"])
    return "no match"


class DualExtractor:
    def __init__(self, primary, secondary):
        self.primary, self.secondary = primary, secondary
        self.name = f"{primary.name}+{secondary.name}"
        self._pool = ThreadPoolExecutor(max_workers=2)

    def __call__(self, question: str, options: dict[str, str], message: str) -> dict:
        # copy_context keeps each call's Langfuse span inside the current turn's trace
        futures = {e.name: self._pool.submit(contextvars.copy_context().run, e, question, options, message)
                   for e in (self.primary, self.secondary)}
        results = {}
        for name, future in futures.items():
            try:
                results[name] = future.result(timeout=20)
            except Exception as error:
                logging.warning("%s extraction failed: %s", name, error)
                results[name] = None
        first, second = results[self.primary.name], results[self.secondary.name]
        chosen = first or second
        if chosen is None:
            raise RuntimeError("both extractors failed")  # graph falls back to keywords
        if first and second and not _same(first, second):
            chosen = {**chosen, "disagreement": {self.primary.name: first, self.secondary.name: second}}
        return chosen
