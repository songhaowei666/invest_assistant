"""定时任务与 Celery Beat / Worker 的公共调度逻辑。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from celery import Celery  # type: ignore[import-untyped]
from celery.beat import Scheduler  # type: ignore[import-untyped]
from celery.schedules import crontab  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import SessionLocal
from extensions.ext_celery import celery_app
from models.scheduled_task import ScheduledTask, ScheduledTaskRun

logger = logging.getLogger(__name__)

# Beat 入口：按 DB 配置触发，再投递 task_key 对应任务
RUN_SCHEDULED_TASK_NAME = "tasks.scheduler.run_scheduled_task"
BEAT_ENTRY_PREFIX = "scheduled_task_"
DEFAULT_TASK_TIMEOUT = 600


def get_celery_app_or_none() -> Celery | None:
    """未配置 broker 时返回 None，不抛错。"""
    return celery_app


def cron_expr_to_crontab(expr: str) -> crontab:
    """将 5 段 cron 表达式转为 Celery crontab（分 时 日 月 周）。"""
    parts = expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"cron 表达式须为 5 段，当前: {expr!r}")
    minute, hour, day_of_month, month_of_year, day_of_week = parts
    return crontab(
        minute=minute,
        hour=hour,
        day_of_month=day_of_month,
        month_of_year=month_of_year,
        day_of_week=day_of_week,
    )


def build_beat_schedule_from_db(db: Session) -> dict[str, dict[str, Any]]:
    """根据已启用的 scheduled_task 行构建 beat_schedule 条目。"""
    stmt = (
        select(ScheduledTask)
        .where(ScheduledTask.enabled.is_(True))
        .order_by(ScheduledTask.id.asc())
    )
    tasks = list(db.scalars(stmt).all())
    schedule: dict[str, dict[str, Any]] = {}
    for task in tasks:
        schedule[f"{BEAT_ENTRY_PREFIX}{task.id}"] = {
            "task": RUN_SCHEDULED_TASK_NAME,
            "schedule": cron_expr_to_crontab(task.cron_expr),
            "args": (task.id,),
        }
    return schedule


def list_beat_schedule_entries(db: Session) -> list[dict[str, Any]]:
    """列出当前 Beat 将调度的条目（与 build_beat_schedule_from_db 一致）。"""
    if get_celery_app_or_none() is None:
        return []
    stmt = (
        select(ScheduledTask)
        .where(ScheduledTask.enabled.is_(True))
        .order_by(ScheduledTask.id.asc())
    )
    tasks = list(db.scalars(stmt).all())
    entries: list[dict[str, Any]] = []
    for task in tasks:
        entries.append(
            {
                "beatKey": f"{BEAT_ENTRY_PREFIX}{task.id}",
                "taskId": task.id,
                "name": task.name,
                "cronExpr": task.cron_expr,
                "beatTask": RUN_SCHEDULED_TASK_NAME,
                "targetTaskKey": task.task_key,
            }
        )
    return entries


def sync_beat_schedule(db: Session) -> dict[str, Any]:
    """从数据库刷新 Celery beat_schedule（API 启动与 CRUD 后调用）。"""
    app = get_celery_app_or_none()
    if app is None:
        logger.debug("未配置 CELERY_BROKER_URL，跳过 beat_schedule 同步")
        return {}
    schedule = build_beat_schedule_from_db(db)
    app.conf.beat_schedule = schedule
    logger.info("已同步 %d 条定时任务到 beat_schedule", len(schedule))
    return schedule


def send_celery_task(task_key: str, timeout: int | None = None) -> tuple[Any, str]:
    """投递并等待 Celery 任务完成，返回 (结果, 日志文本)。"""
    from celery import current_task  # type: ignore[import-untyped]

    app = get_celery_app_or_none()
    if app is None:
        raise RuntimeError("未配置 CELERY_BROKER_URL，无法执行 Celery 任务")
    wait_timeout = timeout if timeout is not None else DEFAULT_TASK_TIMEOUT
    log_lines = [f"task_key={task_key}"]

    # Worker 内（尤其 solo 池）若 send_task + get 会占住唯一执行线程导致死锁，改同步 apply
    if current_task is not None:
        task = app.tasks.get(task_key)
        if task is None:
            raise RuntimeError(f"Celery 任务 {task_key!r} 未注册")
        try:
            eager = task.apply(throw=True)
            result = eager.result
            log_lines.append("mode=apply_in_worker")
            log_lines.append(f"status=success result={result!r}")
            return result, "\n".join(log_lines)
        except Exception as exc:
            log_lines.append(f"status=error error={exc!r}")
            raise RuntimeError("\n".join(log_lines)) from exc

    async_result = app.send_task(task_key, ignore_result=False)
    log_lines.append(f"celery_id={async_result.id}")
    try:
        result = async_result.get(timeout=wait_timeout)
        log_lines.append(f"status=success result={result!r}")
        return result, "\n".join(log_lines)
    except Exception as exc:
        log_lines.append(f"status=error error={exc!r}")
        raise RuntimeError("\n".join(log_lines)) from exc


def execute_scheduled_task(task_id: int, timeout: int | None = None) -> str:
    """执行一条 DB 定时任务：写入 scheduled_task_run 并调用 task_key。"""
    started_at = datetime.now(timezone.utc)
    with SessionLocal() as db:
        task = db.get(ScheduledTask, task_id)
        if task is None:
            return f"skip: task_id={task_id} 不存在"
        if not task.enabled:
            return f"skip: task_id={task_id} 已禁用"
        run = ScheduledTaskRun(task_id=task_id, started_at=started_at, log="running")
        db.add(run)
        db.commit()
        run_id = run.id
        task_key = task.task_key
        task_name = task.name

    log_text = ""
    status = "success"
    try:
        _, log_text = send_celery_task(task_key, timeout=timeout)
    except Exception as exc:
        status = "error"
        log_text = str(exc)
        logger.exception("定时任务执行失败 id=%s name=%s", task_id, task_name)

    finished_at = datetime.now(timezone.utc)
    header = f"task_id={task_id} name={task_name} status={status}"
    full_log = f"{header}\n{log_text}" if log_text else header

    with SessionLocal() as db:
        run = db.get(ScheduledTaskRun, run_id)
        if run:
            run.finished_at = finished_at
            run.log = full_log
            db.commit()

    return full_log


class DatabaseBeatScheduler(Scheduler):
    """Beat 调度器：每次 tick 前从数据库刷新定时任务，CRUD 后无需重启 beat。"""

    def setup_schedule(self) -> None:
        self.merge_inplace(self.app.conf.beat_schedule or {})
        self._merge_database_schedule()

    def _merge_database_schedule(self) -> None:
        from db import SessionLocal

        try:
            with SessionLocal() as db:
                incoming = build_beat_schedule_from_db(db)
        except Exception:
            logger.exception("从数据库加载 beat_schedule 失败")
            return

        # 仅移除已删除/禁用的 DB 条目；用 merge_inplace 更新，保留 last_run_at，避免每 tick 重置错过 cron
        incoming_keys = set(incoming.keys())
        for key in list(self.schedule.keys()):
            if key.startswith(BEAT_ENTRY_PREFIX) and key not in incoming_keys:
                del self.schedule[key]
        self.merge_inplace(incoming)
        self.app.conf.beat_schedule = dict(self.schedule)

    def tick(self, event_t=None, min=min, **kwargs):  # type: ignore[no-untyped-def]
        self._merge_database_schedule()
        return super().tick(event_t=event_t, min=min, **kwargs)
