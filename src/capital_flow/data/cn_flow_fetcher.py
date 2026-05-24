"""A-share capital-flow data source adapters."""

from __future__ import annotations

import ast
from datetime import date, datetime, timedelta
import os
from pathlib import Path
import time
from typing import Callable, Optional, TypeVar

import pandas as pd
import requests

from capital_flow.models.snapshot import CapitalFlowSnapshot


T = TypeVar("T")
ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CACHE_DIR = ROOT / "data" / "_meta" / "capital_flow_cache"
FUND_FLOW_CACHE_DATASET = "eastmoney_fund_flow"
TENCENT_TICK_CACHE_DATASET = "tencent_tick_fallback"
TENCENT_TICK_MAX_PAGES = 12
_THS_FALLBACK_DF_CACHE: dict[str, pd.DataFrame] = {}
_THS_PERIOD_CACHE_KEYS = {
    "即时": "realtime",
    "3日排行": "3d",
    "5日排行": "5d",
    "10日排行": "10d",
}


def _clear_proxy_env() -> None:
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        os.environ.pop(var, None)
    os.environ["NO_PROXY"] = "*"


def _normalize_cn_symbol(symbol: str) -> str:
    text = symbol.strip().upper()
    if text.startswith(("SH", "SZ", "BJ")):
        text = text[2:]
    if text.endswith((".SH", ".SZ", ".BJ")):
        text = text[:-3]
    if not text.isdigit():
        raise ValueError(f"无法识别 A 股代码: {symbol}")
    return text.zfill(6)


def _akshare_market(symbol: str) -> str:
    if symbol.startswith(("6", "9")):
        return "sh"
    if symbol.startswith(("8", "4")):
        return "bj"
    return "sz"


def _tencent_symbol(symbol: str) -> str:
    return f"{_akshare_market(symbol)}{symbol}"


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


def _fetch_cn_fund_flow_df(symbol: str) -> pd.DataFrame:
    _clear_proxy_env()
    market_map = {"sh": 1, "sz": 0, "bj": 0}
    session = requests.Session()
    session.trust_env = False
    response = session.get(
        "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get",
        params={
            "lmt": "0",
            "klt": "101",
            "secid": f"{market_map[_akshare_market(symbol)]}.{symbol}",
            "fields1": "f1,f2,f3,f7",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
            "ut": "b2884a393a59ad64002292a3e90d46a5",
            "_": int(time.time() * 1000),
        },
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Referer": "https://data.eastmoney.com/zjlx/detail.html",
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    klines = (payload.get("data") or {}).get("klines") or []
    if not klines:
        return pd.DataFrame()

    flow_df = pd.DataFrame([item.split(",") for item in klines])
    flow_df.columns = [
        "日期",
        "主力净流入-净额",
        "小单净流入-净额",
        "中单净流入-净额",
        "大单净流入-净额",
        "超大单净流入-净额",
        "主力净流入-净占比",
        "小单净流入-净占比",
        "中单净流入-净占比",
        "大单净流入-净占比",
        "超大单净流入-净占比",
        "收盘价",
        "涨跌幅",
        "_unused_1",
        "_unused_2",
    ]
    output_columns = [
        "日期",
        "收盘价",
        "涨跌幅",
        "主力净流入-净额",
        "主力净流入-净占比",
        "超大单净流入-净额",
        "超大单净流入-净占比",
        "大单净流入-净额",
        "大单净流入-净占比",
        "中单净流入-净额",
        "中单净流入-净占比",
        "小单净流入-净额",
        "小单净流入-净占比",
    ]
    for column in output_columns:
        if column != "日期":
            flow_df[column] = pd.to_numeric(flow_df[column], errors="coerce")
    flow_df["日期"] = pd.to_datetime(flow_df["日期"], errors="coerce").dt.date
    return flow_df[output_columns]


def _fetch_cn_daily_price_df(symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
    _clear_proxy_env()
    import akshare as ak  # type: ignore

    return ak.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
        adjust="",
    )


def _fetch_ths_individual_fund_flow_df(period: str) -> pd.DataFrame:
    cached_df = _THS_FALLBACK_DF_CACHE.get(period)
    if cached_df is not None:
        return cached_df.copy()

    _clear_proxy_env()
    import akshare as ak  # type: ignore

    df = ak.stock_fund_flow_individual(symbol=period)
    _THS_FALLBACK_DF_CACHE[period] = df.copy()
    return df


def _fetch_tencent_tick_df(symbol: str) -> pd.DataFrame:
    _clear_proxy_env()
    session = requests.Session()
    session.trust_env = False
    rows: list[list[object]] = []
    for page in range(TENCENT_TICK_MAX_PAGES):
        response = session.get(
            "http://stock.gtimg.cn/data/index.php",
            params={
                "appn": "detail",
                "action": "data",
                "c": _tencent_symbol(symbol),
                "p": page,
            },
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
            },
            timeout=15,
        )
        response.raise_for_status()
        text_data = response.text
        start = text_data.find("[")
        if start < 0:
            break
        payload = ast.literal_eval(text_data[start:])
        if len(payload) < 2 or not payload[1]:
            break
        page_rows = pd.DataFrame(str(payload[1]).split("|")).iloc[:, 0].str.split("/", expand=True)
        if page_rows.empty:
            break
        rows.extend(page_rows.values.tolist())
    if not rows:
        return pd.DataFrame()

    tick_df = pd.DataFrame(rows).iloc[:, 1:].copy()
    tick_df.columns = ["成交时间", "成交价格", "价格变动", "成交量", "成交金额", "性质"]
    property_map = {"S": "卖盘", "B": "买盘", "M": "中性盘"}
    tick_df["性质"] = tick_df["性质"].map(property_map).fillna(tick_df["性质"])
    for column in ("成交价格", "价格变动", "成交量", "成交金额"):
        tick_df[column] = pd.to_numeric(tick_df[column], errors="coerce")
    return tick_df


