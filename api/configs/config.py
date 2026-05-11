from pathlib import Path
from urllib.parse import quote_plus

from pydantic import model_validator
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
