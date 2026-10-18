"""
港股行情数据获取（腾讯财经接口，不依赖代理）。

用法:
    python -m chanlun.data.hk_fetcher --symbol 03690 --start 2026-03-03 --output data/reports/03690/day/analyze/3690_daily.csv
"""

from __future__ import annotations

import csv
import json
import random
import re
import ssl
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from urllib.request import Request, build_opener, ProxyHandler, HTTPSHandler

from storage_layout import REPORTS_DIR, is_hk_index_symbol, normalize_hk_symbol


def _make_opener() -> object:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return build_opener(ProxyHandler({}), HTTPSHandler(context=ctx))


def _fetch_hk_index_daily_xueqiu(
    symbol: str,
    *,
    start: str,
    end: str | None,
    limit: int = 1000,
) -> list[dict]:
    import requests

    from chanlun.data.hk_minute_fetcher import _raise_xueqiu_cookie_error, _resolve_xueqiu_cookies

    normalized = normalize_hk_symbol(symbol)
    session = requests.Session()
    session.trust_env = False
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": f"https://xueqiu.com/S/HK{normalized}",
            "Accept": "application/json, text/plain, */*",
        }
    )
    cookies, cookie_source = _resolve_xueqiu_cookies()
    session.cookies.update(cookies)
    if cookie_source == "browser":
        session.get(f"https://xueqiu.com/S/HK{normalized}", timeout=15)

    response = session.get(
        "https://stock.xueqiu.com/v5/stock/chart/kline.json",
        params={
            "symbol": f"HK{normalized}",
            "begin": str(int(datetime.now().timestamp() * 1000)),
            "period": "day",
            "type": "normal",
            "count": str(-max(1, int(limit))),
            "indicator": "kline",
        },
        timeout=20,
    )
    if response.status_code >= 400:
        if response.status_code in {401, 403}:
            _raise_xueqiu_cookie_error(cookie_source, f"HTTP {response.status_code}")
        raise RuntimeError(f"雪球接口返回 HTTP {response.status_code}: {response.text[:300]}")

    payload = response.json()
    if payload.get("error_code") not in (None, 0):
        error_code = payload.get("error_code")
        if error_code in {400016, 401, 403}:
            _raise_xueqiu_cookie_error(cookie_source, f"error_code={error_code}")
        raise RuntimeError(f"雪球抓取失败: {payload}")

    data = payload.get("data") or {}
    columns = data.get("column") or []
    items = data.get("item") or []
    if not columns or not items:
        return []

    column_map = {name: idx for idx, name in enumerate(columns)}
    required = ["timestamp", "open", "high", "low", "close", "volume"]
    missing = [name for name in required if name not in column_map]
    if missing:
        raise RuntimeError(f"雪球返回缺少字段: {missing}; 实际列: {columns}")

    start_text = start.strip()
    end_text = (end or date.today().strftime("%Y-%m-%d")).strip()
    rows = []
    for item in items:
        ts_ms = int(item[column_map["timestamp"]])
        trade_day = datetime.fromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d")
        if trade_day < start_text or trade_day > end_text:
            continue
        rows.append(
            {
                "ts": trade_day,
                "open": float(item[column_map["open"]]),
                "high": float(item[column_map["high"]]),
                "low": float(item[column_map["low"]]),
                "close": float(item[column_map["close"]]),
                "volume": int(float(item[column_map["volume"]]) if item[column_map["volume"]] is not None else 0),
            }
        )
    rows.sort(key=lambda row: row["ts"])
    return rows[-max(1, int(limit)) :]


def fetch_hk_daily(
    symbol: str,
    start: str,
    end: Optional[str] = None,
    adjust: str = "",
    limit: int = 1000,
) -> list[dict]:
    """
    获取港股日 K 数据（腾讯财经，默认不复权）。

    Args:
        symbol: 港股代码，如 "03690"
        start:  开始日期，格式 "YYYY-MM-DD"
        end:    结束日期，格式 "YYYY-MM-DD"，None 表示今日
        adjust: 复权方式，""不复权 / "qfq"前复权 / "hfq"后复权
        limit:  期望返回的最大 K 线数量

    Returns:
        OHLCV 字典列表，字段: ts, open, high, low, close, volume
    """
    normalized_symbol = normalize_hk_symbol(symbol)
    if is_hk_index_symbol(normalized_symbol):
        return _fetch_hk_index_daily_xueqiu(normalized_symbol, start=start, end=end, limit=limit)

    if end is None:
        end = date.today().strftime("%Y-%m-%d")

    code = normalized_symbol.lstrip("0").zfill(5)  # 保证5位，如 03690
    effective_limit = max(1, int(limit))
    adj_key = "qfqday" if adjust == "qfq" else "day"
    var_name = f"kline_dayfqhk{code}"
    r_val = f"{random.random():.6f}"
    url = (
        "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        f"?_var={var_name}"
        f"&param=hk{code},day,{start},{end},{effective_limit},qfq"
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
    return rows[-effective_limit:]


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
    parser.add_argument("--adjust", default="", choices=["qfq", "hfq", ""],
                        help="复权方式：默认不复权；可选 qfq/hfq")
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
        normalized_symbol = normalize_hk_symbol(args.symbol)
        default_path = REPORTS_DIR / normalized_symbol / "day" / "analyze" / f"{normalized_symbol}_daily_{args.start}_{args.end or 'today'}.csv"
        save_to_csv(rows, default_path)


if __name__ == "__main__":
    main()
