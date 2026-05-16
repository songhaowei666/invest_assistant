from fastapi import HTTPException

from core.scheduled_celery import cron_expr_to_crontab, sync_beat_schedule
from models.scheduled_task import ScheduledTask
from tasks.discovery import list_task_keys_from_tasks_package
from repositories.scheduled_task_repo import ScheduledTaskRepository
from schemas.scheduled_task import (
    ScheduledTaskDbRow,
    ScheduledTaskItem,
    ScheduledTaskListResponse,
    ScheduledTaskModifyRow,
)


class ScheduledTaskService:
    def __init__(self) -> None:
        self.repo = ScheduledTaskRepository()
        self._known_task_keys = set(list_task_keys_from_tasks_package())

    def _validate_row(self, row: ScheduledTaskDbRow | ScheduledTaskModifyRow) -> None:
        try:
            cron_expr_to_crontab(row.cron_expr)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if self._known_task_keys and row.task_key not in self._known_task_keys:
            raise HTTPException(
                status_code=422,
                detail=f"Celery 任务名 {row.task_key!r} 不在 api/tasks 中，可选: {sorted(self._known_task_keys)}",
            )

    def _after_schedule_changed(self, db) -> None:
        sync_beat_schedule(db)

    def list_tasks(self, db) -> ScheduledTaskListResponse:
        rows = self.repo.list_tasks_with_latest_run(db)
        items = [self._to_item(row) for row in rows]
        return ScheduledTaskListResponse(items=items)

    def add(self, db, payload: list[ScheduledTaskDbRow]) -> ScheduledTaskListResponse:
        seen: set[str] = set()
        for row in payload:
            self._validate_row(row)
            if row.name in seen:
                raise HTTPException(status_code=422, detail=f"请求中任务名称 {row.name} 重复。")
            seen.add(row.name)
            if self.repo.get_by_name(db, row.name):
                raise HTTPException(status_code=409, detail=f"任务名称 {row.name} 已存在。")
            self.repo.add_one(
                db,
                ScheduledTask(
                    name=row.name,
                    cron_expr=row.cron_expr,
                    task_key=row.task_key,
                    enabled=row.enabled,
                ),
            )
        db.commit()
        self._after_schedule_changed(db)
        return self.list_tasks(db)

    def modify(self, db, payload: list[ScheduledTaskModifyRow]) -> ScheduledTaskListResponse:
        seen_names: set[str] = set()
        for row in payload:
            self._validate_row(row)
            if row.name in seen_names:
                raise HTTPException(status_code=422, detail=f"请求中任务名称 {row.name} 重复。")
            seen_names.add(row.name)

        for row in payload:
            target = self.repo.get_by_id(db, row.id)
            if not target:
                raise HTTPException(status_code=404, detail=f"未找到任务 id={row.id}。")
            if row.name != target.name:
                existing = self.repo.get_by_name(db, row.name)
                if existing and existing.id != row.id:
                    raise HTTPException(
                        status_code=409, detail=f"任务名称 {row.name} 已被其它任务使用。"
                    )
            target.name = row.name
            target.cron_expr = row.cron_expr
            target.task_key = row.task_key
            target.enabled = row.enabled

        db.commit()
        self._after_schedule_changed(db)
        return self.list_tasks(db)

    def _to_item(self, row) -> ScheduledTaskItem:
        task = row.task
        return ScheduledTaskItem(
            id=task.id,
            name=task.name,
            cronExpr=task.cron_expr,
            taskKey=task.task_key,
            enabled=task.enabled,
            log=row.log,
            startedAt=row.started_at,
            finishedAt=row.finished_at,
        )
