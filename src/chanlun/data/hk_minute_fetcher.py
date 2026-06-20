"""
港股分钟级 K 线抓取。

当前默认策略：
    - 主数据源优先使用雪球（稳定性更好、历史更完整）
    - 仅在调用方显式允许时，才回退到 AKShare / 东方财富

适用于无港股券商账号、仅需研发/回测分钟数据的场景。

用法:
    from chanlun.data.hk_minute_fetcher import fetch_hk_minute_with_policy, save_to_csv
    rows, used_source = fetch_hk_minute_with_policy(
        "03690", period="60", start="2026-03-01 09:30", end="2026-04-25 16:00"
    )
    save_to_csv(rows, f"data/reports/03690/60m/analyze/03690_60m_{used_source}.csv")

CLI:
    python -m chanlun.data.hk_minute_fetcher --symbol 03690 --period 60 \
        --start "2026-03-01 09:30" --end "2026-04-25 16:00"
"""

from __future__ import annotations

import csv
import multiprocessing as mp
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

import requests

from storage_layout import REPORTS_DIR

_ALLOWED_PERIODS = {"1", "5", "15", "30", "60"}
_ALLOWED_ADJUSTS = {"", "qfq", "hfq"}
_ALLOWED_SOURCES = {"xueqiu", "akshare"}
_DEFAULT_PRIMARY_SOURCE = "xueqiu"
_SOURCE_FETCH_TIMEOUT_SECONDS = 45
_LAST_FETCH_METADATA: dict[str, object] = {}
ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_COOKIE_FILE_CANDIDATES = (
    ROOT / "data" / "_meta" / "xueqiu_cookie.env",
    ROOT / "data" / "_meta" / "xueqiu_cookie.ps1",
    ROOT / "data" / "_meta" / "xueqiu_cookie.txt",
)


class XueqiuCookieError(RuntimeError):
    def __init__(self, message: str, cookie_source: str):
        super().__init__(message)
        self.cookie_source = cookie_source


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


def _extract_cookie_text_from_file(file_path: Path) -> str:
    text = file_path.read_text(encoding="utf-8").lstrip("\ufeff").strip()
    if not text:
        raise RuntimeError(f"雪球 cookie 文件为空: {file_path}")

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("XUEQIU_COOKIE="):
            return line.split("=", 1)[1].strip().strip('"\'')
        match = re.match(r"^\$env:XUEQIU_COOKIE\s*=\s*(['\"])(.*)\1$", line)
        if match:
            return match.group(2).strip()
        return line

    raise RuntimeError(f"雪球 cookie 文件未包含有效内容: {file_path}")


def _resolve_xueqiu_cookie_file() -> tuple[dict[str, str], str] | None:
    explicit_path = os.getenv("XUEQIU_COOKIE_FILE", "").strip()
    candidates = [Path(explicit_path)] if explicit_path else []
    candidates.extend(_DEFAULT_COOKIE_FILE_CANDIDATES)

    for candidate in candidates:
        if not candidate.exists():
            continue
        cookie_text = _extract_cookie_text_from_file(candidate)
        return _parse_cookie_string(cookie_text), f"file:{candidate}"

    return None


def _normalize_source_sequence(
    primary_source: str,
    fallback_sources: Optional[Sequence[str]] = None,
) -> tuple[str, ...]:
    sources = [primary_source]
    if fallback_sources:
        sources.extend(fallback_sources)

    normalized: list[str] = []
    for source in sources:
        if source not in _ALLOWED_SOURCES:
            raise ValueError(f"source 必须是 {_ALLOWED_SOURCES} 之一，收到: {source}")
        if source not in normalized:
            normalized.append(source)
    return tuple(normalized)


def _update_last_fetch_metadata(**kwargs: object) -> None:
    _LAST_FETCH_METADATA.clear()
    _LAST_FETCH_METADATA.update(kwargs)


def get_last_fetch_metadata() -> dict[str, object]:
    return dict(_LAST_FETCH_METADATA)


