#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取当前持仓股票列表，并输出 JSON。
"""

import json
import os
import sys
from pathlib import Path


def _append_api_root_to_path() -> None:
    """将 api 目录加入 sys.path，确保可导入项目模块。"""
    script_file = Path(__file__).resolve()
    api_root = script_file.parents[4]
    api_root_text = str(api_root)
    if api_root_text not in sys.path:
        sys.path.insert(0, api_root_text)


def _fetch_positions() -> dict:
    """复用业务服务层读取当前持仓。"""
    _append_api_root_to_path()

    from db import SessionLocal  # pylint: disable=import-outside-toplevel
    from services.position_service import PositionService  # pylint: disable=import-outside-toplevel

    service = PositionService()
    db = SessionLocal()
    try:
        items = service.list_positions(db)
        return {
            "count": len(items),
            "items": [item.model_dump() for item in items],
        }
    finally:
        db.close()


def main() -> None:
    """执行入口。"""
    try:
        result = _fetch_positions()
    except Exception as exc:  # noqa: BLE001
        result = {
            "error": f"执行失败: {str(exc)}",
            "cwd": os.getcwd(),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
