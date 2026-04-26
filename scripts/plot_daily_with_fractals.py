"""绘制日K并标记顶底分型。"""

from __future__ import annotations

import argparse
from pathlib import Path

import mplfinance as mpf
import pandas as pd


def plot_with_fractals(kline_csv: str, fractal_csv: str, output_png: str, title: str) -> None:
    df = pd.read_csv(kline_csv)
    fx = pd.read_csv(fractal_csv)

    df["ts"] = pd.to_datetime(df["ts"])
    df = df.sort_values("ts").set_index("ts")
    df = df.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
    )

    fx["ts"] = pd.to_datetime(fx["ts"])

    top_mark = pd.Series(index=df.index, dtype="float64")
    bot_mark = pd.Series(index=df.index, dtype="float64")

    for _, row in fx.iterrows():
        ts = row["ts"]
        if ts not in df.index:
            continue
        if row["fx_type"] == "top":
            top_mark.loc[ts] = float(row["price"])
        elif row["fx_type"] == "bottom":
            bot_mark.loc[ts] = float(row["price"])

    ap = [
        mpf.make_addplot(
            top_mark,
            type="scatter",
            marker="v",
            markersize=80,
            color="#e74c3c",
        ),
        mpf.make_addplot(
            bot_mark,
            type="scatter",
            marker="^",
            markersize=80,
            color="#2ecc71",
        ),
    ]

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

    Path(output_png).parent.mkdir(parents=True, exist_ok=True)
    mpf.plot(
        df,
        type="candle",
        style=style,
        title=title,
        volume=True,
        addplot=ap,
        mav=(5, 10, 20),
        tight_layout=True,
        savefig=dict(fname=output_png, dpi=160, bbox_inches="tight"),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="日K叠加分型标记")
    parser.add_argument("--kline", default="data/300124_汇川技术/day/300124_daily_20250930_to_20260412.csv")
    parser.add_argument("--fractals", default="data/300124_汇川技术/day/300124_daily_strict_fractals.csv")
    parser.add_argument("--output", default="data/300124_汇川技术/day/300124_daily_with_fractals.png")
    parser.add_argument("--title", default="300124 Daily Kline with Fractals")
    args = parser.parse_args()

    plot_with_fractals(args.kline, args.fractals, args.output, args.title)
    print(f"已生成: {args.output}")
