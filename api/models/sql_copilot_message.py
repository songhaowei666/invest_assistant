from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class SqlCopilotMessage(Base):
    __tablename__ = "sql_copilot_message"
    __table_args__ = {
        "comment": "SQL Copilot 会话历史消息（短期记忆持久化）",
        "extend_existing": True,
    }

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True, comment="会话 ID")
    user_id: Mapped[str] = mapped_column(String(64), index=True, comment="用户 ID")
    role: Mapped[str] = mapped_column(String(32), comment="消息角色，例如 user 或 assistant")
    content: Mapped[str] = mapped_column(Text, comment="消息正文")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )
