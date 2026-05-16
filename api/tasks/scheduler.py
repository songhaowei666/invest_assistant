"""定时任务调度入口（Beat 调用，再投递 api/tasks 中的具体任务）。"""

from __future__ import annotations

from celery import shared_task  # type: ignore[import-untyped]
from celery.signals import beat_init  # type: ignore[import-untyped]

from core.scheduled_celery import RUN_SCHEDULED_TASK_NAME, execute_scheduled_task, sync_beat_schedule


@shared_task(name=RUN_SCHEDULED_TASK_NAME)
def run_scheduled_task(task_id: int) -> str:
    """Beat 触发：按 scheduled_task.id 执行并写入执行历史。"""
    return execute_scheduled_task(task_id)


@beat_init.connect
def _load_beat_schedule_on_beat_start(**kwargs) -> None:
    """Beat 进程启动时从数据库加载一次调度表。"""
    from db import SessionLocal

    with SessionLocal() as db:
        sync_beat_schedule(db)
