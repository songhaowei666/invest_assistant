"""
在 PostgreSQL 中创建或确认存在 sql_copilot_message 表，并写入表/列 COMMENT。

可重复执行：表已存在时不报错；每次执行会按 ORM 元数据刷新 COMMENT。
依赖 api/.env 中的 DATABASE_URL 或 DB_*（与 configs.config.Settings 一致）。
用法: cd api && python3 scripts/create_sql_copilot_message_table.py
"""

import sys
from pathlib import Path

from sqlalchemy import text

API_DIR = Path(__file__).resolve().parent.parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from db import engine  # noqa: E402
from models.sql_copilot_message import SqlCopilotMessage  # noqa: E402


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


def main() -> None:
    dialect = engine.url.get_dialect().name
    if dialect != "postgresql":
        print(f"当前 DATABASE_URL 不是 PostgreSQL（检测到 {dialect}），已中止。")
        sys.exit(1)

    table = SqlCopilotMessage.__table__
    with engine.begin() as conn:
        table.create(bind=conn, checkfirst=True)
        _apply_pg_comments_for_table(conn, table)

    qname = _pg_qualified_table_name(table)
    print(f"已创建或确认存在表: {qname}")
    print("已为该表及带 comment 的列写入 PostgreSQL 备注（COMMENT ON，可重复执行刷新）。")


if __name__ == "__main__":
    main()
