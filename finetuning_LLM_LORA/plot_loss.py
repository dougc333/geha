"""Plot train and validation loss curves from ``results/train_log.jsonl``."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from .common import RESULTS_DIR, read_jsonl
except ImportError:  # Permit direct execution from finetuning_LLM_LORA/.
    from common import RESULTS_DIR, read_jsonl


def ema(values: list[float], alpha: float = 0.3) -> list[float]:
    smoothed, current = [], None
    for value in values:
        current = value if current is None else alpha * value + (1 - alpha) * current
        smoothed.append(current)
    return smoothed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, default=RESULTS_DIR / "train_log.jsonl")
    parser.add_argument("--output", type=Path, default=RESULTS_DIR / "loss_curve.png")
    args = parser.parse_args()

    records = read_jsonl(args.log)
    config = next((r for r in records if r["type"] == "config"), {})
    train = [r for r in records if r["type"] == "train"]
    val = [r for r in records if r["type"] == "val"]
    if not val:
        raise SystemExit(f"No validation records in {args.log}")

    fig, (ax_loss, ax_lr) = plt.subplots(
        2, 1, figsize=(9, 6.5), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
    )
    if train:
        x = [r["epoch"] for r in train]
        y = [r["loss"] for r in train]
        ax_loss.plot(x, y, color="#9bb7d4", linewidth=1, label="train loss (per step)")
        ax_loss.plot(x, ema(y), color="#1f5fa0", linewidth=2, label="train loss (EMA)")
        ax_lr.plot(x, [r["lr"] for r in train], color="#555555")
    ax_loss.plot(
        [r["epoch"] for r in val], [r["loss"] for r in val],
        color="#d0603a", marker="o", linewidth=2, label="validation loss",
    )
    best = min(val, key=lambda r: r["loss"])
    ax_loss.scatter([best["epoch"]], [best["loss"]], s=160, facecolors="none",
                    edgecolors="#d0603a", linewidths=2, zorder=5)
    ax_loss.annotate(f"best {best['loss']:.3f}\n(epoch {best['epoch']:.2f}, step {best['step']})",
                     (best["epoch"], best["loss"]), textcoords="offset points", xytext=(10, 12))
    for epoch in range(1, int(config.get("epochs", 0)) + 1):
        ax_loss.axvline(epoch, color="#cccccc", linestyle="--", linewidth=0.8)

    ax_loss.set_ylabel("loss (assistant tokens)")
    ax_loss.set_title(
        f"LoRA r={config.get('lora_rank', '?')} on {config.get('base_model', '?')}: "
        f"{config.get('train_examples', '?')} train / {config.get('validation_examples', '?')} val examples"
    )
    ax_loss.legend()
    ax_loss.grid(alpha=0.3)
    ax_lr.set_ylabel("learning rate")
    ax_lr.set_xlabel("epoch")
    ax_lr.grid(alpha=0.3)
    fig.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=150)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
