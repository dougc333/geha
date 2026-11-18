#!/bin/sh
set -eu

workflow_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$workflow_dir"

repo_dir=$(CDPATH= cd -- "$workflow_dir/.." && pwd)
revision=$(git -C "$repo_dir" rev-parse --short HEAD 2>/dev/null || printf 'unversioned')
if ! git -C "$repo_dir" diff --quiet --ignore-submodules -- 2>/dev/null \
   || ! git -C "$repo_dir" diff --cached --quiet --ignore-submodules -- 2>/dev/null \
   || test -n "$(git -C "$repo_dir" ls-files --others --exclude-standard -- \
        document_ingestion_workflow crawl_dir/src geha_processing PDF_processing/bill_lading 2>/dev/null)"; then
  revision="${revision}-dirty"
fi
export APP_BUILD_REVISION=${APP_BUILD_REVISION:-$revision}

# Always rebuild before starting. Docker's layer cache makes unchanged starts fast,
# while changed Python or UI sources produce a new image and recreate both services.
docker compose build
docker compose up -d --wait "$@"

port=${INGESTION_PORT:-8510}
printf '\nDocument ingestion workflow is ready:\n  http://127.0.0.1:%s\n  build: %s\n\n' "$port" "$APP_BUILD_REVISION"
