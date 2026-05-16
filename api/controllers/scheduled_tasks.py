from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db import get_db
from schemas.scheduled_task import (
    ScheduledTaskDbRow,
    ScheduledTaskKeysResponse,
    ScheduledTaskListResponse,
    ScheduledTaskModifyRow,
)
from services.scheduled_task_service import ScheduledTaskService
from tasks.discovery import list_task_keys_from_tasks_package

router = APIRouter(prefix="/scheduled-tasks", tags=["scheduled-tasks"])


@router.get("/task-keys", response_model=ScheduledTaskKeysResponse)
def list_celery_task_keys() -> ScheduledTaskKeysResponse:
    """列出 api/tasks 包内 @shared_task 声明的 Celery 任务名。"""
    return ScheduledTaskKeysResponse(items=list_task_keys_from_tasks_package())


@router.get("", response_model=ScheduledTaskListResponse)
def list_scheduled_tasks(db: Session = Depends(get_db)) -> ScheduledTaskListResponse:
    """查询定时任务列表，含每条任务最近一次执行的日志与时间。"""
    service = ScheduledTaskService()
    return service.list_tasks(db)


@router.post("/add", response_model=ScheduledTaskListResponse)
def add_scheduled_tasks(
    payload: list[ScheduledTaskDbRow], db: Session = Depends(get_db)
) -> ScheduledTaskListResponse:
    """批量新增定时任务配置。"""
    service = ScheduledTaskService()
    return service.add(db, payload)


@router.post("/modify", response_model=ScheduledTaskListResponse)
def modify_scheduled_tasks(
    payload: list[ScheduledTaskModifyRow], db: Session = Depends(get_db)
) -> ScheduledTaskListResponse:
    """批量修改定时任务配置（按 id 定位）。"""
    service = ScheduledTaskService()
    return service.modify(db, payload)
