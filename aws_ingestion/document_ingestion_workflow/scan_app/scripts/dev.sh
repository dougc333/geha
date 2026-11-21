#!/bin/sh
set -eu

PYTHON_BIN="${PYTHON_BIN:-../../.venv/bin/python}"
BACKEND_PID=""

cleanup() {
  if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

"$PYTHON_BIN" server.py &
BACKEND_PID=$!

i=0
until curl -fsS http://127.0.0.1:8788/api/state >/dev/null 2>&1; do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "Scanner API failed to start." >&2
    wait "$BACKEND_PID"
    exit 1
  fi
  i=$((i + 1))
  if [ "$i" -ge 50 ]; then
    echo "Timed out waiting for scanner API on port 8788." >&2
    exit 1
  fi
  sleep 0.1
done

echo "Scanner API: http://127.0.0.1:8788"
echo "React UI:   http://127.0.0.1:5174"

npm run dev:ui
