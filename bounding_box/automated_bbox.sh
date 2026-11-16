#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON="${REPO_DIR}/.venv/bin/python"
DEFAULT_PDF="/Users/dc/ocr-mini-bench/bench_documents/Invoices/medical_bill_en.pdf"

usage() {
  cat <<'EOF'
Run the visible Claude/Playwright bounding-box agent.

Usage:
  ./automated_bbox.sh [PDF] [agent options]

Examples:
  ./automated_bbox.sh
  ./automated_bbox.sh /absolute/path/to/document.pdf --pages 1,3,5
  ./automated_bbox.sh /absolute/path/to/document.pdf --pages 1 --model claude-opus-5-5

The default run uses medical_bill_en.pdf and processes page 1. The agent starts
its own backend on port 8512 and opens a visible Chromium window.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ ! -x "${PYTHON}" ]]; then
  echo "Python virtual environment not found at ${PYTHON}" >&2
  exit 1
fi

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "ANTHROPIC_API_KEY is not set in this terminal." >&2
  echo "Export it before running this script; do not store it in the repository." >&2
  exit 1
fi

PDF="${1:-${DEFAULT_PDF}}"
if [[ $# -gt 0 ]]; then
  shift
fi

if [[ ! -f "${PDF}" ]]; then
  echo "PDF not found: ${PDF}" >&2
  exit 1
fi

EXTRA_ARGS=("$@")
if [[ ${#EXTRA_ARGS[@]} -eq 0 ]]; then
  EXTRA_ARGS=(--pages 1)
fi

cd "${REPO_DIR}"
exec "${PYTHON}" -m bounding_box.figure_bbox_app.browser_bbox_agent \
  --pdf "${PDF}" \
  --headed \
  "${EXTRA_ARGS[@]}"
