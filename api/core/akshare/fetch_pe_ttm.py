"""
使用 akshare.stock_zh_valuation_baidu 拉取 A 股近十年市盈率(TTM)，写入本包目录下 data/ CSV（api/core/akshare/data/）。

接口说明见 docs/akshare_api.md。
用法（在 api 目录下，保证已安装 akshare）:
  python -m core.akshare.fetch_pe_ttm 600519
  python -m core.akshare.fetch_pe_ttm 002044 600036
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import akshare as ak
import pandas as pd

# 与文档 stock_zh_valuation_baidu 一致
_INDICATOR = "市盈率(TTM)"
_PERIOD = "近十年"


def _data_dir() -> Path:
    # 与 fetch_pe_ttm.py 同级的 data/，即 api/core/akshare/data/
    return Path(__file__).resolve().parent / "data"


def _normalize_symbol(raw: str) -> str:
    """统一为 6 位 A 股数字代码（去掉 SH/SZ 等后缀）。"""
    s = raw.strip().upper()
    if "." in s:
        s = s.split(".", 1)[0]
    digits = re.sub(r"\D", "", s)
    if not digits:
        raise ValueError(f"无效股票代码: {raw!r}")
    if len(digits) > 6:
        raise ValueError(f"股票代码过长: {raw!r}")
    return digits.zfill(6)


def fetch_pe_ttm_history(symbol: str) -> pd.DataFrame:
    """返回 date、value 列的 DataFrame。"""
    code = _normalize_symbol(symbol)
    df = ak.stock_zh_valuation_baidu(symbol=code, indicator=_INDICATOR, period=_PERIOD)
    if df is None or df.empty:
        raise RuntimeError(f"未取到数据: {code}")
    return df


def save_to_csv(symbol: str, df: pd.DataFrame, data_dir: Path | None = None) -> Path:
    """写入 {代码}_市盈率TTM_近十年.csv。"""
    root = data_dir if data_dir is not None else _data_dir()
    root.mkdir(parents=True, exist_ok=True)
    code = _normalize_symbol(symbol)
    path = root / f"{code}_市盈率TTM_近十年.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="拉取指定 A 股近十年市盈率(TTM) 并保存到 core/akshare/data/ CSV")
    parser.add_argument(
        "symbols",
        nargs="+",
        help="股票代码，如 600519、002044 或 600519.SH",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="覆盖默认输出目录（默认: api/core/akshare/data/）",
    )
    args = parser.parse_args(argv)

    out_root = Path(args.data_dir).resolve() if args.data_dir else _data_dir()

    for raw in args.symbols:
        df = fetch_pe_ttm_history(raw)
        path = save_to_csv(raw, df, data_dir=out_root)
        print(path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
