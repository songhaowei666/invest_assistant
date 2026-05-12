"""机器人会话：基于 nanobot_main 的 SessionManager 与 AgentLoop。

PG 化改造后，每个对外接口在执行业务前通过 use_user_id 绑定当前 user_id
（当前阶段固定为 default_user），底层 SessionManager / MemoryStore / CronService
会从 ContextVar 读取并按用户隔离存储。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
import uuid
from typing import Any, AsyncIterator

from core import create_bot
from core.user_context import DEFAULT_USER_ID, use_user_id

# 与 nanobot_main.api.server 中 HTTP 会话约定一致
API_CHAT_ID = "default"
CHAT_TIMEOUT_S = 120.0

_nanobot: Any = None
_init_lock = asyncio.Lock()
# 按 session_key 串行聊天请求（对齐 aiohttp 版 API 的 session_locks）
_session_chat_locks: dict[str, asyncio.Lock] = {}

# 历史消息对外字段（近 N 条）
_PUBLIC_MSG_KEYS = ("role", "content", "timestamp", "tool_calls", "tool_call_id", "name")


def _sse_chunk(delta: str, model: str, chunk_id: str, finish_reason: str | None = None) -> bytes:
    payload = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"content": delta} if delta else {},
                "finish_reason": finish_reason,
            }
        ],
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


_SSE_DONE = b"data: [DONE]\n\n"


async def ensure_nanobot() -> Any:
    """懒加载单例。"""
    global _nanobot
    async with _init_lock:
        if _nanobot is None:
            from nanobot_main.nanobot import Nanobot

            _nanobot = create_bot.build_bot()
    return _nanobot


def _chat_lock(session_key: str) -> asyncio.Lock:
    return _session_chat_locks.setdefault(session_key, asyncio.Lock())


def _public_message_row(msg: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for k in _PUBLIC_MSG_KEYS:
        if k in msg:
            row[k] = msg[k]
    return row


def _ensure_session_on_disk(sm: Any, key: str) -> None:
    """如果 PG 中无该会话则创建空会话并保存（用户新会话由前端生成 key 即可）。

    注：函数名沿用旧版（曾经基于磁盘 jsonl），现实际作用于 PG。
    """
    if sm.read_session_file(key) is not None:
        return
    session = sm.get_or_create(key)
    sm.save(session)


def _ensure_session_with_uid(sm: Any, key: str, user_id: str) -> None:
    """asyncio.to_thread 跨线程时 ContextVar 不会自动继承，这里在线程内重新绑定 user_id。"""
    with use_user_id(user_id):
        _ensure_session_on_disk(sm, key)


async def list_sessions_json() -> dict[str, Any]:
    nb = await ensure_nanobot()
    with use_user_id(DEFAULT_USER_ID):
        rows = nb._loop.sessions.list_sessions()
    sessions: list[dict[str, Any]] = []
    for r in rows:
        sessions.append(
            {
                "key": r.get("key", ""),
                "created_at": r.get("created_at"),
                "updated_at": r.get("updated_at"),
                "title": r.get("title") or "",
                "preview": "",
            }
        )
    return {"sessions": sessions}


async def delete_session_json(key: str) -> dict[str, Any]:
    nb = await ensure_nanobot()
    with use_user_id(DEFAULT_USER_ID):
        deleted = nb._loop.sessions.delete_session(key)
    return {"deleted": deleted}


async def session_history_json(key: str, limit: int = 30) -> dict[str, Any]:
    nb = await ensure_nanobot()
    sm = nb._loop.sessions

    def _load() -> dict[str, Any] | None:
        # PG 仓库依赖 ContextVar 中的 user_id；子线程内重新绑定一次。
        with use_user_id(DEFAULT_USER_ID):
            _ensure_session_on_disk(sm, key)
            return sm.read_session_file(key)

    raw = await asyncio.to_thread(_load)
    if raw is None:
        return {"key": key, "created_at": None, "updated_at": None, "messages": []}
    msgs = raw.get("messages") or []
    if not isinstance(msgs, list):
        msgs = []
    tail = msgs[-limit:] if limit > 0 else []
    public = [_public_message_row(m) for m in tail if isinstance(m, dict)]
    return {
        "key": raw.get("key", key),
        "created_at": raw.get("created_at"),
        "updated_at": raw.get("updated_at"),
        "messages": public,
    }


async def chat_sse_tokens(key: str, content: str) -> AsyncIterator[bytes]:
    """OpenAI 兼容 SSE 分片流（与 nanobot_main.api.server 行为一致）。"""


    nb = await ensure_nanobot()
    loop = nb._loop
    model_name = getattr(loop, "model", None) or "nanobot"
    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    lock = _chat_lock(key)
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    stream_failed = False
    emitted_content = False

    async def _on_stream(token: str) -> None:
        nonlocal emitted_content
        if token:
            emitted_content = True
        await queue.put(token)

    async def _on_stream_end(*_a: Any, **_kw: Any) -> None:
        return None

    async def _run() -> None:
        nonlocal stream_failed
        try:
            async with lock:
                # 绑定 user_id 上下文：处理 session 与下游 PG 仓库（SessionManager/MemoryStore/Cron）
                with use_user_id(DEFAULT_USER_ID):
                    await asyncio.to_thread(
                        _ensure_session_with_uid,
                        loop.sessions,
                        key,
                        DEFAULT_USER_ID,
                    )
                    response = await asyncio.wait_for(
                        loop.process_direct(
                            content=content,
                            session_key=key,
                            channel="api",
                            chat_id=API_CHAT_ID,
                            on_stream=_on_stream,
                            on_stream_end=_on_stream_end,
                        ),
                        timeout=CHAT_TIMEOUT_S,
                    )
                if not emitted_content:
                    text = (getattr(response, "content", None) or str(response or "")) or ""
                    if text.strip():
                        await queue.put(text)
        except Exception:
            stream_failed = True
        finally:
            await queue.put(None)

    task = asyncio.create_task(_run())
    try:
        while True:
            token = await queue.get()
            if token is None:
                break
            yield _sse_chunk(token, str(model_name), chunk_id)
    finally:
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    if not stream_failed:
        yield _sse_chunk("", str(model_name), chunk_id, finish_reason="stop")
        yield _SSE_DONE
