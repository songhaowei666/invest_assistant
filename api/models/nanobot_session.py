"""nanobot 会话主表（替代 workspace/sessions/*.jsonl 中的元数据行）。

每条记录表示一个会话：(user_id, session_key) 唯一。
- session_key 形如 "api:<uuid>"，由前端生成。
- title 为会话列表展示标题（独立列）；新建会话未改名时默认取首条用户提问摘要；用户改名后由 metadata_json.title_user_edited 标记，避免被默认逻辑覆盖。
- metadata_json 存原 jsonl 元数据 dict（含 _last_summary / _runtime_checkpoint / WebUI 的 title 等运行期数据）。
- last_consolidated 记录已被记忆模块固化到 history 的消息数（与原 Session.last_consolidated 对齐）。
"""

import sys
from datetime import datetime
from pathlib import Path

_api_root = Path(__file__).resolve().parent.parent
if str(_api_root) not in sys.path:
    sys.path.insert(0, str(_api_root))

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class NanobotSession(Base):
    __tablename__ = "nanobot_session"
    __table_args__ = (
        UniqueConstraint("user_id", "session_key", name="uq_nanobot_session_user_key"),
        {
            "comment": "nanobot 会话主表：按 (user_id, session_key) 隔离",
            "extend_existing": True,
        },
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键，自增")
    user_id: Mapped[str] = mapped_column(String(64), index=True, comment="用户 ID")
    session_key: Mapped[str] = mapped_column(String(255), index=True, comment="会话 key，例如 api:<uuid>")
    # 旧数据可为 NULL，不做回填迁移；新建与后续保存写入非空或空串
    title: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="会话展示标题：首问默认摘要或用户改名",
    )
    metadata_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="会话元数据 JSON：_last_summary / _runtime_checkpoint / title_user_edited 等",
    )
    last_consolidated: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0", comment="已被记忆模块固化的消息数"
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
        comment="更新时间",
    )
