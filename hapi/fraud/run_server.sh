#!/usr/bin/env bash
# Start the fraud-agent trace server (serves ui/dist) on http://localhost:8765.
# Reads ANTHROPIC_API_KEY from the environment, or from ../../bill_lading/.env.
set -euo pipefail
cd "$(dirname "$0")"
if [[ -z "${ANTHROPIC_API_KEY:-}" && -f ../../bill_lading/.env ]]; then
  export "$(grep '^ANTHROPIC_API_KEY=' ../../bill_lading/.env)"
fi
exec uv run -q --no-project --python 3.12 \
  --with langgraph --with langchain-anthropic --with langchain-mcp-adapters --with fastapi --with uvicorn \
  python server.py
