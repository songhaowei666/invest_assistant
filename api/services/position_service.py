from fastapi import HTTPException

from models.position import Position
from models.stock_all_info import StockAllInfo
from models.stock_basic_info import StockBasicInfo
from repositories.position_repo import PositionRepository
from schemas.position import (
    PositionDbRow,
    PositionDeleteRow,
    PositionItem,
    PositionListResponse,
    PositionPriceDividendResponse,
    StockNameSuggestItem,
    StockNameSuggestResponse,
)


class PositionService:
    def __init__(self) -> None:
        self.position_repo = PositionRepository()

    def list_positions(self, db) -> list[PositionItem]:
        positions = self.position_repo.list_positions(db)
        return [self._to_schema(item) for item in positions]

    def add(self, db, payload: list[PositionDbRow]) -> PositionListResponse:
        # 批量新增；code 唯一，本批或库中重复则拒绝
        seen: set[str] = set()
        for row in payload:
            if row.code in seen:
                raise HTTPException(status_code=422, detail=f"请求中股票代码 {row.code} 重复。")
            seen.add(row.code)
            if self.position_repo.get_by_code(db, row.code):
                raise HTTPException(status_code=409, detail=f"股票代码 {row.code} 已存在。")
            self.position_repo.add_one(
                db,
                Position(
                    code=row.code,
                    name=row.name,
                    price=row.price,
                    market_value=row.market_value,
                    position_shares=row.position_shares,
                    position_cost=row.position_cost,
                    dividend_yield=row.dividend_yield,
                    annual_dividend=row.annual_dividend,
                ),
            )
        db.commit()
        return PositionListResponse(items=self.list_positions(db))

    def delete(self, db, payload: list[PositionDeleteRow]) -> PositionListResponse:
        # 按 code 批量删除
        for item in payload:
            target = self.position_repo.get_by_code(db, item.code)
            if not target:
                raise HTTPException(status_code=404, detail=f"未找到股票代码 {item.code}。")
            db.delete(target)
        db.commit()
        return PositionListResponse(items=self.list_positions(db))

    def modify(self, db, payload: list[PositionDbRow]) -> PositionListResponse:
        # 按 code 全量更新除 id 外的业务字段
        for row in payload:
            target = self.position_repo.get_by_code(db, row.code)
            if not target:
                raise HTTPException(status_code=404, detail=f"未找到股票代码 {row.code}。")
            target.name = row.name
            target.price = row.price
            target.market_value = row.market_value
            target.position_shares = row.position_shares
            target.position_cost = row.position_cost
            target.dividend_yield = row.dividend_yield
            target.annual_dividend = row.annual_dividend
        db.commit()
        return PositionListResponse(items=self.list_positions(db))

    def stock_name_suggest(self, db, keyword: str, limit: int) -> StockNameSuggestResponse:
        pattern = f"%{keyword.strip()}%"
        rows = (
            db.query(StockAllInfo)
            .filter(StockAllInfo.name.like(pattern))
            .order_by(StockAllInfo.code.asc())
            .limit(limit)
            .all()
        )
        return StockNameSuggestResponse(
            items=[StockNameSuggestItem(code=row.code, name=row.name) for row in rows]
        )

    def get_price_dividend_by_code(self, db, code: str) -> PositionPriceDividendResponse:
        target = (
            db.query(StockBasicInfo)
            .filter(StockBasicInfo.code == code.strip())
            .first()
        )
        if not target:
            raise HTTPException(status_code=404, detail=f"未找到股票代码 {code}。")
        return PositionPriceDividendResponse(
            code=target.code,
            price=target.price,
            dividendYield=target.dividend_yield,
        )

    def _to_schema(self, position: Position) -> PositionItem:
        return PositionItem(
            id=position.id,
            code=position.code,
            name=position.name,
            price=position.price,
            marketValue=position.market_value,
            positionShares=position.position_shares,
            positionCost=position.position_cost,
            dividendYield=position.dividend_yield,
            totalDividend=position.annual_dividend,
        )
