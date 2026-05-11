from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI
from sqlalchemy.engine.url import make_url

# 兼容直接执行: python api/core/text2sql_vanna_stock.py
API_DIR = Path(__file__).resolve().parent.parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from configs.config import settings
from models.stock_basic_info import StockBasicInfo
from models.stock_financial_report import StockFinancialReport


def _build_vanna_class() -> type:
    try:
        from vanna.chromadb.chromadb_vector import ChromaDB_VectorStore  # type: ignore[reportMissingImports]
        from vanna.openai import OpenAI_Chat  # type: ignore[reportMissingImports]
    except ModuleNotFoundError as exc:
        try:
            from vanna.legacy.chromadb.chromadb_vector import (  # type: ignore[reportMissingImports]
                ChromaDB_VectorStore,
            )
            from vanna.legacy.openai.openai_chat import (  # type: ignore[reportMissingImports]
                OpenAI_Chat,
            )
        except ModuleNotFoundError as legacy_exc:
            raise RuntimeError(
                "缺少可用的 vanna 向量库模块。请先安装："
                "pip install vanna chromadb -i https://pypi.tuna.tsinghua.edu.cn/simple "
                "--trusted-host pypi.tuna.tsinghua.edu.cn"
            ) from legacy_exc

    class MyVanna(ChromaDB_VectorStore, OpenAI_Chat):
        def __init__(self, config=None, client=None):
            ChromaDB_VectorStore.__init__(self, config=config)
            OpenAI_Chat.__init__(self, client=client, config=config)

    return MyVanna


def _table_ddl_text(table) -> str:
    lines: list[str] = [f"CREATE TABLE {table.name} ("]
    col_lines: list[str] = []
    for col in table.columns:
        pk_text = " PRIMARY KEY" if col.primary_key else ""
        null_text = "" if col.nullable else " NOT NULL"
        col_lines.append(f"  {col.name} {col.type}{null_text}{pk_text}")
    lines.append(",\n".join(col_lines))
    lines.append(");")
    if table.comment:
        lines.append(f"COMMENT ON TABLE {table.name} IS '{table.comment}';")
    for col in table.columns:
        if col.comment:
            # 字段备注包含单位与口径，帮助 LLM 生成更准确 SQL
            lines.append(f"COMMENT ON COLUMN {table.name}.{col.name} IS '{col.comment}';")
    return "\n".join(lines)


def _build_vanna() -> Any:
    my_vanna_cls = _build_vanna_class()
    client = OpenAI(
        base_url=settings.OPENAI_BASE_URL,
        api_key=settings.OPENAI_API_KEY,
    )
    vector_store_path = str(API_DIR / "data" / "vanna_stock")
    vn = my_vanna_cls(
        config={
            "model": settings.OPENAI_MODEL,
            "path": vector_store_path,
            "language": "Chinese",
            "n_results_ddl": 30,
        },
        client=client,
    )
    db_url = make_url(settings.DATABASE_URL)
    if (db_url.drivername or "").split("+", 1)[0] not in ("postgresql", "postgres"):
        raise ValueError("当前 text2sql_vanna_stock 仅支持 PostgreSQL")
    vn.connect_to_postgres(
        host=db_url.host,
        dbname=db_url.database,
        user=db_url.username,
        password=db_url.password,
        port=db_url.port or 5432,
    )
    return vn


def _train_stock_schema(vn: Any) -> None:
    vn.train(ddl=_table_ddl_text(StockBasicInfo.__table__))
    vn.train(ddl=_table_ddl_text(StockFinancialReport.__table__))
    vn.train(
        documentation=(
            "查询股票最新快照优先使用 stock_basic_info；"
            "查询历史财务指标优先使用 stock_financial_report；"
            "stock_financial_report 的主键是 (code, report_period)；"
            "stock_financial_report 不包含 pe/pb/price/dividend_yield；"
            "pe、pb、price、dividend_yield 只能来自 stock_basic_info。"
        )
    )
    # 少量样例帮助模型避免把 pe/pb 错用到 stock_financial_report
    vn.train(
        question="查询 600519 最新市盈率和市净率",
        sql="SELECT pe, pb FROM stock_basic_info WHERE code = '600519';",
    )
    vn.train(
        question="查询 600519 最近五个年报的 ROE",
        sql=(
            "SELECT report_period, roe FROM stock_financial_report "
            "WHERE code = '600519' AND RIGHT(report_period, 4) = '1231' "
            "ORDER BY report_period DESC LIMIT 5;"
        ),
    )


def text2sql_query(question: str, auto_train: bool = True) -> dict:
    """
    自然语言转 SQL，并直接执行查询。
    返回值包含 SQL 与查询结果 DataFrame。
    """
    vn = _build_vanna()
    _train_stock_schema(vn)
    sql, df, _ = vn.ask(
        question=question,
        print_results=False,
        visualize=False,
        auto_train=auto_train,
    )
    return {"question": question, "sql": sql, "df": df}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="基于 Vanna 的股票 text2sql（StockBasicInfo + StockFinancialReport）"
    )
    parser.add_argument("question", help="自然语言问题，例如：最近一期茅台的 ROE 是多少")
    args = parser.parse_args(argv)

    result = text2sql_query(args.question)
    print("问题:")
    print(result["question"])
    print("\nSQL:")
    print(result["sql"])
    print("\n结果:")
    if result["df"] is None:
        print("SQL 执行失败或无结果，请检查上方 SQL 是否引用了不存在的字段。")
    elif getattr(result["df"], "empty", False):
        print("查询成功，但结果为空。")
    else:
        print(result["df"].to_string(index=False))
    return 0


if __name__ == "__main__":
    import sys

    # 无命令行参数时，使用默认问题（可按需修改）
    default_question = "查询 600519 历史日期 前 30 %的pe 的年份  只看年报"
    if len(sys.argv) > 1:
        sys.exit(main())
    sys.exit(main([default_question]))

