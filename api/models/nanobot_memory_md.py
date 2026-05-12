"""nanobot MEMORY.md 按行存储（替代 workspace/memory/MEMORY.md）。

按行存以支持 Dream 阶段的"行龄"计算：每行独立 updated_at，写入时只刷新内容
变化的行，保留未改动行的 updated_at，从而替代原 GitStore 提供的 line_ages。

读出时按 line_no 排序拼接成完整文本；写入时按行做 diff：
- 同位置内容相同：保留 updated_at
- 不同：刷新 updated_at = now()
- 新增：插入新行（updated_at = now()）
- 旧行多出：直接删除
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


class NanobotMemoryMd(Base):
    __tablename__ = "nanobot_memory_md"
    __table_args__ = (
        UniqueConstraint("user_id", "line_no", name="uq_nanobot_memory_md_user_line"),
        Index("ix_nanobot_memory_md_user_line", "user_id", "line_no"),
        {
            "comment": "nanobot MEMORY.md 按行存储：用于 Dream 行龄注解",
            "extend_existing": True,
        },
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键，自增")
    user_id: Mapped[str] = mapped_column(String(64), index=True, comment="用户 ID")
    line_no: Mapped[int] = mapped_column(Integer, nullable=False, comment="行号（1-based）")
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default="", comment="单行内容（不含换行符）")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="本行最后更新时间，用于 Dream 行龄计算",
    )
