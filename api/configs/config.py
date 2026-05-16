from pathlib import Path
from urllib.parse import quote_plus

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# api 目录，用于固定加载 api/.env（与工作目录无关）
_API_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    APP_NAME: str = "invest-assistant-backend"
    API_PREFIX: str = "/api/v1"
    # 显式设置 DATABASE_URL 时优先使用（单测等通过环境变量注入）
    DATABASE_URL: str | None = None
    # 与 api/.env 中 DB_* 一致；未设置 DATABASE_URL 时按 DB_TYPE 组装 PostgreSQL 连接串
    DB_TYPE: str = "postgresql"
    DB_USERNAME: str = ""
    DB_PASSWORD: str = ""
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_DATABASE: str = ""
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    DASHSCOPE_API_KEY: str
    DASHSCOPE_BASE_URL: str = "https://api.dashscope.aliyuncs.com/compatible-mode/v1"
    MEM0_API_KEY: str = ""
    MEM0_BASE_URL: str = ""
    PROPOSAL_EXPIRE_MINUTES: int = 30

    # Celery（未设置 CELERY_BROKER_URL 时不初始化，避免本地无 Redis 时报错）
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None
    CELERY_BACKEND: str = "redis"
    BROKER_USE_SSL: bool = False
    REDIS_SSL_CERT_REQS: str = "CERT_NONE"
    REDIS_SSL_CA_CERTS: str | None = None
    REDIS_SSL_CERTFILE: str | None = None
    REDIS_SSL_KEYFILE: str | None = None
    CELERY_USE_SENTINEL: bool = False
    CELERY_SENTINEL_MASTER_NAME: str = "mymaster"
    CELERY_SENTINEL_SOCKET_TIMEOUT: float = 1.0
    CELERY_SENTINEL_PASSWORD: str | None = None
    CELERY_TASK_IGNORE_RESULT: bool = True
    CELERY_LOG_TZ: str = "Asia/Shanghai"
    # 逗号分隔的模块路径，如 tasks.example（供 autodiscover / worker 加载）
    CELERY_IMPORTS: str = ""
    CELERY_TASK_ANNOTATIONS: dict | None = None

    # Redis（业务缓存，与 Celery broker 可共用实例、不同 DB）
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_USERNAME: str = ""
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    REDIS_USE_SSL: bool = False
    REDIS_USE_SENTINEL: bool = False
    REDIS_SENTINELS: str = ""
    REDIS_SENTINEL_SERVICE_NAME: str = ""
    REDIS_SENTINEL_USERNAME: str = ""
    REDIS_SENTINEL_PASSWORD: str = ""
    REDIS_SENTINEL_SOCKET_TIMEOUT: float = 0.1
    REDIS_USE_CLUSTERS: bool = False
    REDIS_CLUSTERS: str = ""
    REDIS_CLUSTERS_PASSWORD: str = ""
    REDIS_SERIALIZATION_PROTOCOL: int = 3
    REDIS_ENABLE_CLIENT_SIDE_CACHE: bool = False
    REDIS_MAX_CONNECTIONS: int | None = None

    @field_validator("REDIS_MAX_CONNECTIONS", mode="before")
    @classmethod
    def _empty_redis_max_connections(cls, v):
        if v is None:
            return None
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    model_config = SettingsConfigDict(
        env_file=_API_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def _resolve_database_url(self):
        if self.DATABASE_URL:
            return self
        dtype = self.DB_TYPE.lower()
        if dtype not in ("postgresql", "postgres"):
            raise ValueError("未设置 DATABASE_URL 时，DB_TYPE 仅支持 postgresql")
        user = quote_plus(self.DB_USERNAME)
        password = quote_plus(self.DB_PASSWORD)
        url = (
            f"postgresql://{user}:{password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_DATABASE}"
        )
        object.__setattr__(self, "DATABASE_URL", url)
        return self


settings = Settings()


if __name__ == "__main__":
    print(settings.OPENAI_API_KEY)
