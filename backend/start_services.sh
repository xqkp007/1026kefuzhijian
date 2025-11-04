#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"

cd "$PROJECT_ROOT"

if [ ! -d ".venv" ]; then
  echo "[!] Virtual environment .venv not found. Please create it first." >&2
  exit 1
fi

if [ ! -f ".venv/bin/activate" ]; then
  echo "[!] .venv/bin/activate not found." >&2
  exit 1
fi

source .venv/bin/activate

if command -v redis-server >/dev/null 2>&1; then
  if ! pgrep redis-server >/dev/null; then
    echo "[*] Starting Redis..."
    redis-server >/dev/null 2>&1 &
    sleep 1
    if ! pgrep redis-server >/dev/null; then
      echo "[x] Failed to start Redis. Start it manually if needed." >&2
    else
      echo "[✓] Redis started"
    fi
  else
    echo "[!] Redis already running, skipping."
  fi
else
  echo "[!] redis-server not found. Please install Redis (e.g. brew install redis)." >&2
fi

trap_handler() {
  echo "\n[!] Stopping services..."
  kill "$UVICORN_PID" "$CELERY_PID" 2>/dev/null || true
  wait "$UVICORN_PID" "$CELERY_PID" 2>/dev/null || true
  echo "[✓] Services stopped."
}

trap trap_handler INT TERM

echo "[*] Starting uvicorn (foreground)..."
uvicorn app.main:app --reload &
UVICORN_PID=$!

echo "[*] Starting celery worker (foreground)..."
celery -A app.celery_app worker --loglevel=info &
CELERY_PID=$!

wait
