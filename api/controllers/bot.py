"""机器人 HTTP 接口：会话列表、增删、近 30 条历史、流式聊天（对齐 nanobot_example 的 JSON 形态）。"""

from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from services import bot_service


router = APIRouter(prefix="/bot", tags=["bot"])


class SessionKeyIn(BaseModel):
    """依赖会话 key 的请求体。"""

    key: str = Field(..., description="会话 key，例如 api:xxxx")


class SessionTitleIn(BaseModel):
    """修改会话标题（类似豆包侧栏重命名）。"""

    key: str = Field(..., description="会话 key，例如 api:xxxx")
    title: str = Field(..., min_length=1, max_length=512, description="新标题")


class SessionHistoryIn(BaseModel):
    """会话历史请求体。"""

    key: str
    limit: int = Field(default=30, ge=1, le=200)


class ChatStreamIn(BaseModel):
    """流式聊天请求体。"""

    key: str
    content: str


@router.post("/sessions/list")
async def bot_sessions_list(_payload: dict[str, Any] = Body(default_factory=dict)) -> dict[str, Any]:
    """1. 历史会话列表（与 nanobot_example listSessions 字段对齐）。"""
    return await bot_service.list_sessions_json()


@router.post("/sessions/delete")
async def bot_sessions_delete(body: SessionKeyIn) -> dict[str, Any]:
    """2. 删除会话。"""
    return await bot_service.delete_session_json(body.key)


@router.post("/sessions/title")
async def bot_sessions_update_title(body: SessionTitleIn) -> dict[str, Any]:
    """重命名会话标题（须为已存在的会话）。"""
    return await bot_service.update_session_title_json(body.key, body.title)


@router.post("/sessions/history")
async def bot_sessions_history(body: SessionHistoryIn) -> dict[str, Any]:
    """3. 查询会话历史（默认近 30 条）；会话不存在时自动创建空会话。"""
    return await bot_service.session_history_json(body.key, body.limit)


@router.post("/chat")
async def bot_chat_stream(body: ChatStreamIn) -> StreamingResponse:
    """4. 用户发消息，返回 OpenAI 兼容 SSE 流。"""

    async def gen() -> AsyncIterator[bytes]:
        async for chunk in bot_service.chat_sse_tokens(body.key, body.content):
            yield chunk

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
