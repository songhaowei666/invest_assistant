"""nanobot 会话消息表（替代 sessions/*.jsonl 中的每行消息）。

每条记录代表会话中的一条消息，按 (user_id, session_key, seq) 排序。
payload_json 完整保留 role / content / timestamp / tool_calls / tool_call_id / name /
reasoning_content / thinking_blocks / media / _channel_delivery 等扩展字段，避免
nanobot 后续新增字段需要回头改 schema。
"""

import sys
from datetime import datetime
from pathlib import Path

_api_root = Path(__file__).resolve().parent.parent
if str(_api_root) not in sys.path:
    sys.path.insert(0, str(_api_root))

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class NanobotSessionMessage(Base):
    __tablename__ = "nanobot_session_message"
    __table_args__ = (
        Index(
            "ix_nanobot_session_message_user_key_seq",
            "user_id",
            "session_key",
            "seq",
        ),
        {
            "comment": "nanobot 会话消息表：按 (user_id, session_key) 分组，seq 内单调递增",
            "extend_existing": True,
        },
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键，自增")
    user_id: Mapped[str] = mapped_column(String(64), index=True, comment="用户 ID")
    session_key: Mapped[str] = mapped_column(String(255), index=True, comment="会话 key")
    seq: Mapped[int] = mapped_column(Integer, nullable=False, comment="会话内消息序号，从 0 开始单调递增")
    payload_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="消息内容 JSON：role / content / timestamp / tool_calls 等完整字段",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="入库时间",
    )
