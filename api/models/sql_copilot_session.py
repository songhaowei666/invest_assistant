from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class SqlCopilotSession(Base):
    __tablename__ = "sql_copilot_session"
    __table_args__ = {
        "comment": "SQL Copilot 会话主表",
        "extend_existing": True,
    }

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        comment="会话 ID（前端生成并复用）",
    )
    user_id: Mapped[str] = mapped_column(String(64), index=True, comment="用户 ID")
    title: Mapped[str] = mapped_column(String(200), default="", comment="会话标题")
    preview: Mapped[str] = mapped_column(Text, default="", comment="会话预览文本")
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
        comment="更新时间",
    )
