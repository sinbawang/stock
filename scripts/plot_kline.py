"""将 CSV K 线数据可视化为蜡烛图。"""

from __future__ import annotations

import argparse
from pathlib import Path

import mplfinance as mpf
import pandas as pd


def plot_kline(csv_path: str, output_path: str, title: str = "Kline") -> None:
    df = pd.read_csv(csv_path)
    required = {"ts", "open", "high", "low", "close"}
    if not required.issubset(set(df.columns)):
        raise ValueError(f"CSV 缺少必要列: {required}")

    df["ts"] = pd.to_datetime(df["ts"])
    df = df.sort_values("ts")
    df = df.set_index("ts")

    rename_map = {
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    }
    df = df.rename(columns=rename_map)

    if "Volume" not in df.columns:
        df["Volume"] = 0

    style = mpf.make_mpf_style(
        marketcolors=mpf.make_marketcolors(
            up="#e74c3c",
            down="#2ecc71",
            edge="inherit",
            wick="inherit",
            volume="inherit",
        ),
        gridstyle="--",
        facecolor="#f9fbfd",
        figcolor="#f9fbfd",
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    mpf.plot(
        df,
        type="candle",
        style=style,
        title=title,
        volume=True,
        mav=(5, 10, 20),
        tight_layout=True,
        savefig=dict(fname=output_path, dpi=160, bbox_inches="tight"),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CSV K 线图可视化")
    parser.add_argument("--input", default="data/03690_美团/day/3690_daily.csv", help="输入 CSV 路径")
    parser.add_argument("--output", default="data/03690_美团/day/3690_daily_kline.png", help="输出图片路径")
    parser.add_argument("--title", default="HK03690 Daily Kline", help="图标题")
    args = parser.parse_args()

    plot_kline(args.input, args.output, args.title)
    print(f"已生成 K 线图: {args.output}")
