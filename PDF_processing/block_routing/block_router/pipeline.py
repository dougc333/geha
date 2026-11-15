"""Accuracy-driven extraction: single pass first; blocks only when the quality score says accuracy is poor.

  1. single_pass(image) -> record               (injected: your model call for the whole page)
  2. quality() of that record                    (deterministic checks, no ground truth needed)
  3. decide(...)                                 (rules -> LLM -> Jev -> deterministic fallback)
  4. if blocks: propose boxes (model picks among deterministic cuts, else fallback), extract each block with its own
     schema (injected `block_extract`), merge, re-score, and keep whichever of the two records scores higher.

Model calls are injected, so nothing here calls a service by itself.
"""
from __future__ import annotations

from typing import Any, Callable

from PIL import Image

from .blocks import layout_features, propose_blocks
from .decide import Config, Decision, decide
from .quality import quality
from .schemas import FAMILIES, INVOICE_BLOCK_ORDER, merge_invoice, bol_blocks

MERGE = {"invoice": merge_invoice, "bill_of_lading": lambda results: {k: v for r in results.values() for k, v in r.items()}}


def family_blocks(family: str) -> dict[str, dict[str, Any]]:
    return bol_blocks() if family == "bill_of_lading" else FAMILIES[family]


def n_schema_fields(family: str) -> int:
    n = 0
    for s in family_blocks(family).values():
        for p in s["properties"].values():
            n += len(p["items"]["properties"]) if p.get("type") == "array" else 1
    return n


def extract_document(image: Image.Image, family: str, *, single_pass: Callable[[Image.Image], dict[str, Any]],
                     block_extract: Callable[[Image.Image, str, dict[str, Any]], dict[str, Any]],
                     llm_decider=None, jev=None, propose_model_call=None, cfg: Config = Config(),
                     n_expected_fields: int | None = None, has_versioned_template: bool = False) -> dict[str, Any]:
    first = single_pass(image)
    q1 = quality(family, first)
    feats = {"family": family, "first_pass_quality": q1["score"], "n_expected_fields": n_expected_fields,
             "has_versioned_template": has_versioned_template, **layout_features(image)}
    decision: Decision = decide(feats, llm_decider=llm_decider, jev=jev, cfg=cfg)
    out: dict[str, Any] = {"decision": decision, "features": feats, "quality_first": q1, "record": first,
                           "chosen": "single_pass", "blocks": None, "quality_final": q1}
    if not decision.use_blocks:
        return out

    schemas = family_blocks(family)
    order = INVOICE_BLOCK_ORDER if family == "invoice" else list(schemas)
    proposal = propose_blocks(image, family, order, propose_model_call)
    results: dict[str, dict[str, Any]] = {}
    for b in proposal["boxes"]:
        l, t, r, bt = b["box_px"]
        results[b["name"]] = block_extract(image.crop((l, t, r, bt)), b["name"], schemas[b["name"]])
    merged = MERGE[family](results)
    q2 = quality(family, merged)
    out.update(blocks={"method": proposal["method"], "reason": proposal.get("reason"), "boxes": proposal["boxes"],
                       "block_results": results}, quality_block=q2)
    s1, s2 = q1["score"], q2["score"]
    if s2 is not None and (s1 is None or s2 >= s1):  # ties go to blocks: they were chosen because accuracy looked poor
        out.update(record=merged, chosen="blocks", quality_final=q2)
    return out
