from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from sqlalchemy import func

from configs.config import settings
from db import SessionLocal
from models.sql_copilot_message import SqlCopilotMessage
from models.sql_copilot_session import SqlCopilotSession
from models.stock_basic_info import StockBasicInfo
from models.stock_financial_report import StockFinancialReport


class Mem0MemoryStore:
    """mem0 记忆封装：统一会话记忆的写入、短期读取与长期召回。"""

    def __init__(self) -> None:
        if not settings.MEM0_API_KEY:
            raise ValueError("MEM0_API_KEY 未配置，无法启用 SQL Copilot 记忆模块。")

        from mem0 import MemoryClient  # type: ignore[reportMissingImports]

        kwargs: dict[str, Any] = {"api_key": settings.MEM0_API_KEY}
        if settings.MEM0_BASE_URL:
            kwargs["host"] = settings.MEM0_BASE_URL
        self.client = MemoryClient(**kwargs)

    def add_turn_memory(self, *, session_id: str, user_id: str, content: str) -> None:
        self.client.add(
            messages=[{"role": "user", "content": content}],
            user_id=user_id,
            metadata={"session_id": session_id, "app": "sql_copilot"},
        )

    def get_recent_messages(self, *, session_id: str, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        # 短期记忆固定窗口为最近 20 条
        result = self.client.get_all(user_id=user_id, limit=limit)
        records = self._extract_records(result)
        filtered = [x for x in records if str(x.get("metadata", {}).get("session_id", "")) == session_id]
        filtered = filtered[-limit:]
        output: list[dict[str, Any]] = []
        for item in filtered:
            content = str(item.get("memory", ""))
            output.append({"role": "user", "content": content})
        return output

    def search_related_memories(
        self, *, session_id: str, user_id: str, query: str, limit: int = 6
    ) -> list[str]:
        result = self.client.search(query=query, user_id=user_id, limit=limit)
        records = self._extract_records(result)
        memories: list[str] = []
        for item in records:
            metadata = item.get("metadata", {}) if isinstance(item, dict) else {}
            if str(metadata.get("session_id", "")) != session_id:
                continue
            memory_text = str(item.get("memory", "")).strip()
            if memory_text:
                memories.append(memory_text)
        return memories

    def _extract_records(self, result: Any) -> list[dict[str, Any]]:
        if isinstance(result, list):
            return [x for x in result if isinstance(x, dict)]
        if isinstance(result, dict):
            candidates = result.get("results") or result.get("memories") or result.get("data") or []
            if isinstance(candidates, list):
                return [x for x in candidates if isinstance(x, dict)]
        return []


class DisabledMemoryStore:
    """临时禁用记忆存储：保留调用链路，避免因缺少 key 报错。"""

    def add_turn_memory(self, *, session_id: str, user_id: str, content: str) -> None:
        return None

    def get_recent_messages(self, *, session_id: str, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return []

    def search_related_memories(
        self, *, session_id: str, user_id: str, query: str, limit: int = 6
    ) -> list[str]:
        return []


class SqlSessionHistoryStore:
    """会话历史持久化存储（数据库）。"""

    def ensure_session(self, *, session_id: str, user_id: str, title: str = "") -> None:
        with SessionLocal() as db:
            session = (
                db.query(SqlCopilotSession)
                .filter(
                    SqlCopilotSession.session_id == session_id,
                    SqlCopilotSession.user_id == user_id,
                )
                .first()
            )
            if session is None:
                db.add(
                    SqlCopilotSession(
                        session_id=session_id,
                        user_id=user_id,
                        title=title,
                    )
                )
            else:
                if title and not session.title:
                    session.title = title
                session.updated_at = func.now()
            db.commit()

    def add_message(self, *, session_id: str, user_id: str, role: str, content: str) -> None:
        self.ensure_session(session_id=session_id, user_id=user_id, title=content[:30] if role == "user" else "")
        with SessionLocal() as db:
            db.add(
                SqlCopilotMessage(
                    session_id=session_id,
                    user_id=user_id,
                    role=role,
                    content=content,
                )
            )
            session = (
                db.query(SqlCopilotSession)
                .filter(
                    SqlCopilotSession.session_id == session_id,
                    SqlCopilotSession.user_id == user_id,
                )
                .first()
            )
            if session is not None:
                session.preview = content[:200]
                session.updated_at = func.now()
            db.commit()

    def get_recent_messages(self, *, session_id: str, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            rows = (
                db.query(SqlCopilotMessage)
                .filter(
                    SqlCopilotMessage.session_id == session_id,
                    SqlCopilotMessage.user_id == user_id,
                )
                .order_by(SqlCopilotMessage.id.desc())
                .limit(limit)
                .all()
            )
        # 倒序查询后反转，确保返回按时间正序
        rows.reverse()
        return [{"role": item.role, "content": item.content} for item in rows]

    def list_sessions(self, *, user_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            rows = (
                db.query(SqlCopilotSession)
                .filter(SqlCopilotSession.user_id == user_id)
                .order_by(SqlCopilotSession.updated_at.desc())
                .limit(limit)
                .all()
            )
            out: list[dict[str, Any]] = []
            for row in rows:
                message_count = (
                    db.query(func.count(SqlCopilotMessage.id))
                    .filter(
                        SqlCopilotMessage.session_id == row.session_id,
                        SqlCopilotMessage.user_id == user_id,
                    )
                    .scalar()
                )
                out.append(
                    {
                        "session_id": row.session_id,
                        "user_id": row.user_id,
                        "title": row.title or "",
                        "preview": row.preview or "",
                        "created_at": row.created_at,
                        "updated_at": row.updated_at,
                        "message_count": int(message_count or 0),
                    }
                )
            return out

    def delete_session(self, *, session_id: str, user_id: str) -> bool:
        with SessionLocal() as db:
            db.query(SqlCopilotMessage).filter(
                SqlCopilotMessage.session_id == session_id,
                SqlCopilotMessage.user_id == user_id,
            ).delete()
            deleted = (
                db.query(SqlCopilotSession)
                .filter(
                    SqlCopilotSession.session_id == session_id,
                    SqlCopilotSession.user_id == user_id,
                )
                .delete()
            )
            db.commit()
            return bool(deleted)

    def session_history(self, *, session_id: str, user_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """读取指定会话的历史消息，按时间正序返回。"""
        return self.get_recent_messages(session_id=session_id, user_id=user_id, limit=limit)


class HybridMemoryStore:
    """记忆编排：短期会话历史走数据库，长期记忆走 mem0。"""

    def __init__(self, *, session_store: SqlSessionHistoryStore, long_term_store: Any):
        self.session_store = session_store
        self.long_term_store = long_term_store

    def add_turn_memory(self, *, session_id: str, user_id: str, content: str) -> None:
        # 持久化会话历史，保障短期 20 条上下文可回读
        self.session_store.add_message(
            session_id=session_id,
            user_id=user_id,
            role="assistant",
            content=content,
        )
        # self.long_term_store.add_turn_memory(session_id=session_id, user_id=user_id, content=content)

    def add_user_message(self, *, session_id: str, user_id: str, content: str) -> None:
        self.session_store.add_message(
            session_id=session_id,
            user_id=user_id,
            role="user",
            content=content,
        )

    def get_recent_messages(self, *, session_id: str, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return self.session_store.get_recent_messages(session_id=session_id, user_id=user_id, limit=limit)

    def search_related_memories(
        self, *, session_id: str, user_id: str, query: str, limit: int = 6
    ) -> list[str]:
        return self.long_term_store.search_related_memories(
            session_id=session_id, user_id=user_id, query=query, limit=limit
        )


class SqlCopilotService:
    def __init__(self) -> None:
        from ai.sql_copilot_graph import SqlCopilotGraph

        # self.long_term_store = Mem0MemoryStore()
        # 临时注释 mem0 实际调用入口：当前缺少 MEM0_API_KEY，后续补齐后取消注释即可恢复。
        self.long_term_store = DisabledMemoryStore()
        self.session_store = SqlSessionHistoryStore()
        self.memory_store = HybridMemoryStore(
            session_store=self.session_store,
            long_term_store=self.long_term_store,
        )
        self.graph = SqlCopilotGraph(self.memory_store)

    def chat(self, *, session_id: str | None, question: str, user_id: str = "default_user") -> dict[str, Any]:
        # 会话 ID 为空时自动创建，便于前端首次发起对话
        current_session_id = (session_id or "").strip() or f"sqlc-{uuid4().hex[:12]}"
        # 先持久化用户输入，保证短期会话历史可追溯
        self.memory_store.add_user_message(session_id=current_session_id, user_id=user_id, content=question)
        return self.graph.run(session_id=current_session_id, user_id=user_id, question=question)

    def list_sessions(self, *, user_id: str = "default_user", limit: int = 100) -> dict[str, Any]:
        rows = self.session_store.list_sessions(user_id=user_id, limit=limit)
        return {"sessions": rows}

    def delete_session(self, *, session_id: str, user_id: str = "default_user") -> dict[str, Any]:
        deleted = self.session_store.delete_session(session_id=session_id, user_id=user_id)
        return {"deleted": deleted}

    def session_history(self, *, session_id: str, user_id: str = "default_user", limit: int = 100) -> dict[str, Any]:
        messages = self.session_store.session_history(session_id=session_id, user_id=user_id, limit=limit)
        return {"messages": messages}

    def query_scope(self) -> dict[str, Any]:
        tables = {
            "stock_basic_info": self._table_fields(StockBasicInfo.__table__),
            "stock_financial_report": self._table_fields(StockFinancialReport.__table__),
        }
        prompt = (
            "请用中文总结这两张表可以查询的范围、常见问题、注意事项，"
            "重点说明哪个字段在哪张表可以查。输出 5-8 条要点。"
        )
        llm = self.graph.llm
        summary = llm.invoke(
            [
                {
                    "role": "system",
                    "content": "你是股票数据查询助手，回答要准确、简洁、可执行。",
                },
                {
                    "role": "user",
                    "content": f"{prompt}\n\n字段信息：{json.dumps(tables, ensure_ascii=False)}",
                },
            ]
        ).content
        return {
            "tables": tables,
            "scope_summary": str(summary or "").strip(),
            "meta": {
                "embedding_model": "text-embedding-3-large",
                "embedding_dimensions": 3072,
                "short_term_memory_limit": 20,
            },
        }

    def _table_fields(self, table: Any) -> list[dict[str, Any]]:
        fields: list[dict[str, Any]] = []
        for col in table.columns:
            fields.append(
                {
                    "name": col.name,
                    "type": str(col.type),
                    "nullable": bool(col.nullable),
                    "comment": col.comment or "",
                }
            )
        return fields
