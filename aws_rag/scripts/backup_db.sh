#!/usr/bin/env bash
# Back up the Neon database (documents, chunks with embeddings, BM25 terms) to S3.
#
#   scripts/backup_db.sh              # dump, upload to s3://<chunks bucket>/backups/
#   scripts/backup_db.sh --keep-local # also keep the dump in backups/ locally
#
# pg_dump must match the server's major version (Neon: Postgres 18); on macOS:
# brew install libpq@18. Custom format (-Fc) is compressed and restored with
# pg_restore; see "Backup and restore" in the README. backups/ in the chunks
# bucket doesn't trigger the embedder (it only watches chunks/*.jsonl).
set -euo pipefail

PG_BIN="${PG_BIN:-/opt/homebrew/opt/libpq@18/bin}"
REGION="${AWS_REGION:-us-west-2}"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="${CHUNKS_BUCKET:-sam-app-chunks-$ACCOUNT}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
FILE="rag_neon_$STAMP.dump"
DIR="$(cd "$(dirname "$0")/.." && pwd)/backups"
mkdir -p "$DIR"

# The URL (with password) stays in the environment, never on the command line.
export PGDATABASE_URL
PGDATABASE_URL="$(aws ssm get-parameter --region "$REGION" --name /rag-demo/database-url \
  --with-decryption --query Parameter.Value --output text)"

"$PG_BIN/pg_dump" --format=custom --no-owner --no-privileges \
  --file="$DIR/$FILE" --dbname="$PGDATABASE_URL"
"$PG_BIN/pg_restore" --list "$DIR/$FILE" > /dev/null  # fails if the file is unreadable

aws s3 cp "$DIR/$FILE" "s3://$BUCKET/backups/$FILE" --region "$REGION" --quiet
echo "backed up $(du -h "$DIR/$FILE" | cut -f1) to s3://$BUCKET/backups/$FILE"

if [[ "${1:-}" != "--keep-local" ]]; then
  rm "$DIR/$FILE"
fi
