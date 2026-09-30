#!/usr/bin/env bash
# Start the fraud-agent trace server (serves ui/dist) on http://localhost:8765.
# Needs ANTHROPIC_API_KEY; NOUS_API_KEY is optional (for the Nous Portal model option).
set -euo pipefail
cd "$(dirname "$0")"
# Keys not already in the environment are read from ../../bill_lading/.env when present.
for var in ANTHROPIC_API_KEY OPENAI_API_KEY NOUS_API_KEY NOUS_KEY; do
  if [[ -z "${!var:-}" && -f ../../bill_lading/.env ]] && grep -q -E "^(export )?$var=" ../../bill_lading/.env; then
    value="$(grep -E "^(export )?$var=" ../../bill_lading/.env | head -1 | sed -E "s/^(export )?$var=//; s/^[\"']//; s/[\"']\$//")"
    export "$var=$value"   # quotes around the value are not part of the key
  fi
done
exec uv run -q --no-project --python 3.12 \
  --with langgraph --with langchain-anthropic --with langchain-openai --with langchain-mcp-adapters --with fastapi --with uvicorn \
  python server.py