def _extract_xueqiu_cookie_from_browser(browser: Optional[str] = None) -> dict[str, str]:
    """从本机浏览器读取 xueqiu.com cookie，避免手工复制。"""
    try:
        import browser_cookie3  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised via tests with monkeypatch
        raise RuntimeError(
            "未安装 browser-cookie3，无法自动读取浏览器雪球 cookie。"
        ) from exc

    domain = ".xueqiu.com"
    browser_name = (browser or os.getenv("XUEQIU_COOKIE_BROWSER", "auto")).strip().lower()
    candidates = ["edge", "chrome", "brave", "chromium", "firefox"] if browser_name in {"", "auto"} else [browser_name]
    errors: list[str] = []

    for candidate in candidates:
        loader = getattr(browser_cookie3, candidate, None)
        if loader is None:
            errors.append(f"{candidate}: not-supported")
            continue

        try:
            jar = loader(domain_name=domain)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{candidate}: {exc}")
            continue

        cookies = {
            cookie.name: cookie.value
            for cookie in jar
            if cookie.domain.endswith("xueqiu.com") and cookie.value
        }
        if cookies:
            return cookies

        errors.append(f"{candidate}: no-xueqiu-cookie")

    if browser_name not in {"", "auto"}:
        raise RuntimeError(
            f"未在浏览器 {browser_name} 中找到可用的雪球 cookie。请先登录 xueqiu.com。"
        )

    raise RuntimeError(
        "未能从本机浏览器自动读取雪球 cookie。"
        " 请先在 Edge/Chrome/Firefox 中登录 xueqiu.com，"
        "必要时关闭浏览器重试，或以管理员权限运行；"
        f"探测详情: {' | '.join(errors)}"
    )


def _resolve_xueqiu_cookies() -> tuple[dict[str, str], str]:
    cookie_text = os.getenv("XUEQIU_COOKIE", "").strip()
    if cookie_text:
        return _parse_cookie_string(cookie_text), "env"

    resolved_from_file = _resolve_xueqiu_cookie_file()
    if resolved_from_file is not None:
        return resolved_from_file

    cookies = _extract_xueqiu_cookie_from_browser()
    return cookies, "browser"


def _build_xueqiu_session(symbol: str) -> tuple[requests.Session, str]:
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

    cookies, cookie_source = _resolve_xueqiu_cookies()
    session.cookies.update(cookies)

    # Only browser-derived cookies still need the HTML preflight.
    # Env/file cookie sources should go straight to the JSON API.
    if cookie_source == "browser":
        session.get(f"https://xueqiu.com/S/HK{symbol}", timeout=15)
    return session, cookie_source


def _raise_xueqiu_cookie_error(cookie_source: str, detail: str) -> None:
    if cookie_source == "env":
        raise XueqiuCookieError(
            f"检测到环境变量 XUEQIU_COOKIE，但它可能已过期或失效。{detail}",
            cookie_source,
        )

    raise XueqiuCookieError(
        f"未从浏览器取得有效的雪球登录态，或浏览器里的登录态已经失效。{detail}",
        cookie_source,
    )


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

    session, cookie_source = _build_xueqiu_session(code)
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


def _fetch_hk_minute_worker(
    queue: mp.Queue,
    source: str,
    symbol: str,
    period: str,
    start: Optional[str],
    end: Optional[str],
    adjust: str,
) -> None:
    try:
        if source == "xueqiu":
            payload = _fetch_hk_minute_xueqiu(symbol, period, start, end, adjust)
        elif source == "akshare":
            payload = _fetch_hk_minute_akshare(symbol, period, start, end, adjust)
        else:
            raise ValueError(f"source 必须是 {_ALLOWED_SOURCES} 之一，收到: {source}")
        queue.put(("ok", payload))
    except Exception as exc:  # noqa: BLE001
        queue.put(("error", f"{type(exc).__name__}: {exc}"))


def _fetch_hk_minute_with_timeout(
    source: str,
    symbol: str,
    period: str,
    start: Optional[str],
    end: Optional[str],
    adjust: str,
) -> list[dict]:
    ctx = mp.get_context("spawn")
    queue: mp.Queue = ctx.Queue()
    process = ctx.Process(
        target=_fetch_hk_minute_worker,
        args=(queue, source, symbol, period, start, end, adjust),
    )
    process.start()
    process.join(_SOURCE_FETCH_TIMEOUT_SECONDS)
    if process.is_alive():
        process.terminate()
        process.join(2)
        raise TimeoutError(f"{source} 港股分钟线抓取超过 {_SOURCE_FETCH_TIMEOUT_SECONDS} 秒")
    if queue.empty():
        raise RuntimeError(f"{source} 港股分钟线抓取无返回")
    status, payload = queue.get()
    if status == "ok":
        return payload
    if source == "xueqiu" and payload.startswith("XueqiuCookieError:"):
        raise XueqiuCookieError(payload.split(":", 1)[1].strip(), "unknown")
    raise RuntimeError(payload)


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
        except XueqiuCookieError as exc:
            raise RuntimeError(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "雪球抓取失败。可选方案：1) 显式设置环境变量 XUEQIU_COOKIE；"
                "2) 先在本机浏览器登录 xueqiu.com，让程序自动读取 cookie；"
                f"3) 改用 source='akshare'。原始错误: {exc}"
            ) from exc

    return _fetch_hk_minute_with_timeout(source, symbol, period, start, end, adjust)


