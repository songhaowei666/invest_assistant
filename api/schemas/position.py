from pydantic import BaseModel, ConfigDict, Field


class PositionItem(BaseModel):
    id: int
    code: str
    name: str
    price: float
    marketValue: float
    positionShares: int
    positionCost: float
    dividendYield: float
    totalDividend: float

    model_config = ConfigDict(from_attributes=True)


class PositionListResponse(BaseModel):
    items: list[PositionItem]


# 与 ORM Position 字段一致（蛇形命名），用于批量新增/修改请求体
class PositionDbRow(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    price: float
    market_value: float
    position_shares: int
    position_cost: float
    dividend_yield: float
    annual_dividend: float


class PositionDeleteRow(BaseModel):
    code: str = Field(min_length=1, max_length=20)


class StockNameSuggestItem(BaseModel):
    code: str
    name: str


class StockNameSuggestResponse(BaseModel):
    items: list[StockNameSuggestItem]


class PositionPriceDividendResponse(BaseModel):
    code: str
    price: float
    dividendYield: float
