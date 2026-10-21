"""LoRA instruction-finetune a small chat LLM on GEHA direct + CoT SFT data.

* Loss is computed on assistant tokens only (prompt/passages are masked).
* Every optimizer step appends a ``train`` record to ``results/train_log.jsonl``;
  every ``--eval-every`` steps (and at each epoch end) a ``val`` record is added.
  ``plot_loss.py`` turns that log into loss curves.
* The adapter with the lowest validation loss is saved; ``--patience`` stops
  early after that many evaluations without improvement.
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
    from .common import ADAPTER_DIR, BASE_MODEL, DATA_DIR, RESULTS_DIR, chat_ids, pick_device, pick_dtype, read_jsonl
except ImportError:  # Permit direct execution from finetuning_LLM_LORA/.
    from common import ADAPTER_DIR, BASE_MODEL, DATA_DIR, RESULTS_DIR, chat_ids, pick_device, pick_dtype, read_jsonl


IGNORE_INDEX = -100
LORA_TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


def encode(example: dict, tokenizer, max_length: int) -> dict[str, list[int]]:
    """Tokenize a chat example and mask everything except the assistant reply."""
    prompt_ids = chat_ids(tokenizer, example["messages"][:-1], add_generation_prompt=True)
    full_ids = chat_ids(tokenizer, example["messages"])
    if full_ids[: len(prompt_ids)] != prompt_ids:
        raise ValueError(f"Chat template prefix mismatch for {example['id']}")
    if len(full_ids) > max_length:
        raise ValueError(f"{example['id']} has {len(full_ids)} tokens; raise --max-length")
    labels = [IGNORE_INDEX] * len(prompt_ids) + full_ids[len(prompt_ids):]
    return {"input_ids": full_ids, "labels": labels}


def example_loss(model, encoded: dict, device: torch.device) -> torch.Tensor:
    input_ids = torch.tensor([encoded["input_ids"]], device=device)
    labels = torch.tensor([encoded["labels"]], device=device)
    return model(input_ids=input_ids, labels=labels).loss


@torch.no_grad()
def validation_loss(model, examples: list[dict], device: torch.device) -> float:
    model.eval()
    total = sum(example_loss(model, example, device).item() for example in examples)
    model.train()
    return total / len(examples)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-model", default=BASE_MODEL)
    parser.add_argument("--output-dir", type=Path, default=ADAPTER_DIR)
    parser.add_argument("--log", type=Path, default=RESULTS_DIR / "train_log.jsonl")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--grad-accum", type=int, default=8, help="examples per optimizer step")
    parser.add_argument("--lora-rank", type=int, default=16)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--max-length", type=int, default=3072)
    parser.add_argument("--eval-every", type=int, default=10, help="optimizer steps between val passes")
    parser.add_argument("--patience", type=int, default=0, help="evals without improvement before stopping (0 = off)")
    parser.add_argument("--limit", type=int, help="use only the first N train/val examples (smoke test)")
    parser.add_argument("--device", help="cuda, mps or cpu (default: best available)")
    parser.add_argument("--dtype", default="auto", choices=["auto", "bf16", "fp32"])
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = pick_device(args.device)

    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    train_rows = read_jsonl(DATA_DIR / "train/generator_sft.jsonl")[: args.limit]
    validation_rows = read_jsonl(DATA_DIR / "validation/generator_sft.jsonl")[: args.limit]
    train = [encode(row, tokenizer, args.max_length) for row in train_rows]
    validation = [encode(row, tokenizer, args.max_length) for row in validation_rows]

    dtype = pick_dtype(args.dtype, device, training=True)
    model = AutoModelForCausalLM.from_pretrained(args.base_model, dtype=dtype).to(device)
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    model = get_peft_model(
        model,
        LoraConfig(
            r=args.lora_rank,
            lora_alpha=2 * args.lora_rank,
            lora_dropout=args.lora_dropout,
            target_modules=LORA_TARGETS,
            task_type="CAUSAL_LM",
        ),
    )
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())

    optimizer = torch.optim.AdamW((p for p in model.parameters() if p.requires_grad), lr=args.learning_rate)
    steps_per_epoch = math.ceil(len(train) / args.grad_accum)
    total_steps = steps_per_epoch * args.epochs
    warmup = max(1, total_steps // 10)
    scheduler = torch.optim.lr_scheduler.LambdaLR(
        optimizer,
        lambda step: min(1.0, (step + 1) / warmup)
        * 0.5 * (1 + math.cos(math.pi * min(1.0, step / total_steps))),
    )

    args.log.parent.mkdir(parents=True, exist_ok=True)
    log = args.log.open("w", encoding="utf-8")

    def emit(record: dict) -> None:
        log.write(json.dumps(record) + "\n")
        log.flush()
        print(json.dumps(record), flush=True)

    emit({
        "type": "config",
        **{key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()},
        "device": str(device),
        "gpu": torch.cuda.get_device_name(0) if device.type == "cuda" else None,
        "torch_dtype": str(dtype).removeprefix("torch."),
        "train_examples": len(train),
        "validation_examples": len(validation),
        "steps_per_epoch": steps_per_epoch,
        "total_steps": total_steps,
        "trainable_params": trainable,
        "total_params": total,
    })

    best, bad_evals, step = math.inf, 0, 0
    started = time.time()

    def evaluate(epoch: float) -> bool:
        """Log validation loss, save the adapter if best; return True to stop early."""
        nonlocal best, bad_evals
        loss = validation_loss(model, validation, device)
        improved = loss < best
        emit({"type": "val", "step": step, "epoch": round(epoch, 3), "loss": loss,
              "best": improved, "elapsed_s": round(time.time() - started)})
        if improved:
            best, bad_evals = loss, 0
            model.save_pretrained(args.output_dir)
            tokenizer.save_pretrained(args.output_dir)
        else:
            bad_evals += 1
        return bool(args.patience) and bad_evals >= args.patience

    evaluate(0.0)
    model.train()
    stop = False
    for epoch in range(args.epochs):
        order = list(range(len(train)))
        random.shuffle(order)
        for start in range(0, len(order), args.grad_accum):
            batch = order[start : start + args.grad_accum]
            batch_loss = 0.0
            for index in batch:
                loss = example_loss(model, train[index], device) / len(batch)
                loss.backward()
                batch_loss += loss.item()
            grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0).item()
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad()
            step += 1
            emit({"type": "train", "step": step, "epoch": round(epoch + (start + len(batch)) / len(order), 3),
                  "loss": batch_loss, "lr": scheduler.get_last_lr()[0], "grad_norm": grad_norm,
                  "elapsed_s": round(time.time() - started)})
            end_of_epoch = start + args.grad_accum >= len(order)
            if (step % args.eval_every == 0 or end_of_epoch) and evaluate(epoch + (start + len(batch)) / len(order)):
                stop = True
                break
        if stop:
            print(f"Early stop: {args.patience} evaluations without improvement", flush=True)
            break

    log.close()
    print(f"Saved best adapter (validation loss {best:.4f}) to: {args.output_dir}")


if __name__ == "__main__":
    main()
