#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Akshare 格雷厄姆防御型校验脚本（单只股票）
判断指定股票在指定日期（为空则当前日期）是否满足七条规则，并输出该股相关数据 JSON
"""

import json
import os
import re
import sys
from datetime import datetime

import akshare as ak
import pandas as pd


CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache")


def _ensure_cache_dir() -> None:
    """确保缓存目录存在。"""
    os.makedirs(CACHE_DIR, exist_ok=True)


def _read_df_cache(cache_path: str):
    """读取 DataFrame 本地缓存（xlsx）。"""
    if not os.path.exists(cache_path):
        return None
    try:
        return pd.read_excel(cache_path)
    except Exception:
        return None


def _write_df_cache(df, cache_path: str) -> None:
    """写入 DataFrame 本地缓存（xlsx）。"""
    try:
        df.to_excel(cache_path, index=False)
    except Exception:
        pass


def _cached_fetch_df(cache_name: str, fetch_func):
    """通用缓存获取：优先读本地 xlsx，未命中再请求并落盘。"""
    _ensure_cache_dir()
    cache_path = os.path.join(CACHE_DIR, cache_name)
    cached_df = _read_df_cache(cache_path)
    if cached_df is not None:
        return cached_df

    fresh_df = fetch_func()
    if fresh_df is not None and len(fresh_df) > 0:
        _write_df_cache(fresh_df, cache_path)
    return fresh_df


def _parse_query_date(argv_date: str | None) -> datetime:
    """解析查询日期，支持 YYYY-MM-DD 或 YYYYMMDD，为空时取当前日期。"""
    if not argv_date:
        return datetime.now()
    text = argv_date.strip()
    if re.fullmatch(r"\d{8}", text):
        return datetime.strptime(text, "%Y%m%d")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return datetime.strptime(text, "%Y-%m-%d")
    raise ValueError("日期格式错误，请使用 YYYY-MM-DD 或 YYYYMMDD")


def _to_suffix_code(code: str) -> str:
    """将 6 位代码转为带交易所后缀代码。"""
    if code.startswith(("600", "601", "603", "605", "688", "689", "900")):
        return f"{code}.SH"
    return f"{code}.SZ"


def _parse_stock_input(raw: str) -> tuple[str, str]:
    """
    解析用户输入的股票代码。
    返回 (六位数字 symbol, 带后缀 stock_code)。
    """
    text = raw.strip().upper()
    if "." in text:
        sym = text.split(".")[0].strip()
        suf = text.split(".")[1].strip()
        if suf not in ("SH", "SZ"):
            raise ValueError("后缀仅支持 .SH 或 .SZ")
        if not re.fullmatch(r"\d{6}", sym):
            raise ValueError("股票代码应为 6 位数字")
        return sym, f"{sym}.{suf}"
    if not re.fullmatch(r"\d{6}", text):
        raise ValueError("股票代码应为 6 位数字或 000001.SZ 形式")
    return text, _to_suffix_code(text)


def _to_xueqiu_symbol(stock_code: str) -> str:
    """600519.SH -> SH600519，供 stock_individual_spot_xq、资产负债表等接口使用。"""
    parts = stock_code.split(".")
    if len(parts) != 2:
        raise ValueError("内部错误：stock_code 格式")
    return f"{parts[1]}{parts[0]}"


def _safe_float(value) -> float | None:
    """安全转换浮点数。"""
    text = str(value).replace(",", "").strip()
    if text in ("", "--", "None", "nan", "NaN"):
        return None
    return float(text)


def _normalize_col(col_name: str) -> str:
    """标准化列名，便于模糊匹配。"""
    return str(col_name).replace(" ", "").replace("_", "").lower()


def _pick_col(columns, keywords: list[str]) -> str:
    """按关键字选择列名。"""
    for col in columns:
        norm = _normalize_col(col)
        for kw in keywords:
            if kw in str(col) or kw in norm:
                return col
    raise ValueError(f"未找到列: {keywords}")


def _annual_dates_by_limit(columns, max_year: int) -> list[str]:
    """提取不晚于 max_year 的年报列（YYYY1231）。"""
    result = []
    for col in columns:
        text = str(col).strip()
        if re.fullmatch(r"\d{8}", text) and text.endswith("1231"):
            year = int(text[:4])
            if year <= max_year:
                result.append(text)
    result.sort()
    return result


def _get_metric_row(df, metric_keywords: list[str]):
    """按指标关键字获取财务摘要中的指标行。"""
    if "指标" not in df.columns:
        raise ValueError("财务摘要缺少 指标 列")
    for kw in metric_keywords:
        matched = df[df["指标"].astype(str).str.contains(kw, na=False)]
        if len(matched) > 0:
            return matched.iloc[0]
    raise ValueError(f"未找到指标行: {metric_keywords}")


def _cached_balance_sheet_by_report(em_symbol: str):
    """东方财富资产负债表（按报告期），带本地 xlsx 缓存。"""
    return _cached_fetch_df(
        cache_name=f"balance_sheet_{em_symbol}.xlsx",
        fetch_func=lambda s=em_symbol: ak.stock_balance_sheet_by_report_em(symbol=s),
    )


def _pick_annual_balance_row(bs_df, year: int):
    """选取指定年份的 12-31 年报行（若有多条取公告日期较新的一条）。"""
    if bs_df is None or len(bs_df) == 0:
        return None
    work = bs_df.copy()
    work["_rd"] = pd.to_datetime(work["REPORT_DATE"], errors="coerce")
    work = work[(work["_rd"].dt.year == year) & (work["_rd"].dt.month == 12) & (work["_rd"].dt.day == 31)]
    if len(work) == 0:
        return None
    if "NOTICE_DATE" in work.columns:
        work["_nd"] = pd.to_datetime(work["NOTICE_DATE"], errors="coerce")
        work = work.sort_values("_nd", na_position="last")
    return work.iloc[-1]


def _long_debt_from_balance_row(row) -> tuple[float | None, str | None]:
    """
    从资产负债表行估算「长期负债」用于与净资产比较。
    优先：长期借款+长期应付款；若均为空则用非流动负债合计作为替代口径。
    """
    if row is None:
        return None, None
    ll = _safe_float(row.get("LONG_LOAN"))
    lp = _safe_float(row.get("LONG_PAYABLE"))
    if ll is not None or lp is not None:
        total = (ll or 0.0) + (lp or 0.0)
        return total, "资产负债表：长期借款+长期应付款（财务摘要无长期负债项时）"
    tnl = _safe_float(row.get("TOTAL_NONCURRENT_LIAB"))
    if tnl is not None:
        return tnl, "资产负债表：非流动负债合计（摘要无长期负债项时的替代口径）"
    return None, None


def _dividend_year_checks_cninfo(symbol: str, annual_dates: list[str]) -> tuple[list[dict], str]:
    """
    用巨潮分红数据按「年报年度」判断是否派现（派息比例>0）。
    返回 (逐年列表, 数据来源说明)。
    """
    df = _cached_fetch_df(
        cache_name=f"dividend_cninfo_{symbol}.xlsx",
        fetch_func=lambda: ak.stock_dividend_cninfo(symbol=symbol),
    )
    if df is None or len(df) == 0:
        return [], "巨潮分红接口无数据"

    rt = df["报告时间"].astype(str)
    ratio = df["派息比例"].apply(_safe_float)
    rows_out = []
    for d in annual_dates:
        y = int(str(d)[:4])
        mask = rt.str.contains(f"{y}年报", na=False)
        sub = df.loc[mask]
        if len(sub) == 0:
            passed = False
            payout = None
        else:
            payouts = [x for x in ratio.loc[sub.index].tolist() if x is not None]
            passed = any((x or 0) > 0 for x in payouts)
            payout = max(payouts) if payouts else None
        rows_out.append(
            {
                "report_date": d,
                "fiscal_year": y,
                "cash_payout_ratio_per_10_shares": payout,
                "passed": passed,
                "source": "巨潮 stock_dividend_cninfo（报告时间含该年年报且派息比例>0）",
            }
        )
    return rows_out, "巨潮分红接口"


def _spot_dict_from_xueqiu(stock_code: str) -> dict:
    """单只股票雪球快照，转为 item->value 字典。"""
    xq = _to_xueqiu_symbol(stock_code)
    df = _cached_fetch_df(
        cache_name=f"individual_spot_{xq}.xlsx",
        fetch_func=lambda s=xq: ak.stock_individual_spot_xq(symbol=s),
    )
    if df is None or len(df) == 0:
        return {}
    out = {}
    for _, row in df.iterrows():
        k = str(row.get("item", "")).strip()
        out[k] = row.get("value")
    return out


def _pick_period_for_valuation(query_date: datetime) -> str:
    """根据查询日期与当前日期差值选择估值数据周期。"""
    days = (datetime.now() - query_date).days
    if days <= 365:
        return "近一年"
    if days <= 365 * 3:
        return "近三年"
    if days <= 365 * 5:
        return "近五年"
    if days <= 365 * 10:
        return "近十年"
    return "全部"


def _pick_pe_pb_at_date(symbol: str, fallback_pe: float | None, fallback_pb: float | None, query_date: datetime):
    """优先取指定日期估值，取不到时使用快照回退。"""
    period = _pick_period_for_valuation(query_date=query_date)
    pe_df = _cached_fetch_df(
        cache_name=f"valuation_{symbol}_pe_ttm_{period}.xlsx",
        fetch_func=lambda: ak.stock_zh_valuation_baidu(symbol=symbol, indicator="市盈率(TTM)", period=period),
    )
    pb_df = _cached_fetch_df(
        cache_name=f"valuation_{symbol}_pb_{period}.xlsx",
        fetch_func=lambda: ak.stock_zh_valuation_baidu(symbol=symbol, indicator="市净率", period=period),
    )
    if pe_df is None or len(pe_df) == 0 or pb_df is None or len(pb_df) == 0:
        return fallback_pe, fallback_pb, "快照回退"

    pe_df = pe_df.copy()
    pb_df = pb_df.copy()
    pe_df["date"] = pe_df["date"].astype(str)
    pb_df["date"] = pb_df["date"].astype(str)
    target_date = query_date.strftime("%Y-%m-%d")

    pe_df = pe_df[pe_df["date"] <= target_date]
    pb_df = pb_df[pb_df["date"] <= target_date]
    if len(pe_df) == 0 or len(pb_df) == 0:
        return fallback_pe, fallback_pb, "快照回退"

    pe = _safe_float(pe_df.iloc[-1]["value"])
    pb = _safe_float(pb_df.iloc[-1]["value"])
    hist_date = str(pe_df.iloc[-1]["date"])
    return pe, pb, f"历史估值截至 {hist_date}"


def _evaluate_financial_rules(symbol: str, stock_code_full: str, max_year: int) -> dict:
    """
    评估规则 2～5：财务稳健、盈利稳定、持续分红、EPS 增长。
    返回结构化结果供 JSON 输出。
    """
    block = {
        "passed": False,
        "error": None,
        "annual_report_dates_used": [],
        "current_ratio": {},
        "long_debt_vs_net_asset": {},
        "ten_year_net_profit": [],
        "ten_year_dividend": [],
        "eps_growth": {},
    }

    df = _cached_fetch_df(
        cache_name=f"financial_abstract_{symbol}.xlsx",
        fetch_func=lambda: ak.stock_financial_abstract(symbol=symbol),
    )
    if df is None or len(df) == 0:
        block["error"] = "无法获取财务摘要"
        return block

    annual_dates = _annual_dates_by_limit(df.columns, max_year=max_year)
    if len(annual_dates) < 10:
        block["error"] = f"可用于统计的年报不足 10 年（当前 {len(annual_dates)} 期）"
        return block
    annual_dates = annual_dates[-10:]
    block["annual_report_dates_used"] = annual_dates

    try:
        current_ratio_row = _get_metric_row(df, ["流动比率"])
        net_asset_row = _get_metric_row(df, ["股东权益合计", "净资产", "归属于母公司股东权益"])
        net_profit_row = _get_metric_row(df, ["归属于母公司股东的净利润", "归母净利润", "净利润"])
        eps_row = _get_metric_row(df, ["基本每股收益", "每股收益", "eps"])
    except ValueError as e:
        block["error"] = str(e)
        return block

    dividend_row = None
    dividend_source = "财务摘要"
    try:
        dividend_row = _get_metric_row(df, ["每股派息", "现金分红", "分红", "派息", "股息"])
    except ValueError:
        dividend_source = "巨潮分红（摘要无派息行）"

    latest_date = annual_dates[-1]
    current_ratio = _safe_float(current_ratio_row[latest_date])
    net_asset = _safe_float(net_asset_row[latest_date])

    long_debt = None
    long_debt_source = None
    try:
        long_debt_row = _get_metric_row(df, ["长期借款", "长期负债", "非流动负债合计", "非流动负债"])
        long_debt = _safe_float(long_debt_row[latest_date])
        long_debt_source = "财务摘要"
    except ValueError:
        em_sym = _to_xueqiu_symbol(stock_code_full)
        bs_df = _cached_balance_sheet_by_report(em_sym)
        year = int(str(latest_date)[:4])
        bs_row = _pick_annual_balance_row(bs_df, year)
        long_debt, long_debt_source = _long_debt_from_balance_row(bs_row)
        if long_debt is None:
            block["error"] = "财务摘要无长期负债相关项，且资产负债表无法解析长期负债"
            return block

    block["current_ratio"] = {
        "passed": current_ratio is not None and current_ratio >= 2,
        "value": current_ratio,
        "report_date": latest_date,
        "rule": "流动比率>=2",
    }
    block["long_debt_vs_net_asset"] = {
        "passed": long_debt is not None
        and net_asset is not None
        and net_asset > 0
        and long_debt <= net_asset,
        "long_term_debt": long_debt,
        "long_term_debt_source": long_debt_source,
        "net_assets": net_asset,
        "report_date": latest_date,
        "rule": "长期负债不超过净资产",
    }

    profit_ok = True
    for d in annual_dates:
        npv = _safe_float(net_profit_row[d])
        ok = npv is not None and npv > 0
        profit_ok = profit_ok and ok
        block["ten_year_net_profit"].append(
            {"report_date": d, "net_profit": npv, "passed": ok}
        )

    div_ok = True
    if dividend_row is not None:
        for d in annual_dates:
            dv = _safe_float(dividend_row[d])
            ok = dv is not None and dv > 0
            div_ok = div_ok and ok
            block["ten_year_dividend"].append(
                {"report_date": d, "dividend_metric": dv, "passed": ok, "source": dividend_source}
            )
    else:
        block["ten_year_dividend"], src_note = _dividend_year_checks_cninfo(symbol, annual_dates)
        div_ok = all(x.get("passed") for x in block["ten_year_dividend"])
        block["dividend_data_source"] = src_note

    eps_start = _safe_float(eps_row[annual_dates[0]])
    eps_end = _safe_float(eps_row[annual_dates[-1]])
    ratio = (eps_end / eps_start) if eps_start and eps_start > 0 and eps_end is not None else None
    eps_ok = ratio is not None and ratio >= 1.2
    block["eps_growth"] = {
        "passed": eps_ok,
        "eps_first_year": eps_start,
        "eps_last_year": eps_end,
        "growth_multiple": round(ratio, 4) if ratio is not None else None,
        "rule": "近十年 EPS 增长不低于 20%（末/首>=1.2）",
        "first_report": annual_dates[0],
        "last_report": annual_dates[-1],
    }

    block["passed"] = (
        block["current_ratio"]["passed"]
        and block["long_debt_vs_net_asset"]["passed"]
        and profit_ok
        and div_ok
        and eps_ok
    )
    return block


def check_single_stock_graham(stock_code: str, query_date: datetime) -> dict:
    """对单只股票校验格雷厄姆防御型七条规则并输出相关数据。"""
    symbol, full_code = _parse_stock_input(stock_code)
    max_year = query_date.year

    spot_map = _spot_dict_from_xueqiu(full_code)
    stock_name = str(spot_map.get("名称", "") or "").strip() or None

    # 雪球字段：资产净值/总市值 在样本中为总市值数值（元）
    market_cap = _safe_float(spot_map.get("资产净值/总市值"))
    spot_pe = _safe_float(spot_map.get("市盈率(TTM)"))
    spot_pb = _safe_float(spot_map.get("市净率"))

    pe, pb, pe_pb_source = _pick_pe_pb_at_date(
        symbol=symbol,
        fallback_pe=spot_pe,
        fallback_pb=spot_pb,
        query_date=query_date,
    )
    pe_pb_product = (pe * pb) if pe is not None and pb is not None else None

    rule1 = {
        "id": 1,
        "name": "规模适中",
        "rule": "总市值不低于 100 亿元",
        "passed": market_cap is not None and market_cap >= 10_000_000_000,
        "market_cap_yuan": market_cap,
        "threshold_yuan": 10_000_000_000,
        "data_source": "雪球个股快照字段「资产净值/总市值」",
    }

    fin = _evaluate_financial_rules(symbol=symbol, stock_code_full=full_code, max_year=max_year)

    rule2_passed = (
        fin["current_ratio"].get("passed", False) and fin["long_debt_vs_net_asset"].get("passed", False)
    )
    rule2 = {
        "id": 2,
        "name": "财务稳健",
        "rule": "流动比率>=2；长期负债不超过净资产",
        "passed": rule2_passed,
        "current_ratio_detail": fin["current_ratio"],
        "long_debt_vs_net_asset_detail": fin["long_debt_vs_net_asset"],
    }
    rule3 = {
        "id": 3,
        "name": "盈利稳定",
        "rule": "过去 10 个年报每年净利润>0",
        "passed": all(x.get("passed") for x in fin["ten_year_net_profit"]) if fin["ten_year_net_profit"] else False,
        "by_year": fin["ten_year_net_profit"],
    }
    rule4 = {
        "id": 4,
        "name": "持续分红",
        "rule": "过去 10 个年报每年分红指标>0",
        "passed": all(x.get("passed") for x in fin["ten_year_dividend"]) if fin["ten_year_dividend"] else False,
        "by_year": fin["ten_year_dividend"],
    }
    rule5 = {
        "id": 5,
        "name": "利润增长（EPS）",
        "rule": "近十年 EPS 增长不低于 20%（末/首>=1.2）",
        "passed": fin["eps_growth"].get("passed", False),
        "detail": fin["eps_growth"],
    }

    rule6 = {
        "id": 6,
        "name": "估值合理",
        "rule": "市盈率 PE<=15",
        "passed": pe is not None and pe <= 15,
        "pe": pe,
        "pe_pb_source": pe_pb_source,
        "spot_pe_ttm": spot_pe,
    }
    rule7 = {
        "id": 7,
        "name": "估值安全",
        "rule": "市净率 PB<=1.5 且 PE×PB<=22.5",
        "passed": pb is not None
        and pe is not None
        and pe_pb_product is not None
        and pb <= 1.5
        and pe_pb_product <= 22.5,
        "pb": pb,
        "pe_times_pb": round(pe_pb_product, 4) if pe_pb_product is not None else None,
        "spot_pb": spot_pb,
    }

    checks = [rule1, rule2, rule3, rule4, rule5, rule6, rule7]
    meets_all = all(c["passed"] for c in checks)

    return {
        "stock_code": full_code,
        "stock_name": stock_name,
        "query_date": query_date.strftime("%Y-%m-%d"),
        "strategy": "格雷厄姆防御型投资者（单股校验）",
        "meets_all_criteria": meets_all,
        "criteria_checks": checks,
        "financial_block_passed": fin["passed"],
        "financial_error": fin.get("error"),
        "spot_snapshot_raw": spot_map,
    }


def main():
    try:
        if len(sys.argv) < 2:
            print(
                json.dumps(
                    {"error": "用法: python get_graham_defensive_count.py <股票代码> [日期]"},
                    ensure_ascii=False,
                    indent=2,
                )
            )
            sys.exit(1)
        stock_arg = sys.argv[1]
        date_text = sys.argv[2] if len(sys.argv) > 2 else None
        query_date = _parse_query_date(date_text)
        result = check_single_stock_graham(stock_arg, query_date)
    except Exception as e:
        result = {"error": f"执行失败: {str(e)}"}
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
