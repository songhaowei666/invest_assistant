"""
脚本职责：检查并维护 stock_all_info 表结构与注释。

执行逻辑：
1) 检查表是否存在，不存在则创建；
2) 检查字段是否存在，不存在则补齐；
3) 检查表/字段注释是否一致，不一致则更新；
依赖 api/.env 中的 DATABASE_URL 或 DB_*（与 configs.config.Settings 一致）。
用法: cd api && python3 scripts/update_stock_all_info_table.py
"""
import sys
from pathlib import Path

from sqlalchemy import text

API_DIR = Path(__file__).resolve().parent.parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from db import engine  # noqa: E402
from models.stock_all_info import StockAllInfo  # noqa: E402


def _pg_qualified_table_name(table) -> str:
    if table.schema:
        return f'"{table.schema}"."{table.name}"'
    return f'"{table.name}"'


def _apply_pg_comments_for_table(conn, table) -> None:
    """按差异更新表与字段注释，避免每次无差别覆盖。"""
    qualified = _pg_qualified_table_name(table)
    table_comment_sql = text(
        """
        SELECT obj_description(c.oid, 'pg_class') AS comment
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = :table_name
          AND n.nspname = :schema_name
        LIMIT 1
        """
    )
    schema_name = table.schema or "public"
    current_table_comment = conn.execute(
        table_comment_sql,
        {"table_name": table.name, "schema_name": schema_name},
    ).scalar_one_or_none()
    if table.comment and current_table_comment != table.comment:
        conn.execute(text(f"COMMENT ON TABLE {qualified} IS :c"), {"c": table.comment})
        print("表注释不一致，已更新。")

    for col in table.columns:
        if not col.comment:
            continue
        col_comment_sql = text(
            """
            SELECT pgd.description
            FROM pg_catalog.pg_statio_all_tables st
            JOIN pg_catalog.pg_description pgd ON pgd.objoid = st.relid
            JOIN information_schema.columns c
              ON c.table_schema = st.schemaname
             AND c.table_name = st.relname
             AND c.ordinal_position = pgd.objsubid
            WHERE st.schemaname = :schema_name
              AND st.relname = :table_name
              AND c.column_name = :column_name
            LIMIT 1
            """
        )
        current_col_comment = conn.execute(
            col_comment_sql,
            {
                "schema_name": schema_name,
                "table_name": table.name,
                "column_name": col.name,
            },
        ).scalar_one_or_none()
        if current_col_comment != col.comment:
            conn.execute(
                text(f'COMMENT ON COLUMN {qualified}."{col.name}" IS :c'),
                {"c": col.comment},
            )
            print(f"字段注释不一致，已更新: {col.name}")


def _column_exists(conn, table, column_name: str) -> bool:
    schema_name = table.schema or "public"
    sql = text(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = :schema_name
          AND table_name = :table_name
          AND column_name = :column_name
        LIMIT 1
        """
    )
    row = conn.execute(
        sql,
        {
            "schema_name": schema_name,
            "table_name": table.name,
            "column_name": column_name,
        },
    ).first()
    return row is not None


def _ensure_columns(conn, table) -> None:
    qualified = _pg_qualified_table_name(table)
    for col in table.columns:
        if _column_exists(conn, table, col.name):
            continue
        col_type = col.type.compile(dialect=conn.dialect)
        nullable = "" if col.nullable else " NOT NULL"
        conn.execute(
            text(
                f'ALTER TABLE {qualified} ADD COLUMN "{col.name}" {col_type}{nullable}'
            )
        )
        print(f"缺失字段已补齐: {col.name}")


def main() -> None:
    dialect = engine.url.get_dialect().name
    if dialect != "postgresql":
        print(f"当前 DATABASE_URL 不是 PostgreSQL（检测到 {dialect}），已中止。")
        sys.exit(1)

    table = StockAllInfo.__table__
    with engine.begin() as conn:
        existed_before = conn.execute(
            text(
                """
                SELECT to_regclass(:table_name) IS NOT NULL
                """
            ),
            {"table_name": f'{table.schema + "." if table.schema else ""}{table.name}'},
        ).scalar_one()
        table.create(bind=conn, checkfirst=True)
        if existed_before:
            print(f"表已存在: {_pg_qualified_table_name(table)}")
        else:
            print(f"表不存在，已创建: {_pg_qualified_table_name(table)}")
        _ensure_columns(conn, table)
        _apply_pg_comments_for_table(conn, table)

    print("表结构与注释检查完成。")


if __name__ == "__main__":
    main()
