from __future__ import annotations

import akshare as ak

from db import SessionLocal
from models.stock_all_info import StockAllInfo


def _normalize_code(value: object) -> str:
    text_value = str(value).strip()
    return text_value.zfill(6)


def update_stock_all_info() -> tuple[int, int, int]:
    """
    使用 AkShare 拉取 A 股股票代码和名称，并更新 stock_all_info 表。

    返回:
        (inserted, updated, total)
    """
    df = ak.stock_info_a_code_name()
    print(df.head())
    if df is None or df.empty:
        raise RuntimeError("未获取到股票全量列表数据")

    required_cols = {"code", "name"}
    if not required_cols.issubset(df.columns):
        raise RuntimeError(f"返回数据缺少必要列: {required_cols}")

    inserted = 0
    updated = 0
    with SessionLocal() as db:
        for _, item in df.iterrows():
            code = _normalize_code(item["code"])
            name = str(item["name"]).strip()
            if not code or not name:
                continue

            row = db.get(StockAllInfo, code)
            if row is None:
                row = StockAllInfo(code=code, name=name)
                db.add(row)
                inserted += 1
            elif row.name != name:
                row.name = name
                updated += 1

        db.commit()

    return inserted, updated, len(df)
