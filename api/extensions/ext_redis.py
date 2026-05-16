"""Redis 扩展（参考 Dify ``ext_redis``，适配 FastAPI）。

使用方法
--------

1. 在 ``api/.env`` 中配置（单机示例）::

       REDIS_HOST=localhost
       REDIS_PORT=6379
       REDIS_PASSWORD=your_password
       REDIS_DB=0

   Sentinel / Cluster / SSL 等见 ``configs.config.Settings`` 中对应字段。

2. 应用启动时 ``extensions.init_extensions`` 会调用 ``init_redis``，
   客户端挂到 ``app.state.redis``；模块级 ``redis_client`` 与之一致。

3. 业务代码中读写缓存::

       from extensions.ext_redis import redis_client, get_redis

       # 方式一：全局包装器（与 Dify 相同，属性委托给底层 redis.Redis）
       redis_client.set("user:1", b"payload")
       value = redis_client.get("user:1")

       # 方式二：显式获取（未初始化时抛 RuntimeError）
       client = get_redis()
       client.setex("session:abc", 3600, b"data")

4. FastAPI 路由内使用 ``app.state``::

       @router.get("/demo")
       def demo(request: Request):
           r = request.app.state.redis
           r.set("k", b"v")
           return {"v": r.get("k")}

5. Celery 任务内直接使用 ``redis_client``（worker 进程同样会执行
   ``init_extensions`` 前导入本模块；若仅 ``celery worker`` 且未走 FastAPI，
   需在 worker 启动路径保证已 ``init_redis`` 或导入后手动 ``initialize``）。
   推荐在任务模块顶部 ``from extensions.ext_redis import redis_client``。

6. Redis 不可用时的降级装饰器::

       from extensions.ext_redis import redis_fallback

       @redis_fallback(default_return=None)
       def load_cache(key: str) -> bytes | None:
           return redis_client.get(key)

   发生 ``redis.RedisError`` 时记录 warning 并返回 ``default_return``。
"""

from __future__ import annotations

import functools
import logging
import ssl
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Callable, ParamSpec, TypeVar, Union

import redis
from redis import RedisError
from redis.cache import CacheConfig
from redis.client import PubSub
from redis.cluster import ClusterNode, RedisCluster
from redis.connection import Connection, SSLConnection
from redis.sentinel import Sentinel

from configs.config import settings

if TYPE_CHECKING:
    from fastapi import FastAPI
    from redis.lock import Lock

logger = logging.getLogger(__name__)

T = TypeVar("T")
P = ParamSpec("P")
R = TypeVar("R")


class RedisClientWrapper:
    """Redis 客户端包装器，支持延迟 ``initialize``（Sentinel 故障转移等场景）。

    属性访问委托给底层 ``redis.Redis`` / ``RedisCluster``；未初始化时访问会抛错。
    """

    _client: Union[redis.Redis, RedisCluster, None]

    def __init__(self) -> None:
        self._client = None

    def initialize(self, client: Union[redis.Redis, RedisCluster]) -> None:
        if self._client is None:
            self._client = client

    if TYPE_CHECKING:
        def get(self, name: str | bytes) -> Any: ...

        def set(
            self,
            name: str | bytes,
            value: Any,
            ex: int | None = None,
            px: int | None = None,
            nx: bool = False,
            xx: bool = False,
            keepttl: bool = False,
            get: bool = False,
            exat: int | None = None,
            pxat: int | None = None,
        ) -> Any: ...

        def setex(self, name: str | bytes, time: int | timedelta, value: Any) -> Any: ...
        def setnx(self, name: str | bytes, value: Any) -> Any: ...
        def delete(self, *names: str | bytes) -> Any: ...
        def incr(self, name: str | bytes, amount: int = 1) -> Any: ...
        def expire(
            self,
            name: str | bytes,
            time: int | timedelta,
            nx: bool = False,
            xx: bool = False,
            gt: bool = False,
            lt: bool = False,
        ) -> Any: ...

        def lock(
            self,
            name: str,
            timeout: float | None = None,
            sleep: float = 0.1,
            blocking: bool = True,
            blocking_timeout: float | None = None,
            thread_local: bool = True,
        ) -> Lock: ...

        def zadd(
            self,
            name: str | bytes,
            mapping: dict[str | bytes | int | float, float | int | str | bytes],
            nx: bool = False,
            xx: bool = False,
            ch: bool = False,
            incr: bool = False,
            gt: bool = False,
            lt: bool = False,
        ) -> Any: ...

        def zremrangebyscore(self, name: str | bytes, min: float | str, max: float | str) -> Any: ...
        def zcard(self, name: str | bytes) -> Any: ...
        def getdel(self, name: str | bytes) -> Any: ...
        def pubsub(self) -> PubSub: ...
        def pipeline(self, transaction: bool = True, shard_hint: str | None = None) -> Any: ...

    def __getattr__(self, item: str) -> Any:
        if self._client is None:
            raise RuntimeError("Redis 客户端未初始化，请先调用 init_redis")
        return getattr(self._client, item)


redis_client: RedisClientWrapper = RedisClientWrapper()


def _empty_to_none(value: str | None) -> str | None:
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None
    return value


def _get_ssl_configuration() -> tuple[type[Union[Connection, SSLConnection]], dict[str, Any]]:
    if not settings.REDIS_USE_SSL:
        return Connection, {}

    cert_reqs_map = {
        "CERT_NONE": ssl.CERT_NONE,
        "CERT_OPTIONAL": ssl.CERT_OPTIONAL,
        "CERT_REQUIRED": ssl.CERT_REQUIRED,
    }
    ssl_cert_reqs = cert_reqs_map.get(settings.REDIS_SSL_CERT_REQS, ssl.CERT_NONE)
    ssl_kwargs = {
        "ssl_cert_reqs": ssl_cert_reqs,
        "ssl_ca_certs": settings.REDIS_SSL_CA_CERTS,
        "ssl_certfile": settings.REDIS_SSL_CERTFILE,
        "ssl_keyfile": settings.REDIS_SSL_KEYFILE,
    }
    return SSLConnection, ssl_kwargs


