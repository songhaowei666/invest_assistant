#!/usr/bin/env bash
set -euo pipefail

# 启动 Web 前端 Vite 开发服务器（工作目录为仓库下的 web/）
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/web"

exec npm run dev
