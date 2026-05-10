#!/usr/bin/env sh
set -eu

exec uvicorn "${APP_MODULE:-app.main:app}" \
  --host 0.0.0.0 \
  --port "${PORT:-8080}" \
  --proxy-headers
