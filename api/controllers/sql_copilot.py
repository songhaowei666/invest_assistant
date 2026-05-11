from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from services.sql_copilot_service import SqlCopilotService


router = APIRouter(prefix="/sql-copilot", tags=["sql-copilot"])


class SqlCopilotChatIn(BaseModel):
    session_id: str | None = Field(default=None, description="会话 ID；不传则后端自动创建")
    question: str = Field(..., description="用户自然语言问题")
    user_id: str = Field(default="default_user", description="用户 ID")


class SqlCopilotSessionsListIn(BaseModel):
    user_id: str = Field(default="default_user", description="用户 ID")
    limit: int = Field(default=100, ge=1, le=500, description="返回会话数量上限")


class SqlCopilotSessionDeleteIn(BaseModel):
    session_id: str = Field(..., description="会话 ID")
    user_id: str = Field(default="default_user", description="用户 ID")


class SqlCopilotSessionHistoryIn(BaseModel):
    session_id: str = Field(..., description="会话 ID")
    user_id: str = Field(default="default_user", description="用户 ID")
    limit: int = Field(default=100, ge=1, le=500, description="返回历史条数上限")


@router.post("/chat")
def sql_copilot_chat(body: SqlCopilotChatIn) -> dict[str, Any]:
    service = SqlCopilotService()
    return service.chat(session_id=body.session_id, question=body.question, user_id=body.user_id)


@router.get("/query-scope")
def sql_copilot_query_scope() -> dict[str, Any]:
    service = SqlCopilotService()
    return service.query_scope()


@router.post("/sessions/list")
def sql_copilot_sessions_list(body: SqlCopilotSessionsListIn) -> dict[str, Any]:
    service = SqlCopilotService()
    return service.list_sessions(user_id=body.user_id, limit=body.limit)


@router.post("/sessions/delete")
def sql_copilot_sessions_delete(body: SqlCopilotSessionDeleteIn) -> dict[str, Any]:
    service = SqlCopilotService()
    return service.delete_session(session_id=body.session_id, user_id=body.user_id)


@router.post("/sessions/history")
def sql_copilot_sessions_history(body: SqlCopilotSessionHistoryIn) -> dict[str, Any]:
    service = SqlCopilotService()
    return service.session_history(session_id=body.session_id, user_id=body.user_id, limit=body.limit)
