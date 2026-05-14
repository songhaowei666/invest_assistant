"""Session management for conversation history.

存储层已从 workspace/sessions/*.jsonl 改为 PostgreSQL（按 user_id 隔离）。
Session 数据类与所有纯内存方法保持原状，仅替换底层 _load / save / list /
delete / read_session_file / flush_all 等访问磁盘的方法为 PG 调用。

历史的 jsonl 读写、_repair、legacy 迁移逻辑作为代码保留以便参考但不会被触发。
"""

from __future__ import annotations

import json
import os
import shutil
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot_main.config.paths import get_legacy_sessions_dir
from nanobot_main.utils.helpers import (
    ensure_dir,
    estimate_message_tokens,
    find_legal_message_start,
    image_placeholder_text,
    safe_filename,
)

# PG 仓库：用户上下文取自 api/core/user_context.current_user_id
from core.user_context import get_user_id  # noqa: E402
from repositories.nanobot_session_repo import NanobotSessionRepo  # noqa: E402

FILE_MAX_MESSAGES = 2000


def _clip_session_title(text: str, max_chars: int) -> str:
    """截断列表标题，避免过长；与 WebUI 标题长度习惯一致。"""
    t = (text or "").strip()
    if not t:
        return ""
    if max_chars <= 0 or len(t) <= max_chars:
        return t
    return t[: max_chars - 1].rstrip() + "…"


def _first_user_snippet_for_title(messages: list[dict[str, Any]], max_chars: int = 60) -> str:
    """取首条非空用户文本作为默认会话标题（新建会话）。"""
    for message in messages:
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return _clip_session_title(content, max_chars)
    return ""


def effective_session_title_for_persist(session: Session) -> str:
    """计算写入 PG 的 title 列：用户改名 > WebUI 元数据标题 > 已有列值 > 首条用户提问。

    与 nanobot_main.utils.webui_titles 中 webui / title / title_user_edited 语义保持一致。
    """
    meta = session.metadata or {}
    if meta.get("title_user_edited") is True:
        return _clip_session_title(session.title, 512)
    if meta.get("webui") is True:
        raw = meta.get("title")
        if isinstance(raw, str) and raw.strip():
            return _clip_session_title(raw, 512)
    existing = (session.title or "").strip()
    if existing:
        return _clip_session_title(existing, 512)
    return _clip_session_title(_first_user_snippet_for_title(session.messages), 512)


