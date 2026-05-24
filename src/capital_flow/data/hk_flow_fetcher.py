"""H-share capital-flow and volume data source adapters."""

from __future__ import annotations

from io import StringIO
from datetime import date, datetime, timedelta
import multiprocessing as mp
import os
from pathlib import Path
import re
import time
from typing import Optional

import browser_cookie3  # type: ignore
import pandas as pd
import requests

from capital_flow.models.snapshot import CapitalFlowSnapshot


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CACHE_DIR = ROOT / "data" / "_meta" / "capital_flow_cache"
HK_CONNECT_CACHE_DATASET = "eastmoney_hk_connect_components"
SOUTHBOUND_HOLDING_CACHE_DATASET = "eastmoney_southbound_holding"
SOUTHBOUND_NET_BUY_CACHE_DATASET = "eastmoney_southbound_net_buy"
HKEX_SHORT_SELLING_CACHE_DATASET = "hkex_short_selling_turnover"
REQUEST_TIMEOUT_SECONDS = 8
_DATASET_MEMORY_CACHE: dict[tuple[str, str, int | None], tuple[pd.DataFrame, str, list[str]]] = {}
_DATASET_FAILURE_CACHE: dict[tuple[str, str, int | None], str] = {}
_EASTMONEY_BLOCK_MARKERS = (
    "拖动下方滑块完成拼图",
    "拖动左边滑块完成上方拼图",
    "请完成安全验证",
)
_EASTMONEY_BUSINESS_MARKERS = (
    "港股通成交榜",
    "持股明细",
    "/hsgt/StockHdDetail/",
)


def _clear_proxy_env() -> None:
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        os.environ.pop(var, None)
    os.environ["NO_PROXY"] = "*"


def _normalize_hk_symbol(symbol: str) -> str:
    text = symbol.strip().upper()
    if text.startswith("HK"):
        text = text[2:]
    if text.endswith(".HK"):
        text = text[:-3]
    text = text.strip(".")
    if not text.isdigit():
        raise ValueError(f"无法识别港股代码: {symbol}")
    return text.zfill(5)


def _coerce_float(value: object) -> Optional[float]:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text or text in {"-", "--", "None", "nan", "NaN", "<NA>"}:
            return None
        multiplier = 1.0
        if text.endswith("亿"):
            multiplier = 100000000.0
            text = text[:-1]
        elif text.endswith("万"):
            multiplier = 10000.0
            text = text[:-1]
        if text.endswith("%"):
            text = text[:-1]
        text = text.replace(",", "")
        try:
            return float(text) * multiplier
        except ValueError:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _cache_path(cache_dir: Path, dataset: str) -> Path:
    return cache_dir / f"hk_{dataset}.csv"


def _memory_cache_key(cache_dir: Path, dataset: str, max_cache_age_days: int | None) -> tuple[str, str, int | None]:
    return dataset, str(cache_dir.resolve()), max_cache_age_days


def _write_cache(df: pd.DataFrame, cache_dir: Path, dataset: str) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(_cache_path(cache_dir, dataset), index=False, encoding="utf-8-sig")


def _read_cache(cache_dir: Path, dataset: str, max_cache_age_days: int | None = 7) -> pd.DataFrame | None:
    path = _cache_path(cache_dir, dataset)
    if not path.exists():
        return None
    if max_cache_age_days is not None:
        modified = datetime.fromtimestamp(path.stat().st_mtime)
        if datetime.now() - modified > timedelta(days=max_cache_age_days):
            return None
    return pd.read_csv(path)


def _new_html_session(*, referer: str | None = None) -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
    )
    if referer:
        session.headers["Referer"] = referer
    return session


def _looks_like_eastmoney_blocked_html(html: str) -> bool:
    if not any(marker in html for marker in _EASTMONEY_BLOCK_MARKERS):
        return False
    if any(marker in html for marker in _EASTMONEY_BUSINESS_MARKERS):
        return False
    if re.search(r"\|\s*\d{4}-\d{2}-\d{2}\s*\|\s*持股明细\s*\|", html):
        return False
    return True


