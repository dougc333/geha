#!/bin/sh
set -eu

pg_restore \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --no-owner \
  --no-privileges \
  /docker-entrypoint-initdb.d/geha_rag.dump
