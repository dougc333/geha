#!/usr/bin/env bash
# Recreate the GEHA LoRA generator experiment end to end.
# Intended for a CUDA GPU (Google Colab: see colab_train.ipynb).
# Usage: ./run_all.sh            EPOCHS=2 ./run_all.sh
set -euo pipefail
cd "$(dirname "$0")"
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python; fi
EPOCHS="${EPOCHS:-3}"

$PY prepare_sft.py                    # data/*/generator_sft.jsonl
$PY split_stats.py --tokenizer        # results/data_splits.{md,json}
$PY train_lora.py --epochs "$EPOCHS"  # adapter + results/train_log.jsonl
$PY plot_loss.py                      # results/loss_curve.png
$PY eval_generator.py                 # results/generator_{comparison.json,predictions.jsonl}
