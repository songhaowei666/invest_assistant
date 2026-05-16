"""FastAPI 扩展入口（Celery、Redis 等）。"""

from fastapi import FastAPI

from extensions.ext_celery import init_celery
from extensions.ext_redis import init_redis


def init_extensions(app: FastAPI) -> None:
    """注册各扩展。

    - Celery：``app.state.celery``（未配置 ``CELERY_BROKER_URL`` 时跳过）
    - Redis：``app.state.redis``（未配置 ``REDIS_HOST`` 时跳过）
    """
    init_celery(app)
    init_redis(app)
