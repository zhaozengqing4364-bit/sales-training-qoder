#!/bin/sh

set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DEV_UP_SCRIPT="$ROOT_DIR/scripts/dev-up.sh"

if [ ! -f "$DEV_UP_SCRIPT" ]; then
  echo "[ERROR] 未找到启动脚本: $DEV_UP_SCRIPT" >&2
  exit 1
fi

# 演练 WebSocket 在 uvicorn --reload 下易被 worker 重启掐断（关闭码 1006）。
export BACKEND_UVICORN_RELOAD="${BACKEND_UVICORN_RELOAD:-0}"

exec bash "$DEV_UP_SCRIPT" "$@"
