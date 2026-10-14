"""Typed questions for the compiled workflow: one yes/no decision per provider and scheme,
answered with a probability.

Every classifier has the same interface:

    result = await classifier.ask(node, evidence)
    # {"probabilities": {"yes": p, "no": 1 - p}, "backend": "...", "model": "...", "usage": {...}}

`node` is the question step from the workflow spec (its `question` text, `choices` and the
`prior` the rules classifier uses); `evidence` is that provider's features from the code
step (workflow_ops.py).

  jev    TypeSafe Jev `Choice` probabilities, called the way dental_enrollment_chatbot/src/
         jev_router.py and dspy_dental_chatbot/src/safety_guard.py call it. Needs the
         typesafe-sdk package and TYPESAFE_API_KEY.
  llm    a cheap model (Claude Haiku 4.5) constrained to {"answer": "yes"|"no", "p_yes": 0..1}
         by structured output. Its probability is self-reported, not calibrated.
  rules  no model: a logistic curve on the step's `score` with the center and scale in the
         spec (hand-set from the clean Synthea baseline, or fitted by compile_workflow.py
         --calibrate). The offline stand-in, so the workflow and its tests run without keys.

make_classifier("auto") picks jev, then llm, then rules, by what is configured.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
from typing import Literal, Protocol

from pydantic import BaseModel, Field


class Classifier(Protocol):
    name: str

    async def ask(self, node: dict, evidence: dict) -> dict: ...


def _evidence_text(evidence: dict) -> str:
    """The evidence a model sees: features without the score (which would anchor it)."""
    return json.dumps({k: v for k, v in evidence.items() if k != "score"}, default=str)


def _yes_no(p_yes: float) -> dict:
    p = min(1.0, max(0.0, float(p_yes)))
    return {"yes": round(p, 4), "no": round(1 - p, 4)}


class RulesClassifier:
    name = "rules"

    async def ask(self, node: dict, evidence: dict) -> dict:
        prior = node["prior"]
        x = float(evidence.get(prior.get("feature", "score"), 0.0))
        p = 1 / (1 + math.exp(-(x - prior["center"]) / prior["scale"]))
        return {"probabilities": _yes_no(p), "backend": self.name, "model": "logistic",
                "usage": {"input_tokens": 0, "output_tokens": 0}}


class Answer(BaseModel):
    answer: Literal["yes", "no"]
    p_yes: float = Field(ge=0.0, le=1.0, description="probability that the answer is yes")


LLM_SYSTEM = """You review one provider's billing evidence for a health plan's payment-integrity
team. Answer the question from the evidence only. Synthetic claims data has noise: an
isolated oddity is not a pattern. p_yes is your probability that the answer is yes."""


class LLMClassifier:
    name = "llm"

    def __init__(self, model=None, model_id: str = "claude-haiku-4-5"):
        self.model_id = model_id
        self._model = model

    def _structured(self):
        if self._model is None:
            from langchain_anthropic import ChatAnthropic
            self._model = ChatAnthropic(model=self.model_id, max_tokens=300, temperature=0)
        return self._model.with_structured_output(Answer, include_raw=True)

    async def ask(self, node: dict, evidence: dict) -> dict:
        choices = "\n".join(f"- {k}: {v}" for k, v in node["choices"].items())
        reply = await self._structured().ainvoke([
            ("system", LLM_SYSTEM),
            ("user", f"Question: {node['question']}\nChoices:\n{choices}\n\nEvidence: {_evidence_text(evidence)}")])
        parsed: Answer = reply["parsed"]
        if parsed is None:
            raise ValueError(f"no structured answer: {reply.get('parsing_error')}")
        meta = getattr(reply["raw"], "usage_metadata", None) or {}
        p = parsed.p_yes if parsed.answer == "yes" or parsed.p_yes < 0.5 else 1 - parsed.p_yes
        return {"probabilities": _yes_no(p), "backend": self.name, "model": self.model_id,
                "usage": {"input_tokens": meta.get("input_tokens", 0), "output_tokens": meta.get("output_tokens", 0)}}


def jev_available() -> bool:
    if not os.getenv("TYPESAFE_API_KEY"):
        return False
    try:
        import typesafe_sdk  # noqa: F401
    except ImportError:
        return False
    return True


class JevClassifier:
    """Jev's `Choice` over the node's choices plus "unsure"; p(yes) renormalized over yes/no."""
    name = "jev"

    def __init__(self, client=None):
        self._client = client

    def _get_client(self):
        if self._client is None:
            from typesafe_sdk import TypeSafeClient
            self._client = TypeSafeClient(api_key=os.environ["TYPESAFE_API_KEY"])
        return self._client

    async def ask(self, node: dict, evidence: dict) -> dict:
        from typesafe_sdk import Choice
        choice = Choice(instructions=f"{node['question']} Judge only from the evidence; an isolated oddity is not a pattern.",
                        criteria={**node["choices"], "unsure": "The evidence does not decide it."})
        response = await asyncio.to_thread(self._get_client().system_one,
                                           state={"provider_evidence": _evidence_text(evidence)}, questions={"q": choice})
        probs = {k: float(v) for k, v in response.choices["q"].probabilities.items()}
        yes, no = probs.get("yes", 0.0), probs.get("no", 0.0)
        p = yes / (yes + no) if yes + no else 0.5
        return {"probabilities": _yes_no(p), "backend": self.name, "model": getattr(response, "model", "jev"),
                "raw_probabilities": probs, "usage": {"input_tokens": 0, "output_tokens": 0}}


def make_classifier(name: str = "auto") -> Classifier:
    if name == "auto":
        name = "jev" if jev_available() else "llm" if os.getenv("ANTHROPIC_API_KEY") else "rules"
    return {"jev": JevClassifier, "llm": LLMClassifier, "rules": RulesClassifier}[name]()
