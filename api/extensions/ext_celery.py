"""Celery 扩展（参考 Dify ``ext_celery``，适配 FastAPI）。

- 配置 ``CELERY_BROKER_URL`` 后，模块导入时会构建 ``celery_app``，供
  ``celery -A extensions.ext_celery:celery_app worker`` 使用。
- ``init_celery(app)`` 在 FastAPI 启动时把同一实例挂到 ``app.state.celery``。
- FastAPI 无 Flask 的 ``app_context``：任务内请自行管理 DB 会话等资源。
"""

from __future__ import annotations

import ssl
from typing import TYPE_CHECKING, Any

from celery import Celery, Task  # type: ignore[import-untyped]

from configs.config import settings

if TYPE_CHECKING:
    from fastapi import FastAPI


def _get_celery_ssl_options() -> dict[str, Any] | None:
    """Redis 作为 broker/backend 且开启 BROKER_USE_SSL 时的 SSL 参数。"""
    if not settings.BROKER_USE_SSL:
        return None
    broker = settings.CELERY_BROKER_URL or ""
    if not (
        broker.startswith("redis://")
        or broker.startswith("rediss://")
    ):
        return None

    cert_reqs_map = {
        "CERT_NONE": ssl.CERT_NONE,
        "CERT_OPTIONAL": ssl.CERT_OPTIONAL,
        "CERT_REQUIRED": ssl.CERT_REQUIRED,
    }
    ssl_cert_reqs = cert_reqs_map.get(settings.REDIS_SSL_CERT_REQS, ssl.CERT_NONE)
    return {
        "ssl_cert_reqs": ssl_cert_reqs,
        "ssl_ca_certs": settings.REDIS_SSL_CA_CERTS,
        "ssl_certfile": settings.REDIS_SSL_CERTFILE,
        "ssl_keyfile": settings.REDIS_SSL_KEYFILE,
    }


def _parse_imports(raw: str) -> list[str]:
    if not raw or not raw.strip():
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def _merge_celery_imports(raw: str) -> list[str]:
    """合并用户配置与内置 tasks.scheduler（定时任务 Beat 入口）。"""
    modules = _parse_imports(raw)
    for required in ("tasks.scheduler", "tasks.stock", "tasks.nanobot_dream"):
        if required not in modules:
            modules.append(required)
    return modules


def _build_celery() -> Celery:
    """根据 Settings 构造 Celery 应用。"""

    class FastAPITask(Task):
        """在 worker 中执行任务；需要 DB 时在 ``run`` 内自行 ``SessionLocal()``。"""

        def __call__(self, *args: object, **kwargs: object) -> object:
            return self.run(*args, **kwargs)

    broker_transport_options: dict[str, Any] = {}
    if settings.CELERY_USE_SENTINEL:
        broker_transport_options = {
            "master_name": settings.CELERY_SENTINEL_MASTER_NAME,
            "sentinel_kwargs": {
                "socket_timeout": settings.CELERY_SENTINEL_SOCKET_TIMEOUT,
                "password": settings.CELERY_SENTINEL_PASSWORD,
            },
        }

    app_name = settings.APP_NAME.replace(" ", "-")
    celery = Celery(
        app_name,
        task_cls=FastAPITask,
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND or settings.CELERY_BROKER_URL,
    )

    celery.conf.update(
        result_backend=settings.CELERY_RESULT_BACKEND or settings.CELERY_BROKER_URL,
        broker_transport_options=broker_transport_options,
        broker_connection_retry_on_startup=True,
        worker_hijack_root_logger=False,
        timezone=settings.CELERY_LOG_TZ or "UTC",
        task_ignore_result=settings.CELERY_TASK_IGNORE_RESULT,
        imports=_merge_celery_imports(settings.CELERY_IMPORTS),
        beat_schedule={},
        beat_scheduler="core.scheduled_celery:DatabaseBeatScheduler",
    )
    if settings.CELERY_TASK_ANNOTATIONS is not None:
        celery.conf.update(task_annotations=settings.CELERY_TASK_ANNOTATIONS)

    if settings.CELERY_BACKEND == "redis" and broker_transport_options:
        celery.conf.update(
            result_backend_transport_options=broker_transport_options,
        )

    ssl_options = _get_celery_ssl_options()
    if ssl_options:
        ssl_conf: dict[str, Any] = {"broker_use_ssl": ssl_options}
        if settings.CELERY_BACKEND == "redis":
            ssl_conf["redis_backend_use_ssl"] = ssl_options
        celery.conf.update(ssl_conf)

    celery.set_default()
    return celery


# 未配置 broker 时为 None；配置后供 worker 与 API 共用
celery_app: Celery | None
if settings.CELERY_BROKER_URL:
    celery_app = _build_celery()
else:
    celery_app = None


def init_celery(app: FastAPI) -> Celery | None:
    """将 Celery 挂到 ``app.state.celery``；未配置 broker 时跳过。"""
    if celery_app is None:
        return None
    app.state.celery = celery_app
    return celery_app


def get_celery() -> Celery:
    """从业务代码取 Celery 实例（须在已 ``init_celery`` 且已配置 broker 的进程中调用）。"""
    if celery_app is None:
        raise RuntimeError("未配置 CELERY_BROKER_URL，Celery 未初始化")
    return celery_app
