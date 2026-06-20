"""通用 K 线抓取脚本。

示例:
    python scripts/fetch_kline.py --symbol 03690 --start 2026-03-03 --end 2026-04-12 --interval day --output data/reports/03690/day/analyze/3690_daily.csv
    python scripts/fetch_kline.py --symbol sz000001 --start 2026-04-01 --end 2026-04-12 --interval 60m --output data/reports/000001/60m/analyze/sz000001_60m.csv
"""

from __future__ import annotations

import argparse

from chanlun.data.kline_fetcher import fetch_kline, get_last_fetch_metadata, save_to_csv
from chanlun.data.source_profiles import available_source_profiles


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="抓取任意股票任意级别 K 线数据")
    parser.add_argument("--symbol", required=True, help="股票代码，如 03690 / hk03690 / sz000001 / sh600519")
    parser.add_argument("--start", default=None, help="开始时间，如 2026-03-03 或 2026-04-10 10:30")
    parser.add_argument("--end", default=None, help="结束时间，如 2026-04-12 或 2026-04-10 15:00")
    parser.add_argument("--interval", default="day", help="级别：day/week/month/60m/30m/15m/5m")
    parser.add_argument("--adjust", default="qfq", help="复权：qfq/hfq/空字符串")
    parser.add_argument("--limit", default=1000, type=int, help="最多返回条数（分钟线主要依赖此值）")
    parser.add_argument(
        "--source-profile",
        default=None,
        choices=available_source_profiles(),
        help="分钟线数据源配置；A股分钟线会按 profile 改变抓取顺序，默认读取 CHANLUN_SOURCE_PROFILE 或 mainland",
    )
    parser.add_argument("--output", required=True, help="输出 CSV 文件路径")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print(
        f"正在抓取: symbol={args.symbol}, interval={args.interval}, "
        f"start={args.start}, end={args.end}, limit={args.limit}, source_profile={args.source_profile}"
    )

    rows = fetch_kline(
        symbol=args.symbol,
        start=args.start,
        end=args.end,
        interval=args.interval,
        adjust=args.adjust,
        limit=args.limit,
        source_profile=args.source_profile,
    )
    fetch_meta = get_last_fetch_metadata()

    print(f"抓取完成: {len(rows)} 根 K 线")
    if fetch_meta.get("actual_source"):
        print(f"实际命中源: {fetch_meta['actual_source']}")
    if rows:
        print(f"首条: {rows[0]}")
        print(f"末条: {rows[-1]}")

    save_to_csv(rows, args.output)
    print(f"已保存到: {args.output}")


if __name__ == "__main__":
    main()
