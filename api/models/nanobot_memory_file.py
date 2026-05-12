"""nanobot 单文件型记忆表（替代 workspace/SOUL.md 与 workspace/USER.md）。

每个 user 下 name 唯一：name ∈ {"SOUL", "USER"}。
"""

import sys
from datetime import datetime
from pathlib import Path

_api_root = Path(__file__).resolve().parent.parent
if str(_api_root) not in sys.path:
    sys.path.insert(0, str(_api_root))

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class NanobotMemoryFile(Base):
    __tablename__ = "nanobot_memory_file"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_nanobot_memory_file_user_name"),
        {
            "comment": "nanobot 单文件型记忆：SOUL.md / USER.md 全文存储，按 (user_id, name) 隔离",
            "extend_existing": True,
        },
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键，自增")
    user_id: Mapped[str] = mapped_column(String(64), index=True, comment="用户 ID")
    name: Mapped[str] = mapped_column(String(16), comment="记忆文件名：SOUL 或 USER")
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default="", comment="完整文本内容")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="更新时间",
    )
