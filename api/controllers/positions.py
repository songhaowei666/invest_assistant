from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from db import get_db
from schemas.position import (
    PositionDbRow,
    PositionDeleteRow,
    PositionListResponse,
    PositionPriceDividendResponse,
    StockNameSuggestResponse,
)
from services.position_service import PositionService


router = APIRouter(prefix="/positions", tags=["positions"])


@router.get("", response_model=PositionListResponse)
def list_positions(db: Session = Depends(get_db)) -> PositionListResponse:
    service = PositionService()
    return PositionListResponse(items=service.list_positions(db))


# 批量新增：JSON 数组，元素字段与 ORM 一致（蛇形命名）
@router.post("/add", response_model=PositionListResponse)
def add_position(payload: list[PositionDbRow], db: Session = Depends(get_db)) -> PositionListResponse:
    service = PositionService()
    return service.add(db, payload)


# 批量删除：JSON 数组，每项为 {"code": "..."}
@router.post("/delete", response_model=PositionListResponse)
def delete_position(payload: list[PositionDeleteRow], db: Session = Depends(get_db)) -> PositionListResponse:
    service = PositionService()
    return service.delete(db, payload)


# 批量全量修改：JSON 数组，元素字段与新增相同
@router.post("/modify", response_model=PositionListResponse)
def modify_position(payload: list[PositionDbRow], db: Session = Depends(get_db)) -> PositionListResponse:
    service = PositionService()
    return service.modify(db, payload)


@router.get("/stock-name-suggest", response_model=StockNameSuggestResponse)
def stock_name_suggest(
    keyword: str = Query(..., min_length=1, description="股票名称关键词"),
    limit: int = Query(10, ge=1, le=100, description="返回条数上限"),
    db: Session = Depends(get_db),
) -> StockNameSuggestResponse:
    service = PositionService()
    return service.stock_name_suggest(db, keyword, limit)


@router.get("/price-dividend", response_model=PositionPriceDividendResponse)
def get_price_dividend(
    code: str = Query(..., min_length=1, max_length=20, description="股票代码"),
    db: Session = Depends(get_db),
) -> PositionPriceDividendResponse:
    service = PositionService()
    return service.get_price_dividend_by_code(db, code)
