#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单独更新格雷厄姆选股缓存数据（xlsx）
"""

import argparse
import json
import os
import re

import akshare as ak
import pandas as pd


BASE_DIR = os.path.dirname(__file__)
CACHE_DIR = os.path.join(BASE_DIR, "..", "cache")
# 行情只保留这一份文件名，不要求每次最新；本地已有则默认不重复拉取
SPOT_XLSX = "stock_zh_a_spot_em.xlsx"


def _ensure_cache_dir() -> None:
    """确保缓存目录存在。"""
    os.makedirs(CACHE_DIR, exist_ok=True)


def _to_symbol(code: str) -> str:
    """将 6 位代码转换为 akshare symbol。"""
    return code.strip().split(".")[0]


def _to_suffix_code(code: str) -> str:
    """将 6 位代码转为带后缀代码。"""
    if code.startswith(("600", "601", "603", "605", "688", "689", "900")):
        return f"{code}.SH"
    return f"{code}.SZ"


def _safe_float(value):
    """安全转换浮点数。"""
    text = str(value).replace(",", "").strip()
    if text in ("", "--", "None", "nan", "NaN"):
        return None
    return float(text)


def _pick_col(columns, keywords):
    """按关键字自动识别列。"""
    for col in columns:
        col_text = str(col)
        norm = col_text.replace(" ", "").replace("_", "").lower()
        for kw in keywords:
            if kw in col_text or kw in norm:
                return col
    raise ValueError(f"未找到列: {keywords}")


def _save_xlsx(df, filename: str) -> None:
    """将 DataFrame 保存为 xlsx。"""
    _ensure_cache_dir()
    path = os.path.join(CACHE_DIR, filename)
    df.to_excel(path, index=False)


def _spot_cache_path() -> str:
    """行情 xlsx 的绝对路径。"""
    return os.path.join(CACHE_DIR, SPOT_XLSX)


def load_or_update_spot_cache(force_refresh: bool = False):
    """
    行情只保存一份 xlsx。
    默认：本地已存在则直接读本地，不追求最新；仅当文件不存在或 force_refresh 时才请求网络。
    返回 (DataFrame, 说明字典)。
    """
    _ensure_cache_dir()
    path = _spot_cache_path()
    if not force_refresh and os.path.exists(path):
        df = pd.read_excel(path)
        if df is None or len(df) == 0:
            raise RuntimeError(f"本地行情文件为空或损坏: {path}")
        return df, {"spot": "使用本地已有文件", "path": path}

    df = ak.stock_zh_a_spot_em()
    if df is None or len(df) == 0:
        raise RuntimeError("获取 stock_zh_a_spot_em 失败")
    _save_xlsx(df, SPOT_XLSX)
    return df, {"spot": "已从网络拉取并覆盖保存", "path": path}


def _build_default_symbols(spot_df, limit: int):
    """
    根据策略的初筛条件构建默认股票池，避免一次更新全市场导致资源占用过大。
    """
    code_col = _pick_col(spot_df.columns, ["代码"])
    cap_col = _pick_col(spot_df.columns, ["总市值"])
    pe_col = _pick_col(spot_df.columns, ["市盈率"])
    pb_col = _pick_col(spot_df.columns, ["市净率"])

    symbols = []
    for _, row in spot_df.iterrows():
        code = str(row[code_col]).strip()
        if not re.fullmatch(r"\d{6}", code):
            continue
        cap = _safe_float(row[cap_col])
        pe = _safe_float(row[pe_col])
        pb = _safe_float(row[pb_col])
        if cap is None or pe is None or pb is None:
            continue
        if cap < 10000000000:
            continue
        if pe > 15:
            continue
        if pb > 1.5 or pe * pb > 22.5:
            continue
        symbols.append(_to_symbol(code))
        if len(symbols) >= limit:
            break
    return symbols


def update_financial_cache(symbols, skip_existing: bool = False):
    """更新财务摘要缓存。skip_existing 为 True 时已有 xlsx 则跳过，不追求最新。"""
    count = 0
    skipped = 0
    for symbol in symbols:
        fname = f"financial_abstract_{symbol}.xlsx"
        fpath = os.path.join(CACHE_DIR, fname)
        if skip_existing and os.path.exists(fpath):
            skipped += 1
            continue
        df = ak.stock_financial_abstract(symbol=symbol)
        if df is None or len(df) == 0:
            continue
        _save_xlsx(df, fname)
        count += 1
    return count, skipped


def update_valuation_cache(symbols, skip_existing: bool = False):
    """更新估值缓存。skip_existing 为 True 时该 symbol 下各 period 文件都已存在则整只跳过。"""
    periods = ["近一年", "近三年", "近五年", "近十年", "全部"]
    count = 0
    skipped_symbols = 0
    for symbol in symbols:
        if skip_existing:
            all_exist = True
            for period in periods:
                pe_name = f"valuation_{symbol}_pe_ttm_{period}.xlsx"
                pb_name = f"valuation_{symbol}_pb_{period}.xlsx"
                if not os.path.exists(os.path.join(CACHE_DIR, pe_name)) or not os.path.exists(
                    os.path.join(CACHE_DIR, pb_name)
                ):
                    all_exist = False
                    break
            if all_exist:
                skipped_symbols += 1
                continue
        for period in periods:
            pe_df = ak.stock_zh_valuation_baidu(symbol=symbol, indicator="市盈率(TTM)", period=period)
            pb_df = ak.stock_zh_valuation_baidu(symbol=symbol, indicator="市净率", period=period)
            if pe_df is not None and len(pe_df) > 0:
                _save_xlsx(pe_df, f"valuation_{symbol}_pe_ttm_{period}.xlsx")
            if pb_df is not None and len(pb_df) > 0:
                _save_xlsx(pb_df, f"valuation_{symbol}_pb_{period}.xlsx")
        count += 1
    return count, skipped_symbols


def main():
    parser = argparse.ArgumentParser(description="单独更新格雷厄姆选股缓存")
    parser.add_argument(
        "--mode",
        choices=["spot", "financial", "valuation", "all"],
        default="all",
        help="更新模式：spot/financial/valuation/all",
    )
    parser.add_argument(
        "--symbols",
        default="",
        help="指定股票代码，逗号分隔（可传 600519 或 600519.SH）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=80,
        help="未指定 --symbols 时，从初筛股票池最多选取多少只更新（默认 80）",
    )
    parser.add_argument(
        "--force-spot",
        action="store_true",
        help="强制重新拉取行情并覆盖本地唯一行情文件（默认有本地则不再请求）",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="财务/估值：本地已有对应 xlsx 则跳过，不重复拉取",
    )
    args = parser.parse_args()

    # 行情只存一份 xlsx；默认有本地则直接读，不追求最新；仅无文件或 --force-spot 时拉网
    need_spot = args.mode == "spot" or (
        args.mode in ("financial", "valuation", "all") and not args.symbols.strip()
    )
    if need_spot:
        spot_df, spot_meta = load_or_update_spot_cache(force_refresh=args.force_spot)
    else:
        spot_df, spot_meta = None, {"spot": "已指定 --symbols，未读取行情文件"}

    if args.mode == "spot":
        symbols = []
    elif args.symbols.strip():
        symbols = [_to_symbol(x) for x in args.symbols.split(",") if x.strip()]
    else:
        symbols = _build_default_symbols(spot_df, limit=args.limit)

    result = {
        "mode": args.mode,
        "cache_dir": os.path.abspath(CACHE_DIR),
        "spot_file": SPOT_XLSX,
        "spot_meta": spot_meta,
        "symbols_count": len(symbols),
        "symbols_preview": [_to_suffix_code(s) for s in symbols[:10]],
    }

    if args.mode in ("financial", "all"):
        updated, skipped = update_financial_cache(symbols, skip_existing=args.skip_existing)
        result["financial_updated_count"] = updated
        result["financial_skipped_existing"] = skipped
    if args.mode in ("valuation", "all"):
        updated, skipped = update_valuation_cache(symbols, skip_existing=args.skip_existing)
        result["valuation_updated_symbols"] = updated
        result["valuation_skipped_symbols_all_cached"] = skipped
    if args.mode == "spot":
        result["spot_done"] = True

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    load_or_update_spot_cache()
    # update_financial_cache(["600519"], skip_existing=True)
