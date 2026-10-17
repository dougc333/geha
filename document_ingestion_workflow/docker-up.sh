#!/bin/sh
set -eu

workflow_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$workflow_dir"

docker compose up -d --wait "$@"

port=${INGESTION_PORT:-8510}
printf '\nDocument ingestion workflow is ready:\n  http://127.0.0.1:%s\n\n' "$port"
