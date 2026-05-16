from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ScheduledTaskItem(BaseModel):
    id: int
    name: str
    cronExpr: str
    taskKey: str
    enabled: bool
    log: str | None = None
    startedAt: datetime | None = None
    finishedAt: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ScheduledTaskListResponse(BaseModel):
    items: list[ScheduledTaskItem]


class ScheduledTaskKeysResponse(BaseModel):
    """api/tasks 中扫描到的 Celery 任务名。"""

    items: list[str]


class ScheduledTaskDbRow(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    cron_expr: str = Field(min_length=1, max_length=128)
    task_key: str = Field(min_length=1, max_length=256)
    enabled: bool = True


class ScheduledTaskModifyRow(BaseModel):
    id: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=128)
    cron_expr: str = Field(min_length=1, max_length=128)
    task_key: str = Field(min_length=1, max_length=256)
    enabled: bool = True