def _with_retries(fetcher: Callable[[], T], label: str, attempts: int = 3) -> T:
    last_error: Optional[Exception] = None
    for attempt in range(attempts):
        try:
            return fetcher()
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.5 * (attempt + 1))
    assert last_error is not None
    raise RuntimeError(f"{label} 抓取失败（已重试{attempts}次）: {last_error}") from last_error


def _cache_path(symbol: str, dataset: str, cache_dir: Path) -> Path:
    return cache_dir / f"{symbol}_{dataset}.csv"


def _write_cache(df: pd.DataFrame, symbol: str, dataset: str, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(symbol=symbol, dataset=dataset, cache_dir=cache_dir)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def _read_cache(symbol: str, dataset: str, cache_dir: Path) -> pd.DataFrame:
    path = _cache_path(symbol=symbol, dataset=dataset, cache_dir=cache_dir)
    if not path.exists():
        raise FileNotFoundError(f"未找到资金面缓存: {path}")
    return pd.read_csv(path)


def _ths_cache_path(period: str, cache_dir: Path) -> Path:
    cache_key = _THS_PERIOD_CACHE_KEYS.get(period, period)
    return cache_dir / f"ths_fund_flow_{cache_key}.csv"


def _write_ths_cache(df: pd.DataFrame, period: str, cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _ths_cache_path(period=period, cache_dir=cache_dir)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def _read_ths_cache(period: str, cache_dir: Path) -> pd.DataFrame:
    path = _ths_cache_path(period=period, cache_dir=cache_dir)
    if not path.exists():
        raise FileNotFoundError(f"未找到同花顺资金流缓存: {path}")
    return pd.read_csv(path)


def _fetch_ths_period_with_cache(
    period: str,
    label: str,
    cache_dir: Path,
    use_cache: bool,
) -> tuple[pd.DataFrame, Optional[str]]:
    try:
        df = _with_retries(lambda: _fetch_ths_individual_fund_flow_df(period), label)
        _write_ths_cache(df, period=period, cache_dir=cache_dir)
        return df, None
    except Exception as exc:
        if not use_cache:
            raise
        try:
            cached_df = _read_ths_cache(period=period, cache_dir=cache_dir)
            return cached_df, f"{label}远端抓取失败，使用同花顺本地缓存: {exc}"
        except Exception as cache_exc:
            raise RuntimeError(f"{exc}; 同花顺缓存回退不可用: {cache_exc}") from exc


def _row_for_symbol(df: pd.DataFrame, symbol: str, column: str = "股票代码") -> Optional[pd.Series]:
    if column not in df.columns:
        return None
    matches = df[df[column].astype(str).str.strip().str.zfill(6) == symbol]
    if matches.empty:
        return None
    return matches.iloc[0]


def _latest_daily_trade_date(symbol: str, reference_date: Optional[date]) -> tuple[date, Optional[str]]:
    end_date = reference_date or date.today()
    start_date = end_date - timedelta(days=45)
    try:
        daily_df = _with_retries(
            lambda: _fetch_cn_daily_price_df(symbol=symbol, start_date=start_date, end_date=end_date),
            "A股日线日期定位",
        )
        row = _latest_row_on_or_before(daily_df, end_date)
        return pd.Timestamp(row["日期"]).date(), None
    except Exception as exc:
        return end_date, f"fallback 日期定位失败，使用参考日期 {end_date.isoformat()}: {exc}"


def _fetch_ths_fallback_fund_flow_df(
    symbol: str,
    trade_date: Optional[date],
    cache_dir: Path,
    use_cache: bool,
) -> tuple[pd.DataFrame, str]:
    fallback_warnings: list[str] = []
    today_df, today_cache_warning = _fetch_ths_period_with_cache("即时", "同花顺即时资金流", cache_dir, use_cache)
    if today_cache_warning:
        fallback_warnings.append(today_cache_warning)
    today_row = _row_for_symbol(today_df, symbol)
    if today_row is None:
        raise RuntimeError(f"同花顺即时资金流未找到标的: {symbol}")

    period_values: dict[str, Optional[float]] = {}
    for period, output_name in (("3日排行", "3d"), ("5日排行", "5d"), ("10日排行", "10d")):
        try:
            period_df, period_cache_warning = _fetch_ths_period_with_cache(
                period,
                f"同花顺{period}资金流",
                cache_dir,
                use_cache,
            )
            if period_cache_warning:
                fallback_warnings.append(period_cache_warning)
            period_row = _row_for_symbol(period_df, symbol)
            period_values[output_name] = _coerce_float(period_row.get("资金流入净额")) if period_row is not None else None
        except Exception as exc:
            period_values[output_name] = None
            fallback_warnings.append(f"同花顺{period}补充失败: {exc}")

    resolved_trade_date, date_warning = _latest_daily_trade_date(symbol, trade_date)
    if date_warning:
        fallback_warnings.append(date_warning)

    flow_df = pd.DataFrame(
        [
            {
                "日期": resolved_trade_date,
                "收盘价": _coerce_float(today_row.get("最新价")),
                "涨跌幅": _coerce_float(today_row.get("涨跌幅")),
                "主力净流入-净额": _coerce_float(today_row.get("净额")),
                "主力净流入_3d_fallback": period_values.get("3d"),
                "主力净流入_5d_fallback": period_values.get("5d"),
                "主力净流入_10d_fallback": period_values.get("10d"),
            }
        ]
    )
    warning = "同花顺 fallback 使用资金净额替代主力净流入口径，缺少大单拆分"
    if fallback_warnings:
        warning += "；" + "；".join(fallback_warnings)
    return flow_df, warning


def _aggregate_tencent_tick_fallback_df(tick_df: pd.DataFrame, trade_date: date) -> pd.DataFrame:
    if tick_df.empty:
        raise RuntimeError("腾讯分笔成交数据为空")
    required_columns = {"成交价格", "成交金额", "性质"}
    missing_columns = required_columns - set(tick_df.columns)
    if missing_columns:
        raise RuntimeError(f"腾讯分笔成交数据缺少列: {sorted(missing_columns)}")

    working_df = tick_df.copy()
    working_df["成交金额"] = pd.to_numeric(working_df["成交金额"], errors="coerce")
    working_df["成交价格"] = pd.to_numeric(working_df["成交价格"], errors="coerce")
    working_df = working_df[pd.notna(working_df["成交金额"])]
    if working_df.empty:
        raise RuntimeError("腾讯分笔成交数据没有可用成交金额")

    buy_amount = working_df.loc[working_df["性质"] == "买盘", "成交金额"].sum()
    sell_amount = working_df.loc[working_df["性质"] == "卖盘", "成交金额"].sum()
    large_order_df = working_df[working_df["成交金额"] >= 200_000]
    large_buy_amount = large_order_df.loc[large_order_df["性质"] == "买盘", "成交金额"].sum()
    large_sell_amount = large_order_df.loc[large_order_df["性质"] == "卖盘", "成交金额"].sum()
    latest_price = working_df["成交价格"].dropna().iloc[-1] if not working_df["成交价格"].dropna().empty else None

    return pd.DataFrame(
        [
            {
                "日期": trade_date,
                "收盘价": latest_price,
                "主力净流入-净额": float(buy_amount - sell_amount),
                "大单净流入-净额": float(large_buy_amount - large_sell_amount),
            }
        ]
    )


def _fetch_tencent_tick_fallback_fund_flow_df(
    symbol: str,
    trade_date: Optional[date],
    cache_dir: Path,
    use_cache: bool,
    max_cache_age_days: Optional[int],
) -> tuple[pd.DataFrame, str]:
    resolved_trade_date, date_warning = _latest_daily_trade_date(symbol, trade_date)
    try:
        tick_df = _with_retries(lambda: _fetch_tencent_tick_df(symbol), "腾讯分笔成交")
        flow_df = _aggregate_tencent_tick_fallback_df(tick_df, resolved_trade_date)
        _write_cache(flow_df, symbol=symbol, dataset=TENCENT_TICK_CACHE_DATASET, cache_dir=cache_dir)
        warning = "腾讯分笔成交 fallback 使用买盘成交金额-卖盘成交金额近似主力净流入，缺少多日窗口和大小单完整拆分"
        if date_warning:
            warning += f"；{date_warning}"
        return flow_df, warning
    except Exception as exc:
        if not use_cache:
            raise
        try:
            cached_df = _read_cache(symbol=symbol, dataset=TENCENT_TICK_CACHE_DATASET, cache_dir=cache_dir)
            cached_trade_date = _validate_cache_age(cached_df, trade_date=trade_date, max_cache_age_days=max_cache_age_days)
            warning = (
                "腾讯分笔成交远端抓取失败，使用本地缓存 "
                f"{cached_trade_date.isoformat()}: {exc}；腾讯分笔成交 fallback 使用买盘成交金额-卖盘成交金额近似主力净流入"
            )
            return cached_df, warning
        except Exception as cache_exc:
            raise RuntimeError(f"{exc}; 腾讯分笔缓存回退不可用: {cache_exc}") from exc


def _latest_cache_trade_date(df: pd.DataFrame, trade_date: Optional[date] = None) -> date:
    row = _latest_row_on_or_before(df, trade_date)
    return pd.Timestamp(row["日期"]).date()


def _validate_cache_age(
    df: pd.DataFrame,
    trade_date: Optional[date],
    max_cache_age_days: Optional[int],
) -> date:
    latest_trade_date = _latest_cache_trade_date(df, trade_date)
    if max_cache_age_days is None:
        return latest_trade_date
    reference_date = trade_date or date.today()
    age_days = (reference_date - latest_trade_date).days
    if age_days < 0:
        return latest_trade_date
    if age_days > max_cache_age_days:
        raise RuntimeError(
            f"资金面缓存已过期: latest={latest_trade_date.isoformat()}, "
            f"reference={reference_date.isoformat()}, max_age_days={max_cache_age_days}"
        )
    return latest_trade_date


def _fetch_fund_flow_with_cache(
    symbol: str,
    trade_date: Optional[date],
    use_cache: bool,
    use_fallback: bool,
    cache_dir: Path,
    max_cache_age_days: Optional[int],
) -> tuple[pd.DataFrame, str, Optional[str]]:
    remote_error: Optional[Exception] = None
    try:
        fund_flow_df = _with_retries(
            lambda: _fetch_cn_fund_flow_df(symbol),
            "A股个股资金流",
        )
        if fund_flow_df.empty:
            raise RuntimeError(f"未取到 A 股资金流数据: {symbol}")
        _write_cache(fund_flow_df, symbol=symbol, dataset=FUND_FLOW_CACHE_DATASET, cache_dir=cache_dir)
        return fund_flow_df, "eastmoney.fund_flow", None
    except Exception as exc:
        remote_error = exc
        if not use_cache:
            if not use_fallback:
                raise
        else:
            try:
                cached_df = _read_cache(symbol=symbol, dataset=FUND_FLOW_CACHE_DATASET, cache_dir=cache_dir)
                cached_trade_date = _validate_cache_age(
                    cached_df,
                    trade_date=trade_date,
                    max_cache_age_days=max_cache_age_days,
                )
                warning = f"A股个股资金流远端抓取失败，使用本地缓存 {cached_trade_date.isoformat()}: {exc}"
                return cached_df, "eastmoney.fund_flow.cache", warning
            except Exception as cache_exc:
                if not use_fallback:
                    raise RuntimeError(f"{exc}; 缓存回退不可用: {cache_exc}") from exc

    if use_fallback:
        try:
            fallback_df, fallback_warning = _fetch_ths_fallback_fund_flow_df(symbol, trade_date, cache_dir, use_cache)
            warning = f"A股个股资金流远端抓取失败，使用同花顺低置信度fallback: {remote_error}; {fallback_warning}"
            return fallback_df, "ths.fund_flow.fallback", warning
        except Exception as ths_fallback_exc:
            try:
                tencent_df, tencent_warning = _fetch_tencent_tick_fallback_fund_flow_df(
                    symbol,
                    trade_date,
                    cache_dir,
                    use_cache,
                    max_cache_age_days,
                )
                warning = (
                    f"A股个股资金流远端抓取失败，使用腾讯分笔低置信度fallback: {remote_error}; "
                    f"同花顺fallback不可用: {ths_fallback_exc}; {tencent_warning}"
                )
                return tencent_df, "tencent.tick.fallback", warning
            except Exception as tencent_fallback_exc:
                raise RuntimeError(
                    f"{remote_error}; fallback回退不可用: 同花顺: {ths_fallback_exc}; 腾讯分笔: {tencent_fallback_exc}"
                ) from remote_error

    assert remote_error is not None
    raise remote_error


def _prepare_date_column(df: pd.DataFrame, column: str = "日期") -> pd.DataFrame:
    if column not in df.columns:
        raise RuntimeError(f"资金面数据缺少日期列: {column}; 实际列: {list(df.columns)}")
    working_df = df.copy()
    working_df[column] = pd.to_datetime(working_df[column], errors="coerce")
    working_df = working_df[pd.notna(working_df[column])]
    if working_df.empty:
        raise RuntimeError("资金面数据没有可用日期")
    return working_df.sort_values(column).reset_index(drop=True)


def _latest_row_on_or_before(df: pd.DataFrame, target_date: Optional[date]) -> pd.Series:
    working_df = _prepare_date_column(df)
    if target_date is not None:
        cutoff = pd.Timestamp(target_date)
        working_df = working_df[working_df["日期"] <= cutoff]
    if working_df.empty:
        raise RuntimeError(f"未取到 {target_date} 之前的 A 股资金面数据")
    return working_df.iloc[-1]


def _rolling_sum_until(df: pd.DataFrame, target_date: date, column: str, periods: int) -> Optional[float]:
    working_df = _prepare_date_column(df)
    if column not in working_df.columns:
        return None
    window_df = working_df[working_df["日期"] <= pd.Timestamp(target_date)].tail(periods)
    values = [_coerce_float(value) for value in window_df[column].tolist()]
    present_values = [value for value in values if value is not None]
    if not present_values:
        return None
    return float(sum(present_values))


def _daily_row_metrics(symbol: str, target_date: date) -> dict[str, Optional[float]]:
    start_date = target_date - timedelta(days=45)
    daily_df = _with_retries(
        lambda: _fetch_cn_daily_price_df(symbol=symbol, start_date=start_date, end_date=target_date),
        "A股日线成交/换手",
    )
    working_df = _prepare_date_column(daily_df)
    row = _latest_row_on_or_before(working_df, target_date)
    target_timestamp = row["日期"]
    amount = _coerce_float(row.get("成交额"))
    turnover_rate = _coerce_float(row.get("换手率"))
    amount_ratio_5d = None
    amount_history = working_df[working_df["日期"] <= target_timestamp].tail(5)
    amounts = [_coerce_float(value) for value in amount_history.get("成交额", pd.Series(dtype=float)).tolist()]
    present_amounts = [value for value in amounts if value is not None and value > 0]
    if amount is not None and len(present_amounts) >= 2:
        amount_ratio_5d = amount / (sum(present_amounts) / len(present_amounts))
    return {
        "turnover": amount,
        "turnover_rate": turnover_rate,
        "amount_ratio_5d": amount_ratio_5d,
    }


def _safe_daily_row_metrics(symbol: str, target_date: date) -> tuple[dict[str, Optional[float]], Optional[str]]:
    try:
        return _daily_row_metrics(symbol=symbol, target_date=target_date), None
    except Exception as exc:
        return {}, f"日线成交/换手补充失败: {exc}"


def fetch_cn_capital_flow_snapshot(
    symbol: str,
    name: str,
    trade_date: Optional[date] = None,
    source: str = "akshare.eastmoney",
    use_cache: bool = True,
    use_fallback: bool = True,
    cache_dir: Path | str = DEFAULT_CACHE_DIR,
    max_cache_age_days: Optional[int] = 7,
) -> CapitalFlowSnapshot:
    """Fetch a standardized A-share capital-flow snapshot from public AkShare sources."""

    normalized_symbol = _normalize_cn_symbol(symbol)
    fund_flow_df, flow_source, cache_warning = _fetch_fund_flow_with_cache(
        symbol=normalized_symbol,
        trade_date=trade_date,
        use_cache=use_cache,
        use_fallback=use_fallback,
        cache_dir=Path(cache_dir),
        max_cache_age_days=max_cache_age_days,
    )

    flow_row = _latest_row_on_or_before(fund_flow_df, trade_date)
    resolved_trade_date = pd.Timestamp(flow_row["日期"]).date()
    daily_metrics, daily_warning = _safe_daily_row_metrics(normalized_symbol, resolved_trade_date)
    notes = "；".join(value for value in (cache_warning, daily_warning) if value)

    raw_payload_ref = f"{flow_source}:{normalized_symbol}:{resolved_trade_date.isoformat()}"
    if daily_warning is None:
        raw_payload_ref += "+akshare.stock_zh_a_hist"

    return CapitalFlowSnapshot(
        symbol=normalized_symbol,
        name=name,
        market="CN",
        trade_date=resolved_trade_date,
        source=f"{source}.cache" if flow_source.endswith(".cache") and ".cache" not in source else flow_source if flow_source.endswith(".fallback") else source,
        updated_at=datetime.now(),
        turnover=daily_metrics.get("turnover"),
        turnover_rate=daily_metrics.get("turnover_rate"),
        amount_ratio_5d=daily_metrics.get("amount_ratio_5d"),
        main_net_inflow=_coerce_float(flow_row.get("主力净流入-净额")),
        main_net_inflow_3d=_coerce_float(flow_row.get("主力净流入_3d_fallback"))
        or _rolling_sum_until(fund_flow_df, resolved_trade_date, "主力净流入-净额", 3),
        main_net_inflow_5d=_coerce_float(flow_row.get("主力净流入_5d_fallback"))
        or _rolling_sum_until(fund_flow_df, resolved_trade_date, "主力净流入-净额", 5),
        main_net_inflow_10d=_coerce_float(flow_row.get("主力净流入_10d_fallback"))
        or _rolling_sum_until(fund_flow_df, resolved_trade_date, "主力净流入-净额", 10),
        super_large_net_inflow=_coerce_float(flow_row.get("超大单净流入-净额")),
        large_order_net_inflow=_coerce_float(flow_row.get("大单净流入-净额")),
        medium_order_net_inflow=_coerce_float(flow_row.get("中单净流入-净额")),
        small_order_net_inflow=_coerce_float(flow_row.get("小单净流入-净额")),
        notes=notes,
        raw_payload_ref=raw_payload_ref,
    )