def fetch_hk_minute_with_policy(
    symbol: str,
    period: str = "60",
    start: Optional[str] = None,
    end: Optional[str] = None,
    adjust: str = "qfq",
    primary_source: str = _DEFAULT_PRIMARY_SOURCE,
    fallback_sources: Optional[Sequence[str]] = None,
    min_rows: Optional[int] = None,
) -> tuple[list[dict], str]:
    """
    按统一策略抓取港股分钟线。

    默认只使用雪球；只有显式传入 fallback_sources 时才会回退到其它源。
    若允许多个来源，则返回“可行范围内 K 线数量最多”的成功结果。
    当提供 min_rows 时，它只作为继续探测后续来源的软阈值，不再作为最终失败门槛。

    Returns:
        (rows, used_source)
    """
    source_order = _normalize_source_sequence(primary_source, fallback_sources)
    failures: list[str] = []
    best_rows: list[dict] = []
    best_source: str | None = None
    source_attempts: list[dict[str, object]] = []

    _update_last_fetch_metadata(
        symbol=_normalize_symbol(symbol),
        period=period,
        source_plan="->".join(source_order),
        actual_source=None,
        source_attempts=source_attempts,
        row_count=0,
    )

    for source in source_order:
        try:
            rows = fetch_hk_minute(
                symbol=symbol,
                period=period,
                start=start,
                end=end,
                adjust=adjust,
                source=source,
            )
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{source}: {exc}")
            source_attempts.append({"source": source, "status": "error", "error": str(exc)})
            continue

        source_attempts.append({"source": source, "status": "ok", "row_count": len(rows)})

        if len(rows) > len(best_rows):
            best_rows = rows
            best_source = source

        if min_rows is not None and len(rows) < min_rows:
            failures.append(f"{source}: insufficient_rows={len(rows)} < {min_rows}")
            if rows:
                continue

        if not rows:
            failures.append(f"{source}: empty")
            continue

    if best_source is not None:
        _update_last_fetch_metadata(
            symbol=_normalize_symbol(symbol),
            period=period,
            source_plan="->".join(source_order),
            actual_source=best_source,
            source_attempts=source_attempts,
            row_count=len(best_rows),
        )
        return best_rows, best_source

    attempted = " -> ".join(source_order)
    _update_last_fetch_metadata(
        symbol=_normalize_symbol(symbol),
        period=period,
        source_plan="->".join(source_order),
        actual_source=None,
        source_attempts=source_attempts,
        row_count=0,
    )
    raise RuntimeError(
        "港股分钟线抓取失败。"
        f"尝试顺序: {attempted}。"
        f"失败详情: {' | '.join(failures)}"
    )


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
    parser = argparse.ArgumentParser(description="港股分钟级 K 线抓取（雪球优先）")
    parser.add_argument("--symbol", required=True, help="港股代码，如 03690")
    parser.add_argument("--period", default="60", choices=sorted(_ALLOWED_PERIODS),
                        help="分钟周期: 1/5/15/30/60")
    parser.add_argument("--start", default=None, help="起始时间 YYYY-MM-DD [HH:MM]")
    parser.add_argument("--end", default=None, help="结束时间 YYYY-MM-DD [HH:MM]")
    parser.add_argument("--adjust", default="qfq", choices=sorted(_ALLOWED_ADJUSTS),
                        help="复权: 留空 / qfq / hfq")
    parser.add_argument("--source", default="xueqiu", choices=sorted(_ALLOWED_SOURCES),
                        help="数据源: xueqiu / akshare")
    parser.add_argument("--fallback-source", action="append", choices=sorted(_ALLOWED_SOURCES), default=None,
                        help="显式允许的回退数据源，可重复指定；默认不回退")
    parser.add_argument("--output", default=None, help="输出 CSV 路径，默认按目录约定生成")
    args = parser.parse_args()

    print(f"正在抓取 港股 {args.symbol} {args.period}m K 线 "
          f"({args.start or '最早'} ~ {args.end or '至今'}) ...")
    rows, used_source = fetch_hk_minute_with_policy(
        args.symbol,
        period=args.period,
        start=args.start,
        end=args.end,
        adjust=args.adjust,
        primary_source=args.source,
        fallback_sources=args.fallback_source,
    )
    fetch_meta = get_last_fetch_metadata()
    print(f"获取 {len(rows)} 根 K 线，使用数据源: {used_source}")
    if fetch_meta.get("source_plan"):
        print(f"抓取链路: {fetch_meta['source_plan']}")
    if fetch_meta.get("actual_source"):
        print(f"实际命中源: {fetch_meta['actual_source']}")

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
        out = REPORTS_DIR / code / f"{args.period}m" / "analyze" / f"{code}_{args.period}m.csv"
    save_to_csv(rows, out)


if __name__ == "__main__":
    main()
