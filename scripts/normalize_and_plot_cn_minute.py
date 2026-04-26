"""标准化中文券商分钟线 CSV，并生成 K 线图。

适用来源：同花顺、平安证券等导出的分钟线 CSV。
输出标准列：ts, open, high, low, close, volume
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from plot_kline import plot_kline


COLUMN_ALIASES = {
    "ts": ["ts", "datetime", "time", "trade_time", "日期", "时间", "日期时间", "成交时间"],
    "open": ["open", "o", "开盘", "开盘价"],
    "high": ["high", "h", "最高", "最高价"],
    "low": ["low", "l", "最低", "最低价"],
    "close": ["close", "c", "收盘", "收盘价", "现价", "最新价"],
    "volume": ["volume", "vol", "成交量", "总手", "成交股数", "量"],
}


def _normalize_col_name(name: str) -> str:
    return str(name).strip().lower().replace(" ", "")


def _find_column(df: pd.DataFrame, target: str) -> str | None:
    normalized_map = {_normalize_col_name(c): c for c in df.columns}
    for alias in COLUMN_ALIASES[target]:
        key = _normalize_col_name(alias)
        if key in normalized_map:
            return normalized_map[key]
    return None


def normalize_csv(input_csv: str, output_csv: str) -> pd.DataFrame:
    df = pd.read_csv(input_csv)

    ts_col = _find_column(df, "ts")
    open_col = _find_column(df, "open")
    high_col = _find_column(df, "high")
    low_col = _find_column(df, "low")
    close_col = _find_column(df, "close")
    volume_col = _find_column(df, "volume")

    missing = []
    if ts_col is None:
        missing.append("时间列")
    if open_col is None:
        missing.append("开盘列")
    if high_col is None:
        missing.append("最高列")
    if low_col is None:
        missing.append("最低列")
    if close_col is None:
        missing.append("收盘列")
    if missing:
        raise ValueError("输入 CSV 缺少必要字段: " + ", ".join(missing))

    out = pd.DataFrame(
        {
            "ts": pd.to_datetime(df[ts_col], errors="coerce"),
            "open": pd.to_numeric(df[open_col], errors="coerce"),
            "high": pd.to_numeric(df[high_col], errors="coerce"),
            "low": pd.to_numeric(df[low_col], errors="coerce"),
            "close": pd.to_numeric(df[close_col], errors="coerce"),
            "volume": pd.to_numeric(df[volume_col], errors="coerce") if volume_col else 0,
        }
    )

    out = out.dropna(subset=["ts", "open", "high", "low", "close"])
    out = out.sort_values("ts").drop_duplicates(subset=["ts"], keep="last")
    out["volume"] = out["volume"].fillna(0).astype("int64")

    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_csv, index=False)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="标准化中文分钟线 CSV 并绘制 K 线图")
    parser.add_argument("--input", required=True, help="输入 CSV 路径（同花顺/平安导出）")
    parser.add_argument("--output-csv", default="data/03690_美团/60m/3690_60m_real.csv", help="标准化输出 CSV")
    parser.add_argument("--output-png", default="data/03690_美团/60m/3690_60m_real.png", help="输出 K 线图")
    parser.add_argument("--title", default="03690 60m Kline (Real)", help="图表标题")
    args = parser.parse_args()

    out = normalize_csv(args.input, args.output_csv)
    print(f"标准化完成: {len(out)} 根, 已保存 {args.output_csv}")

    plot_kline(args.output_csv, args.output_png, args.title)
    print(f"图像已生成: {args.output_png}")


if __name__ == "__main__":
    main()
