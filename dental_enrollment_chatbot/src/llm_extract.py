"""Prototype: read a member's free-text answer with a model on Amazon Bedrock.

The model only maps the member's words onto the question's fixed options; the
state machine and the brochure tables still make every decision. It may answer
"ambiguous" (the chatbot then asks between the candidates) or "none" (it asks
again). Calls run in your AWS account (us-west-2), so member text is not sent to
another company.

Enable it with LLM_EXTRACT=1 (see app.py) or DentalEnrollmentGraph(extractor=BedrockExtractor()).
"""

from __future__ import annotations

import os

import boto3

import tracing

DEFAULT_MODEL = os.getenv("LLM_EXTRACT_MODEL", "amazon.nova-lite-v1:0")

SYSTEM = (
    "You classify a federal dental plan member's reply to one enrollment question.\n"
    "Use only the options listed. Classify what the member says; never infer eligibility.\n"
    "- decision \"one\": the reply clearly selects or describes exactly one option.\n"
    "- decision \"ambiguous\": the reply fits more than one option, or the option the member names "
    "conflicts with facts they state (for example they name a qualifying life event but describe "
    "having just started a federal job). List every plausible option in candidates.\n"
    "- decision \"none\": the reply matches none of the options.\n"
    "Call record_answer exactly once."
)


class BedrockExtractor:
    name = "bedrock"

    def __init__(self, model: str = DEFAULT_MODEL, region: str = "us-west-2"):
        self.model = model
        self.client = boto3.client("bedrock-runtime", region_name=region)

    def __call__(self, question: str, options: dict[str, str], message: str) -> dict:
        """{"decision": "one"|"ambiguous"|"none", "label": str|None, "candidates": [...], "reason": str}"""
        labels = list(options)
        tool = {"toolSpec": {
            "name": "record_answer",
            "description": "Record how the member's reply answers the question.",
            "inputSchema": {"json": {
                "type": "object",
                "properties": {
                    "decision": {"type": "string", "enum": ["one", "ambiguous", "none"]},
                    "label": {"type": "string", "enum": labels, "description": "the option, when decision is one"},
                    "candidates": {"type": "array", "items": {"type": "string", "enum": labels},
                                   "description": "the plausible options, when decision is ambiguous"},
                    "reason": {"type": "string", "description": "one short sentence"},
                },
                "required": ["decision", "reason"],
            }},
        }}
        listing = "\n".join(f"- {label}: {text}" for label, text in options.items())
        prompt = f"QUESTION: {question}\nOPTIONS:\n{listing}\n\nMEMBER'S REPLY:\n{message}"
        with tracing.generation("extract-answer", self.model, prompt) as generation:
            out = self.client.converse(
                modelId=self.model,
                system=[{"text": SYSTEM}],
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                toolConfig={"tools": [tool], "toolChoice": {"tool": {"name": "record_answer"}}},
                inferenceConfig={"maxTokens": 300, "temperature": 0},
            )
            call = next(b["toolUse"]["input"] for b in out["output"]["message"]["content"] if "toolUse" in b)
            result = normalize(call, labels)
            if generation is not None:
                generation.update(output=result, usage_details={"input": out["usage"]["inputTokens"],
                                                                "output": out["usage"]["outputTokens"]})
        return result


def normalize(call: dict, labels: list[str]) -> dict:
    """Drop anything outside the allowed labels and make the decision consistent with it."""
    candidates = [c for c in dict.fromkeys(call.get("candidates") or []) if c in labels]
    label = call.get("label") if call.get("label") in labels else None
    decision = call.get("decision")
    if decision == "ambiguous" and len(candidates) < 2:
        decision, label = ("one", candidates[0]) if candidates else ("one" if label else "none", label)
    if decision == "one" and not label:
        decision = "none"
    return {"decision": decision if decision in ("one", "ambiguous", "none") else "none",
            "label": label if decision == "one" else None,
            "candidates": candidates if decision == "ambiguous" else [],
            "reason": str(call.get("reason", ""))}
