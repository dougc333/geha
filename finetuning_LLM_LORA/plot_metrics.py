"""Training dashboard: loss, generalization gap, LR, grad norm, time, and eval.

Reads ``results/train_log.jsonl`` (and ``results/generator_comparison.json``
when the eval has run) and writes ``results/training_dashboard.png``:

1. train loss (per step + EMA) and validation loss, best checkpoint circled
2. generalization gap = validation loss - mean train loss over the steps since
   the previous validation pass (rising above zero while train falls = overfitting)
3. learning-rate schedule
4. gradient norm (per step + EMA; clipped at 1.0)
5. wall-clock minutes, with the GPU and total time in the title
6. base vs finetuned on the held-out brochure (or "pending" before the eval)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

try:
    from .common import RESULTS_DIR, read_jsonl
    from .plot_loss import ema
except ImportError:  # Permit direct execution from finetuning_LLM_LORA/.
    from common import RESULTS_DIR, read_jsonl
    from plot_loss import ema


SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e2dc"
BLUE = "#2a78d6"  # train / finetuned
BLUE_LIGHT = "#86b6ef"  # raw per-step train values
ORANGE = "#eb6834"  # validation
BASE_GRAY = "#a8a69f"  # base model

EVAL_METRICS = [
    ("direct", "answer_f1", "Answer F1 (direct)"),
    ("cot", "answer_f1", "Answer F1 (CoT)"),
    ("cot", "format_ok", "CoT format followed"),
    ("cot", "citation_precision", "Cites gold passage"),
    ("cot", "quote_grounded", "Quotes found in passages"),
]


def style(ax, title: str, ylabel: str, xlabel: str = "epoch") -> None:
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", fontsize=12, color=INK, fontweight="bold")
    ax.set_ylabel(ylabel, color=INK_2)
    ax.set_xlabel(xlabel, color=INK_2)
    ax.tick_params(colors=INK_2, labelsize=9)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)


def epoch_lines(ax, epochs: int) -> None:
    for epoch in range(1, epochs + 1):
        ax.axvline(epoch, color=GRID, linestyle="--", linewidth=0.8, zorder=0)


def plot_eval(ax, comparison: dict | None) -> None:
    if not comparison:
        style(ax, "Held-out brochure eval", "", "")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.text(0.5, 0.5, "pending: run eval_generator.py", ha="center", va="center",
                color=INK_2, fontsize=11, transform=ax.transAxes)
        return
    metrics = comparison["metrics"]
    rows = [(label, metrics[task][key]) for task, key, label in EVAL_METRICS if key in metrics.get(task, {})]
    y = list(range(len(rows)))[::-1]
    height = 0.36
    base = [values["baseline"] for _, values in rows]
    tuned = [values["fine_tuned"] for _, values in rows]
    ax.barh([v + height / 2 + 0.01 for v in y], base, height=height, color=BASE_GRAY, label="base")
    ax.barh([v - height / 2 - 0.01 for v in y], tuned, height=height, color=BLUE, label="finetuned")
    for v, b, t in zip(y, base, tuned):
        ax.text(b + 0.01, v + height / 2 + 0.01, f"{b:.2f}", va="center", fontsize=8, color=INK_2)
        ax.text(t + 0.01, v - height / 2 - 0.01, f"{t:.2f}  ({t - b:+.2f})", va="center", fontsize=8, color=INK)
    ax.set_yticks(y, [label for label, _ in rows])
    ax.set_xlim(0, 1.45)  # room right of the bars for value labels and the legend
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    style(ax, f"Held-out brochure eval (n={metrics['direct']['n']} per task)", "", "score (0–1)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper right", frameon=False, fontsize=9)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, default=RESULTS_DIR / "train_log.jsonl")
    parser.add_argument("--comparison", type=Path, default=RESULTS_DIR / "generator_comparison.json")
    parser.add_argument("--output", type=Path, default=RESULTS_DIR / "training_dashboard.png")
    args = parser.parse_args()

    records = read_jsonl(args.log)
    config = next((r for r in records if r["type"] == "config"), {})
    train = [r for r in records if r["type"] == "train"]
    val = [r for r in records if r["type"] == "val"]
    if not train or not val:
        raise SystemExit(f"Need train and val records in {args.log}")
    comparison = json.loads(args.comparison.read_text()) if args.comparison.exists() else None
    epochs = int(config.get("epochs", 0))

    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.titlepad": 10})
    fig, axes = plt.subplots(2, 3, figsize=(17, 9.5), facecolor=SURFACE)
    (ax_loss, ax_gap, ax_lr), (ax_grad, ax_time, ax_eval) = axes

    x = [r["epoch"] for r in train]
    loss = [r["loss"] for r in train]
    smooth = ema(loss)

    # 1. Loss
    ax_loss.plot(x, loss, color=BLUE_LIGHT, linewidth=1, label="train (per step)")
    ax_loss.plot(x, smooth, color=BLUE, linewidth=2, label="train (EMA)")
    ax_loss.plot([r["epoch"] for r in val], [r["loss"] for r in val], color=ORANGE,
                 linewidth=2, marker="o", markersize=6, label="validation")
    best = min(val, key=lambda r: r["loss"])
    ax_loss.scatter([best["epoch"]], [best["loss"]], s=170, facecolors="none",
                    edgecolors=ORANGE, linewidths=2, zorder=5)
    ax_loss.annotate(f"best {best['loss']:.3f} @ step {best['step']}", (best["epoch"], best["loss"]),
                     textcoords="offset points", xytext=(8, 10), fontsize=9, color=INK)
    epoch_lines(ax_loss, epochs)
    style(ax_loss, "Loss on answer tokens", "cross-entropy")
    ax_loss.legend(frameon=False, fontsize=9)

    # 2. Generalization gap: each validation pass vs the mean train loss of the
    # steps since the previous pass (an EMA lags early and fakes a negative gap).
    gap, previous = [], 0
    for r in val:
        window = [t["loss"] for t in train if previous < t["step"] <= r["step"]]
        if window:
            gap.append((r["epoch"], r["loss"] - sum(window) / len(window)))
        previous = r["step"]
    if gap:
        ax_gap.plot([g[0] for g in gap], [g[1] for g in gap], color=ORANGE, linewidth=2, marker="o", markersize=6)
        values = [g[1] for g in gap] + [0.0]
        pad = max(0.02, (max(values) - min(values)) * 0.25)
        ax_gap.set_ylim(min(values) - pad, max(values) + pad)
    ax_gap.axhline(0, color=INK_2, linewidth=1)
    epoch_lines(ax_gap, epochs)
    style(ax_gap, "Generalization gap (val − recent train)", "loss difference")
    ax_gap.text(0.02, 0.03, "rising above 0 while train falls = overfitting", transform=ax_gap.transAxes,
                va="bottom", fontsize=9, color=INK_2)

    # 3. Learning rate
    ax_lr.plot(x, [r["lr"] for r in train], color=BLUE, linewidth=2)
    epoch_lines(ax_lr, epochs)
    style(ax_lr, "Learning rate (warmup + cosine)", "lr")
    ax_lr.ticklabel_format(axis="y", style="sci", scilimits=(0, 0))

    # 4. Gradient norm
    grad = [r["grad_norm"] for r in train]
    ax_grad.plot(x, grad, color=BLUE_LIGHT, linewidth=1, label="per step")
    ax_grad.plot(x, ema(grad), color=BLUE, linewidth=2, label="EMA")
    ax_grad.axhline(1.0, color=INK_2, linewidth=1, linestyle=":")
    ax_grad.text(0.99, 1.0, "clip = 1.0", transform=ax_grad.get_yaxis_transform(), ha="right",
                 va="bottom", fontsize=8, color=INK_2)
    epoch_lines(ax_grad, epochs)
    style(ax_grad, "Gradient norm (before clipping)", "L2 norm")
    ax_grad.legend(frameon=False, fontsize=9)

    # 5. Wall-clock time
    minutes = [r["elapsed_s"] / 60 for r in train]
    ax_time.plot(x, minutes, color=BLUE, linewidth=2)
    epoch_lines(ax_time, epochs)
    total = max([r["elapsed_s"] for r in train + val]) / 60
    gpu = config.get("gpu") or config.get("device", "?")
    style(ax_time, f"Wall clock: {total:.1f} min on {gpu} ({config.get('torch_dtype', '?')})", "minutes")
    per_step = (train[-1]["elapsed_s"] - train[0]["elapsed_s"]) / max(1, len(train) - 1)
    ax_time.text(0.02, 0.96, f"≈{per_step:.1f} s per step incl. validation passes",
                 transform=ax_time.transAxes, va="top", fontsize=9, color=INK_2)

    # 6. Eval
    plot_eval(ax_eval, comparison)

    fig.suptitle(
        f"LoRA r={config.get('lora_rank', '?')} on {config.get('base_model', '?')} · "
        f"{config.get('train_examples', '?')} train / {config.get('validation_examples', '?')} val examples · "
        f"{config.get('steps_per_epoch', '?')} steps per epoch",
        x=0.01, ha="left", fontsize=14, color=INK, fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=150, facecolor=SURFACE)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