def _extract_eastmoney_cookie_from_browser(browser: Optional[str] = None) -> dict[str, str]:
    candidates = ["edge", "chrome", "brave", "chromium", "firefox"] if not browser else [browser]
    errors: list[str] = []
    for candidate in candidates:
        loader = getattr(browser_cookie3, candidate, None)
        if loader is None:
            errors.append(f"{candidate}: not-supported")
            continue
        try:
            jar = loader(domain_name=".eastmoney.com")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{candidate}: {exc}")
            continue
        cookies = {
            cookie.name: cookie.value
            for cookie in jar
            if cookie.domain.endswith("eastmoney.com") and cookie.value
        }
        if cookies:
            return cookies
        errors.append(f"{candidate}: no-eastmoney-cookie")
    raise RuntimeError(
        "未在本机浏览器中找到可用的东方财富 cookie。"
        f" 探测详情: {' | '.join(errors)}"
    )


def _request_html(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def _fetch_datacenter_rows(params: dict[str, object]) -> list[dict[str, object]]:
    _clear_proxy_env()
    session = requests.Session()
    session.trust_env = False
    response = session.get(
        "http://datacenter-web.eastmoney.com/api/data/v1/get",
        params=params,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Referer": "https://data.eastmoney.com/hsgt/hsgtV2.html",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    rows = ((payload.get("result") or {}).get("data")) or []
    return rows if isinstance(rows, list) else []


def _fetch_html(url: str, *, referer: str | None = None) -> str:
    _clear_proxy_env()
    session = _new_html_session(referer=referer)
    html = _request_html(session, url)
    if not _looks_like_eastmoney_blocked_html(html) or "eastmoney.com" not in url:
        return html

    cookie_session = _new_html_session(referer=referer)
    cookie_session.cookies.update(_extract_eastmoney_cookie_from_browser())
    if referer:
        _request_html(cookie_session, referer)
    html = _request_html(cookie_session, url)
    if _looks_like_eastmoney_blocked_html(html):
        raise RuntimeError("东方财富返回滑块验证页，浏览器 cookie 兜底后仍未放行")
    return html


def _fetch_hk_connect_components_df() -> pd.DataFrame:
    _clear_proxy_env()
    session = requests.Session()
    session.trust_env = False
    response = session.get(
        "https://33.push2.eastmoney.com/api/qt/clist/get",
        params={
            "pn": "1",
            "pz": "5000",
            "po": "1",
            "np": "1",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2",
            "fid": "f12",
            "fs": "b:DLMK0146,b:DLMK0144",
            "fields": "f2,f3,f4,f5,f6,f8,f12,f14,f15,f16,f17,f18",
            "_": int(time.time() * 1000),
        },
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Referer": "https://quote.eastmoney.com/center/gridlist.html#hk_components",
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    rows = ((payload.get("data") or {}).get("diff")) or []
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    rename_map = {
        "f12": "代码",
        "f14": "名称",
        "f2": "最新价",
        "f3": "涨跌幅",
        "f4": "涨跌额",
        "f5": "成交量",
        "f6": "成交额",
        "f8": "换手率",
        "f15": "最高",
        "f16": "最低",
        "f17": "今开",
        "f18": "昨收",
    }
    df = df.rename(columns=rename_map)
    output_columns = [column for column in rename_map.values() if column in df.columns]
    return df[output_columns].copy()


def _fetch_hk_connect_components_with_cache(
    cache_dir: Path,
    use_cache: bool = True,
    max_cache_age_days: int | None = 7,
) -> tuple[pd.DataFrame, str, list[str]]:
    key = _memory_cache_key(cache_dir, HK_CONNECT_CACHE_DATASET, max_cache_age_days)
    if key in _DATASET_MEMORY_CACHE:
        df, source, notes = _DATASET_MEMORY_CACHE[key]
        return df.copy(), source, list(notes)
    if key in _DATASET_FAILURE_CACHE:
        raise RuntimeError(_DATASET_FAILURE_CACHE[key])
    notes: list[str] = []
    try:
        df = _fetch_hk_connect_components_df()
        if df.empty:
            raise RuntimeError("港股通成份行情为空")
        _write_cache(df, cache_dir, HK_CONNECT_CACHE_DATASET)
        result = (df, "eastmoney.hk_connect_components", notes)
        _DATASET_MEMORY_CACHE[key] = result
        return df.copy(), result[1], list(result[2])
    except Exception as exc:
        if not use_cache:
            raise
        cached = _read_cache(cache_dir, HK_CONNECT_CACHE_DATASET, max_cache_age_days=max_cache_age_days)
        if cached is None or cached.empty:
            _DATASET_FAILURE_CACHE[key] = str(exc)
            raise
        notes.append(f"港股通成份行情远端抓取失败，使用本地缓存: {exc}")
        result = (cached, "eastmoney.hk_connect_components.cache", notes)
        _DATASET_MEMORY_CACHE[key] = result
        return cached.copy(), result[1], list(result[2])


def _normalize_southbound_holding_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "股票代码" in df.columns:
        return df
    columns = list(df.columns)
    if len(columns) < 29:
        return df
    rename_map = {
        columns[1]: "持股日期",
        columns[4]: "股票简称",
        columns[5]: "股票代码",
        columns[10]: "持股市值",
        columns[11]: "持股数量",
        columns[16]: "当日收盘价",
        columns[17]: "当日涨跌幅",
        columns[23]: "持股数量占发行股百分比",
        columns[25]: "持股市值变化-1日",
        columns[26]: "持股市值变化-5日",
        columns[27]: "持股市值变化-10日",
    }
    return df.rename(columns=rename_map)


def _southbound_net_buy_dataset(symbol: str) -> str:
    return f"{SOUTHBOUND_NET_BUY_CACHE_DATASET}_{symbol}"


def _flatten_html_table_columns(columns: object) -> list[str]:
    flat: list[str] = []
    for column in columns:
        if isinstance(column, tuple):
            parts = [str(part).strip() for part in column if str(part).strip() and not str(part).startswith("Unnamed")]
            flat.append(" ".join(parts))
        else:
            flat.append(str(column).strip())
    return flat


def _normalize_southbound_net_buy_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df.columns = _flatten_html_table_columns(df.columns)
    rename_map: dict[str, str] = {}
    for column in df.columns:
        normalized = re.sub(r"\s+", "", str(column))
        if "日期" in normalized:
            rename_map[column] = "日期"
        elif "收盘价" in normalized:
            rename_map[column] = "收盘价"
        elif "涨跌幅" in normalized:
            rename_map[column] = "涨跌幅"
        elif "港股通净买额" in normalized and "(沪)" not in normalized and "(深)" not in normalized:
            rename_map[column] = "港股通净买额"
        elif "港股通(沪)净买额" in normalized:
            rename_map[column] = "港股通(沪)净买额"
        elif "港股通(深)净买额" in normalized:
            rename_map[column] = "港股通(深)净买额"
        elif "港股通(沪)买入额" in normalized:
            rename_map[column] = "港股通(沪)买入额"
        elif "港股通(沪)卖出额" in normalized:
            rename_map[column] = "港股通(沪)卖出额"
        elif "港股通(深)买入额" in normalized:
            rename_map[column] = "港股通(深)买入额"
        elif "港股通(深)卖出额" in normalized:
            rename_map[column] = "港股通(深)卖出额"
        elif "港股通成交金额" in normalized or "港股通成交额" in normalized:
            rename_map[column] = "港股通成交额"
    df = df.rename(columns=rename_map)
    desired_columns = [
        "日期",
        "收盘价",
        "涨跌幅",
        "港股通净买额",
        "港股通(沪)净买额",
        "港股通(沪)买入额",
        "港股通(沪)卖出额",
        "港股通(深)净买额",
        "港股通(深)买入额",
        "港股通(深)卖出额",
        "港股通成交额",
    ]
    output_columns = [column for column in desired_columns if column in df.columns]
    if "日期" in df.columns:
        df = df[df["日期"].astype(str).str.match(r"\d{4}-\d{2}-\d{2}", na=False)].copy()
        if not df.empty:
            df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
            df = df.dropna(subset=["日期"]).sort_values("日期", ascending=False)
            df["日期"] = df["日期"].dt.date
    return df[output_columns].reset_index(drop=True) if output_columns else df.reset_index(drop=True)


def _parse_southbound_net_buy_text_rows(html: str) -> pd.DataFrame:
    pattern = re.compile(
        r"\|\s*(?P<date>\d{4}-\d{2}-\d{2})\s*"
        r"\|\s*持股明细\s*"
        r"\|\s*(?P<close>[^|]+?)\s*"
        r"\|\s*(?P<pct>[^|]+?)\s*"
        r"\|\s*(?P<net>[^|]+?)\s*"
        r"\|\s*(?P<sh_rank>[^|]+?)\s*"
        r"\|\s*(?P<sh_net>[^|]+?)\s*"
        r"\|\s*(?P<sh_buy>[^|]+?)\s*"
        r"\|\s*(?P<sh_sell>[^|]+?)\s*"
        r"\|\s*(?P<sz_rank>[^|]+?)\s*"
        r"\|\s*(?P<sz_net>[^|]+?)\s*"
        r"\|\s*(?P<sz_buy>[^|]+?)\s*"
        r"\|\s*(?P<sz_sell>[^|]+?)\s*"
        r"\|\s*(?P<turnover>[^|]+?)\s*\|"
    )
    rows = [
        {
            "日期": match.group("date"),
            "收盘价": match.group("close"),
            "涨跌幅": match.group("pct"),
            "港股通净买额": match.group("net"),
            "港股通(沪)净买额": match.group("sh_net"),
            "港股通(沪)买入额": match.group("sh_buy"),
            "港股通(沪)卖出额": match.group("sh_sell"),
            "港股通(深)净买额": match.group("sz_net"),
            "港股通(深)买入额": match.group("sz_buy"),
            "港股通(深)卖出额": match.group("sz_sell"),
            "港股通成交额": match.group("turnover"),
        }
        for match in pattern.finditer(html)
    ]
    if not rows:
        return pd.DataFrame()
    return _normalize_southbound_net_buy_columns(pd.DataFrame(rows))


def _parse_southbound_net_buy_html(html: str) -> pd.DataFrame:
    try:
        tables = pd.read_html(StringIO(html))
    except ValueError:
        tables = []
    for table in tables:
        normalized = _normalize_southbound_net_buy_columns(table)
        if normalized.empty:
            continue
        if "日期" in normalized.columns and "港股通净买额" in normalized.columns:
            return normalized
    text_rows = _parse_southbound_net_buy_text_rows(html)
    if not text_rows.empty:
        return text_rows
    return pd.DataFrame()


def _fetch_hk_southbound_net_buy_df_remote(symbol: str) -> pd.DataFrame:
    normalized_symbol = _normalize_hk_symbol(symbol)
    rows = _fetch_datacenter_rows(
        {
            "reportName": "RPT_HK_DEAL_RANK",
            "columns": "ALL",
            "pageNumber": 1,
            "pageSize": 100,
            "sortColumns": "TRADE_DATE",
            "sortTypes": -1,
            "source": "WEB",
            "client": "WEB",
            "filter": f'(SECURITY_CODE="{normalized_symbol}")',
        }
    )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    rename_map = {
        "TRADE_DATE": "日期",
        "CLOSE_PRICE": "收盘价",
        "CHANGE_RATE": "涨跌幅",
        "HK_NET_BUYAMT": "港股通净买额",
        "HKSH_NET_BUYAMT": "港股通(沪)净买额",
        "HKSH_BUY_AMT": "港股通(沪)买入额",
        "HKSH_SELL_AMT": "港股通(沪)卖出额",
        "HKSZ_NET_BUYAMT": "港股通(深)净买额",
        "HKSZ_BUY_AMT": "港股通(深)买入额",
        "HKSZ_SELL_AMT": "港股通(深)卖出额",
        "HK_DEAL_AMT": "港股通成交额",
    }
    output_columns = [column for column in rename_map if column in df.columns]
    if not output_columns:
        return pd.DataFrame()
    return _normalize_southbound_net_buy_columns(df[output_columns].rename(columns=rename_map))


def _fetch_hk_southbound_net_buy_df(symbol: str) -> pd.DataFrame:
    normalized_symbol = _normalize_hk_symbol(symbol)
    df = _fetch_hk_southbound_net_buy_df_remote(normalized_symbol)
    if not df.empty:
        return df

    html = _fetch_html(
        f"https://data.eastmoney.com/hsgt/{normalized_symbol}.html",
        referer="https://data.eastmoney.com/hsgt/hsgtV2.html",
    )
    df = _parse_southbound_net_buy_html(html)
    if df.empty:
        raise RuntimeError(f"东方财富港股通成交榜页面未返回 {normalized_symbol} 的净买额表格")
    return df


def _fetch_hk_southbound_net_buy_with_cache(
    symbol: str,
    cache_dir: Path,
    use_cache: bool = True,
    max_cache_age_days: int | None = 7,
) -> tuple[pd.DataFrame, str, list[str]]:
    normalized_symbol = _normalize_hk_symbol(symbol)
    dataset = _southbound_net_buy_dataset(normalized_symbol)
    key = _memory_cache_key(cache_dir, dataset, max_cache_age_days)
    if key in _DATASET_MEMORY_CACHE:
        df, source, notes = _DATASET_MEMORY_CACHE[key]
        return df.copy(), source, list(notes)
    notes: list[str] = []
    try:
        df = _fetch_hk_southbound_net_buy_df(normalized_symbol)
        _write_cache(df, cache_dir, dataset)
        result = (df, "eastmoney.southbound_net_buy", notes)
        _DATASET_MEMORY_CACHE[key] = result
        return df.copy(), result[1], list(result[2])
    except Exception as exc:
        if not use_cache:
            raise
        cached = _read_cache(cache_dir, dataset, max_cache_age_days=max_cache_age_days)
        if cached is None or cached.empty:
            raise
        notes.append(f"南向净买额远端抓取失败，使用本地缓存: {exc}")
        result = (cached, "eastmoney.southbound_net_buy.cache", notes)
        _DATASET_MEMORY_CACHE[key] = result
        return cached.copy(), result[1], list(result[2])


def _fetch_hk_southbound_holding_df() -> pd.DataFrame:
    ctx = mp.get_context("spawn")
    queue: mp.Queue = ctx.Queue()
    process = ctx.Process(target=_fetch_hk_southbound_holding_worker, args=(queue,))
    process.start()
    process.join(REQUEST_TIMEOUT_SECONDS)
    if process.is_alive():
        process.terminate()
        process.join(2)
        raise TimeoutError(f"南向持股统计抓取超过 {REQUEST_TIMEOUT_SECONDS} 秒")
    if queue.empty():
        raise RuntimeError("南向持股统计抓取无返回")
    status, payload = queue.get()
    if status == "ok":
        return payload
    raise RuntimeError(payload)


def _fetch_hk_southbound_holding_worker(queue: mp.Queue) -> None:
    try:
        queue.put(("ok", _fetch_hk_southbound_holding_df_remote()))
    except Exception as exc:
        queue.put(("error", f"{type(exc).__name__}: {exc}"))


def _fetch_hk_southbound_holding_df_remote() -> pd.DataFrame:
    _clear_proxy_env()
    session = requests.Session()
    session.trust_env = False
    params = {
        "sortColumns": "TRADE_DATE",
        "sortTypes": "-1",
        "pageSize": "5000",
        "pageNumber": "1",
        "columns": "ALL",
        "source": "WEB",
        "client": "WEB",
        "filter": '(INTERVAL_TYPE="1")(RN=1)',
        "reportName": "RPT_MUTUAL_STOCK_HOLDRANKS",
    }
    response = session.get("http://datacenter-web.eastmoney.com/api/data/v1/get", params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()
    result = payload.get("result") or {}
    rows = result.get("data") or []
    pages = int(result.get("pages") or 1)
    for page in range(2, pages + 1):
        params["pageNumber"] = str(page)
        page_response = session.get("http://datacenter-web.eastmoney.com/api/data/v1/get", params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        page_response.raise_for_status()
        page_payload = page_response.json()
        rows.extend(((page_payload.get("result") or {}).get("data")) or [])
    if not rows:
        return pd.DataFrame()
    df = _normalize_southbound_holding_columns(pd.DataFrame(rows))
    desired_columns = [
        "持股日期",
        "股票代码",
        "股票简称",
        "当日收盘价",
        "当日涨跌幅",
        "持股数量",
        "持股市值",
        "持股数量占发行股百分比",
        "持股市值变化-1日",
        "持股市值变化-5日",
        "持股市值变化-10日",
    ]
    output_columns = [column for column in desired_columns if column in df.columns]
    return df[output_columns].copy() if output_columns else df.copy()


def _fetch_hk_southbound_holding_with_cache(
    cache_dir: Path,
    use_cache: bool = True,
    max_cache_age_days: int | None = 7,
) -> tuple[pd.DataFrame, str, list[str]]:
    key = _memory_cache_key(cache_dir, SOUTHBOUND_HOLDING_CACHE_DATASET, max_cache_age_days)
    if key in _DATASET_MEMORY_CACHE:
        df, source, notes = _DATASET_MEMORY_CACHE[key]
        return df.copy(), source, list(notes)
    notes: list[str] = []
    try:
        df = _fetch_hk_southbound_holding_df()
        if df.empty:
            raise RuntimeError("南向持股统计为空")
        _write_cache(df, cache_dir, SOUTHBOUND_HOLDING_CACHE_DATASET)
        result = (df, "eastmoney.southbound_holding", notes)
        _DATASET_MEMORY_CACHE[key] = result
        return df.copy(), result[1], list(result[2])
    except Exception as exc:
        if not use_cache:
            raise
        cached = _read_cache(cache_dir, SOUTHBOUND_HOLDING_CACHE_DATASET, max_cache_age_days=max_cache_age_days)
        if cached is None or cached.empty:
            raise
        notes.append(f"南向持股统计远端抓取失败，使用本地缓存: {exc}")
        result = (cached, "eastmoney.southbound_holding.cache", notes)
        _DATASET_MEMORY_CACHE[key] = result
        return cached.copy(), result[1], list(result[2])


def _parse_hkex_short_selling_text(text: str, trade_date: date | None = None) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    date_match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    parsed_date = trade_date
    if parsed_date is None and date_match:
        day, month, year = date_match.groups()
        parsed_date = date(int(year), int(month), int(day))
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not re.match(r"^\d{1,5}\s+", line):
            continue
        match = re.match(r"^(\d{1,5})\s+(.+?)\s+([\d,]+)\s+([\d,]+(?:\.\d+)?)\s*$", line)
        if not match:
            continue
        code, stock_name, short_sell_shares, short_sell_turnover = match.groups()
        rows.append(
            {
                "日期": parsed_date,
                "股票代码": code.zfill(5),
                "股票简称": " ".join(stock_name.split()),
                "沽空股数": _coerce_float(short_sell_shares),
                "沽空成交额": _coerce_float(short_sell_turnover),
            }
        )
    return pd.DataFrame(rows)


def _fetch_hkex_short_selling_df(trade_date: date | None = None) -> pd.DataFrame:
    _clear_proxy_env()
    session = requests.Session()
    session.trust_env = False
    response = session.get(
        "https://www.hkex.com.hk/eng/stat/smstat/ssturnover/ncms/ashtmain.htm",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    df = _parse_hkex_short_selling_text(response.text, trade_date=trade_date)
    if df.empty:
        raise RuntimeError("HKEX 日终沽空统计未返回个股明细")
    return df


def _fetch_hkex_short_selling_with_cache(
    cache_dir: Path,
    trade_date: date | None = None,
    use_cache: bool = True,
    max_cache_age_days: int | None = 7,
) -> tuple[pd.DataFrame, str, list[str]]:
    key = _memory_cache_key(cache_dir, HKEX_SHORT_SELLING_CACHE_DATASET, max_cache_age_days)
    if key in _DATASET_MEMORY_CACHE:
        df, source, notes = _DATASET_MEMORY_CACHE[key]
        return df.copy(), source, list(notes)
    if key in _DATASET_FAILURE_CACHE:
        raise RuntimeError(_DATASET_FAILURE_CACHE[key])
    notes: list[str] = []
    try:
        df = _fetch_hkex_short_selling_df(trade_date=trade_date)
        _write_cache(df, cache_dir, HKEX_SHORT_SELLING_CACHE_DATASET)
        result = (df, "hkex.short_selling_turnover", notes)
        _DATASET_MEMORY_CACHE[key] = result
        return df.copy(), result[1], list(result[2])
    except Exception as exc:
        if not use_cache:
            raise
        cached = _read_cache(cache_dir, HKEX_SHORT_SELLING_CACHE_DATASET, max_cache_age_days=max_cache_age_days)
        if cached is None or cached.empty:
            _DATASET_FAILURE_CACHE[key] = str(exc)
            raise
        notes.append(f"HKEX 日终沽空统计远端抓取失败，使用本地缓存: {exc}")
        result = (cached, "hkex.short_selling_turnover.cache", notes)
        _DATASET_MEMORY_CACHE[key] = result
        return cached.copy(), result[1], list(result[2])


def _match_symbol_row(df: pd.DataFrame, code_column: str, symbol: str) -> pd.Series | None:
    if code_column not in df.columns:
        return None
    matched = df[df[code_column].astype(str).str.zfill(5) == symbol]
    if matched.empty:
        return None
    return matched.iloc[0]


def _coerce_date(value: object) -> date | None:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def _match_trade_date_row(df: pd.DataFrame, date_column: str, trade_date: date | None) -> pd.Series | None:
    if df.empty or date_column not in df.columns:
        return None
    if trade_date is None:
        return df.iloc[0]
    parsed_dates = pd.to_datetime(df[date_column], errors="coerce")
    matched = df[parsed_dates.dt.date == trade_date]
    if matched.empty:
        return None
    return matched.iloc[0]


def fetch_hk_capital_flow_snapshot(
    symbol: str,
    name: str,
    trade_date: Optional[date] = None,
    source: str = "eastmoney.hk_connect_components",
    use_cache: bool = True,
    cache_dir: Path | None = None,
    max_cache_age_days: int | None = 7,
) -> CapitalFlowSnapshot:
    """Fetch a standardized HK capital-flow snapshot.

    V1 uses Eastmoney HK Stock Connect component quotes, Eastmoney southbound
    holding and top-turnover pages, and HKEX short-selling turnover data.
    """

    normalized_symbol = _normalize_hk_symbol(symbol)
    actual_cache_dir = cache_dir or DEFAULT_CACHE_DIR
    notes: list[str] = []
    sources: list[str] = []
    raw_refs: list[str] = []
    errors: list[str] = []
    turnover: float | None = None
    turnover_rate: float | None = None
    southbound_net_buy: float | None = None
    southbound_holding_change: float | None = None
    short_sell_turnover: float | None = None
    short_sell_ratio: float | None = None
    snapshot_trade_date = trade_date

    try:
        components_df, components_source, component_notes = _fetch_hk_connect_components_with_cache(
            cache_dir=actual_cache_dir,
            use_cache=use_cache,
            max_cache_age_days=max_cache_age_days,
        )
        notes.extend(component_notes)
        component_row = _match_symbol_row(components_df, "代码", normalized_symbol)
        if component_row is None:
            raise RuntimeError(f"港股通成份行情未找到 {normalized_symbol} {name}")
        turnover = _coerce_float(component_row.get("成交额"))
        turnover_rate = _coerce_float(component_row.get("换手率"))
        sources.append(components_source)
        raw_refs.append(f"{components_source}:{_cache_path(actual_cache_dir, HK_CONNECT_CACHE_DATASET)}")
    except Exception as exc:
        errors.append(f"港股通成份行情不可用: {exc}")

    try:
        net_buy_df, net_buy_source, net_buy_notes = _fetch_hk_southbound_net_buy_with_cache(
            symbol=normalized_symbol,
            cache_dir=actual_cache_dir,
            use_cache=use_cache,
            max_cache_age_days=max_cache_age_days,
        )
        notes.extend(net_buy_notes)
        net_buy_row = _match_trade_date_row(net_buy_df, "日期", trade_date)
        if net_buy_row is None:
            if trade_date is None:
                raise RuntimeError(f"南向净买额未找到 {normalized_symbol} {name}")
            raise RuntimeError(f"南向净买额未找到 {normalized_symbol} {name} 在 {trade_date.isoformat()} 的上榜记录")
        southbound_net_buy = _coerce_float(net_buy_row.get("港股通净买额"))
        snapshot_trade_date = snapshot_trade_date or _coerce_date(net_buy_row.get("日期"))
        sources.append(net_buy_source)
        raw_refs.append(f"{net_buy_source}:{_cache_path(actual_cache_dir, _southbound_net_buy_dataset(normalized_symbol))}")
    except Exception as exc:
        errors.append(f"南向净买额不可用: {exc}")

    try:
        holding_df, holding_source, holding_notes = _fetch_hk_southbound_holding_with_cache(
            cache_dir=actual_cache_dir,
            use_cache=use_cache,
            max_cache_age_days=max_cache_age_days,
        )
        notes.extend(holding_notes)
        holding_row = _match_symbol_row(holding_df, "股票代码", normalized_symbol)
        if holding_row is None:
            raise RuntimeError(f"南向持股统计未找到 {normalized_symbol} {name}")
        southbound_holding_change = _coerce_float(holding_row.get("持股市值变化-1日"))
        snapshot_trade_date = snapshot_trade_date or _coerce_date(holding_row.get("持股日期"))
        sources.append(holding_source)
        raw_refs.append(f"{holding_source}:{_cache_path(actual_cache_dir, SOUTHBOUND_HOLDING_CACHE_DATASET)}")
    except Exception as exc:
        errors.append(f"南向持股统计不可用: {exc}")

    try:
        short_df, short_source, short_notes = _fetch_hkex_short_selling_with_cache(
            cache_dir=actual_cache_dir,
            trade_date=trade_date,
            use_cache=use_cache,
            max_cache_age_days=max_cache_age_days,
        )
        notes.extend(short_notes)
        short_row = _match_symbol_row(short_df, "股票代码", normalized_symbol)
        if short_row is None:
            raise RuntimeError(f"HKEX 日终沽空统计未找到 {normalized_symbol} {name}")
        short_sell_turnover = _coerce_float(short_row.get("沽空成交额"))
        if turnover and short_sell_turnover is not None:
            short_sell_ratio = short_sell_turnover / turnover * 100
        snapshot_trade_date = snapshot_trade_date or _coerce_date(short_row.get("日期"))
        sources.append(short_source)
        raw_refs.append(f"{short_source}:{_cache_path(actual_cache_dir, HKEX_SHORT_SELLING_CACHE_DATASET)}")
    except Exception as exc:
        errors.append(f"HKEX 日终沽空统计不可用: {exc}")

    if not sources:
        raise RuntimeError("；".join(errors))
    actual_source = "+".join(sources) if source == "eastmoney.hk_connect_components" else source
    if turnover is not None or turnover_rate is not None:
        notes.append("港股 V1 使用港股通成份行情的成交额/换手率作为量能线索")
    if southbound_net_buy is not None:
        notes.append("南向净买额来自东方财富港股通个股成交榜历史，仅在个股上榜交易日可用")
    if southbound_holding_change is not None:
        notes.append("南向持股变化来自东方财富沪深港通持股统计的1日持股市值变化")
    if short_sell_turnover is not None:
        notes.append("沽空成交额来自 HKEX 日终沽空统计；沽空比例用沽空成交额/成交额计算")
    if errors:
        notes.extend(errors)
    if southbound_net_buy is None:
        notes.append("个股南向净买额缺失时，仅能依赖南向持股变化和成交/沽空线索")
    if short_sell_turnover is None and turnover is not None:
        notes.append("沽空比例依赖 HKEX 沽空成交额与成交额同时可用")

    return CapitalFlowSnapshot(
        symbol=normalized_symbol,
        name=name,
        market="HK",
        trade_date=snapshot_trade_date or date.today(),
        source=actual_source,
        updated_at=datetime.now(),
        turnover=turnover,
        turnover_rate=turnover_rate,
        southbound_net_buy=southbound_net_buy,
        southbound_holding_change=southbound_holding_change,
        short_sell_ratio=short_sell_ratio,
        short_sell_turnover=short_sell_turnover,
        notes="；".join(notes),
        raw_payload_ref=";".join(raw_refs) if raw_refs else None,
    )