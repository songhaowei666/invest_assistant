from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import akshare as ak
import pandas as pd

# 兼容直接执行: python api/core/akshare/update_stock_tables.py
API_DIR = Path(__file__).resolve().parents[2]
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from sqlalchemy import select
from sqlalchemy.orm import Session

from db import SessionLocal
from models.position import Position
from models.stock_basic_info import StockBasicInfo
from models.stock_financial_report import StockFinancialReport


def _normalize_stock_code(code: str) -> str:
    text = code.strip().upper()
    if "." in text:
        text = text.split(".", 1)[0]
    digits = re.sub(r"\D", "", text)
    if not re.fullmatch(r"\d{6}", digits):
        raise ValueError(f"股票代码格式错误: {code}")
    return digits


def _to_xq_symbol(code: str) -> str:
    if code.startswith(("600", "601", "603", "605", "688", "689", "900")):
        return f"SH{code}"
    if code.startswith(("430", "440", "830", "831", "832", "833", "834", "835", "836", "837", "838", "839", "870", "871", "872", "873", "874", "875", "876", "877", "878", "879")):
        return f"BJ{code}"
    return f"SZ{code}"


def _safe_float(value) -> float | None:
    text = str(value).replace(",", "").replace("%", "").strip()
    if text in ("", "--", "None", "nan", "NaN"):
        return None
    return float(text)


def _spot_item_dict(spot_df: pd.DataFrame) -> dict[str, object]:
    result: dict[str, object] = {}
    for _, row in spot_df.iterrows():
        key = str(row.get("item", "")).strip()
        result[key] = row.get("value")
    return result


def _pick_metric_row(fin_df: pd.DataFrame, metric_keywords: list[str]) -> pd.Series | None:
    if "指标" not in fin_df.columns:
        return None
    metric_col = fin_df["指标"].astype(str)
    for keyword in metric_keywords:
        matched = fin_df[metric_col.str.contains(keyword, na=False)]
        if not matched.empty:
            return matched.iloc[0]
    return None


def update_stock_basic_info(code: str) -> StockBasicInfo:
    normalized_code = _normalize_stock_code(code)
    xq_symbol = _to_xq_symbol(normalized_code)
    spot_df = ak.stock_individual_spot_xq(symbol=xq_symbol)
    if spot_df is None or spot_df.empty:
        raise RuntimeError(f"未获取到雪球个股快照数据: {xq_symbol}")

    spot = _spot_item_dict(spot_df)
    with SessionLocal() as db:
        row = db.get(StockBasicInfo, normalized_code)
        if row is None:
            row = StockBasicInfo(code=normalized_code)
            db.add(row)

        row.price = _safe_float(spot.get("现价"))
        row.pe = _safe_float(spot.get("市盈率(TTM)"))
        row.pb = _safe_float(spot.get("市净率"))
        row.dividend_yield = _safe_float(spot.get("股息率(TTM)"))
        row.eps = _safe_float(spot.get("每股收益"))
        row.bps = _safe_float(spot.get("每股净资产"))

        db.commit()
        db.refresh(row)
        return row


def list_position_stock_codes(db: Session | None = None) -> list[str]:
    """从持仓表读取不重复的股票代码（6 位）。"""
    stmt = select(Position.code).order_by(Position.code.asc())

    def _collect(session: Session) -> list[str]:
        raw_codes = list(session.scalars(stmt).all())
        seen: set[str] = set()
        result: list[str] = []
        for code in raw_codes:
            normalized = _normalize_stock_code(code)
            if normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result

    if db is not None:
        return _collect(db)
    with SessionLocal() as session:
        return _collect(session)


def update_position_stocks_basic_info() -> str:
    """按持仓股票代码批量更新 StockBasicInfo 基础快照。"""
    codes = list_position_stock_codes()
    if not codes:
        return "skip: 持仓表无股票代码"

    ok: list[str] = []
    failed: list[tuple[str, str]] = []
    for code in codes:
        try:
            update_stock_basic_info(code)
            ok.append(code)
        except Exception as exc:
            failed.append((code, repr(exc)))

    lines = [f"total={len(codes)} success={len(ok)} failed={len(failed)}"]
    if ok:
        lines.append("ok: " + ",".join(ok))
    for code, err in failed:
        lines.append(f"fail {code}: {err}")
    return "\n".join(lines)


