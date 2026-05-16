"""Celery 任务样例（与 ``extensions.ext_celery`` 配合）。

使用前在环境变量中配置 ``CELERY_BROKER_URL``，并设置::

    CELERY_IMPORTS=tasks.sample

Worker 示例::

    celery -A extensions.ext_celery:celery_app worker -l info

使用 ``shared_task``，便于在 ``celery_app`` 可能为 None 的 API 进程里也能导入本模块；
worker 进程会先加载 ``ext_celery`` 并 ``set_default()``，再按 ``CELERY_IMPORTS`` 加载本文件，
任务会注册到同一应用上。
"""

from __future__ import annotations

from celery import shared_task  # type: ignore[import-untyped]


@shared_task(name="tasks.sample.ping")
def ping() -> str:
    """简单连通性任务。"""
    print("ping")
    return "pong"


@shared_task(name="tasks.sample.echo", bind=True)
def echo(self, text: str) -> str:
    """回显字符串；``bind=True`` 时第一个参数为任务实例。"""
    return text


if __name__ == "__main__":
    import sys
    from pathlib import Path

    api_dir = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(api_dir))

    import extensions.ext_celery  # 加载 .env 里的 Redis broker

    result = echo.delay("hello")
    print("task id:", result.id)

# 在已 ``init_extensions`` 的 FastAPI 路由中投递任务示例（需已配置 ``CELERY_BROKER_URL``）：
#
#     from fastapi import Request
#     from tasks.sample import ping
#
#     @router.post("/demo-celery")
#     def demo_celery(request: Request) -> dict:
#         if getattr(request.app.state, "celery", None) is None:
#             return {"queued": False}
#         ping.delay()
#         return {"queued": True}
#
# 或 ``from extensions.ext_celery import get_celery`` 后 ``get_celery().send_task(...)``。
