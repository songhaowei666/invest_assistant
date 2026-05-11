from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class StockFinancialReport(Base):
    __tablename__ = "stock_financial_report"
    __table_args__ = {
        "comment": "股票财务数据（按报告期）：用于存储多期财报指标历史，字段单位见列备注",
        "extend_existing": True,
    }

    code: Mapped[str] = mapped_column(
        String(20), primary_key=True, comment="股票编码（6位数字代码，如 600519）"
    )
    report_period: Mapped[str] = mapped_column(
        String(16),
        primary_key=True,
        comment="报告期（YYYYMMDD，如 20241231 表示 2024 年年报）",
    )

    operating_revenue: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="营业收入（元，财报口径，优先营业总收入）"
    )
    gross_profit_margin: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="毛利率（主营业务毛利占营业收入的比例，单位：%，数值 35.6 表示 35.6%）",
    )
    net_profit: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="净利润（元，财报口径，优先归母净利润）"
    )
    roe: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="净资产收益率 ROE（%，数值 12.3 表示 12.3%）"
    )
    debt_to_asset_ratio: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="资产负债率（%，数值 55.2 表示 55.2%）"
    )

    eps: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="每股收益 EPS（元/股）"
    )
    bps: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="每股净资产 BPS（元/股）"
    )

