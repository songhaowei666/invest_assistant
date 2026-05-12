"""nanobot 会话存储仓库：封装会话主表 + 消息表的 PG 增删改查。

设计要点：
- 所有方法显式接收 user_id，由上层（SessionManager）从 ContextVar 取值后传入，
  避免 repo 与 ContextVar 直接耦合，便于单测/复用。
- save_session 优先增量插入新消息行（依据当前 DB 中已有消息数对比内存 messages 长度），
  仅在前缀被截断（enforce_file_cap / retain_recent_legal_suffix）等场景退化为整表重写。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select

from db import SessionLocal
from models.nanobot_session import NanobotSession
from models.nanobot_session_message import NanobotSessionMessage


def _to_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat()


class NanobotSessionRepo:
    """会话主表 + 消息表的统一访问入口。"""

    def get_session_row(self, user_id: str, session_key: str) -> NanobotSession | None:
        with SessionLocal() as db:
            stmt = (
                select(NanobotSession)
                .where(NanobotSession.user_id == user_id)
                .where(NanobotSession.session_key == session_key)
            )
            return db.scalar(stmt)

    def load_session_full(self, user_id: str, session_key: str) -> dict[str, Any] | None:
        """读取会话全量（含所有消息），返回 dict；不存在时返回 None。

        返回结构与 SessionManager.read_session_file 对齐：
            {
              "key": session_key,
              "created_at": iso str | None,
              "updated_at": iso str | None,
              "metadata": dict,
              "last_consolidated": int,
              "messages": [dict, ...],
            }
        """
        with SessionLocal() as db:
            row = db.scalar(
                select(NanobotSession)
                .where(NanobotSession.user_id == user_id)
                .where(NanobotSession.session_key == session_key)
            )
            if row is None:
                return None
            msgs = list(
                db.scalars(
                    select(NanobotSessionMessage)
                    .where(NanobotSessionMessage.user_id == user_id)
                    .where(NanobotSessionMessage.session_key == session_key)
                    .order_by(NanobotSessionMessage.seq.asc())
                )
            )
            return {
                "key": row.session_key,
                "created_at": _to_iso(row.created_at),
                "updated_at": _to_iso(row.updated_at),
                "metadata": dict(row.metadata_json or {}),
                "last_consolidated": int(row.last_consolidated or 0),
                "messages": [dict(m.payload_json or {}) for m in msgs],
            }

    def count_messages(self, user_id: str, session_key: str) -> int:
        with SessionLocal() as db:
            return int(
                db.scalar(
                    select(func.count(NanobotSessionMessage.id))
                    .where(NanobotSessionMessage.user_id == user_id)
                    .where(NanobotSessionMessage.session_key == session_key)
                )
                or 0
            )

    def save_session(
        self,
        *,
        user_id: str,
        session_key: str,
        created_at: datetime,
        updated_at: datetime,
        metadata: dict[str, Any],
        last_consolidated: int,
        messages: list[dict[str, Any]],
    ) -> None:
        """保存会话：upsert 主表 + 同步消息行。

        消息同步策略：
        - 若 DB 现有消息数 <= len(messages) 且前缀一致（按 seq），仅追加缺失的消息。
        - 否则整体重写（先清空再批量插入），覆盖 retain_recent_legal_suffix 类场景。
        """
        with SessionLocal() as db:
            row = db.scalar(
                select(NanobotSession)
                .where(NanobotSession.user_id == user_id)
                .where(NanobotSession.session_key == session_key)
            )
            if row is None:
                row = NanobotSession(
                    user_id=user_id,
                    session_key=session_key,
                    metadata_json=dict(metadata or {}),
                    last_consolidated=int(last_consolidated or 0),
                    created_at=created_at,
                    updated_at=updated_at,
                )
                db.add(row)
            else:
                row.metadata_json = dict(metadata or {})
                row.last_consolidated = int(last_consolidated or 0)
                row.updated_at = updated_at

            existing = int(
                db.scalar(
                    select(func.count(NanobotSessionMessage.id))
                    .where(NanobotSessionMessage.user_id == user_id)
                    .where(NanobotSessionMessage.session_key == session_key)
                )
                or 0
            )
            target_len = len(messages)

            if target_len >= existing:
                # 仅追加新消息（默认情况下 messages 只增不删，前缀不变）
                for seq in range(existing, target_len):
                    db.add(
                        NanobotSessionMessage(
                            user_id=user_id,
                            session_key=session_key,
                            seq=seq,
                            payload_json=dict(messages[seq] or {}),
                        )
                    )
            else:
                # 前缀被截断（enforce_file_cap 等），退化为整表重写
                db.execute(
                    delete(NanobotSessionMessage)
                    .where(NanobotSessionMessage.user_id == user_id)
                    .where(NanobotSessionMessage.session_key == session_key)
                )
                for seq, msg in enumerate(messages):
                    db.add(
                        NanobotSessionMessage(
                            user_id=user_id,
                            session_key=session_key,
                            seq=seq,
                            payload_json=dict(msg or {}),
                        )
                    )

            db.commit()

    def overwrite_messages(
        self,
        *,
        user_id: str,
        session_key: str,
        messages: list[dict[str, Any]],
    ) -> None:
        """整体重写消息行（用于显式 retain/截断场景）。"""
        with SessionLocal() as db:
            db.execute(
                delete(NanobotSessionMessage)
                .where(NanobotSessionMessage.user_id == user_id)
                .where(NanobotSessionMessage.session_key == session_key)
            )
            for seq, msg in enumerate(messages):
                db.add(
                    NanobotSessionMessage(
                        user_id=user_id,
                        session_key=session_key,
                        seq=seq,
                        payload_json=dict(msg or {}),
                    )
                )
            db.commit()

    def delete_session(self, user_id: str, session_key: str) -> bool:
        with SessionLocal() as db:
            db.execute(
                delete(NanobotSessionMessage)
                .where(NanobotSessionMessage.user_id == user_id)
                .where(NanobotSessionMessage.session_key == session_key)
            )
            result = db.execute(
                delete(NanobotSession)
                .where(NanobotSession.user_id == user_id)
                .where(NanobotSession.session_key == session_key)
            )
            db.commit()
            return bool(result.rowcount or 0)

    def list_sessions(self, user_id: str) -> list[dict[str, Any]]:
        """返回会话简要信息列表，按 updated_at 倒序。"""
        with SessionLocal() as db:
            rows = list(
                db.scalars(
                    select(NanobotSession)
                    .where(NanobotSession.user_id == user_id)
                    .order_by(NanobotSession.updated_at.desc())
                )
            )
            out: list[dict[str, Any]] = []
            for r in rows:
                meta = dict(r.metadata_json or {})
                title = meta.get("title") if isinstance(meta.get("title"), str) else ""
                out.append(
                    {
                        "key": r.session_key,
                        "created_at": _to_iso(r.created_at),
                        "updated_at": _to_iso(r.updated_at),
                        "title": title,
                        "path": "",  # PG 化后无文件路径，保留字段兼容上层
                    }
                )
            return out
