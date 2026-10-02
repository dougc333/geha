#!/usr/bin/env python3
"""Claude OCR over the same eight bill-of-lading blocks, scored like the others.

A third provider next to langgraph_paddle_vs_chat5.py, which is left unchanged:
this script imports its prompt pieces (the GPT instructions, per-block cell
counts and the block-6 column hint) and its scoring (score_one, summarize), so
Claude gets exactly the request GPT got and is scored the same way. Output:
claude_run_<UTC>/claude/block_N.json (one per block, same fields as the openai/
files), comparison_results.json, and README_claude.md, which puts Claude next to
the GPT and Paddle results of an existing comparison run (read, not re-run).

    ANTHROPIC_API_KEY=... python claude_block_ocr.py \
        [--compare-run paddle_vs_gpt4o_run_20260927T192115Z] [--model claude-opus-5-5]
    python claude_block_ocr.py --platform bedrock   # Claude on Amazon Bedrock, AWS credentials
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import time
from pathlib import Path
from typing import Any

import anthropic

from langgraph_paddle_vs_chat5 import (
    DEFAULT_BLOCK_DIR,
    DEFAULT_GOLD,
    DEFAULT_OUTPUT_ROOT,
    OPENAI_CELL_COUNTS,
    OPENAI_INSTRUCTIONS,
    OPENAI_LAYOUT_HINTS,
    load_expected,
    score_one,
    summarize,
)

DEFAULT_COMPARE_RUN = DEFAULT_OUTPUT_ROOT / "paddle_vs_gpt4o_run_20260927T192115Z"


def instructions(block: int) -> str:
    """Identical to the text openai_ocr_node sends for this block."""
    return (
        OPENAI_INSTRUCTIONS
        + f" The image contains exactly {OPENAI_CELL_COUNTS[block]} bordered cell or column "
          "regions. Inspect the entire image and return exactly that many "
          "entries in left-to-right, top-to-bottom order. For every entry, "
          "copy the visible heading literally into heading and all remaining "
          "visible text into content. Use an empty heading only when that "
          "region visibly has no heading."
        + OPENAI_LAYOUT_HINTS.get(block, "")
    )


# Same shape as the GPT schema. The exact count is asked for in the prompt and
# checked after the call (cell_count_ok) rather than enforced with minItems.
SCHEMA = {
    "type": "object",
    "properties": {
        "cells": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"heading": {"type": "string"}, "content": {"type": "string"}},
                "required": ["heading", "content"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["cells"],
    "additionalProperties": False,
}


def ocr_block(client: Any, model: str, effort: str, block: int, image: Path,
              platform: str = "anthropic") -> dict[str, Any]:
    prompt = instructions(block)
    started = time.perf_counter()
    base = {"block": block, "provider": "Anthropic", "prompt": prompt}
    # Server-side fallback (a safety-classifier decline is re-run on a fallback
    # model inside the same call) exists on the Claude API only, not on Bedrock.
    fallback = ({"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
                if platform == "anthropic" else {})
    try:
        response = client.beta.messages.create(
            model=model,
            max_tokens=16000,
            system=prompt,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {
                    "type": "base64", "media_type": "image/png",
                    "data": base64.standard_b64encode(image.read_bytes()).decode("ascii"),
                }},
                {"type": "text", "text": f"Transcribe bill-of-lading block {block}."},
            ]}],
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": SCHEMA}},
            **fallback,
        )
    except anthropic.APIError as exc:  # keep partial benchmark results, like the other branches
        return {**base, "status": "error", "model": model,
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "error": f"{type(exc).__name__}: {exc}", "text": ""}
    elapsed = round(time.perf_counter() - started, 3)
    result = {**base, "model": response.model, "requested_model": model, "effort": effort,
              "response_id": response.id, "request_id": response._request_id,
              "elapsed_seconds": elapsed, "stop_reason": response.stop_reason,
              "usage": {"input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens}}
    if response.stop_reason != "end_turn":
        detail = response.stop_details.explanation if response.stop_details else ""
        return {**result, "status": "error", "error": f"stop_reason={response.stop_reason} {detail}".strip(),
                "text": ""}
    cells = json.loads(next(b.text for b in response.content if b.type == "text"))["cells"]
    return {**result, "status": "ok", "structured_cells": cells,
            "cell_count_ok": len(cells) == OPENAI_CELL_COUNTS[block],
            "text": "\n\n".join("\n".join(p for p in (c["heading"], c["content"]) if p) for c in cells)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--block-dir", type=Path, default=DEFAULT_BLOCK_DIR)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--compare-run", type=Path, default=DEFAULT_COMPARE_RUN,
                        help="existing paddle_vs_* run whose GPT and Paddle results go in the report")
    parser.add_argument("--model", default=None, help="default claude-opus-5-5 (Bedrock: anthropic.claude-opus-5-5)")
    parser.add_argument("--platform", default="anthropic", choices=["anthropic", "bedrock"])
    parser.add_argument("--aws-region", default="us-west-2")
    parser.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"])
    args = parser.parse_args()

    expected = load_expected(args.gold)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.output_root / f"claude_run_{stamp}"
    (out / "claude").mkdir(parents=True)

    if args.platform == "bedrock":
        client = anthropic.AnthropicBedrockMantle(aws_region=args.aws_region, max_retries=2, timeout=180)
        args.model = args.model or "anthropic.claude-opus-5-5"
    else:
        client = anthropic.Anthropic(max_retries=2, timeout=180)
        args.model = args.model or "claude-opus-5-5"
    results = []
    for block in range(1, 9):
        result = ocr_block(client, args.model, args.effort, block, args.block_dir / f"block_{block}.png",
                           args.platform)
        (out / "claude" / f"block_{block}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        results.append(result)
        print(json.dumps({"provider": "claude", "block": block, "status": result["status"],
                          "seconds": result["elapsed_seconds"]}), flush=True)

    scored = [score_one(r, expected[r["block"]]) for r in results]
    summary = summarize(scored)
    (out / "comparison_results.json").write_text(json.dumps({
        "schema_version": "1.0", "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "block_dir": str(args.block_dir), "gold_path": str(args.gold),
        "summaries": {"claude": summary}, "results": {"claude": scored},
    }, indent=2, ensure_ascii=False) + "\n")

    other = json.loads((args.compare_run / "comparison_results.json").read_text())
    rows = [(f"Claude ({args.platform})", args.model, summary)]
    for key, name in (("openai", "OpenAI"), ("paddle", "Fireworks PaddleOCR-VL")):
        model = other["results"][key][0].get("model", "")
        rows.append((name, model, other["summaries"][key]))
    by_block = {name: {r["block"]: r for r in res} for name, res in
                (("claude", scored), ("openai", other["results"]["openai"]), ("paddle", other["results"]["paddle"]))}
    lines = [
        f"# Claude ({args.model}) vs GPT and PaddleOCR-VL: bill-of-lading OCR", "",
        f"Claude run `{out.name}` (effort `{args.effort}`); GPT and Paddle results from "
        f"`{args.compare_run.name}` (not re-run). Same eight block images; Claude got the "
        "same instructions, cell counts and block-6 hint as GPT; same recall scoring.", "",
        "| Provider | Model | Matched | Recall | Perfect blocks | OK calls | Total latency | Mean latency |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, model, s in rows:
        lines.append(f"| {name} | `{model}` | {s['matched_items']}/{s['expected_items']} | {s['accuracy_pct']}% | "
                     f"{s['perfect_blocks']}/8 | {s['successful_blocks']}/8 | {s['total_latency_seconds']}s | "
                     f"{s['mean_latency_seconds']}s |")
    lines += ["", "| Block | Claude | Claude missing | Claude s | GPT | GPT s | Paddle | Paddle s |",
              "|---:|---:|---|---:|---:|---:|---:|---:|"]
    for b in range(1, 9):
        c, o, p = by_block["claude"][b], by_block["openai"][b], by_block["paddle"][b]
        missing = ("; ".join(c["missing_items"]) or "None").replace("|", "\\|")
        lines.append(f"| {b} | {c['accuracy_pct']}% | {missing} | {c['elapsed_seconds']} | "
                     f"{o['accuracy_pct']}% | {o['elapsed_seconds']} | {p['accuracy_pct']}% | {p['elapsed_seconds']} |")
    counts = [r["block"] for r in results if r["status"] == "ok" and not r.get("cell_count_ok")]
    lines += ["", f"Blocks where Claude returned a different number of entries than asked: {counts or 'none'}.",
              "Recall only checks that each expected string appears somewhere in the block's text "
              "(lowercase, punctuation removed); it does not penalize extra text, order, or "
              "decimal-point errors.", ""]
    (out / "README_claude.md").write_text("\n".join(lines))
    (args.output_root / "README_claude.md").write_text("\n".join(lines))
    print(json.dumps({"output_dir": str(out), "summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
