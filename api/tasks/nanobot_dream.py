"""nanobot Dream 记忆整理 Celery 任务。

通过 Celery 触发与 CLI cron job ``dream`` 相同的 ``Dream.run()`` 流程，
在指定 ``user_id`` 上下文中消费未处理的 history 并更新长期记忆文件。

Worker 示例::

    celery -A extensions.ext_celery:celery_app call tasks.nanobot_dream.run
    celery -A extensions.ext_celery:celery_app call tasks.nanobot_dream.run --args='["default_user"]'
"""

from __future__ import annotations

import asyncio
import logging

from celery import shared_task  # type: ignore[import-untyped]

from core.create_bot import WORKSPACE, build_bot
from core.user_context import DEFAULT_USER_ID, use_user_id
from nanobot_main.config.loader import load_config

logger = logging.getLogger(__name__)

_nanobot = None


def _ensure_nanobot():
    """Worker 进程内懒加载单例 Nanobot，并应用 config.json 中的 Dream 参数。"""
    global _nanobot
    if _nanobot is not None:
        return _nanobot

    nb = build_bot()
    config = load_config(WORKSPACE / "config.json")
    dream_cfg = config.agents.defaults.dream
    dream = nb._loop.dream
    if dream_cfg.model_override:
        dream.model = dream_cfg.model_override
    dream.max_batch_size = dream_cfg.max_batch_size
    dream.max_iterations = dream_cfg.max_iterations
    dream.annotate_line_ages = dream_cfg.annotate_line_ages

    _nanobot = nb
    return _nanobot


async def _run_dream_async(user_id: str) -> bool:
    nb = _ensure_nanobot()
    with use_user_id(user_id):
        return await nb._loop.dream.run()


@shared_task(name="tasks.nanobot_dream.run")
def run(user_id: str = DEFAULT_USER_ID) -> str:
    """执行 nanobot Dream 记忆整理。

    Args:
        user_id: 记忆 PG 隔离键，默认 ``default_user``。

    Returns:
        人类可读的执行摘要，供定时任务执行历史展示。
    """
    uid = user_id or DEFAULT_USER_ID
    try:
        did_work = asyncio.run(_run_dream_async(uid))
    except Exception:
        logger.exception("nanobot Dream 任务失败 user_id=%s", uid)
        raise

    if did_work:
        return f"dream completed user_id={uid}"
    return f"dream idle (nothing to process) user_id={uid}"
