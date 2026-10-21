#!/usr/bin/env bash
# Bundle code + data for upload to Google Colab (see colab_train.ipynb).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p finetuning_LLM_LORA/dist
rm -f finetuning_LLM_LORA/dist/finetuning_LLM_LORA.zip
zip -qr finetuning_LLM_LORA/dist/finetuning_LLM_LORA.zip finetuning_LLM_LORA \
  -x 'finetuning_LLM_LORA/.venv/*' 'finetuning_LLM_LORA/models/*' 'finetuning_LLM_LORA/dist/*' \
     'finetuning_LLM_LORA/results/*' 'finetuning_LLM_LORA/data/*/generator_sft.jsonl' \
     '*/__pycache__/*' '*.ipynb'
echo "Wrote finetuning_LLM_LORA/dist/finetuning_LLM_LORA.zip"
