"""
数据清洗模块。

处理数据质量问题、缺失值、异常值等。
"""

from dataclasses import replace
from typing import List

import pandas as pd

from ..models import Bar
from .quote_repair import repair_ohlc_values


def clean_bars(bars: List[Bar]) -> List[Bar]:
    """
    清洗 K 线数据。
    
    步骤：
    1. 按时间排序
    2. 去除重复时间戳
    3. 去除无效 K 线（high < low）
    4. 修复非正价格（如港股占位 bar 的 open=0.0），无法修复则丢弃
    
    Args:
        bars: 原始 K 线列表
    
    Returns:
        清洗后的 K 线列表
    """
    if not bars:
        return []

    # 按时间排序
    bars = sorted(bars, key=lambda b: b.ts)

    # 去除重复时间戳（保留第一个）
    seen_ts = set()
    deduped = []
    for bar in bars:
        if bar.ts not in seen_ts:
            deduped.append(bar)
            seen_ts.add(bar.ts)

    # 去除无效 K 线，并修复非正价格（典型：open=0 的零成交占位 bar）
    valid = []
    last_valid_close = None
    for bar in deduped:
        if bar.high < bar.low or bar.high < 0 or bar.low < 0:
            continue

        if bar.open > 0 and bar.high > 0 and bar.low > 0 and bar.close > 0:
            valid.append(bar)
            last_valid_close = bar.close
            continue

        open_, high, low, close, _ = repair_ohlc_values(
            bar.open,
            bar.high,
            bar.low,
            bar.close,
            prev_close=last_valid_close,
        )
        if open_ <= 0 or high <= 0 or low <= 0 or close <= 0:
            # 全部价格都无法恢复，视为不可用数据
            continue

        repaired = replace(bar, open=open_, high=high, low=low, close=close)
        valid.append(repaired)
        last_valid_close = close

    return valid


def bars_to_dataframe(bars: List[Bar]) -> pd.DataFrame:
    """将 Bar 列表转换为 DataFrame"""
    data = {
        "ts": [b.ts for b in bars],
        "open": [b.open for b in bars],
        "high": [b.high for b in bars],
        "low": [b.low for b in bars],
        "close": [b.close for b in bars],
        "volume": [b.volume for b in bars]
    }
    return pd.DataFrame(data)
