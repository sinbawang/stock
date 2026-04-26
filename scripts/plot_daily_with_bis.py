"""绘制日K并叠加分型与笔连线。"""

from __future__ import annotations

import argparse
from pathlib import Path

import mplfinance as mpf
import numpy as np
import pandas as pd


def plot_daily_with_bis(
    kline_csv: str,
    fractals_csv: str,
    bis_csv: str,
    output_png: str,
    title: str,
) -> None:
    df = pd.read_csv(kline_csv)
    fx = pd.read_csv(fractals_csv)
    bis = pd.read_csv(bis_csv)

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
        if row["ts"] not in df.index:
            continue
        if row["fx_type"] == "top":
            top_mark.loc[row["ts"]] = float(row["price"])
        else:
            bot_mark.loc[row["ts"]] = float(row["price"])

    addplots = [
        mpf.make_addplot(top_mark, type="scatter", marker="v", markersize=80, color="#e74c3c"),
        mpf.make_addplot(bot_mark, type="scatter", marker="^", markersize=80, color="#2ecc71"),
    ]

    fx_map = {
        int(r.fx_id): (pd.to_datetime(r.ts), float(r.price))
        for r in fx.itertuples(index=False)
    }

    if not bis.empty:
        for r in bis.itertuples(index=False):
            s = fx_map.get(int(r.start_fx_id))
            e = fx_map.get(int(r.end_fx_id))
            if s is None or e is None:
                continue

            if s[0] not in df.index or e[0] not in df.index:
                continue

            s_idx = df.index.get_loc(s[0])
            e_idx = df.index.get_loc(e[0])
            if e_idx <= s_idx:
                continue

            values = np.full(len(df.index), np.nan)
            span = e_idx - s_idx
            for i in range(span + 1):
                t = i / span
                values[s_idx + i] = s[1] + (e[1] - s[1]) * t

            color = "#1f77b4" if r.direction == "up" else "#ff7f0e"
            width = 2.1 if bool(r.is_confirmed) else 1.2
            addplots.append(mpf.make_addplot(values, color=color, width=width))

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
        addplot=addplots,
        mav=(5, 10, 20),
        tight_layout=True,
        savefig=dict(fname=output_png, dpi=160, bbox_inches="tight"),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="日K叠加分型和笔")
    parser.add_argument("--kline", default="data/300124_汇川技术/day/300124_daily_20250930_to_20260412.csv")
    parser.add_argument("--fractals", default="data/300124_汇川技术/day/300124_daily_strict_fractals.csv")
    parser.add_argument("--bis", default="data/300124_汇川技术/day/300124_daily_strict_bis.csv")
    parser.add_argument("--output", default="data/300124_汇川技术/day/300124_daily_with_bis.png")
    parser.add_argument("--title", default="300124 Daily with Fractals and Bis")
    args = parser.parse_args()

    plot_daily_with_bis(args.kline, args.fractals, args.bis, args.output, args.title)
    print(f"已生成: {args.output}")
