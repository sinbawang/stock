"""通用 K 线抓取模块（腾讯财经）。

支持:
- 股票代码: A 股/港股等腾讯可识别代码
- 周期: day/week/month/m60/m30/m15/m5
- 时间范围过滤

示例:
    from chanlun.data.kline_fetcher import fetch_kline, save_to_csv
    rows = fetch_kline("03690", start="2026-03-03", end="2026-04-12", interval="day")
    save_to_csv(rows, "data/reports/03690/day/analyze/3690_daily.csv")
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

import requests


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


def _symbol_for_eastmoney(norm_symbol: str) -> str:
    if norm_symbol.startswith(("sh", "sz", "bj")):
        return norm_symbol[2:]
    raise ValueError(f"东方财富分钟线仅支持 A 股代码，收到: {norm_symbol}")


def _eastmoney_market_code(norm_symbol: str) -> str:
    if norm_symbol.startswith("sh"):
        return "1"
    return "0"


def _symbol_for_xueqiu(norm_symbol: str) -> str:
    if norm_symbol.startswith("sh"):
        return f"SH{norm_symbol[2:]}"
    if norm_symbol.startswith("sz"):
        return f"SZ{norm_symbol[2:]}"
    if norm_symbol.startswith("bj"):
        return f"BJ{norm_symbol[2:]}"
    raise ValueError(f"雪球分钟线仅支持 A 股代码，收到: {norm_symbol}")


def _fetch_intraday_xueqiu(
    norm_symbol: str,
    interval: str,
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
    adjust: str,
    min_rows: Optional[int] = None,
) -> list[dict]:
    if adjust not in {"", "qfq"}:
        raise ValueError("雪球分钟线当前仅支持不复权或前复权(qfq)")

    from chanlun.data.hk_minute_fetcher import _raise_xueqiu_cookie_error, _resolve_xueqiu_cookies

    xueqiu_symbol = _symbol_for_xueqiu(norm_symbol)
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        os.environ.pop(var, None)
    os.environ["NO_PROXY"] = "*"

    session = requests.Session()
    session.trust_env = False
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": f"https://xueqiu.com/S/{xueqiu_symbol}",
            "Accept": "application/json, text/plain, */*",
        }
    )

    cookies, cookie_source = _resolve_xueqiu_cookies()
    session.cookies.update(cookies)
    if cookie_source == "browser":
        session.get(f"https://xueqiu.com/S/{xueqiu_symbol}", timeout=15)

    actual_start = start_dt or datetime(1990, 1, 1)
    actual_end = end_dt or datetime.now()
    rows_by_ts: dict[str, dict] = {}
    begin_ms = int(actual_end.timestamp() * 1000)
    period = interval.removeprefix("m") + "m"

    for _ in range(20):
        response = session.get(
            "https://stock.xueqiu.com/v5/stock/chart/kline.json",
            params={
                "symbol": xueqiu_symbol,
                "begin": str(begin_ms),
                "period": period,
                "type": "before",
                "count": "-5000",
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
            break

        column_map = {name: idx for idx, name in enumerate(columns)}
        required = ["timestamp", "open", "high", "low", "close", "volume"]
        missing = [name for name in required if name not in column_map]
        if missing:
            raise RuntimeError(f"雪球返回缺少字段: {missing}; 实际列: {columns}")

        oldest_ms: Optional[int] = None
        added = 0
        for item in items:
            ts_ms = int(item[column_map["timestamp"]])
            ts_dt = datetime.fromtimestamp(ts_ms / 1000)
            if oldest_ms is None or ts_ms < oldest_ms:
                oldest_ms = ts_ms
            if ts_dt < actual_start or ts_dt > actual_end:
                continue
            key = ts_dt.strftime("%Y-%m-%d %H:%M")
            if key in rows_by_ts:
                continue
            rows_by_ts[key] = {
                "ts": key,
                "open": float(item[column_map["open"]]),
                "high": float(item[column_map["high"]]),
                "low": float(item[column_map["low"]]),
                "close": float(item[column_map["close"]]),
                "volume": int(float(item[column_map["volume"]]) if item[column_map["volume"]] is not None else 0),
            }
            added += 1

        if oldest_ms is None or oldest_ms >= begin_ms or added == 0:
            break
        if min_rows is not None and len(rows_by_ts) >= min_rows:
            break
        if datetime.fromtimestamp(oldest_ms / 1000) <= actual_start:
            break
        begin_ms = oldest_ms - 1

    rows = list(rows_by_ts.values())
    rows.sort(key=lambda row: row["ts"])
    return rows


def _fetch_intraday_eastmoney(
    norm_symbol: str,
    interval: str,
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
    adjust: str,
) -> list[dict]:
    period = interval.removeprefix("m")
    params = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "klt": period,
        "fqt": {"": "0", "qfq": "1", "hfq": "2"}.get(adjust, "1"),
        "secid": f"{_eastmoney_market_code(norm_symbol)}.{_symbol_for_eastmoney(norm_symbol)}",
        "beg": "0",
        "end": "20500000",
    }
    session = requests.Session()
    session.trust_env = False
    response = session.get(
        "https://push2his.eastmoney.com/api/qt/stock/kline/get",
        params=params,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0",
            "Referer": "https://quote.eastmoney.com/",
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    klines = (payload.get("data") or {}).get("klines") or []

    rows = []
    for item in klines:
        fields = item.split(",")
        if len(fields) < 6:
            continue
        ts_dt = datetime.strptime(fields[0], "%Y-%m-%d %H:%M")
        if start_dt and ts_dt < start_dt:
            continue
        if end_dt and ts_dt > end_dt:
            continue
        rows.append({
            "ts": ts_dt.strftime("%Y-%m-%d %H:%M"),
            "open": float(fields[1]),
            "close": float(fields[2]),
            "high": float(fields[3]),
            "low": float(fields[4]),
            "volume": int(float(fields[5])) if fields[5] else 0,
        })

    rows.sort(key=lambda row: row["ts"])
    return rows


def fetch_kline(
    symbol: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    interval: str = "day",
    adjust: str = "qfq",
    limit: int = 1000,
    min_rows: Optional[int] = None,
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

    if (
        min_rows is not None
        and is_intraday
        and len(rows) < min_rows
        and norm_symbol.startswith(("sh", "sz", "bj"))
    ):
        best_rows = rows
        for fallback_fetcher in (_fetch_intraday_xueqiu, _fetch_intraday_eastmoney):
            try:
                if fallback_fetcher is _fetch_intraday_xueqiu:
                    fallback_rows = fallback_fetcher(norm_symbol, norm_interval, start_dt, end_dt, adjust, min_rows)
                else:
                    fallback_rows = fallback_fetcher(norm_symbol, norm_interval, start_dt, end_dt, adjust)
            except Exception:  # noqa: BLE001
                continue
            if len(fallback_rows) > len(best_rows):
                best_rows = fallback_rows
            if len(best_rows) >= min_rows:
                return best_rows
        return best_rows

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
