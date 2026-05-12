from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db import get_db
from schemas.earnings_lens import EarningsLensResponse
from services.earnings_lens_service import EarningsLensService


router = APIRouter(prefix="/earnings-lens", tags=["earnings-lens"])


@router.get("", response_model=EarningsLensResponse)
def get_earnings_lens(db: Session = Depends(get_db)) -> EarningsLensResponse:
    """透视盈余：当前持仓与估值快照、近四年年报（报告期 1231）。"""
    service = EarningsLensService()
    return service.get_earnings_lens(db)
