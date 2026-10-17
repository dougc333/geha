#!/usr/bin/env zsh

set -eu

cd /Users/dc/geha
source ~/.zshrc
source .venv/bin/activate

if ! python -c "import dspy" >/dev/null 2>&1; then
  print -u2 "DSPy is not installed in /Users/dc/geha/.venv."
  print -u2 "Install it with: uv pip install --python /Users/dc/geha/.venv/bin/python -r dspy_dental_chatbot/requirements.txt"
  exit 1
fi

exec python -m streamlit run dspy_dental_chatbot/src/app.py --server.port 8506
