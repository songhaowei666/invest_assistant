"""Celery 定时任务配置与执行历史表。"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class ScheduledTask(Base):
    __tablename__ = "scheduled_task"
    __table_args__ = {
        "comment": "定时任务配置：名称、cron、Celery 任务名及启用状态",
        "extend_existing": True,
    }

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="主键，自增"
    )
    name: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, comment="定时任务名称，唯一"
    )
    cron_expr: Mapped[str] = mapped_column(String(128), comment="cron 表达式")
    task_key: Mapped[str] = mapped_column(
        String(256), comment="Celery 任务名，如 tasks.sample.ping"
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", comment="是否启用"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    runs: Mapped[list["ScheduledTaskRun"]] = relationship(
        "ScheduledTaskRun", back_populates="task", cascade="all, delete-orphan"
    )


class ScheduledTaskRun(Base):
    __tablename__ = "scheduled_task_run"
    __table_args__ = (
        Index("ix_scheduled_task_run_task_id_started_at", "task_id", "started_at"),
        {
            "comment": "定时任务执行历史：日志与起止时间",
            "extend_existing": True,
        },
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="主键，自增"
    )
    task_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("scheduled_task.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属任务 ID",
    )
    log: Mapped[str | None] = mapped_column(Text, nullable=True, comment="执行日志")
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="执行开始时间"
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="执行完成时间"
    )

    task: Mapped["ScheduledTask"] = relationship("ScheduledTask", back_populates="runs")
