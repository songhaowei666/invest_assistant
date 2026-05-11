#!/usr/bin/env bash
set -euo pipefail

# 启动 FastAPI 服务（工作目录为仓库下的 api/）
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/api"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi

# DEBUG=1 时使用 debugpy 启动，便于 Cursor/VSCode 远程附加断点调试。
# 用法示例：
#   DEBUG=1 ./scripts/start-api.sh
# 然后在 IDE 使用 "Python: Attach" 连接 localhost:${DEBUG_PORT:-5678}
if [[ "${DEBUG:-0}" == "1" ]]; then
  DEBUG_PORT="${DEBUG_PORT:-5678}"
  # 断点调试时默认关闭 reload，避免热重载多进程影响断点稳定性。
  if [[ "${RELOAD:-0}" == "1" ]]; then
    echo "[DEBUG] 等待调试器附加: localhost:${DEBUG_PORT}（已启用 --wait-for-client, RELOAD=1）"
    exec python3 -m debugpy --listen "0.0.0.0:${DEBUG_PORT}" --wait-for-client -m uvicorn main:app --reload --host 0.0.0.0 --port 8000 --log-level debug
  else
    echo "[DEBUG] 等待调试器附加: localhost:${DEBUG_PORT}（已启用 --wait-for-client）"
    exec python3 -m debugpy --listen "0.0.0.0:${DEBUG_PORT}" --wait-for-client -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level debug
  fi
fi

exec python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
