#!/bin/sh

set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DEV_UP_SCRIPT="$ROOT_DIR/scripts/dev-up.sh"

if [ ! -f "$DEV_UP_SCRIPT" ]; then
  echo "[ERROR] 未找到启动脚本: $DEV_UP_SCRIPT" >&2
  exit 1
fi

# 默认开发启动打开后端热重载；如需稳定语音 WebSocket，可用 BACKEND_UVICORN_RELOAD=0 ./start-all.sh 关闭。
export BACKEND_UVICORN_RELOAD="${BACKEND_UVICORN_RELOAD:-1}"

exec bash "$DEV_UP_SCRIPT" "$@"
