"""通过 Longbridge OpenAPI 获取美团 03690 60 分钟 K 线并可视化。

前置条件（环境变量）:
- LONGPORT_APP_KEY
- LONGPORT_APP_SECRET
- LONGPORT_ACCESS_TOKEN

示例:
    c:\sinba\stock\venv\scripts\python scripts\fetch_3690_60m_longbridge.py
"""

from __future__ import annotations

import argparse
import csv
import os
from datetime import date, datetime
from pathlib import Path

import mplfinance as mpf
import pandas as pd
from longport.openapi import AdjustType, Config, Period, QuoteContext


def _check_env() -> None:
    required = [
        "LONGPORT_APP_KEY",
        "LONGPORT_APP_SECRET",
        "LONGPORT_ACCESS_TOKEN",
    ]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        missing_text = ", ".join(missing)
        raise RuntimeError(
            "缺少长桥环境变量: "
            + missing_text
            + "。请先在开发者中心申请凭证并设置环境变量。"
        )


def fetch_60m(symbol: str, start: date, end: date) -> list[dict]:
    _check_env()

    config = Config.from_env()
    ctx = QuoteContext(config)

    candles = ctx.history_candlesticks_by_date(
        symbol,
        Period.Min_60,
        AdjustType.ForwardAdjust,
        start,
        end,
    )

    rows = []
    for c in candles:
        rows.append(
            {
                "ts": c.timestamp.strftime("%Y-%m-%d %H:%M"),
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "volume": int(c.volume),
            }
        )

    rows.sort(key=lambda x: x["ts"])
    return rows


def save_csv(rows: list[dict], output_csv: str) -> None:
    if not rows:
        raise RuntimeError("未获取到数据，请确认账号权限与时间范围")

    path = Path(output_csv)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["ts", "open", "high", "low", "close", "volume"]
        )
        writer.writeheader()
        writer.writerows(rows)


def plot_kline(csv_path: str, output_png: str, title: str) -> None:
    df = pd.read_csv(csv_path)
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
    df = df[["Open", "High", "Low", "Close", "Volume"]].astype(float)

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
        mav=(5, 10, 20),
        tight_layout=True,
        savefig=dict(fname=output_png, dpi=160, bbox_inches="tight"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Longbridge 获取 03690 60 分钟 K 线")
    parser.add_argument("--symbol", default="3690.HK", help="标的代码，默认 3690.HK")
    parser.add_argument("--start", default="2026-01-05", help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end", default=date.today().strftime("%Y-%m-%d"), help="结束日期 YYYY-MM-DD")
    parser.add_argument("--output-csv", default="data/03690_美团/60m/3690_60m_longbridge.csv", help="输出 CSV")
    parser.add_argument("--output-png", default="data/03690_美团/60m/3690_60m_longbridge.png", help="输出图像")
    args = parser.parse_args()

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date()

    print(f"正在获取 {args.symbol} 60 分钟 K 线: {args.start} ~ {args.end}")
    rows = fetch_60m(args.symbol, start, end)
    print(f"获取完成: {len(rows)} 根")

    save_csv(rows, args.output_csv)
    print(f"CSV 已保存: {args.output_csv}")

    title = f"{args.symbol} 60m Kline ({args.start} ~ {args.end})"
    plot_kline(args.output_csv, args.output_png, title)
    print(f"图像已生成: {args.output_png}")


if __name__ == "__main__":
    main()
