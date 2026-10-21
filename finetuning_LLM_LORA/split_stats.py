"""Describe the train/validation/test splits and check them for leakage.

Writes ``results/data_splits.md`` and ``results/data_splits.json``. Pass
``--tokenizer`` to add prompt/target token lengths for the SFT examples.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from statistics import mean

try:
    from .common import BASE_MODEL, DATA_DIR, RESULTS_DIR, SPLITS, chat_ids, read_jsonl
except ImportError:  # Permit direct execution from finetuning_LLM_LORA/.
    from common import BASE_MODEL, DATA_DIR, RESULTS_DIR, SPLITS, chat_ids, read_jsonl


def split_summary(split: str, tokenizer=None) -> dict:
    chunks = read_jsonl(DATA_DIR / split / "chunks.jsonl")
    qa = read_jsonl(DATA_DIR / split / "qa_pairs.jsonl")
    sft_path = DATA_DIR / split / "generator_sft.jsonl"
    sft = read_jsonl(sft_path) if sft_path.exists() else []
    summary = {
        "documents": sorted({c["document_id"] for c in chunks}),
        "sections": sorted({str(c.get("section") or "Unsectioned") for c in chunks}),
        "chunks": len(chunks),
        "qa_pairs": len(qa),
        "qa_by_synthesizer": dict(Counter(q.get("synthesizer_name", "?") for q in qa)),
        "sft_examples": dict(Counter(e["task"] for e in sft)),
        "chunk_ids": {c["chunk_id"] for c in chunks},
        "questions": {q["question"].strip().lower() for q in qa},
        "qa_source_ids": {cid for q in qa for cid in q.get("source_chunk_ids", [])},
    }
    if tokenizer and sft:
        lengths = {"prompt": [], "target": []}
        for example in sft:
            prompt = len(chat_ids(tokenizer, example["messages"][:-1], add_generation_prompt=True))
            lengths["prompt"].append(prompt)
            lengths["target"].append(len(chat_ids(tokenizer, example["messages"])) - prompt)
        summary["tokens"] = {
            key: {"min": min(v), "mean": round(mean(v)), "max": max(v)} for key, v in lengths.items()
        }
    return summary


def leakage_checks(summaries: dict) -> dict[str, bool]:
    train, validation, test = (summaries[s] for s in SPLITS)
    return {
        "chunk ids disjoint (train/val/test)": not (
            train["chunk_ids"] & validation["chunk_ids"]
            or train["chunk_ids"] & test["chunk_ids"]
            or validation["chunk_ids"] & test["chunk_ids"]
        ),
        "sections disjoint (train vs val)": not set(train["sections"]) & set(validation["sections"]),
        "documents disjoint (train+val vs test)": not (
            set(train["documents"] + validation["documents"]) & set(test["documents"])
        ),
        "questions disjoint (all splits)": not (
            train["questions"] & validation["questions"]
            or train["questions"] & test["questions"]
            or validation["questions"] & test["questions"]
        ),
        "every QA source chunk is in its own split": all(
            summaries[s]["qa_source_ids"] <= summaries[s]["chunk_ids"] for s in SPLITS
        ),
    }


def markdown(summaries: dict, checks: dict[str, bool]) -> str:
    lines = [
        "# Data splits",
        "",
        "| | train | validation | test |",
        "| --- | ---: | ---: | ---: |",
    ]
    def row(label, fn):
        lines.append(f"| {label} | " + " | ".join(str(fn(summaries[s])) for s in SPLITS) + " |")
    row("source document", lambda s: ", ".join(d.replace("fedvip--2026-geha-dental-", "") for d in s["documents"]))
    row("sections", lambda s: len(s["sections"]))
    row("chunks (retrieval corpus / distractor pool)", lambda s: s["chunks"])
    row("QA pairs", lambda s: s["qa_pairs"])
    row("SFT examples: direct", lambda s: s["sft_examples"].get("direct", 0))
    row("SFT examples: cot", lambda s: s["sft_examples"].get("cot", 0))
    if "tokens" in summaries["train"]:
        row("prompt tokens min/mean/max", lambda s: "{min}/{mean}/{max}".format(**s["tokens"]["prompt"]))
        row("target tokens min/mean/max", lambda s: "{min}/{mean}/{max}".format(**s["tokens"]["target"]))
    lines += ["", "## Leakage checks", ""]
    lines += [f"- [{'x' if ok else ' '}] {name}" for name, ok in checks.items()]
    lines += ["", "## Sections per split", ""]
    for split in SPLITS:
        lines.append(f"**{split}**: " + "; ".join(summaries[split]["sections"]))
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tokenizer", nargs="?", const=BASE_MODEL, help="add token lengths (default model if no value)")
    args = parser.parse_args()
    tokenizer = None
    if args.tokenizer:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(args.tokenizer)

    summaries = {split: split_summary(split, tokenizer) for split in SPLITS}
    checks = leakage_checks(summaries)
    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "data_splits.md").write_text(markdown(summaries, checks))
    serializable = {
        split: {k: v for k, v in s.items() if not isinstance(v, set)} for split, s in summaries.items()
    }
    (RESULTS_DIR / "data_splits.json").write_text(
        json.dumps({"splits": serializable, "leakage_checks": checks}, indent=2)
    )
    print(markdown(summaries, checks))
    if not all(checks.values()):
        raise SystemExit("Leakage check failed")


if __name__ == "__main__":
    main()
