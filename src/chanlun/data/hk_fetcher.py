"""
港股行情数据获取（腾讯财经接口，不依赖代理）。

用法:
    python -m chanlun.data.hk_fetcher --symbol 03690 --start 2026-03-03 --output data/03690_美团/day/3690_daily.csv
"""

from __future__ import annotations

import csv
import json
import random
import re
import ssl
from datetime import date
from pathlib import Path
from typing import Optional
from urllib.request import Request, build_opener, ProxyHandler, HTTPSHandler


def _make_opener() -> object:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return build_opener(ProxyHandler({}), HTTPSHandler(context=ctx))


def fetch_hk_daily(
    symbol: str,
    start: str,
    end: Optional[str] = None,
    adjust: str = "qfq",
) -> list[dict]:
    """
    获取港股日 K 数据（腾讯财经前复权）。

    Args:
        symbol: 港股代码，如 "03690"
        start:  开始日期，格式 "YYYY-MM-DD"
        end:    结束日期，格式 "YYYY-MM-DD"，None 表示今日
        adjust: 复权方式，"qfq"前复权 / ""不复权（腾讯仅支持 qfq）

    Returns:
        OHLCV 字典列表，字段: ts, open, high, low, close, volume
    """
    if end is None:
        end = date.today().strftime("%Y-%m-%d")

    code = symbol.lstrip("0").zfill(5)  # 保证5位，如 03690
    adj_key = "qfqday" if adjust == "qfq" else "day"
    var_name = f"kline_dayfqhk{code}"
    r_val = f"{random.random():.6f}"
    url = (
        "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        f"?_var={var_name}"
        f"&param=hk{code},day,{start},{end},500,qfq"
        f"&r={r_val}"
    )

    opener = _make_opener()
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0",
        "Referer": "https://gu.qq.com/",
    })

    with opener.open(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8")

    m = re.search(r"=\s*(\{.*\})", raw, re.DOTALL)
    if not m:
        raise ValueError(f"腾讯财经 API 返回格式异常: {raw[:200]}")

    payload = json.loads(m.group(1))
    code_data = payload.get("data", {}).get(f"hk{code}", {})
    klines = code_data.get(adj_key) or code_data.get("day") or []

    rows = []
    for k in klines:
        # 格式: [日期, 开, 收, 高, 低, 量, ...]
        if len(k) < 5:
            continue
        rows.append({
            "ts":     k[0],
            "open":   float(k[1]),
            "close":  float(k[2]),
            "high":   float(k[3]),
            "low":    float(k[4]),
            "volume": int(float(k[5])) if len(k) > 5 else 0,
        })

    rows.sort(key=lambda r: r["ts"])
    return rows


def save_to_csv(rows: list[dict], filepath: str) -> None:
    """将 K 线数据保存到 CSV 文件。"""
    if not rows:
        return

    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"已保存 {len(rows)} 根 K 线到 {path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="获取港股日 K 数据")
    parser.add_argument("--symbol", default="03690", help="港股代码，如 03690")
    parser.add_argument("--start",  default="2026-03-03", help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end",    default=None, help="结束日期 YYYY-MM-DD，默认今日")
    parser.add_argument("--output", default=None, help="输出 CSV 路径")
    parser.add_argument("--adjust", default="qfq", choices=["qfq", "hfq", ""],
                        help="复权方式：qfq前复权 hfq后复权 无复权留空")
    args = parser.parse_args()

    print(f"正在获取 {args.symbol} 日 K 数据（{args.start} ~ {args.end or '今日'}）...")
    rows = fetch_hk_daily(args.symbol, args.start, args.end, args.adjust)
    print(f"获取 {len(rows)} 根 K 线")

    if rows:
        for r in rows[:3]:
            print(f"  {r['ts']}  开={r['open']}  高={r['high']}  低={r['low']}  收={r['close']}  量={r['volume']}")
        if len(rows) > 3:
            r = rows[-1]
            print(f"  ...  {r['ts']}  开={r['open']}  高={r['high']}  低={r['low']}  收={r['close']}")

    if args.output:
        save_to_csv(rows, args.output)
    else:
        if args.symbol == "03690":
            default_path = f"data/03690_美团/day/{args.symbol}_daily_{args.start}_{args.end or 'today'}.csv"
        else:
            default_path = f"data/{args.symbol}/day/{args.symbol}_daily_{args.start}_{args.end or 'today'}.csv"
        save_to_csv(rows, default_path)


if __name__ == "__main__":
    main()
