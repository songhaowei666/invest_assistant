"""
在 PostgreSQL 中创建或确认存在 accounts、account_refresh_tokens 表，并写入表/列 COMMENT。

可重复执行：表已存在时不报错；每次执行会按 ORM 元数据刷新 COMMENT。
用法: cd api && python3 scripts/create_account_tables.py
"""

import sys
from pathlib import Path

from sqlalchemy import text

API_DIR = Path(__file__).resolve().parent.parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from db import engine  # noqa: E402
from models.account import Account, AccountRefreshToken  # noqa: E402

TABLES = (Account, AccountRefreshToken)


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

    with engine.begin() as conn:
        for model in TABLES:
            table = model.__table__
            table.create(bind=conn, checkfirst=True)
            _apply_pg_comments_for_table(conn, table)
            qname = _pg_qualified_table_name(table)
            print(f"已创建或确认存在表: {qname}")

    print("已为上述表及带 comment 的列写入 PostgreSQL 备注（COMMENT ON，可重复执行刷新）。")


if __name__ == "__main__":
    main()
