"""Should this page be extracted in blocks (bounding boxes + one schema per block) or in a single pass?

Chain, first stage that decides wins; every stage is recorded in `Decision.trace`:
  1. rules     deterministic, from measured quality of a first pass or from how many fields are expected
  2. llm       asked only when the rules are inconclusive; counts only if it answers with enough confidence
  3. jev       when the LLM cannot decide (low confidence, invalid reply, error): TypeSafe Jev `Choice`
  4. fallback  deterministic, used when Jev is unsure, unavailable or fails

Rules and fallback are fully deterministic. The LLM stage is not guaranteed to be; Jev returns probabilities and the
winner is picked deterministically from them (ties broken by name).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable

from .jev import JevRouter, jev_available


@dataclass(frozen=True)
class Config:
    quality_ok: float = 0.97          # first-pass quality at or above this: a single pass is good enough
    quality_poor: float = 0.90        # below this: use blocks
    fields_many: int = 30             # no first pass: at least this many expected fields -> blocks
    fields_few: int = 12              # no first pass: at most this many -> single pass
    fallback_fields: int = 20         # fallback when nothing else decides and the field count is known
    llm_min_confidence: float = 0.7
    block_families: tuple[str, ...] = ("invoice", "bill_of_lading")


@dataclass
class Decision:
    use_blocks: bool
    method: str                       # rules | llm | jev | fallback
    reason: str
    confidence: float | None = None
    trace: list[dict[str, Any]] = field(default_factory=list)


def rule_decision(f: dict[str, Any], cfg: Config = Config()) -> tuple[bool | None, str]:
    if f.get("family") not in cfg.block_families:
        return False, f"no block schemas for family {f.get('family')!r}"
    if f.get("has_versioned_template"):
        return True, "a versioned block geometry exists for this template"
    q = f.get("first_pass_quality")
    if q is not None:
        if q >= cfg.quality_ok:
            return False, f"first-pass quality {q:.3f} >= {cfg.quality_ok}: a single pass is good enough"
        if q < cfg.quality_poor:
            return True, f"first-pass quality {q:.3f} < {cfg.quality_poor}: accuracy is poor, use blocks"
        return None, f"first-pass quality {q:.3f} is in the ambiguous band [{cfg.quality_poor}, {cfg.quality_ok})"
    n = f.get("n_expected_fields")
    if n is not None:
        if n >= cfg.fields_many:
            return True, f"{n} expected fields >= {cfg.fields_many}: dense page, use blocks"
        if n <= cfg.fields_few:
            return False, f"{n} expected fields <= {cfg.fields_few}: simple page, single pass"
        return None, f"{n} expected fields is in the ambiguous band"
    return None, "no first-pass quality and no field count"


def fallback_decision(f: dict[str, Any], cfg: Config = Config()) -> tuple[bool, str]:
    q, n = f.get("first_pass_quality"), f.get("n_expected_fields")
    if q is not None:
        return q < cfg.quality_ok, f"fallback on first-pass quality {q:.3f} vs {cfg.quality_ok}"
    if n is not None:
        return n >= cfg.fallback_fields, f"fallback on {n} expected fields vs {cfg.fallback_fields}"
    return True, "fallback default: nothing is known, so use blocks (costs more, safer for accuracy)"


LLM_PROMPT = """You decide how to extract fields from one document page: "blocks" (split into regions, one schema per region)
or "single_pass". Use blocks when the page is dense or multi-region and one read would likely lose or mix up fields.
Features (JSON): {features}
Reply with JSON only: {{"use_blocks": true|false|null, "confidence": <0-1>, "reason": "<short>"}}. Use null if the features do not decide it."""


def make_llm_decider(client=None, model: str | None = None) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Default LLM stage (Anthropic SDK, temperature 0). Pass your own callable to use another model."""
    model = model or os.environ.get("BLOCK_ROUTER_MODEL", "claude-haiku-4-5")

    def decider(features: dict[str, Any]) -> dict[str, Any]:
        nonlocal client
        if client is None:
            import anthropic
            client = anthropic.Anthropic()
        msg = client.messages.create(model=model, max_tokens=300, temperature=0,
                                     messages=[{"role": "user", "content": LLM_PROMPT.format(features=json.dumps(features, sort_keys=True))}])
        text = msg.content[0].text
        return json.loads(text[text.index("{"): text.rindex("}") + 1])

    return decider


def decide(features: dict[str, Any], llm_decider: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
           jev: JevRouter | None | bool = None, cfg: Config = Config()) -> Decision:
    """`jev`: a JevRouter to use; None = create one if the SDK and TYPESAFE_API_KEY are present (a REAL service call);
    False = never call Jev (use this in tests and offline runs)."""
    trace: list[dict[str, Any]] = []

    use, reason = rule_decision(features, cfg)
    trace.append({"stage": "rules", "use_blocks": use, "reason": reason})
    if use is not None:
        return Decision(use, "rules", reason, None, trace)

    if llm_decider is not None:
        try:
            r = llm_decider(features)
            ok = r.get("use_blocks") in (True, False) and float(r.get("confidence", 0)) >= cfg.llm_min_confidence
            trace.append({"stage": "llm", "accepted": ok, **{k: r.get(k) for k in ("use_blocks", "confidence", "reason")}})
            if ok:
                return Decision(bool(r["use_blocks"]), "llm", str(r.get("reason", "")), float(r["confidence"]), trace)
        except Exception as e:  # noqa: BLE001 - any failure means "the LLM could not decide"
            trace.append({"stage": "llm", "accepted": False, "error": f"{type(e).__name__}: {e}"})
    else:
        trace.append({"stage": "llm", "accepted": False, "skipped": "no LLM decider supplied"})

    router = None if jev is False else jev if jev is not None else (JevRouter() if jev_available() else None)
    if router is not None:
        try:
            r = router.route(features)
            trace.append({"stage": "jev", "accepted": r["use_blocks"] is not None, "probabilities": r["probabilities"], "margin": r["margin"]})
            if r["use_blocks"] is not None:
                return Decision(r["use_blocks"], "jev", f"Jev chose {r['top']!r} (margin {r['margin']})", r["probabilities"].get(r["top"]), trace)
        except Exception as e:  # noqa: BLE001
            trace.append({"stage": "jev", "accepted": False, "error": f"{type(e).__name__}: {e}"})
    else:
        trace.append({"stage": "jev", "accepted": False, "skipped": "SDK or TYPESAFE_API_KEY not available"})

    use, reason = fallback_decision(features, cfg)
    trace.append({"stage": "fallback", "use_blocks": use, "reason": reason})
    return Decision(use, "fallback", reason, None, trace)
