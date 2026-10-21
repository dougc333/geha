"""LoRA instruction-finetune a small chat LLM on the GEHA direct + CoT SFT data.

Loss is computed on assistant tokens only. The adapter with the lowest
validation loss is kept.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path

import torch
from peft import LoraConfig, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer

try:
    from .prepare_retriever_splits import read_jsonl
except ImportError:  # Permit direct execution from finetuning/.
    from prepare_retriever_splits import read_jsonl


HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
OUTPUT_DIR = HERE / "models/geha-dental-generator-lora"
BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
IGNORE_INDEX = -100


def pick_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def encode(example: dict, tokenizer, max_length: int) -> dict[str, list[int]]:
    """Tokenize a chat example and mask everything except the assistant reply."""
    prompt_ids = tokenizer.apply_chat_template(
        example["messages"][:-1], add_generation_prompt=True, tokenize=True
    )
    full_ids = tokenizer.apply_chat_template(example["messages"], tokenize=True)
    if hasattr(prompt_ids, "input_ids"):  # transformers 5 may return BatchEncoding
        prompt_ids, full_ids = prompt_ids["input_ids"], full_ids["input_ids"]
    if full_ids[: len(prompt_ids)] != prompt_ids:
        raise ValueError(f"Chat template prefix mismatch for {example['id']}")
    if len(full_ids) > max_length:
        raise ValueError(
            f"{example['id']} has {len(full_ids)} tokens; raise --max-length"
        )
    labels = [IGNORE_INDEX] * len(prompt_ids) + full_ids[len(prompt_ids):]
    return {"input_ids": full_ids, "labels": labels}


def batch_loss(model, encoded: dict, device: torch.device) -> torch.Tensor:
    input_ids = torch.tensor([encoded["input_ids"]], device=device)
    labels = torch.tensor([encoded["labels"]], device=device)
    return model(input_ids=input_ids, labels=labels).loss


@torch.no_grad()
def validation_loss(model, examples: list[dict], device: torch.device) -> float:
    model.eval()
    total = sum(batch_loss(model, example, device).item() for example in examples)
    model.train()
    return total / len(examples)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-model", default=BASE_MODEL)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--grad-accum", type=int, default=8)
    parser.add_argument("--lora-rank", type=int, default=16)
    parser.add_argument("--max-length", type=int, default=3072)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = pick_device()

    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    train = [
        encode(row, tokenizer, args.max_length)
        for row in read_jsonl(DATA_DIR / "train/generator_sft.jsonl")
    ]
    validation = [
        encode(row, tokenizer, args.max_length)
        for row in read_jsonl(DATA_DIR / "validation/generator_sft.jsonl")
    ]

    # fp32 weights: M1-class MPS has no native bf16 and fp16 LoRA can diverge.
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model, dtype=torch.float32
    ).to(device)
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    model = get_peft_model(
        model,
        LoraConfig(
            r=args.lora_rank,
            lora_alpha=2 * args.lora_rank,
            lora_dropout=0.05,
            target_modules=[
                "q_proj", "k_proj", "v_proj", "o_proj",
                "gate_proj", "up_proj", "down_proj",
            ],
            task_type="CAUSAL_LM",
        ),
    )
    model.print_trainable_parameters()

    optimizer = torch.optim.AdamW(
        (p for p in model.parameters() if p.requires_grad), lr=args.learning_rate
    )
    total_steps = math.ceil(len(train) / args.grad_accum) * args.epochs
    warmup = max(1, total_steps // 10)
    scheduler = torch.optim.lr_scheduler.LambdaLR(
        optimizer,
        lambda step: min(1.0, (step + 1) / warmup)
        * 0.5 * (1 + math.cos(math.pi * min(1.0, step / total_steps))),
    )

    history = [{"epoch": 0, "validation_loss": validation_loss(model, validation, device)}]
    print(json.dumps(history[-1]), flush=True)
    best = history[0]["validation_loss"]
    model.train()
    for epoch in range(1, args.epochs + 1):
        order = list(range(len(train)))
        random.shuffle(order)
        running, started = 0.0, time.time()
        for index, example_index in enumerate(order, start=1):
            loss = batch_loss(model, train[example_index], device) / args.grad_accum
            loss.backward()
            running += loss.item()
            if index % args.grad_accum == 0 or index == len(order):
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad()
        record = {
            "epoch": epoch,
            "train_loss": running * args.grad_accum / len(order),
            "validation_loss": validation_loss(model, validation, device),
            "seconds": round(time.time() - started),
        }
        history.append(record)
        print(json.dumps(record), flush=True)
        if record["validation_loss"] < best:
            best = record["validation_loss"]
            model.save_pretrained(args.output_dir)
            tokenizer.save_pretrained(args.output_dir)

    (args.output_dir / "training_history.json").write_text(
        json.dumps({"base_model": args.base_model, "history": history}, indent=2)
    )
    print(f"Saved best adapter (validation loss {best:.4f}) to: {args.output_dir}")


if __name__ == "__main__":
    main()
