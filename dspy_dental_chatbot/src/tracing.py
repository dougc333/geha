"""Langfuse tracing for the enrollment chatbot: one trace per chat turn.

Each trace records the stage, the member's message with SSNs, emails and phone
numbers masked, how the answer was understood (menu, keyword, llm, fallback),
and whether the bot asked again. Bedrock extraction calls appear inside the turn
as generations with token usage. Traces are tagged "dental-enrollment" plus the
parsing mode and anything in TRACE_TAGS (e.g. "simulated").

Off unless DENTAL_TRACING=1. Keys then come from LANGFUSE_PUBLIC_KEY /
LANGFUSE_SECRET_KEY, or, if those aren't set, from the aws_rag SSM parameters
/rag-demo/langfuse-public-key and -secret-key. With no keys, tracing stays off.
"""

from __future__ import annotations

import contextvars
import os
import re
from contextlib import contextmanager, nullcontext

PROJECT_TAG = "dental-enrollment"
_parses: contextvars.ContextVar[list | None] = contextvars.ContextVar("parses", default=None)

_MASKS = (
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I), "[EMAIL]"),
    (re.compile(r"(?<!\d)(?:\+?1[-. ]*)?\(?\d{3}[-. )]*\d{3}[-. ]*\d{4}(?!\d)"), "[PHONE]"),
)


def scrub(text: str) -> str:
    for pattern, mask in _MASKS:
        text = pattern.sub(mask, text)
    return text


def _client():
    if os.getenv("DENTAL_TRACING") != "1":  # opt-in, so unit tests and casual runs send nothing
        return None
    if not os.getenv("LANGFUSE_PUBLIC_KEY"):
        try:
            import boto3
            ssm = boto3.client("ssm", region_name="us-west-2")
            found = {p["Name"]: p["Value"] for p in ssm.get_parameters(
                Names=["/rag-demo/langfuse-public-key", "/rag-demo/langfuse-secret-key"],
                WithDecryption=True)["Parameters"]}
            os.environ["LANGFUSE_PUBLIC_KEY"] = found["/rag-demo/langfuse-public-key"]
            os.environ["LANGFUSE_SECRET_KEY"] = found["/rag-demo/langfuse-secret-key"]
        except Exception:
            return None
    os.environ.setdefault("LANGFUSE_HOST", "https://cloud.langfuse.com")
    from langfuse import get_client
    return get_client()


langfuse = _client()


def note_parse(stage: str, method: str, result) -> None:
    """Record how one answer was understood; called by the graph's parser."""
    parses = _parses.get()
    if parses is not None:
        parses.append({"stage": stage, "method": method, "result": result})


@contextmanager
def turn(thread_id: str, stage: str, message: str, mode: str):
    """Trace one chat turn. Yields finish(result) to call with the graph's result."""
    token = _parses.set([])
    finished: dict = {}

    def finish(result: dict) -> None:
        finished.update(result)

    try:
        if langfuse is None:
            yield finish
            return
        from langfuse import propagate_attributes
        tags = [PROJECT_TAG, mode, *filter(None, os.getenv("TRACE_TAGS", "").split(","))]
        with propagate_attributes(session_id=thread_id, tags=tags):
            with langfuse.start_as_current_observation(
                as_type="agent", name="enrollment-turn",
                input={"stage": stage or "start", "message": scrub(message)},
            ) as observation:
                yield finish
                response = finished.get("response", "")
                after = finished.get("stage", "")
                clarify = "could mean more than one" in response
                observation.update(
                    output={"response": response[:500], "stage": after, "complete": bool(finished.get("complete"))},
                    metadata={"stage_before": stage, "stage_after": after, "parses": _parses.get(),
                              "disagreement": any(isinstance(p["result"], dict) and bool(p["result"].get("disagreement"))
                                                  for p in _parses.get() or []),
                              "clarify": clarify,
                              "reprompt": bool(stage) and after == stage and not clarify
                                          and not finished.get("complete")},
                )
    finally:
        _parses.reset(token)


def generation(name: str, model: str, prompt: str):
    """Context manager for one model call; .update(...) it with output and usage."""
    if langfuse is None:
        return nullcontext(None)
    return langfuse.start_as_current_observation(as_type="generation", name=name, model=model,
                                                 input=scrub(prompt))


def flush() -> None:
    if langfuse is not None:
        langfuse.flush()
