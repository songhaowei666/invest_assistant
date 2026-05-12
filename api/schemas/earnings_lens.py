from pydantic import BaseModel, ConfigDict


class EarningsLensSnapshot(BaseModel):
    """来自 stock_basic_info 的最新快照（与持仓 code 对齐）。"""

    model_config = ConfigDict(from_attributes=True)

    pe: float | None = None
    pb: float | None = None
    price: float | None = None
    roe: float | None = None
    grossProfitMargin: float | None = None
    operatingRevenue: float | None = None
    netProfit: float | None = None
    dividendYield: float | None = None
    eps: float | None = None
    bps: float | None = None
    debtToAssetRatio: float | None = None


class EarningsLensReportPoint(BaseModel):
    """单期年报指标（报告期以 1231 结尾）。"""

    model_config = ConfigDict(from_attributes=True)

    reportPeriod: str
    operatingRevenue: float | None = None
    grossProfitMargin: float | None = None
    netProfit: float | None = None
    roe: float | None = None
    debtToAssetRatio: float | None = None
    eps: float | None = None
    bps: float | None = None


class EarningsLensRow(BaseModel):
    """单只持仓的透视盈余行。"""

    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    marketValue: float
    marketWeight: float = 0.0
    snapshot: EarningsLensSnapshot | None = None
    annualReports: list[EarningsLensReportPoint] = []


class EarningsLensSummary(BaseModel):
    """组合级轻量汇总。"""

    model_config = ConfigDict(from_attributes=True)

    positionCount: int
    withBasicSnapshotCount: int


class EarningsLensMcWeighted(BaseModel):
    """按持仓市值加权（各指标仅在有效样本内用对应子集市值作分母，与同花顺 F12 类组合透视思路一致）。"""

    model_config = ConfigDict(from_attributes=True)

    totalMarketValue: float
    weightedPe: float = 0.0
    weightedPb: float = 0.0
    weightedRoe: float = 0.0
    weightedDividendYield: float = 0.0
    weightedGrossProfitMargin: float = 0.0
    weightedDebtToAssetRatio: float = 0.0
    countForPe: int = 0
    countForPb: int = 0
    countForRoe: int = 0
    countForDividendYield: int = 0
    countForGrossProfitMargin: int = 0
    countForDebtToAssetRatio: int = 0


class EarningsLensResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    summary: EarningsLensSummary
    mcWeighted: EarningsLensMcWeighted
    rows: list[EarningsLensRow]
