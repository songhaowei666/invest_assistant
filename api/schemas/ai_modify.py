from pydantic import BaseModel, Field


class PositionChange(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    positionShares: int | None = None
    positionCost: float | None = None
    price: float | None = None
    totalDividend: float | None = None
    dividendYield: float | None = None