def _get_cache_configuration() -> CacheConfig | None:
    if not settings.REDIS_ENABLE_CLIENT_SIDE_CACHE:
        return None
    if settings.REDIS_SERIALIZATION_PROTOCOL < 3:
        raise ValueError("客户端缓存仅支持 RESP3，请设置 REDIS_SERIALIZATION_PROTOCOL>=3")
    return CacheConfig()


def _get_base_redis_params() -> dict[str, Any]:
    return {
        "username": _empty_to_none(settings.REDIS_USERNAME),
        "password": _empty_to_none(settings.REDIS_PASSWORD),
        "db": settings.REDIS_DB,
        "encoding": "utf-8",
        "encoding_errors": "strict",
        "decode_responses": False,
        "protocol": settings.REDIS_SERIALIZATION_PROTOCOL,
        "cache_config": _get_cache_configuration(),
    }


def _create_sentinel_client(redis_params: dict[str, Any]) -> Union[redis.Redis, RedisCluster]:
    sentinels = settings.REDIS_SENTINELS
    if not sentinels:
        raise ValueError("REDIS_USE_SENTINEL=true 时必须设置 REDIS_SENTINELS")
    if not settings.REDIS_SENTINEL_SERVICE_NAME:
        raise ValueError("REDIS_USE_SENTINEL=true 时必须设置 REDIS_SENTINEL_SERVICE_NAME")

    sentinel_hosts = [
        (node.split(":")[0], int(node.split(":")[1]))
        for node in sentinels.split(",")
    ]
    sentinel_kwargs: dict[str, Any] = {
        "socket_timeout": settings.REDIS_SENTINEL_SOCKET_TIMEOUT,
        "username": _empty_to_none(settings.REDIS_SENTINEL_USERNAME),
        "password": _empty_to_none(settings.REDIS_SENTINEL_PASSWORD),
    }
    if settings.REDIS_MAX_CONNECTIONS:
        sentinel_kwargs["max_connections"] = settings.REDIS_MAX_CONNECTIONS

    sentinel = Sentinel(sentinel_hosts, sentinel_kwargs=sentinel_kwargs)
    return sentinel.master_for(settings.REDIS_SENTINEL_SERVICE_NAME, **redis_params)


def _create_cluster_client() -> Union[redis.Redis, RedisCluster]:
    clusters = settings.REDIS_CLUSTERS
    if not clusters:
        raise ValueError("REDIS_USE_CLUSTERS=true 时必须设置 REDIS_CLUSTERS")

    nodes = [
        ClusterNode(host=node.split(":")[0], port=int(node.split(":")[1]))
        for node in clusters.split(",")
    ]
    cluster_kwargs: dict[str, Any] = {
        "startup_nodes": nodes,
        "password": _empty_to_none(settings.REDIS_CLUSTERS_PASSWORD),
        "protocol": settings.REDIS_SERIALIZATION_PROTOCOL,
        "cache_config": _get_cache_configuration(),
    }
    if settings.REDIS_MAX_CONNECTIONS:
        cluster_kwargs["max_connections"] = settings.REDIS_MAX_CONNECTIONS
    return RedisCluster(**cluster_kwargs)


def _create_standalone_client(redis_params: dict[str, Any]) -> Union[redis.Redis, RedisCluster]:
    connection_class, ssl_kwargs = _get_ssl_configuration()
    redis_params.update(
        {
            "host": settings.REDIS_HOST,
            "port": settings.REDIS_PORT,
            "connection_class": connection_class,
        }
    )
    if settings.REDIS_MAX_CONNECTIONS:
        redis_params["max_connections"] = settings.REDIS_MAX_CONNECTIONS
    if ssl_kwargs:
        redis_params.update(ssl_kwargs)

    pool = redis.ConnectionPool(**redis_params)
    return redis.Redis(connection_pool=pool)


def _create_redis_client() -> Union[redis.Redis, RedisCluster]:
    if settings.REDIS_USE_SENTINEL:
        return _create_sentinel_client(_get_base_redis_params())
    if settings.REDIS_USE_CLUSTERS:
        return _create_cluster_client()
    return _create_standalone_client(_get_base_redis_params())


def init_redis(app: FastAPI) -> RedisClientWrapper | None:
    """初始化 Redis 并挂到 ``app.state.redis``；未配置 ``REDIS_HOST`` 时跳过。"""
    if not settings.REDIS_HOST or not settings.REDIS_HOST.strip():
        return None

    client = _create_redis_client()
    redis_client.initialize(client)
    app.state.redis = redis_client
    return redis_client


def get_redis() -> RedisClientWrapper:
    """获取已初始化的 Redis 包装器。"""
    if redis_client._client is None:
        raise RuntimeError("Redis 未初始化，请确认已配置 REDIS_HOST 且已调用 init_redis")
    return redis_client


def redis_fallback(default_return: T | None = None):
    """Redis 操作失败时返回默认值并记录日志。"""

    def decorator(func: Callable[P, R]) -> Callable[P, R | T | None]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R | T | None:
            try:
                return func(*args, **kwargs)
            except RedisError as e:
                func_name = getattr(func, "__name__", "Unknown")
                logger.warning(
                    "Redis 操作失败 %s: %s", func_name, str(e), exc_info=True
                )
                return default_return

        return wrapper

    return decorator
