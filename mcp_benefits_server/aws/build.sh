#!/bin/zsh
# Assemble the Lambda package in aws/.build: the server code, the one parser it reuses from
# the DSPy chatbot, and only the plan documents the tools read. Paths mirror the repo,
# so tools.py resolves its data exactly as it does locally.
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
OUT="$HERE/.build"
PYTHON_BIN="${PYTHON_BIN:-$REPO/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3)"
fi

rm -rf "$OUT"
mkdir -p "$OUT/mcp_benefits_server/src" "$OUT/dspy_dental_chatbot/src"

cp "$HERE/handler.py" "$HERE/requirements.txt" "$OUT/"
cp "$REPO"/mcp_benefits_server/src/{registry,tools,server}.py "$OUT/mcp_benefits_server/src/"
cp "$REPO/dspy_dental_chatbot/src/guide_tables.py" "$OUT/dspy_dental_chatbot/src/"
"$PYTHON_BIN" "$HERE/package_crawl_corpus.py" "$OUT"

echo "package: $OUT ($(find "$OUT" -type f | wc -l | tr -d ' ') files, $(du -sh "$OUT" | cut -f1))"
