"""
港股分钟级 K 线抓取（基于 AKShare 东方财富接口）。

适用于无港股券商账号、仅需研发/回测分钟数据的场景。

特点:
    - 不需要开户、不需要 token
    - 支持 1m / 5m / 15m / 30m / 60m
    - 历史长度受东方财富限制（1m 约最近数日，5m+ 较长）
    - 准实时（分钟级延迟，非 Tick 推送）

用法:
    from chanlun.data.hk_minute_fetcher import fetch_hk_minute, save_to_csv
    rows = fetch_hk_minute("03690", period="60", start="2026-03-01 09:30",
                           end="2026-04-25 16:00", adjust="qfq")
    save_to_csv(rows, "data/03690_美团/60m/03690_60m.csv")

CLI:
    python -m chanlun.data.hk_minute_fetcher --symbol 03690 --period 60 \
        --start "2026-03-01 09:30" --end "2026-04-25 16:00"
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

_ALLOWED_PERIODS = {"1", "5", "15", "30", "60"}
_ALLOWED_ADJUSTS = {"", "qfq", "hfq"}
_ALLOWED_SOURCES = {"xueqiu", "akshare"}


def _normalize_symbol(symbol: str) -> str:
    """统一为 5 位数字（AKShare 东方财富港股要求，例如 '03690'、'00700'）。"""
    s = symbol.strip().lower()
    if s.startswith("hk"):
        s = s[2:]
    if "." in s:
        s = s.split(".", 1)[0]
    if not s.isdigit():
        raise ValueError(f"无法识别港股代码: {symbol}")
    return s.zfill(5)


def _parse_dt(value: Optional[str], default: str) -> str:
    """规范化为 'YYYY-MM-DD HH:MM:SS'，AKShare 要求该格式。"""
    if not value:
        return default
    text = value.strip()
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y%m%d%H%M",
        "%Y%m%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    raise ValueError(f"无法解析时间: {value}")


def _parse_cookie_string(cookie_text: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for chunk in cookie_text.split(";"):
        part = chunk.strip()
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        cookies[key.strip()] = value.strip()
    return cookies


def _build_xueqiu_session(symbol: str) -> requests.Session:
    import os

    for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        os.environ.pop(var, None)
    os.environ["NO_PROXY"] = "*"

    session = requests.Session()
    session.trust_env = False
    user_agent = os.getenv(
        "XUEQIU_USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    )
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Referer": f"https://xueqiu.com/S/HK{symbol}",
            "Accept": "application/json, text/plain, */*",
        }
    )

    cookie_text = os.getenv("XUEQIU_COOKIE", "").strip()
    if cookie_text:
        session.cookies.update(_parse_cookie_string(cookie_text))

    session.get(f"https://xueqiu.com/S/HK{symbol}", timeout=15)
    return session


def _map_xueqiu_period(period: str) -> str:
    return f"{period}m"


def _fetch_hk_minute_xueqiu(
    symbol: str,
    period: str,
    start: Optional[str],
    end: Optional[str],
    adjust: str,
) -> list[dict]:
    if adjust not in {"", "qfq"}:
        raise ValueError("雪球分钟线当前仅支持不复权或前复权(qfq)")

    code = _normalize_symbol(symbol)
    start_dt = datetime.strptime(_parse_dt(start, "1990-01-01 00:00:00"), "%Y-%m-%d %H:%M:%S")
    end_dt = datetime.strptime(
        _parse_dt(end, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        "%Y-%m-%d %H:%M:%S",
    )

    session = _build_xueqiu_session(code)
    response = session.get(
        "https://stock.xueqiu.com/v5/stock/chart/kline.json",
        params={
            "symbol": code,
            "begin": str(int(end_dt.timestamp() * 1000)),
            "period": _map_xueqiu_period(period),
            "type": "before",
            "count": "-5000",
            "indicator": "kline",
        },
        timeout=20,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"雪球接口返回 HTTP {response.status_code}: {response.text[:300]}")

    payload = response.json()
    if payload.get("error_code") not in (None, 0):
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

    rows: list[dict] = []
    for item in items:
        ts = datetime.fromtimestamp(item[column_map["timestamp"]] / 1000)
        if ts < start_dt or ts > end_dt:
            continue
        rows.append(
            {
                "ts": ts.strftime("%Y-%m-%d %H:%M"),
                "open": float(item[column_map["open"]]),
                "high": float(item[column_map["high"]]),
                "low": float(item[column_map["low"]]),
                "close": float(item[column_map["close"]]),
                "volume": int(float(item[column_map["volume"]]) if item[column_map["volume"]] is not None else 0),
            }
        )

    rows.sort(key=lambda x: x["ts"])
    return rows


def _fetch_hk_minute_akshare(
    symbol: str,
    period: str,
    start: Optional[str],
    end: Optional[str],
    adjust: str,
) -> list[dict]:
    import os
    import time

    # 延迟导入，避免无 akshare 时模块整体不可用
    # 绕过本地拦截代理（与项目其它 fetcher 行为一致）
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        os.environ.pop(var, None)
    os.environ["NO_PROXY"] = "*"

    import akshare as ak  # type: ignore

    code = _normalize_symbol(symbol)
    start_str = _parse_dt(start, "1990-01-01 00:00:00")
    end_str = _parse_dt(end, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    last_err: Optional[Exception] = None
    df = None
    for attempt in range(5):
        try:
            df = ak.stock_hk_hist_min_em(
                symbol=code,
                period=period,
                adjust=adjust,
                start_date=start_str,
                end_date=end_str,
            )
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2 + attempt * 2)
    if df is None:
        raise RuntimeError(f"AKShare 抓取失败（已重试5次）: {last_err}")

    if df is None or df.empty:
        return []

    col_map = {
        "时间": "ts", "datetime": "ts", "date": "ts",
        "开盘": "open", "open": "open",
        "收盘": "close", "close": "close",
        "最高": "high", "high": "high",
        "最低": "low", "low": "low",
        "成交量": "volume", "volume": "volume",
    }
    rename = {c: col_map[c] for c in df.columns if c in col_map}
    df = df.rename(columns=rename)

    needed = ["ts", "open", "high", "low", "close", "volume"]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise RuntimeError(f"AKShare 返回缺少字段: {missing}; 实际列: {list(df.columns)}")

    rows: list[dict] = []
    for r in df[needed].itertuples(index=False):
        ts_val = r.ts
        if isinstance(ts_val, datetime):
            ts_str = ts_val.strftime("%Y-%m-%d %H:%M")
        else:
            ts_str = str(ts_val)[:16]
        rows.append({
            "ts": ts_str,
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": int(float(r.volume)) if r.volume is not None else 0,
        })

    rows.sort(key=lambda x: x["ts"])
    return rows


def fetch_hk_minute(
    symbol: str,
    period: str = "60",
    start: Optional[str] = None,
    end: Optional[str] = None,
    adjust: str = "qfq",
    source: str = "xueqiu",
) -> list[dict]:
    """
    抓取港股分钟 K 线。

    Args:
        symbol: 港股代码，如 "03690" / "hk03690" / "0700.HK"
        period: 分钟周期，"1"/"5"/"15"/"30"/"60"
        start:  起始时间，"YYYY-MM-DD" 或 "YYYY-MM-DD HH:MM"
        end:    结束时间，同上；为空则到当前
        adjust: ""/"qfq"/"hfq"

    Returns:
        list[dict]，字段: ts, open, high, low, close, volume
    """
    if period not in _ALLOWED_PERIODS:
        raise ValueError(f"period 必须是 {_ALLOWED_PERIODS} 之一，收到: {period}")
    if adjust not in _ALLOWED_ADJUSTS:
        raise ValueError(f"adjust 必须是 {_ALLOWED_ADJUSTS} 之一，收到: {adjust}")
    if source not in _ALLOWED_SOURCES:
        raise ValueError(f"source 必须是 {_ALLOWED_SOURCES} 之一，收到: {source}")

    if source == "xueqiu":
        try:
            return _fetch_hk_minute_xueqiu(symbol, period, start, end, adjust)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "雪球抓取失败。请确认已在环境变量 XUEQIU_COOKIE 中提供可用登录 cookie，"
                f"或改用 source='akshare'。原始错误: {exc}"
            ) from exc

    return _fetch_hk_minute_akshare(symbol, period, start, end, adjust)


def save_to_csv(rows: list[dict], filepath: str) -> None:
    if not rows:
        raise ValueError("无可保存数据")
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ts", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"已保存 {len(rows)} 根 K 线到 {path}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="港股分钟级 K 线抓取（AKShare）")
    parser.add_argument("--symbol", required=True, help="港股代码，如 03690")
    parser.add_argument("--period", default="60", choices=sorted(_ALLOWED_PERIODS),
                        help="分钟周期: 1/5/15/30/60")
    parser.add_argument("--start", default=None, help="起始时间 YYYY-MM-DD [HH:MM]")
    parser.add_argument("--end", default=None, help="结束时间 YYYY-MM-DD [HH:MM]")
    parser.add_argument("--adjust", default="qfq", choices=sorted(_ALLOWED_ADJUSTS),
                        help="复权: 留空 / qfq / hfq")
    parser.add_argument("--source", default="xueqiu", choices=sorted(_ALLOWED_SOURCES),
                        help="数据源: xueqiu / akshare")
    parser.add_argument("--output", default=None, help="输出 CSV 路径，默认按目录约定生成")
    args = parser.parse_args()

    print(f"正在抓取 港股 {args.symbol} {args.period}m K 线 "
          f"({args.start or '最早'} ~ {args.end or '至今'}) ...")
    rows = fetch_hk_minute(args.symbol, args.period, args.start, args.end, args.adjust, source=args.source)
    print(f"获取 {len(rows)} 根 K 线")

    if rows:
        head = rows[0]
        tail = rows[-1]
        print(f"  首: {head['ts']}  O={head['open']} H={head['high']} "
              f"L={head['low']} C={head['close']} V={head['volume']}")
        print(f"  末: {tail['ts']}  O={tail['open']} H={tail['high']} "
              f"L={tail['low']} C={tail['close']} V={tail['volume']}")

    if args.output:
        out = args.output
    else:
        code = _normalize_symbol(args.symbol)
        out = f"data/{code}/{args.period}m/{code}_{args.period}m.csv"
    save_to_csv(rows, out)


if __name__ == "__main__":
    main()
