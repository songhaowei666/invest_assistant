import sys
from pathlib import Path

# 直接执行本文件（python api/models/position.py）时，需将 api 目录加入 sys.path 才能 import models
_api_root = Path(__file__).resolve().parent.parent
if str(_api_root) not in sys.path:
    sys.path.insert(0, str(_api_root))

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Position(Base):
    __tablename__ = "positions"
    # 表/列备注由 api/scripts/create_pg_tables.py 在 PostgreSQL 上执行 COMMENT ON 写入
    # extend_existing：允许同一进程内重复执行本模块（如 python -m models.position）时不报表已存在
    __table_args__ = {
        "comment": "持仓表：标的代码、持仓数量、成本、市值及股息相关指标",
        "extend_existing": True,
    }

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, comment="主键，自增"
    )
    code: Mapped[str] = mapped_column(
        String(20), unique=True, index=True, comment="股票代码，唯一"
    )
    name: Mapped[str] = mapped_column(String(100), comment="名称")
    price: Mapped[float] = mapped_column(Float, comment="当前价格")
    market_value: Mapped[float] = mapped_column(Float, comment="市值")
    position_shares: Mapped[int] = mapped_column(Integer, comment="持股数量")
    position_cost: Mapped[float] = mapped_column(Float, comment="持仓成本")
    dividend_yield: Mapped[float] = mapped_column(Float, comment="股息率")
    annual_dividend: Mapped[float] = mapped_column(Float, comment="年分红")


def _position_table_metadata_text() -> str:
    # 从 SQLAlchemy Table 元数据拼出表结构描述（供打印或作为模型上下文）
    t = Position.__table__
    lines: list[str] = []
    qname = f'"{t.schema}"."{t.name}"' if t.schema else f'"{t.name}"'
    lines.append(f"表: {qname}")
    if t.comment:
        lines.append(f"表说明: {t.comment}")
    lines.append("列:")
    for col in t.columns:
        parts: list[str] = [str(col.type)]
        if col.primary_key:
            parts.append("主键")
            if col.autoincrement:
                parts.append("自增")
        if col.nullable is False:
            parts.append("NOT NULL")
        if col.unique:
            parts.append("唯一")
        if getattr(col, "index", False):
            parts.append("索引")
        col_desc = f"  - {col.name}: {', '.join(parts)}"
        if col.comment:
            col_desc += f" | {col.comment}"
        lines.append(col_desc)
    return "\n".join(lines)


if __name__ == "__main__":
    print(_position_table_metadata_text())
