"""
在 PostgreSQL 中创建或确认存在 nanobot 相关 7 张表，并写入表/列 COMMENT。

可重复执行：表已存在时不报错（checkfirst）；每次执行会按 ORM 元数据刷新 COMMENT。
依赖 api/.env 中的 DATABASE_URL 或 DB_*（与 configs.config.Settings 一致）。
用法: cd api && python3 scripts/create_nanobot_tables.py

注意：这些 ORM 模型未加入 api/models/__init__.py 聚合导入，因此 api/main.py 启动
的 Base.metadata.create_all 与 api/scripts/create_pg_tables.py 都不会创建它们；
必须通过本脚本手动建表。
"""

import sys
from pathlib import Path

from sqlalchemy import text

API_DIR = Path(__file__).resolve().parent.parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from db import engine  # noqa: E402

from models.nanobot_cron_job import NanobotCronJob  # noqa: E402
from models.nanobot_memory_cursor import NanobotMemoryCursor  # noqa: E402
from models.nanobot_memory_file import NanobotMemoryFile  # noqa: E402
from models.nanobot_memory_history import NanobotMemoryHistory  # noqa: E402
from models.nanobot_memory_md import NanobotMemoryMd  # noqa: E402
from models.nanobot_session import NanobotSession  # noqa: E402
from models.nanobot_session_message import NanobotSessionMessage  # noqa: E402

_NANOBOT_MODELS = [
    NanobotSession,
    NanobotSessionMessage,
    NanobotCronJob,
    NanobotMemoryFile,
    NanobotMemoryMd,
    NanobotMemoryHistory,
    NanobotMemoryCursor,
]


def _pg_qualified_table_name(table) -> str:
    if table.schema:
        return f'"{table.schema}"."{table.name}"'
    return f'"{table.name}"'


def _apply_pg_comments_for_table(conn, table) -> None:
    """根据 ORM 元数据对该表执行 COMMENT ON TABLE / COLUMN。"""
    qualified = _pg_qualified_table_name(table)
    if table.comment:
        conn.execute(text(f"COMMENT ON TABLE {qualified} IS :c"), {"c": table.comment})
    for col in table.columns:
        if col.comment:
            conn.execute(
                text(f'COMMENT ON COLUMN {qualified}."{col.name}" IS :c'),
                {"c": col.comment},
            )


def _ensure_nanobot_session_title_column(conn) -> None:
    """已有库仅执行过旧版建表时无 title 列，在此补列（不回填历史数据）。

    必须在 COMMENT ON COLUMN ... title 之前执行：checkfirst 建表不会给已存在的表加新列。
    """
    conn.execute(
        text(
            'ALTER TABLE "nanobot_session" ADD COLUMN IF NOT EXISTS "title" VARCHAR(512)'
        )
    )


def main() -> None:
    dialect = engine.url.get_dialect().name
    if dialect != "postgresql":
        print(f"当前 DATABASE_URL 不是 PostgreSQL（检测到 {dialect}），已中止。")
        sys.exit(1)

    tables = [model.__table__ for model in _NANOBOT_MODELS]

    with engine.begin() as conn:
        for table in tables:
            table.create(bind=conn, checkfirst=True)
            if table.name == "nanobot_session":
                _ensure_nanobot_session_title_column(conn)
            _apply_pg_comments_for_table(conn, table)

    names = ", ".join(_pg_qualified_table_name(t) for t in tables)
    print(f"已创建或确认存在以下表: {names}")
    print("已为带 comment 的表与字段写入 PostgreSQL 备注（COMMENT ON，可重复执行刷新）。")


if __name__ == "__main__":
    main()
