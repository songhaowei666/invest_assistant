"""nanobot 记忆游标表（替代 memory/.cursor 与 memory/.dream_cursor）。

按 (user_id, name) 唯一，name ∈ {"cursor", "dream_cursor"}。
"""

import sys
from pathlib import Path

_api_root = Path(__file__).resolve().parent.parent
if str(_api_root) not in sys.path:
    sys.path.insert(0, str(_api_root))

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class NanobotMemoryCursor(Base):
    __tablename__ = "nanobot_memory_cursor"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_nanobot_memory_cursor_user_name"),
        {
            "comment": "nanobot 记忆游标：cursor 用于 history 自增，dream_cursor 表示 Dream 已消费位置",
            "extend_existing": True,
        },
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键，自增")
    user_id: Mapped[str] = mapped_column(String(64), index=True, comment="用户 ID")
    name: Mapped[str] = mapped_column(String(32), comment="游标名称：cursor 或 dream_cursor")
    value: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", comment="游标当前值")
