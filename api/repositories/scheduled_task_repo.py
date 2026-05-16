from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.scheduled_task import ScheduledTask, ScheduledTaskRun


@dataclass
class ScheduledTaskWithLatestRun:
    """任务配置与最近一次执行记录（可能无执行历史）。"""

    task: ScheduledTask
    log: str | None
    started_at: datetime | None
    finished_at: datetime | None


class ScheduledTaskRepository:
    def list_tasks_with_latest_run(self, db: Session) -> list[ScheduledTaskWithLatestRun]:
        tasks = list(
            db.scalars(select(ScheduledTask).order_by(ScheduledTask.id.asc())).all()
        )
        if not tasks:
            return []

        task_ids = [t.id for t in tasks]
        runs = list(
            db.scalars(
                select(ScheduledTaskRun)
                .where(ScheduledTaskRun.task_id.in_(task_ids))
                .order_by(
                    ScheduledTaskRun.task_id.asc(),
                    ScheduledTaskRun.started_at.desc().nulls_last(),
                    ScheduledTaskRun.id.desc(),
                )
            ).all()
        )

        latest_by_task: dict[int, ScheduledTaskRun] = {}
        for run in runs:
            if run.task_id not in latest_by_task:
                latest_by_task[run.task_id] = run

        return [
            ScheduledTaskWithLatestRun(
                task=task,
                log=latest_by_task[task.id].log if task.id in latest_by_task else None,
                started_at=(
                    latest_by_task[task.id].started_at if task.id in latest_by_task else None
                ),
                finished_at=(
                    latest_by_task[task.id].finished_at if task.id in latest_by_task else None
                ),
            )
            for task in tasks
        ]

    def get_by_id(self, db: Session, task_id: int) -> ScheduledTask | None:
        return db.get(ScheduledTask, task_id)

    def get_by_name(self, db: Session, name: str) -> ScheduledTask | None:
        stmt = select(ScheduledTask).where(ScheduledTask.name == name)
        return db.scalar(stmt)

    def add_one(self, db: Session, task: ScheduledTask) -> None:
        db.add(task)
