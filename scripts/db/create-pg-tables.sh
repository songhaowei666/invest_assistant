#!/usr/bin/env bash
set -euo pipefail

# 在 PostgreSQL 中根据 ORM 模型建表（工作目录为仓库下的 api/）
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/api"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi

exec python3 scripts/create_pg_tables.py
