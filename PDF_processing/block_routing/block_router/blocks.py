"""Bounding boxes for blocks: deterministic candidates, a prompt that lets a model CHOOSE among them, validation.

The model never invents coordinates. Python finds candidate horizontal cuts (blank gaps and long ruling lines)
from the page image, the model picks which cuts bound which named block, and the result is validated; if the
reply is invalid, a deterministic fallback splits at the strongest cuts. (Horizontal bands only; vertical splits
inside a band are a next step, as in ocr-mini-bench's blocking pipeline.)
"""
from __future__ import annotations

import json
from typing import Any

import numpy as np
from PIL import Image

PAGE_TOP, PAGE_BOTTOM = "page_top", "page_bottom"


def _ink(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("L")) < 200


def candidate_cuts(image: Image.Image, min_gap_frac: float = 0.012, rule_frac: float = 0.35) -> list[dict[str, Any]]:
    """Candidate horizontal cuts, top to bottom: {'id','y','kind','strength'}. Deterministic."""
    ink = _ink(image)
    h = ink.shape[0]
    row = ink.mean(axis=1)
    cuts: list[dict[str, Any]] = []
    min_gap = max(int(h * min_gap_frac), 3)
    blank = row < 0.002
    y = 0
    while y < h:  # blank gaps: cut in the middle of a run of empty rows
        if blank[y]:
            s = y
            while y < h and blank[y]:
                y += 1
            if y - s >= min_gap and s > 0 and y < h:
                cuts.append({"y": (s + y) // 2, "kind": "gap", "strength": y - s})
        else:
            y += 1
    y = 0
    while y < h:  # ruling lines: runs of rows that are dark across a large share of the width
        if row[y] >= rule_frac:
            s = y
            while y < h and row[y] >= rule_frac:
                y += 1
            if y - s <= max(int(h * 0.01), 6):
                cuts.append({"y": (s + y) // 2, "kind": "rule", "strength": 1000 + int(row[s:y].max() * 100)})
        else:
            y += 1
    cuts.sort(key=lambda c: c["y"])
    merged: list[dict[str, Any]] = []
    for c in cuts:  # drop near-duplicate cuts, keep the stronger
        if merged and c["y"] - merged[-1]["y"] < min_gap:
            if c["strength"] > merged[-1]["strength"]:
                merged[-1] = c
        else:
            merged.append(c)
    for i, c in enumerate(merged):
        c["id"] = f"h{i}"
    return merged


def layout_features(image: Image.Image) -> dict[str, Any]:
    """Cheap, deterministic features the router can reason about."""
    ink = _ink(image)
    cuts = candidate_cuts(image)
    return {"ink_density": round(float(ink.mean()), 4), "n_candidate_cuts": len(cuts),
            "n_rules": sum(c["kind"] == "rule" for c in cuts), "page_px": [image.width, image.height]}


PROPOSAL_PROMPT = """You are splitting a scanned {family} page into horizontal blocks so each block can be read separately.
You may ONLY use the candidate cut ids below; never invent coordinates. Use "page_top" and "page_bottom" for the page edges.
Blocks must be listed top to bottom, must not overlap, and should together cover the content.
Name each block with one of: {block_names}. Skip a name if the page has no such block.

Candidate cuts (id: y position in px, kind):
{cuts}

Reply with JSON only: {{"blocks": [{{"name": "<block name>", "top": "<cut id or page_top>", "bottom": "<cut id or page_bottom>"}}]}}"""


def proposal_prompt(family: str, block_names: list[str], cuts: list[dict[str, Any]]) -> str:
    return PROPOSAL_PROMPT.format(family=family, block_names=", ".join(block_names),
                                  cuts="\n".join(f"{c['id']}: y={c['y']} ({c['kind']})" for c in cuts))


class InvalidProposal(ValueError):
    pass


def boxes_from_proposal(proposal: dict[str, Any], cuts: list[dict[str, Any]], page_w: int, page_h: int,
                        allowed_names: list[str]) -> list[dict[str, Any]]:
    """Validate a model proposal and turn it into pixel boxes. Raises InvalidProposal on any problem."""
    ys = {PAGE_TOP: 0, PAGE_BOTTOM: page_h, **{c["id"]: c["y"] for c in cuts}}
    boxes, last_bottom = [], 0
    blocks = proposal.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise InvalidProposal("no blocks")
    for b in blocks:
        if b.get("name") not in allowed_names:
            raise InvalidProposal(f"unknown block name {b.get('name')!r}")
        if b.get("top") not in ys or b.get("bottom") not in ys:
            raise InvalidProposal(f"unknown cut id in {b}")
        top, bottom = ys[b["top"]], ys[b["bottom"]]
        if bottom - top < 8:
            raise InvalidProposal(f"empty block {b}")
        if top < last_bottom:
            raise InvalidProposal(f"overlapping or unordered block {b}")
        boxes.append({"name": b["name"], "box_px": [0, top, page_w, bottom]})
        last_bottom = bottom
    return boxes


def fallback_boxes(cuts: list[dict[str, Any]], names: list[str], page_w: int, page_h: int) -> list[dict[str, Any]]:
    """Deterministic: use the len(names)-1 strongest cuts, in page order, one block per name."""
    k = max(len(names) - 1, 0)
    chosen = sorted(sorted(cuts, key=lambda c: (-c["strength"], c["y"]))[:k], key=lambda c: c["y"])
    edges = [0] + [c["y"] for c in chosen] + [page_h]
    return [{"name": n, "box_px": [0, edges[i], page_w, edges[i + 1]]} for i, n in enumerate(names[: len(edges) - 1])]


def propose_blocks(image: Image.Image, family: str, block_names: list[str], model_call=None) -> dict[str, Any]:
    """Boxes for the page. `model_call(prompt, image) -> str` returns the model's JSON text; None skips the model.
    Always returns boxes: the model's if valid, otherwise the deterministic fallback (recorded in 'method')."""
    cuts = candidate_cuts(image)
    w, h = image.size
    if model_call is not None:
        try:
            text = model_call(proposal_prompt(family, block_names, cuts), image)
            proposal = json.loads(text[text.index("{"): text.rindex("}") + 1])
            return {"method": "model", "boxes": boxes_from_proposal(proposal, cuts, w, h, block_names), "cuts": cuts}
        except (InvalidProposal, ValueError, KeyError, TypeError, AttributeError) as e:
            return {"method": "fallback", "reason": f"model proposal rejected: {e}", "boxes": fallback_boxes(cuts, block_names, w, h), "cuts": cuts}
    return {"method": "fallback", "reason": "no model call supplied", "boxes": fallback_boxes(cuts, block_names, w, h), "cuts": cuts}
