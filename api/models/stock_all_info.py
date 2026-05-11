from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class StockAllInfo(Base):
    __tablename__ = "stock_all_info"
    __table_args__ = {
        "comment": "股票全量清单：用于存储 A 股股票代码与名称的全量映射，作为证券主数据入口表",
        "extend_existing": True,
    }

    code: Mapped[str] = mapped_column(
        String(20),
        primary_key=True,
        comment="股票代码（6 位数字，如 600519；来自 akshare stock_info_a_code_name 接口）",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="股票简称（中文简称，如 贵州茅台；与 code 一一对应）",
    )
