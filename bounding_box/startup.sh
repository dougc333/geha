#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
UI_DIR="${SCRIPT_DIR}/figure_bbox_app/ui"
PYTHON="${REPO_DIR}/.venv/bin/python"
BACKEND_PID=""

cleanup() {
  if [[ -n "${BACKEND_PID}" ]] && kill -0 "${BACKEND_PID}" 2>/dev/null; then
    kill "${BACKEND_PID}" 2>/dev/null || true
    wait "${BACKEND_PID}" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

if [[ ! -x "${PYTHON}" ]]; then
  echo "Python virtual environment not found at ${PYTHON}" >&2
  echo "Create /Users/dc/geha/.venv and install the project dependencies first." >&2
  exit 1
fi

if [[ ! -x "${UI_DIR}/node_modules/.bin/vite" ]]; then
  echo "Frontend dependencies are missing." >&2
  echo "Run: cd ${UI_DIR} && npm install" >&2
  exit 1
fi

cd "${REPO_DIR}"
"${PYTHON}" -m bounding_box.figure_bbox_app.backend --port 8511 &
BACKEND_PID=$!

for _ in {1..40}; do
  if curl --silent --fail http://127.0.0.1:8511/api/document >/dev/null; then
    break
  fi
  if ! kill -0 "${BACKEND_PID}" 2>/dev/null; then
    wait "${BACKEND_PID}"
    exit 1
  fi
  sleep 0.25
done

if ! curl --silent --fail http://127.0.0.1:8511/api/document >/dev/null; then
  echo "The Python backend did not become ready at http://127.0.0.1:8511." >&2
  exit 1
fi

echo
echo "Bounding-box backend: http://127.0.0.1:8511/"
echo "Bounding-box frontend: http://127.0.0.1:5175/"
echo "Press Ctrl+C to stop both servers."
echo

cd "${UI_DIR}"
npm run dev -- --strictPort
