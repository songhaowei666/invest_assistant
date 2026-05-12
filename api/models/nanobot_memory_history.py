"""nanobot 记忆历史表（替代 workspace/memory/history.jsonl）。

按 (user_id, cursor) 唯一，cursor 单调递增，由 nanobot_memory_cursor 表维护。
"""

import sys
from datetime import datetime
from pathlib import Path

_api_root = Path(__file__).resolve().parent.parent
if str(_api_root) not in sys.path:
    sys.path.insert(0, str(_api_root))

from sqlalchemy import DateTime, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class NanobotMemoryHistory(Base):
    __tablename__ = "nanobot_memory_history"
    __table_args__ = (
        UniqueConstraint("user_id", "cursor", name="uq_nanobot_memory_history_user_cursor"),
        Index("ix_nanobot_memory_history_user_cursor", "user_id", "cursor"),
        {
            "comment": "nanobot 记忆历史表：替代 history.jsonl，cursor 单调递增",
            "extend_existing": True,
        },
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键，自增")
    user_id: Mapped[str] = mapped_column(String(64), index=True, comment="用户 ID")
    cursor: Mapped[int] = mapped_column(Integer, nullable=False, comment="单调递增游标")
    timestamp: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="人类可读时间戳，格式 YYYY-MM-DD HH:MM"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default="", comment="历史条目正文")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="入库时间",
    )
