"""nanobot 定时任务表（替代 workspace/cron/jobs.json 与 cron/action.jsonl）。

按 (user_id, job_id) 唯一；schedule/payload/state 拆为三个 JSONB 字段保留原有结构，
方便 CronService 加载/保存时直接做 dataclass <-> dict 转换。
"""

import sys
from pathlib import Path

_api_root = Path(__file__).resolve().parent.parent
if str(_api_root) not in sys.path:
    sys.path.insert(0, str(_api_root))

from sqlalchemy import BigInteger, Boolean, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class NanobotCronJob(Base):
    __tablename__ = "nanobot_cron_job"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_nanobot_cron_job_user_id"),
        {
            "comment": "nanobot 定时任务表：按 (user_id, job_id) 隔离",
            "extend_existing": True,
        },
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键，自增")
    user_id: Mapped[str] = mapped_column(String(64), index=True, comment="用户 ID")
    job_id: Mapped[str] = mapped_column(String(64), index=True, comment="任务 ID（nanobot uuid8 或系统任务标识）")
    name: Mapped[str] = mapped_column(String(255), nullable=False, server_default="", comment="任务名称")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", comment="是否启用")
    schedule_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, comment="调度计划：kind/at_ms/every_ms/expr/tz"
    )
    payload_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, comment="执行载荷：kind/message/deliver/channel/to/channel_meta/session_key"
    )
    state_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="运行时状态：next_run_at_ms/last_run_at_ms/last_status/last_error/run_history",
    )
    created_at_ms: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0", comment="创建时间（毫秒）"
    )
    updated_at_ms: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0", comment="更新时间（毫秒）"
    )
    delete_after_run: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", comment="一次性任务执行后是否删除"
    )