@dataclass
class Session:
    """A conversation session."""

    key: str  # channel:chat_id
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    # 与会话主表 nanobot_session.title 同步，供列表展示；默认由首条用户提问推导
    title: str = ""
    last_consolidated: int = 0  # Number of messages already consolidated to files

    @staticmethod
    def _annotate_message_time(message: dict[str, Any], content: Any) -> Any:
        """Expose persisted turn timestamps to the model for relative-date reasoning.

        Annotating *every* assistant turn trains the model (via in-context
        demonstrations) to start its own replies with the same
        ``[Message Time: ...]`` prefix, which leaks metadata back to the user.
        We therefore only annotate:

        * ``user`` turns — needed so the model can pin the conversation in time.
        * proactive deliveries (``_channel_delivery=True``) — cron / heartbeat
          assistant pushes that may sit hours away from the next user reply,
          and are too infrequent to act as parroting demonstrations.
        """
        timestamp = message.get("timestamp")
        if not timestamp or not isinstance(content, str):
            return content
        role = message.get("role")
        if role == "user":
            pass
        elif role == "assistant" and message.get("_channel_delivery"):
            pass
        else:
            return content
        return f"[Message Time: {timestamp}]\n{content}"

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """Add a message to the session."""
        msg = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.messages.append(msg)
        self.updated_at = datetime.now()

    def get_history(
        self,
        max_messages: int = 120,
        *,
        max_tokens: int = 0,
        include_timestamps: bool = False,
    ) -> list[dict[str, Any]]:
        """Return unconsolidated messages for LLM input.

        History is sliced by message count first (``max_messages``), then by
        token budget from the tail (``max_tokens``) when provided.
        """
        unconsolidated = self.messages[self.last_consolidated:]
        max_messages = max_messages if max_messages > 0 else 120
        sliced = unconsolidated[-max_messages:]

        # Avoid starting mid-turn when possible, except for proactive
        # assistant deliveries that the user may be replying to.
        for i, message in enumerate(sliced):
            if message.get("role") == "user":
                start = i
                if i > 0 and sliced[i - 1].get("_channel_delivery"):
                    start = i - 1
                sliced = sliced[start:]
                break

        # Drop orphan tool results at the front.
        start = find_legal_message_start(sliced)
        if start:
            sliced = sliced[start:]

        out: list[dict[str, Any]] = []
        for message in sliced:
            content = message.get("content", "")
            # Synthesize an ``[image: path]`` breadcrumb from the persisted
            # ``media`` kwarg so LLM replay still sees *something* where the
            # image used to be. Without this, an image-only user turn
            # replays as an empty user message — the assistant's reply then
            # looks like it's responding to nothing.
            media = message.get("media")
            if isinstance(media, list) and media and isinstance(content, str):
                breadcrumbs = "\n".join(
                    image_placeholder_text(p) for p in media if isinstance(p, str) and p
                )
                content = f"{content}\n{breadcrumbs}" if content else breadcrumbs
            if include_timestamps:
                content = self._annotate_message_time(message, content)
            entry: dict[str, Any] = {"role": message["role"], "content": content}
            for key in ("tool_calls", "tool_call_id", "name", "reasoning_content", "thinking_blocks"):
                if key in message:
                    entry[key] = message[key]
            out.append(entry)

        if max_tokens > 0 and out:
            kept: list[dict[str, Any]] = []
            used = 0
            for message in reversed(out):
                tokens = estimate_message_tokens(message)
                if kept and used + tokens > max_tokens:
                    break
                kept.append(message)
                used += tokens
            kept.reverse()

            # Keep history aligned to the first visible user turn.
            first_user = next((i for i, m in enumerate(kept) if m.get("role") == "user"), None)
            if first_user is not None:
                kept = kept[first_user:]
            else:
                # Tight token budgets can otherwise leave assistant-only tails.
                # If a user turn exists in the unsliced output, recover the
                # nearest one even if it slightly exceeds the token budget.
                recovered_user = next(
                    (i for i in range(len(out) - 1, -1, -1) if out[i].get("role") == "user"),
                    None,
                )
                if recovered_user is not None:
                    kept = out[recovered_user:]

            # And keep a legal tool-call boundary at the front.
            start = find_legal_message_start(kept)
            if start:
                kept = kept[start:]
            out = kept
        return out

    def clear(self) -> None:
        """Clear all messages and reset session to initial state."""
        self.messages = []
        self.last_consolidated = 0
        self.updated_at = datetime.now()

    def retain_recent_legal_suffix(self, max_messages: int) -> None:
        """Keep a legal recent suffix constrained by a hard message cap."""
        if max_messages <= 0:
            self.clear()
            return
        if len(self.messages) <= max_messages:
            return

        retained = list(self.messages[-max_messages:])

        # Prefer starting at a user turn when one exists within the tail.
        first_user = next((i for i, m in enumerate(retained) if m.get("role") == "user"), None)
        if first_user is not None:
            retained = retained[first_user:]
        else:
            # If the tail is assistant/tool-only, anchor to the latest user in
            # the full session and take a capped forward window from there.
            latest_user = next(
                (i for i in range(len(self.messages) - 1, -1, -1)
                 if self.messages[i].get("role") == "user"),
                None,
            )
            if latest_user is not None:
                retained = list(self.messages[latest_user: latest_user + max_messages])

        # Mirror get_history(): avoid persisting orphan tool results at the front.
        start = find_legal_message_start(retained)
        if start:
            retained = retained[start:]

        # Hard-cap guarantee: never keep more than max_messages.
        if len(retained) > max_messages:
            retained = retained[-max_messages:]
            start = find_legal_message_start(retained)
            if start:
                retained = retained[start:]

        dropped = len(self.messages) - len(retained)
        self.messages = retained
        self.last_consolidated = max(0, self.last_consolidated - dropped)
        self.updated_at = datetime.now()

    def enforce_file_cap(
        self,
        on_archive: Any = None,
        limit: int = FILE_MAX_MESSAGES,
    ) -> None:
        """Bound session message growth by archiving and trimming old prefixes."""
        if limit <= 0 or len(self.messages) <= limit:
            return

        before = list(self.messages)
        before_last_consolidated = self.last_consolidated
        before_count = len(before)
        self.retain_recent_legal_suffix(limit)
        dropped_count = before_count - len(self.messages)
        if dropped_count <= 0:
            return

        dropped = before[:dropped_count]
        already_consolidated = min(before_last_consolidated, dropped_count)
        archive_chunk = dropped[already_consolidated:]
        if archive_chunk and on_archive:
            on_archive(archive_chunk)
        logger.info(
            "Session file cap hit for {}: dropped {}, raw-archived {}, kept {}",
            self.key,
            dropped_count,
            len(archive_chunk),
            len(self.messages),
        )


