"""Compare the base and LoRA-finetuned generator on the held-out brochure test set.

Both models see the same passages (gold + distractors) and instructions.
Metrics per task:

* ``answer_f1``: SQuAD-style token F1 of the answer against the reference.
* ``format_ok`` (cot): output has an ``Evidence:`` list and an ``Answer:`` line.
* ``citation_precision`` (cot): share of cited passage numbers that are gold.
* ``quote_grounded`` (cot): share of quoted evidence found verbatim in the passages.
"""

from __future__ import annotations

import argparse
import json
import re
import string
from collections import Counter
from pathlib import Path
from statistics import mean

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

try:
    from .prepare_retriever_splits import read_jsonl, write_jsonl
    from .train_generator import BASE_MODEL, DATA_DIR, OUTPUT_DIR, pick_device
except ImportError:  # Permit direct execution from finetuning/.
    from prepare_retriever_splits import read_jsonl, write_jsonl
    from train_generator import BASE_MODEL, DATA_DIR, OUTPUT_DIR, pick_device


RESULTS_DIR = Path(__file__).resolve().parent / "results"


def normalize_tokens(text: str) -> list[str]:
    text = text.lower()
    text = "".join(ch for ch in text if ch not in set(string.punctuation) - {"$", "%"})
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    return text.split()


def token_f1(prediction: str, reference: str) -> float:
    predicted, expected = normalize_tokens(prediction), normalize_tokens(reference)
    common = sum((Counter(predicted) & Counter(expected)).values())
    if not common:
        return 0.0
    precision, recall = common / len(predicted), common / len(expected)
    return 2 * precision * recall / (precision + recall)


def extract_answer(output: str) -> str:
    match = re.search(r"Answer:\s*(.*)", output, flags=re.DOTALL)
    return match.group(1).strip() if match else output.strip()


def score(example: dict, output: str) -> dict:
    answer = extract_answer(output) if example["task"] == "cot" else output.strip()
    result = {
        "answer_f1": token_f1(answer, example["reference_answer"]),
        "answer_words": len(answer.split()),
    }
    if example["task"] == "cot":
        evidence = output.split("Answer:")[0]
        cited = [int(n) for n in re.findall(r"\[(\d+)\]", evidence)]
        quotes = re.findall(r'"([^"]{10,})"', evidence)
        prompt = re.sub(r"\s+", " ", example["messages"][1]["content"])
        result.update(
            format_ok=float("Evidence:" in output and "Answer:" in output and bool(cited)),
            citation_precision=(
                mean(n in example["gold_passages"] for n in cited) if cited else 0.0
            ),
            quote_grounded=(
                mean(re.sub(r"\s+", " ", q) in prompt for q in quotes) if quotes else 0.0
            ),
        )
    return result


@torch.no_grad()
def generate(model, tokenizer, example: dict, device, max_new_tokens: int) -> str:
    input_ids = tokenizer.apply_chat_template(
        example["messages"][:-1], add_generation_prompt=True, return_tensors="pt"
    )
    if hasattr(input_ids, "input_ids"):  # transformers 5 may return BatchEncoding
        input_ids = input_ids["input_ids"]
    input_ids = input_ids.to(device)
    output = model.generate(
        input_ids=input_ids,
        attention_mask=torch.ones_like(input_ids),
        max_new_tokens=max_new_tokens,
        do_sample=False,
        pad_token_id=tokenizer.eos_token_id,
    )
    return tokenizer.decode(output[0, input_ids.shape[1]:], skip_special_tokens=True)


def summarize(rows: list[dict]) -> dict:
    summary: dict = {}
    for task in ("direct", "cot"):
        task_rows = [row for row in rows if row["task"] == task]
        metrics = [key for key in task_rows[0]["base"] if key != "output"]
        summary[task] = {"n": len(task_rows)}
        for key in metrics:
            base = mean(row["base"][key] for row in task_rows)
            tuned = mean(row["finetuned"][key] for row in task_rows)
            summary[task][key] = {
                "baseline": base,
                "fine_tuned": tuned,
                "absolute_change": tuned - base,
            }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--split", default="test")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-new-tokens", type=int, default=320)
    args = parser.parse_args()

    device = pick_device()
    examples = read_jsonl(DATA_DIR / args.split / "generator_sft.jsonl")[: args.limit]
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForCausalLM.from_pretrained(BASE_MODEL, dtype=torch.float32)
    model = PeftModel.from_pretrained(model, args.adapter).to(device).eval()

    rows = []
    for number, example in enumerate(examples, start=1):
        with model.disable_adapter():
            base_output = generate(model, tokenizer, example, device, args.max_new_tokens)
        tuned_output = generate(model, tokenizer, example, device, args.max_new_tokens)
        rows.append(
            {
                "id": example["id"],
                "task": example["task"],
                "reference_answer": example["reference_answer"],
                "base": {"output": base_output, **score(example, base_output)},
                "finetuned": {"output": tuned_output, **score(example, tuned_output)},
            }
        )
        print(f"{number}/{len(examples)} {example['id']}", flush=True)

    RESULTS_DIR.mkdir(exist_ok=True)
    write_jsonl(RESULTS_DIR / "generator_predictions.jsonl", rows)
    comparison = {
        "split": args.split,
        "base_model": BASE_MODEL,
        "adapter": args.adapter.name,
        "metrics": summarize(rows),
    }
    (RESULTS_DIR / "generator_comparison.json").write_text(json.dumps(comparison, indent=2))
    print(json.dumps(comparison, indent=2))


if __name__ == "__main__":
    main()
