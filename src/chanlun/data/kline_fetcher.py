"""通用 K 线抓取模块（腾讯财经）。

支持:
- 股票代码: A 股/港股等腾讯可识别代码
- 周期: day/week/month/m60/m30/m15/m5
- 时间范围过滤

示例:
    from chanlun.data.kline_fetcher import fetch_kline, save_to_csv
    rows = fetch_kline("03690", start="2026-03-03", end="2026-04-12", interval="day")
    save_to_csv(rows, "data/03690_美团/day/3690_daily.csv")
"""

from __future__ import annotations

import csv
import json
import random
import re
import ssl
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener


_ALLOWED_INTERVALS = {"day", "week", "month", "m60", "m30", "m15", "m5"}


def _make_opener():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return build_opener(ProxyHandler({}), HTTPSHandler(context=ctx))


def _normalize_symbol(symbol: str) -> str:
    s = symbol.strip().lower()

    if s.startswith(("sh", "sz", "bj", "hk", "us")):
        if s.startswith("hk"):
            code = s[2:]
            return f"hk{code.zfill(5)}"
        return s

    if "." in s:
        code, market = s.split(".", 1)
        market = market.lower()
        if market in {"hk", "hkex"}:
            return f"hk{code.zfill(5)}"
        if market in {"sh", "ss"}:
            return f"sh{code.zfill(6)}"
        if market == "sz":
            return f"sz{code.zfill(6)}"
        if market == "bj":
            return f"bj{code.zfill(6)}"
        if market == "us":
            return f"us{code.upper()}"

    if re.fullmatch(r"\d{5}", s):
        return f"hk{s}"

    if re.fullmatch(r"\d{6}", s):
        if s.startswith(("6", "9", "5")):
            return f"sh{s}"
        return f"sz{s}"

    raise ValueError(f"无法识别股票代码: {symbol}")


def _normalize_interval(interval: str) -> str:
    m = interval.strip().lower()
    mapping = {
        "d": "day",
        "1d": "day",
        "day": "day",
        "daily": "day",
        "w": "week",
        "1w": "week",
        "week": "week",
        "m": "month",
        "1m": "month",
        "month": "month",
        "60": "m60",
        "60m": "m60",
        "60k": "m60",
        "m60": "m60",
        "30": "m30",
        "30m": "m30",
        "30k": "m30",
        "m30": "m30",
        "15": "m15",
        "15m": "m15",
        "15k": "m15",
        "m15": "m15",
        "5": "m5",
        "5m": "m5",
        "5k": "m5",
        "m5": "m5",
    }
    out = mapping.get(m)
    if not out:
        raise ValueError(f"不支持的级别: {interval}")
    return out


def _parse_time(value: Optional[str], is_intraday: bool) -> Optional[datetime]:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None

    formats = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y%m%d%H%M",
        "%Y-%m-%d",
        "%Y%m%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(text, fmt)
            if not is_intraday and fmt in {"%Y-%m-%d", "%Y%m%d"}:
                return dt
            return dt
        except ValueError:
            continue

    raise ValueError(f"无法解析时间: {value}")


def _parse_bar_ts(ts: str, is_intraday: bool) -> datetime:
    if is_intraday:
        return datetime.strptime(ts, "%Y%m%d%H%M")
    return datetime.strptime(ts, "%Y-%m-%d")


def _fetch_day_like(opener, symbol: str, interval: str, start: str, end: str, limit: int, adjust: str) -> list[list[str]]:
    adj = adjust if adjust in {"qfq", "hfq", ""} else "qfq"
    params = {
        "_var": "v",
        "param": f"{symbol},{interval},{start},{end},{limit},{adj}",
        "r": f"{random.random():.6f}",
    }
    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?" + urlencode(params)
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0",
        "Referer": "https://gu.qq.com/",
    })
    raw = opener.open(req, timeout=20).read().decode("utf-8")

    m = re.search(r"=\s*(\{.*\})", raw, re.DOTALL)
    if not m:
        raise ValueError(f"响应格式异常: {raw[:200]}")

    payload = json.loads(m.group(1))
    code_data = payload.get("data", {}).get(symbol, {})

    key = "qfqday" if interval == "day" and adjust == "qfq" else interval
    return code_data.get(key) or code_data.get(interval) or []


def _fetch_intraday(opener, symbol: str, interval: str, limit: int) -> list[list[str]]:
    params = {
        "param": f"{symbol},{interval},,{limit}",
        "r": f"{random.random():.6f}",
    }
    url = "https://ifzq.gtimg.cn/appstock/app/kline/mkline?" + urlencode(params)
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0",
        "Referer": "https://gu.qq.com/",
    })
    raw = opener.open(req, timeout=20).read().decode("utf-8")
    payload = json.loads(raw)

    if payload.get("code") != 0:
        raise ValueError(f"分钟线接口返回错误: {payload.get('msg', 'unknown error')}")

    code_data = payload.get("data", {}).get(symbol, {})
    return code_data.get(interval) or []


def fetch_kline(
    symbol: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    interval: str = "day",
    adjust: str = "qfq",
    limit: int = 1000,
) -> list[dict]:
    """抓取指定股票、指定时间范围、指定级别 K 线。"""
    norm_symbol = _normalize_symbol(symbol)
    norm_interval = _normalize_interval(interval)
    is_intraday = norm_interval.startswith("m")

    start_dt = _parse_time(start, is_intraday)
    end_dt = _parse_time(end, is_intraday)

    if is_intraday and norm_symbol.startswith("hk"):
        raise ValueError("腾讯分钟线接口暂不支持港股代码（如 hk03690），请改用 A 股代码或日/周/月级别")

    opener = _make_opener()

    if is_intraday:
        raw_rows = _fetch_intraday(opener, norm_symbol, norm_interval, limit)
    else:
        req_start = (start_dt or datetime(1990, 1, 1)).strftime("%Y-%m-%d")
        req_end = (end_dt or datetime.today()).strftime("%Y-%m-%d")
        raw_rows = _fetch_day_like(opener, norm_symbol, norm_interval, req_start, req_end, limit, adjust)

    rows = []
    for bar in raw_rows:
        if len(bar) < 6:
            continue

        ts_dt = _parse_bar_ts(bar[0], is_intraday)
        if start_dt and ts_dt < start_dt:
            continue
        if end_dt and ts_dt > end_dt:
            continue

        rows.append({
            "ts": ts_dt.strftime("%Y-%m-%d %H:%M") if is_intraday else ts_dt.strftime("%Y-%m-%d"),
            "open": float(bar[1]),
            "close": float(bar[2]),
            "high": float(bar[3]),
            "low": float(bar[4]),
            "volume": int(float(bar[5])),
        })

    rows.sort(key=lambda r: r["ts"])
    return rows


def save_to_csv(rows: list[dict], filepath: str) -> None:
    """将 K 线结果保存为 CSV。"""
    if not rows:
        raise ValueError("无可保存数据")

    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ts", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        writer.writerows(rows)
