#!/bin/sh

set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DEV_UP_SCRIPT="$ROOT_DIR/scripts/dev-up.sh"

if [ ! -f "$DEV_UP_SCRIPT" ]; then
  echo "[ERROR] 未找到启动脚本: $DEV_UP_SCRIPT" >&2
  exit 1
fi

exec bash "$DEV_UP_SCRIPT" "$@"
