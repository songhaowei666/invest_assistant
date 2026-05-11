"""
根据 SQLAlchemy 模型在 PostgreSQL 中创建表（含 positions 及关联业务表）。

建表后为模型里声明了 comment 的表、列执行 COMMENT ON（备注以 ORM 元数据为准）。
依赖 api/.env 中的 DATABASE_URL 或 DB_*（与 configs.config.Settings 一致）。
用法: cd api && python3 scripts/create_pg_tables.py
"""
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

# 通过 models 包导入全部实体，确保 Base.metadata 注册完整
import models  # noqa: E402, F401
from models.base import Base  # noqa: E402

from sqlalchemy import text  # noqa: E402

from db import engine  # noqa: E402


def _pg_qualified_table_name(table) -> str:
    """拼出 PostgreSQL 中带引号的表名（含 schema）。"""
    if table.schema:
        return f'"{table.schema}"."{table.name}"'
    return f'"{table.name}"'


def _apply_pg_table_column_comments(conn) -> None:
    """根据 ORM 元数据中的 comment，执行 COMMENT ON TABLE / COLUMN。"""
    for table in Base.metadata.sorted_tables:
        qualified = _pg_qualified_table_name(table)
        if table.comment:
            conn.execute(text(f"COMMENT ON TABLE {qualified} IS :c"), {"c": table.comment})
        for col in table.columns:
            if col.comment:
                conn.execute(
                    text(f'COMMENT ON COLUMN {qualified}."{col.name}" IS :c'),
                    {"c": col.comment},
                )


def main() -> None:
    dialect = engine.url.get_dialect().name
    if dialect != "postgresql":
        print(f"当前 DATABASE_URL 不是 PostgreSQL（检测到 {dialect}），已中止。")
        sys.exit(1)
    with engine.begin() as conn:
        Base.metadata.create_all(bind=conn)
        _apply_pg_table_column_comments(conn)
    names = ", ".join(sorted(Base.metadata.tables.keys()))
    print(f"已创建或确认存在以下表: {names}")
    print("已为带 comment 的表与字段写入 PostgreSQL 备注（COMMENT ON）。")


if __name__ == "__main__":
    main()
