"""数据读取模块。"""

from __future__ import annotations

from typing import List, Optional
from pathlib import Path

try:
    import pandas as pd
except ModuleNotFoundError:  # pragma: no cover - optional dependency in current env
    pd = None

from ..models import Bar
from .kline_fetcher import fetch_kline, save_to_csv


def read_bars_from_csv(
    filepath: str,
    ts_column: str = "ts",
    open_column: str = "open",
    high_column: str = "high",
    low_column: str = "low",
    close_column: str = "close",
    volume_column: Optional[str] = "volume"
) -> List[Bar]:
    """
    从 CSV 文件读取 K 线数据。
    
    Args:
        filepath: CSV 文件路径
        ts_column: 时间戳列名
        open_column: 开盘价列名
        high_column: 最高价列名
        low_column: 最低价列名
        close_column: 收盘价列名
        volume_column: 成交量列名（可选）
    
    Returns:
        Bar 对象列表
    """
    if pd is None:
        raise ModuleNotFoundError("read_bars_from_csv requires pandas")

    df = pd.read_csv(filepath)

    # 标准化列名
    df.columns = df.columns.str.lower()

    # 时间戳转换
    df[ts_column] = pd.to_datetime(df[ts_column])

    bars = []
    for _, row in df.iterrows():
        bar = Bar(
            ts=row[ts_column],
            open=float(row[open_column]),
            high=float(row[high_column]),
            low=float(row[low_column]),
            close=float(row[close_column]),
            volume=int(row[volume_column]) if volume_column and volume_column in df.columns else 0
        )
        bars.append(bar)

    return bars


def read_bars_from_dataframe(df: pd.DataFrame) -> List[Bar]:
    """
    从 pandas DataFrame 读取 K 线数据。
    
    期望的 DataFrame 列：ts, open, high, low, close, volume (可选)
    """
    if pd is None:
        raise ModuleNotFoundError("read_bars_from_dataframe requires pandas")

    bars = []
    for _, row in df.iterrows():
        bar = Bar(
            ts=row["ts"],
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=int(row.get("volume", 0))
        )
        bars.append(bar)
    return bars
