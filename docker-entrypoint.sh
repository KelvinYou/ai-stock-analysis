#!/bin/sh
set -eu

if [ "${1:-api}" = "api" ]; then
    exec uvicorn stock_analysis.api.app:app \
        --host 0.0.0.0 \
        --port "${PORT:-8000}"
fi

exec "$@"