class SessionManager:
    """
    Manages conversation sessions.

    Sessions 数据持久化位置：PostgreSQL（nanobot_session / nanobot_session_message），
    按当前 user_id（core.user_context.current_user_id）隔离。

    workspace 参数仅作历史签名兼容，PG 化后不再使用 sessions 目录。
    历史 jsonl 相关方法保留，但仅作参考或在工具函数中复用。
    """

    def __init__(self, workspace: Path):
        self.workspace = workspace
        # PG 化后不再使用 sessions_dir / legacy_sessions_dir，仅保留属性兼容其它引用
        self.sessions_dir = workspace / "sessions"
        self.legacy_sessions_dir = get_legacy_sessions_dir()
        self._cache: dict[str, Session] = {}
        self._repo = NanobotSessionRepo()

    @staticmethod
    def safe_key(key: str) -> str:
        """Public helper used by HTTP handlers to map an arbitrary key to a stable filename stem."""
        return safe_filename(key.replace(":", "_"))

    def _get_session_path(self, key: str) -> Path:
        """[deprecated] 旧版按文件存储时的 session 路径，PG 化后保留但不再使用。"""
        return self.sessions_dir / f"{self.safe_key(key)}.jsonl"

    def _get_legacy_session_path(self, key: str) -> Path:
        """[deprecated] 旧版 ~/.nanobot/sessions 路径，PG 化后保留但不再使用。"""
        return self.legacy_sessions_dir / f"{self.safe_key(key)}.jsonl"

    def get_or_create(self, key: str) -> Session:
        """
        Get an existing session or create a new one.

        Args:
            key: Session key (usually channel:chat_id).

        Returns:
            The session.
        """
        if key in self._cache:
            return self._cache[key]

        session = self._load(key)
        if session is None:
            session = Session(key=key)

        self._cache[key] = session
        return session

    def _load(self, key: str) -> Session | None:
        """从 PG 加载 session：按 (user_id, session_key) 查询主表 + 消息表。"""
        user_id = get_user_id()
        try:
            payload = self._repo.load_session_full(user_id, key)
        except Exception as e:
            logger.warning("Failed to load session {} for user {}: {}", key, user_id, e)
            return None

        if payload is None:
            return None

        try:
            created_at = (
                datetime.fromisoformat(payload["created_at"])
                if payload.get("created_at")
                else datetime.now()
            )
            updated_at = (
                datetime.fromisoformat(payload["updated_at"])
                if payload.get("updated_at")
                else datetime.now()
            )
            return Session(
                key=key,
                messages=list(payload.get("messages") or []),
                created_at=created_at,
                updated_at=updated_at,
                metadata=dict(payload.get("metadata") or {}),
                title=str(payload.get("title") or ""),
                last_consolidated=int(payload.get("last_consolidated", 0) or 0),
            )
        except Exception as e:
            logger.warning("Failed to deserialize session {} for user {}: {}", key, user_id, e)
            return None

    def _repair(self, key: str) -> Session | None:
        """Attempt to recover a session from a corrupt JSONL file."""
        path = self._get_session_path(key)
        if not path.exists():
            return None

        try:
            messages: list[dict[str, Any]] = []
            metadata: dict[str, Any] = {}
            created_at: datetime | None = None
            updated_at: datetime | None = None
            last_consolidated = 0
            skipped = 0

            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        skipped += 1
                        continue

                    if data.get("_type") == "metadata":
                        metadata = data.get("metadata", {})
                        if data.get("created_at"):
                            with suppress(ValueError, TypeError):
                                created_at = datetime.fromisoformat(data["created_at"])
                        if data.get("updated_at"):
                            with suppress(ValueError, TypeError):
                                updated_at = datetime.fromisoformat(data["updated_at"])
                        last_consolidated = data.get("last_consolidated", 0)
                    else:
                        messages.append(data)

            if skipped:
                logger.warning("Skipped {} corrupt lines in session {}", skipped, key)

            if not messages and not metadata:
                return None

            return Session(
                key=key,
                messages=messages,
                created_at=created_at or datetime.now(),
                updated_at=updated_at or datetime.now(),
                metadata=metadata,
                last_consolidated=last_consolidated
            )
        except Exception as e:
            logger.warning("Repair failed for session {}: {}", key, e)
            return None

    @staticmethod
    def _session_payload(session: Session) -> dict[str, Any]:
        return {
            "key": session.key,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "title": session.title,
            "metadata": session.metadata,
            "messages": session.messages,
        }

    def save(self, session: Session, *, fsync: bool = False) -> None:
        """保存 session 到 PG。

        fsync 参数保留以兼容旧接口；PG 事务提交后即视为持久化，
        无需 file/dir fsync，参数被忽略。
        """
        user_id = get_user_id()
        try:
            effective = effective_session_title_for_persist(session)
            self._repo.save_session(
                user_id=user_id,
                session_key=session.key,
                created_at=session.created_at,
                updated_at=session.updated_at,
                title=effective,
                metadata=session.metadata or {},
                last_consolidated=session.last_consolidated,
                messages=list(session.messages or []),
            )
            session.title = effective
        except Exception:
            logger.exception("Failed to save session {} for user {}", session.key, user_id)
            raise

        self._cache[session.key] = session

    def flush_all(self) -> int:
        """Re-save every cached session with fsync for durable shutdown.

        Returns the number of sessions flushed.  Errors on individual
        sessions are logged but do not prevent other sessions from being
        flushed.
        """
        flushed = 0
        for key, session in list(self._cache.items()):
            try:
                self.save(session, fsync=True)
                flushed += 1
            except Exception:
                logger.warning("Failed to flush session {}", key, exc_info=True)
        return flushed

    def invalidate(self, key: str) -> None:
        """Remove a session from the in-memory cache."""
        self._cache.pop(key, None)

    def delete_session(self, key: str) -> bool:
        """从 PG 删除会话主表与消息行，并清理内存缓存。

        Returns True if a session row was deleted.
        """
        user_id = get_user_id()
        self.invalidate(key)
        try:
            return self._repo.delete_session(user_id, key)
        except Exception:
            logger.exception("Failed to delete session {} for user {}", key, user_id)
            return False

    def read_session_file(self, key: str) -> dict[str, Any] | None:
        """从 PG 读取会话全量（不进缓存），供只读 HTTP 接口使用。

        返回结构：``{"key", "created_at", "updated_at", "title", "metadata", "messages"}``，
        会话不存在时返回 ``None``。
        """
        user_id = get_user_id()
        try:
            payload = self._repo.load_session_full(user_id, key)
        except Exception:
            logger.exception("Failed to read session {} for user {}", key, user_id)
            return None

        if payload is None:
            return None

        return {
            "key": payload.get("key", key),
            "created_at": payload.get("created_at"),
            "updated_at": payload.get("updated_at"),
            "title": str(payload.get("title") or ""),
            "metadata": dict(payload.get("metadata") or {}),
            "messages": list(payload.get("messages") or []),
        }

    def list_sessions(self) -> list[dict[str, Any]]:
        """
        List all sessions for current user.

        Returns:
            List of session info dicts: ``{key, created_at, updated_at, title, path}``，
            顺序为按 ``created_at`` 倒序（新建在上）。
        """
        user_id = get_user_id()
        try:
            return self._repo.list_sessions(user_id)
        except Exception:
            logger.exception("Failed to list sessions for user {}", user_id)
            return []

    def update_session_title(self, key: str, new_title: str) -> bool:
        """用户重命名会话（写入 title 列并标记 title_user_edited，避免被首问默认逻辑覆盖）。"""
        user_id = get_user_id()
        clipped = _clip_session_title(new_title, 512)
        if not clipped:
            return False
        try:
            if self._repo.get_session_row(user_id, key) is None:
                return False
        except Exception:
            logger.exception("Failed to check session {} for user {}", key, user_id)
            return False
        session = self.get_or_create(key)
        session.title = clipped
        session.metadata["title_user_edited"] = True
        session.updated_at = datetime.now()
        try:
            self.save(session)
        except Exception:
            logger.exception("Failed to rename session {} for user {}", key, user_id)
            return False
        return True
