#!/bin/zsh
# Assemble the Lambda package in aws/.build: the server code, the one parser it reuses from
# the enrollment chatbot, and only the plan documents the tools read. Paths mirror the repo,
# so tools.py resolves its data exactly as it does locally.
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
OUT="$HERE/.build"

rm -rf "$OUT"
mkdir -p "$OUT/mcp_benefits_server/src" "$OUT/dental_enrollment_chatbot/src"

cp "$HERE/handler.py" "$HERE/requirements.txt" "$OUT/"
cp "$REPO"/mcp_benefits_server/src/{registry,tools,server}.py "$OUT/mcp_benefits_server/src/"
cp "$REPO/dental_enrollment_chatbot/src/guide_tables.py" "$OUT/dental_enrollment_chatbot/src/"
"$REPO/.venv/bin/python" "$HERE/package_crawl_corpus.py" "$OUT"

echo "package: $OUT ($(find "$OUT" -type f | wc -l | tr -d ' ') files, $(du -sh "$OUT" | cut -f1))"
