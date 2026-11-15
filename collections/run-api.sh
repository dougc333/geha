#!/bin/sh
set -eu

if curl --silent --fail --max-time 2 http://127.0.0.1:8520/api/health >/dev/null 2>&1; then
  echo "GEHA collection API already running on http://127.0.0.1:8520"
  while :; do sleep 3600; done
fi

exec /Users/dc/.pyenv/versions/3.12.13/bin/python server.py
