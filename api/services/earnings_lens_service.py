import math
from collections import defaultdict

from models.stock_basic_info import StockBasicInfo
from models.stock_financial_report import StockFinancialReport
from repositories.position_repo import PositionRepository
from schemas.earnings_lens import (
    EarningsLensMcWeighted,
    EarningsLensReportPoint,
    EarningsLensResponse,
    EarningsLensRow,
    EarningsLensSnapshot,
    EarningsLensSummary,
)


class EarningsLensService:
    """透视盈余：复用持仓仓储，批量关联估值快照与年报。"""

    def __init__(self) -> None:
        self.position_repo = PositionRepository()

    @staticmethod
    def _safe_position_mv(p) -> float:
        """持仓市值缺失或非正、非有限时按 0 处理。"""
        if p.market_value is None:
            return 0.0
        try:
            v = float(p.market_value)
        except (TypeError, ValueError):
            return 0.0
        if not math.isfinite(v) or v < 0:
            return 0.0
        return v

    @staticmethod
    def _mv_weighted_avg(
        pairs: list[tuple[float, float | None]],
        *,
        value_ok,
    ) -> tuple[float | None, int]:
        """pairs 为 (持仓市值, 指标值)；仅在 value_ok(v) 为真时纳入，分母为纳入部分的市值和。"""
        use: list[tuple[float, float]] = []
        for mv, v in pairs:
            if v is None or not math.isfinite(float(v)):
                continue
            fv = float(v)
            if not value_ok(fv):
                continue
            if mv <= 0 or not math.isfinite(float(mv)):
                continue
            use.append((float(mv), fv))
        if not use:
            return None, 0
        denom = sum(m for m, _ in use)
        if denom <= 0:
            return None, 0
        return sum(m * val for m, val in use) / denom, len(use)

    def get_earnings_lens(self, db) -> EarningsLensResponse:
        positions = self.position_repo.list_positions(db)
        if not positions:
            return EarningsLensResponse(
                summary=EarningsLensSummary(positionCount=0, withBasicSnapshotCount=0),
                mcWeighted=EarningsLensMcWeighted(
                    totalMarketValue=0.0,
                    weightedPe=0.0,
                    weightedPb=0.0,
                    weightedRoe=0.0,
                    weightedDividendYield=0.0,
                    weightedGrossProfitMargin=0.0,
                    weightedDebtToAssetRatio=0.0,
                ),
                rows=[],
            )

        codes = [p.code for p in positions]
        basics = (
            db.query(StockBasicInfo).filter(StockBasicInfo.code.in_(codes)).all()
        )
        basic_by_code = {b.code: b for b in basics}

        reports = (
            db.query(StockFinancialReport)
            .filter(
                StockFinancialReport.code.in_(codes),
                StockFinancialReport.report_period.like("%1231"),
            )
            .order_by(
                StockFinancialReport.code.asc(),
                StockFinancialReport.report_period.desc(),
            )
            .all()
        )
        reports_by_code: dict[str, list[StockFinancialReport]] = defaultdict(list)
        for row in reports:
            if len(reports_by_code[row.code]) >= 4:
                continue
            reports_by_code[row.code].append(row)

        total_mv = sum(self._safe_position_mv(p) for p in positions)

        with_basic = 0
        out_rows: list[EarningsLensRow] = []
        for p in positions:
            b = basic_by_code.get(p.code)
            if b is not None:
                with_basic += 1
            snapshot = self._basic_to_snapshot(b) if b else None
            annual = [
                EarningsLensReportPoint(
                    reportPeriod=fr.report_period,
                    operatingRevenue=fr.operating_revenue,
                    grossProfitMargin=fr.gross_profit_margin,
                    netProfit=fr.net_profit,
                    roe=fr.roe,
                    debtToAssetRatio=fr.debt_to_asset_ratio,
                    eps=fr.eps,
                    bps=fr.bps,
                )
                for fr in reports_by_code.get(p.code, [])
            ]
            mv = self._safe_position_mv(p)
            mw = (mv / total_mv) if total_mv > 0 else 0.0
            out_rows.append(
                EarningsLensRow(
                    code=p.code,
                    name=p.name,
                    marketValue=mv,
                    marketWeight=mw,
                    snapshot=snapshot,
                    annualReports=annual,
                )
            )

        mv_snap_pairs: list[tuple[float, EarningsLensSnapshot | None]] = [
            (float(r.marketValue), r.snapshot) for r in out_rows
        ]

        def snap_pairs(getter):
            return [(mv, getter(s) if s else None) for mv, s in mv_snap_pairs]

        w_pe, c_pe = self._mv_weighted_avg(
            snap_pairs(lambda s: s.pe), value_ok=lambda v: v > 0
        )
        w_pb, c_pb = self._mv_weighted_avg(
            snap_pairs(lambda s: s.pb), value_ok=lambda v: v > 0
        )
        w_roe, c_roe = self._mv_weighted_avg(
            snap_pairs(lambda s: s.roe), value_ok=lambda _: True
        )
        w_dy, c_dy = self._mv_weighted_avg(
            snap_pairs(lambda s: s.dividendYield), value_ok=lambda v: v >= 0
        )
        w_gm, c_gm = self._mv_weighted_avg(
            snap_pairs(lambda s: s.grossProfitMargin), value_ok=lambda _: True
        )
        w_da, c_da = self._mv_weighted_avg(
            snap_pairs(lambda s: s.debtToAssetRatio), value_ok=lambda v: v >= 0
        )

        mc_weighted = EarningsLensMcWeighted(
            totalMarketValue=float(total_mv),
            weightedPe=w_pe if w_pe is not None else 0.0,
            weightedPb=w_pb if w_pb is not None else 0.0,
            weightedRoe=w_roe if w_roe is not None else 0.0,
            weightedDividendYield=w_dy if w_dy is not None else 0.0,
            weightedGrossProfitMargin=w_gm if w_gm is not None else 0.0,
            weightedDebtToAssetRatio=w_da if w_da is not None else 0.0,
            countForPe=c_pe,
            countForPb=c_pb,
            countForRoe=c_roe,
            countForDividendYield=c_dy,
            countForGrossProfitMargin=c_gm,
            countForDebtToAssetRatio=c_da,
        )

        return EarningsLensResponse(
            summary=EarningsLensSummary(
                positionCount=len(positions),
                withBasicSnapshotCount=with_basic,
            ),
            mcWeighted=mc_weighted,
            rows=out_rows,
        )

    @staticmethod
    def _basic_to_snapshot(b: StockBasicInfo) -> EarningsLensSnapshot:
        return EarningsLensSnapshot(
            pe=b.pe,
            pb=b.pb,
            price=b.price,
            roe=b.roe,
            grossProfitMargin=b.gross_profit_margin,
            operatingRevenue=b.operating_revenue,
            netProfit=b.net_profit,
            dividendYield=b.dividend_yield,
            eps=b.eps,
            bps=b.bps,
            debtToAssetRatio=b.debt_to_asset_ratio,
        )
