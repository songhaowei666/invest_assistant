"""股票数据相关 Celery 任务。"""

from __future__ import annotations

from celery import shared_task  # type: ignore[import-untyped]

from core.akshare.update_stock_tables import update_position_stocks_basic_info


@shared_task(name="tasks.stock.update_position_basic_info")
def update_position_basic_info() -> str:
    """根据 Position 持仓代码，批量更新 StockBasicInfo 基础快照。"""
    return update_position_stocks_basic_info()
