"""FastAPI 扩展入口（Celery 等）。"""

from fastapi import FastAPI

from extensions.ext_celery import init_celery


def init_extensions(app: FastAPI) -> None:
    """注册各扩展（含 Celery：挂到 ``app.state.celery``）。

    由 ``main.py`` 在构造 ``FastAPI`` 后立即调用；未配置 ``CELERY_BROKER_URL`` 时
    ``init_celery`` 不挂载实例。
    """
    init_celery(app)
