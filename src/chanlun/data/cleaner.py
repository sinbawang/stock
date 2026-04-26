"""
数据清洗模块。

处理数据质量问题、缺失值、异常值等。
"""

from typing import List
import pandas as pd
from ..models import Bar


def clean_bars(bars: List[Bar]) -> List[Bar]:
    """
    清洗 K 线数据。
    
    步骤：
    1. 按时间排序
    2. 去除重复时间戳
    3. 去除无效 K 线（high < low）
    4. 去除缺失值
    
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

    # 去除无效 K 线
    valid = []
    for bar in deduped:
        if not (bar.high < bar.low or bar.high < 0 or bar.low < 0):
            valid.append(bar)

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
