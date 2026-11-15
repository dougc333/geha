"""TypeSafe Jev as the tie-breaker router.

Same call pattern as hapi/fraud/questions.py (JevClassifier): a `Choice` with instructions and criteria, sent with
`TypeSafeClient.system_one(state=..., questions=...)`. Jev returns probabilities over the criteria; the highest one
wins if it is clear of the runner-up and is not "unsure". Nothing is trained here; thresholds are set on a labeled set.
"""
from __future__ import annotations

import json
import os
from typing import Any

ROUTE_INSTRUCTIONS = (
    "Decide how to extract fields from this document page. Choose 'blocks' if the page is dense or has several "
    "distinct regions (tables, party boxes, totals) and a single read is likely to lose or mix up fields. Choose "
    "'single_pass' if the page is simple and one read is likely accurate. Judge only from the features given."
)
CRITERIA = {
    "blocks": "Split the page into blocks and extract each with its own schema.",
    "single_pass": "Extract the whole page in one pass.",
    "unsure": "The features do not decide it.",
}


def jev_available() -> bool:
    if not os.getenv("TYPESAFE_API_KEY"):
        return False
    try:
        import typesafe_sdk  # noqa: F401
    except ImportError:
        return False
    return True


class JevRouter:
    name = "jev"

    def __init__(self, client=None, min_margin: float = 0.15):
        self._client = client
        self.min_margin = min_margin

    def _get_client(self):
        if self._client is None:
            from typesafe_sdk import TypeSafeClient
            self._client = TypeSafeClient(api_key=os.environ["TYPESAFE_API_KEY"])
        return self._client

    def route(self, features: dict[str, Any]) -> dict[str, Any]:
        """Returns {'use_blocks': True|False|None, 'probabilities', 'margin', 'top'}; None means Jev is unsure."""
        from typesafe_sdk import Choice
        choice = Choice(instructions=ROUTE_INSTRUCTIONS, criteria=CRITERIA)
        response = self._get_client().system_one(state={"features": json.dumps(features, sort_keys=True)}, questions={"route": choice})
        return self.interpret({k: float(v) for k, v in response.choices["route"].probabilities.items()})

    def interpret(self, probs: dict[str, float]) -> dict[str, Any]:
        ranked = sorted(probs.items(), key=lambda kv: (-kv[1], kv[0]))  # ties broken by name: deterministic
        top, runner = ranked[0], (ranked[1][1] if len(ranked) > 1 else 0.0)
        margin = round(top[1] - runner, 4)
        if top[0] == "unsure" or margin < self.min_margin:
            return {"use_blocks": None, "probabilities": probs, "margin": margin, "top": top[0]}
        return {"use_blocks": top[0] == "blocks", "probabilities": probs, "margin": margin, "top": top[0]}
