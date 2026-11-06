#!/usr/bin/env bash
# Start the API and the frontend together; stop both on exit. Run through `make dev`.
set -euo pipefail

trap 'kill 0' EXIT

"${PYTHON:-.venv/bin/python}" -m uvicorn backend.app.main:app \
  --host 127.0.0.1 --port 8010 --reload --reload-dir backend --reload-dir src &

npm --prefix frontend run dev &

wait