def update_stock_financial_report(code: str) -> int:
    normalized_code = _normalize_stock_code(code)
    fin_df = ak.stock_financial_abstract(symbol=normalized_code)
    if fin_df is None or fin_df.empty:
        raise RuntimeError(f"未获取到财务摘要数据: {normalized_code}")

    report_periods = [
        col for col in fin_df.columns if isinstance(col, str) and re.fullmatch(r"\d{8}", col)
    ]
    report_periods.sort()
    if not report_periods:
        raise RuntimeError("财务摘要中未找到报告期列")

    revenue_row = _pick_metric_row(fin_df, ["营业总收入", "营业收入"])
    gross_profit_margin_row = _pick_metric_row(fin_df, ["毛利率"])
    net_profit_row = _pick_metric_row(fin_df, ["归属于母公司股东的净利润", "归母净利润", "净利润"])
    roe_row = _pick_metric_row(fin_df, ["净资产收益率", "ROE"])
    debt_ratio_row = _pick_metric_row(fin_df, ["资产负债率"])
    eps_row = _pick_metric_row(fin_df, ["基本每股收益", "每股收益"])
    bps_row = _pick_metric_row(fin_df, ["每股净资产"])

    updated_count = 0
    with SessionLocal() as db:
        for period in report_periods:
            pk = {"code": normalized_code, "report_period": period}
            row = db.get(StockFinancialReport, pk)
            if row is None:
                row = StockFinancialReport(code=normalized_code, report_period=period)
                db.add(row)

            row.operating_revenue = _safe_float(revenue_row[period]) if revenue_row is not None else None
            row.gross_profit_margin = (
                _safe_float(gross_profit_margin_row[period])
                if gross_profit_margin_row is not None
                else None
            )
            row.net_profit = _safe_float(net_profit_row[period]) if net_profit_row is not None else None
            row.roe = _safe_float(roe_row[period]) if roe_row is not None else None
            row.debt_to_asset_ratio = _safe_float(debt_ratio_row[period]) if debt_ratio_row is not None else None
            row.eps = _safe_float(eps_row[period]) if eps_row is not None else None
            row.bps = _safe_float(bps_row[period]) if bps_row is not None else None
            updated_count += 1

        db.commit()
    return updated_count


def sync_latest_financial_report_to_basic_info(code: str) -> StockBasicInfo:
    normalized_code = _normalize_stock_code(code)
    with SessionLocal() as db:
        latest_report = (
            db.query(StockFinancialReport)
            .filter(StockFinancialReport.code == normalized_code)
            .order_by(StockFinancialReport.report_period.desc())
            .first()
        )
        if latest_report is None:
            raise RuntimeError(f"未找到财务报告数据，无法同步: {normalized_code}")

        basic_row = db.get(StockBasicInfo, normalized_code)
        if basic_row is None:
            basic_row = StockBasicInfo(code=normalized_code)
            db.add(basic_row)

        basic_row.roe = latest_report.roe
        basic_row.gross_profit_margin = latest_report.gross_profit_margin
        basic_row.net_profit = latest_report.net_profit
        basic_row.operating_revenue = latest_report.operating_revenue
        basic_row.debt_to_asset_ratio = latest_report.debt_to_asset_ratio

        db.commit()
        db.refresh(basic_row)
        return basic_row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="更新股票基础信息和财务报告数据")
    parser.add_argument("code", help="股票代码，例如 600519 或 600519.SH")
    parser.add_argument(
        "--target",
        choices=("basic", "financial", "sync", "both"),
        default="both",
        help="指定更新目标，默认 both",
    )
    args = parser.parse_args(argv)

    if args.target in ("basic", "both"):
        basic_row = update_stock_basic_info(args.code)
        print(f"已更新 StockBasicInfo: code={basic_row.code}")

    if args.target in ("financial", "both"):
        count = update_stock_financial_report(args.code)
        print(f"已更新 StockFinancialReport: code={_normalize_stock_code(args.code)}, rows={count}")

    if args.target in ("sync", "both"):
        basic_row = sync_latest_financial_report_to_basic_info(args.code)
        print(f"已同步财务最新报告期到 StockBasicInfo: code={basic_row.code}")

    return 0


if __name__ == "__main__":
    # update_stock_basic_info("600519")
    update_stock_financial_report("600519")
    sync_latest_financial_report_to_basic_info("600519")