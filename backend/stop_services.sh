#!/usr/bin/env bash
set -euo pipefail

kill_if_running() {
  local pattern="$1"
  if pgrep -f "$pattern" >/dev/null; then
    echo "Stopping processes matching: $pattern"
    pkill -f "$pattern" || true
  else
    echo "No process found for pattern: $pattern"
  fi
}

kill_if_running "uvicorn app.main:app"
kill_if_running "celery -A app.celery_app worker"
kill_if_running "redis-server"

echo "All matching services signaled to stop."
