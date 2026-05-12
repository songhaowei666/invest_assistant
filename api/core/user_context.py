"""当前请求/任务的 user_id 上下文。

通过 ContextVar 在请求入口（HTTP / Cron timer / 后台任务）处设置当前 user_id，
让底层 PG 存储层（SessionManager / CronService / MemoryStore 等）按用户隔离查询。

设计原则：
- 默认 user_id = "default_user"，登录态接入前对外接口表现一致。
- 通过 use_user_id(uid) 上下文管理器使用，自动恢复旧值，避免污染外层调用栈。
- 异步后台任务用 contextvars.copy_context() 携带当前值（参见 cron timer 与 dream 调度）。
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

DEFAULT_USER_ID = "default_user"

current_user_id: ContextVar[str] = ContextVar("current_user_id", default=DEFAULT_USER_ID)


def get_user_id() -> str:
    """读取当前上下文中的 user_id，未设置时回退到 default_user。"""
    try:
        value = current_user_id.get()
    except LookupError:
        return DEFAULT_USER_ID
    return value or DEFAULT_USER_ID


def set_user_id(user_id: str | None):
    """显式设置当前 user_id，返回 reset token，调用方负责 reset 还原。

    一般推荐使用 use_user_id 上下文管理器以避免漏掉 reset。
    """
    return current_user_id.set(user_id or DEFAULT_USER_ID)


@contextmanager
def use_user_id(user_id: str | None) -> Iterator[str]:
    """上下文管理器：在 with 块内绑定 user_id，退出时自动还原。"""
    token = current_user_id.set(user_id or DEFAULT_USER_ID)
    try:
        yield current_user_id.get()
    finally:
        current_user_id.reset(token)
