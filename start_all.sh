#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${ROOT_DIR}/backend"
FRONTEND_DIR="${ROOT_DIR}/frontend"
BACKEND_VENV="${BACKEND_DIR}/.venv/bin/activate"

# Helper: check if a TCP port is free (LISTEN not occupied)
is_port_in_use() {
  local port=$1
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"${port}" -sTCP:LISTEN -nP >/dev/null 2>&1
    return $?
  elif command -v nc >/dev/null 2>&1; then
    nc -z localhost "${port}" >/dev/null 2>&1
    return $?
  else
    return 1
  fi
}

if ! command -v npm >/dev/null 2>&1; then
  echo "[x] npm 未安装，请先安装 Node.js / npm。" >&2
  exit 1
fi

if [ ! -d "${FRONTEND_DIR}/node_modules" ]; then
  echo "[x] frontend/node_modules 不存在，请先在 frontend 目录执行 'npm install'。" >&2
  exit 1
fi

if [ ! -f "${BACKEND_VENV}" ]; then
  echo "[x] 未找到后端虚拟环境，请先在 backend 目录创建 .venv 并安装依赖。" >&2
  exit 1
fi

BACKEND_UVICORN_PID=""
BACKEND_CELERY_PID=""

cleanup() {
  trap - INT TERM
  echo
  echo "[!] 捕获到退出信号，正在关闭服务..."
  if [ -n "${FRONTEND_PID:-}" ] && kill -0 "${FRONTEND_PID}" >/dev/null 2>&1; then
    kill "${FRONTEND_PID}" >/dev/null 2>&1 || true
    wait "${FRONTEND_PID}" 2>/dev/null || true
  fi
  if [ -n "${BACKEND_CELERY_PID:-}" ] && kill -0 "${BACKEND_CELERY_PID}" >/dev/null 2>&1; then
    kill "${BACKEND_CELERY_PID}" >/dev/null 2>&1 || true
    wait "${BACKEND_CELERY_PID}" 2>/dev/null || true
  fi
  if [ -n "${BACKEND_UVICORN_PID:-}" ] && kill -0 "${BACKEND_UVICORN_PID}" >/dev/null 2>&1; then
    kill "${BACKEND_UVICORN_PID}" >/dev/null 2>&1 || true
    wait "${BACKEND_UVICORN_PID}" 2>/dev/null || true
  fi
  echo "[✓] 所有服务已停止。"
}

trap cleanup INT TERM

echo "[*] 启动后端（FastAPI + Celery）..."
cd "${BACKEND_DIR}" || exit 1
# shellcheck disable=SC1090
source "${BACKEND_VENV}"
mkdir -p "${BACKEND_DIR}/logs"
: > "${BACKEND_DIR}/logs/celery.log"

# Ensure backend port is available to avoid confusing reload errors
if is_port_in_use 8000; then
  echo "[x] 端口 8000 已被占用。请先停止已运行的后端或改用其它端口。" >&2
  echo "    你可以运行：lsof -iTCP:8000 -sTCP:LISTEN -nP" >&2
  exit 1
fi

if command -v redis-server >/dev/null 2>&1; then
  if ! pgrep redis-server >/dev/null; then
    echo "[*] 启动 Redis..."
    redis-server >/dev/null 2>&1 &
    sleep 1
    if ! pgrep redis-server >/dev/null; then
      echo "[x] Redis 启动失败，请手动检查。" >&2
    else
      echo "[✓] Redis 已启动。"
    fi
  else
    echo "[!] 检测到 Redis 已在运行，跳过启动。"
  fi
else
  echo "[!] 未找到 redis-server 命令，跳过自动启动。"
fi

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_UVICORN_PID=$!
echo "[✓] FastAPI 运行中 (PID=${BACKEND_UVICORN_PID})"

# Celery 任务执行不需要走全局代理，这里临时屏蔽 SOCKS/HTTP 代理变量，避免 httpx 报缺少 socksio。
ORIGINAL_HTTP_PROXY="${HTTP_PROXY-}"
ORIGINAL_HTTPS_PROXY="${HTTPS_PROXY-}"
ORIGINAL_ALL_PROXY="${ALL_PROXY-}"
ORIGINAL_LOWER_HTTP_PROXY="${http_proxy-}"
ORIGINAL_LOWER_HTTPS_PROXY="${https_proxy-}"
ORIGINAL_LOWER_ALL_PROXY="${all_proxy-}"
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy

celery -A app.celery_app worker --loglevel=info -Q evaluation --logfile="${BACKEND_DIR}/logs/celery.log" &
BACKEND_CELERY_PID=$!
echo "[✓] Celery worker 运行中 (PID=${BACKEND_CELERY_PID})"

if [ -n "${ORIGINAL_HTTP_PROXY}" ]; then export HTTP_PROXY="${ORIGINAL_HTTP_PROXY}"; else unset HTTP_PROXY; fi
if [ -n "${ORIGINAL_HTTPS_PROXY}" ]; then export HTTPS_PROXY="${ORIGINAL_HTTPS_PROXY}"; else unset HTTPS_PROXY; fi
if [ -n "${ORIGINAL_ALL_PROXY}" ]; then export ALL_PROXY="${ORIGINAL_ALL_PROXY}"; else unset ALL_PROXY; fi
if [ -n "${ORIGINAL_LOWER_HTTP_PROXY}" ]; then export http_proxy="${ORIGINAL_LOWER_HTTP_PROXY}"; else unset http_proxy; fi
if [ -n "${ORIGINAL_LOWER_HTTPS_PROXY}" ]; then export https_proxy="${ORIGINAL_LOWER_HTTPS_PROXY}"; else unset https_proxy; fi
if [ -n "${ORIGINAL_LOWER_ALL_PROXY}" ]; then export all_proxy="${ORIGINAL_LOWER_ALL_PROXY}"; else unset all_proxy; fi

cd "${ROOT_DIR}" || exit 1

echo "[*] 启动前端（Vite Dev Server）..."
(
  cd "${FRONTEND_DIR}"
  npm run dev -- --host 0.0.0.0 --port 5173
) &
FRONTEND_PID=$!

echo "[✓] 前后端已启动。按 Ctrl+C 退出并关闭所有进程。"

wait
