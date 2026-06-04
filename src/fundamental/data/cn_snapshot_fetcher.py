"""Fetch standardized CN fundamental snapshots from public data sources."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import os
from typing import Optional

import numpy as np
import pandas as pd

from fundamental.config.registry import get_submodel_for_symbol
from fundamental.data.derived_metrics import (
    derive_asset_turnover,
    derive_dupont_driver,
    derive_equity_multiplier,
    derive_net_margin,
    derive_peg,
)
from fundamental.data.hk_snapshot_fetcher import FundamentalSnapshotFetchResult
from fundamental.models.snapshot import FundamentalSnapshot


@dataclass(frozen=True)
class CnPeriodSnapshotsFetchResult:
    annual: FundamentalSnapshotFetchResult
    interim: Optional[FundamentalSnapshotFetchResult] = None


@dataclass(frozen=True)
class CnAvailableReportPeriods:
    annual: date
    interim: Optional[date] = None


def _clear_proxy_env() -> None:
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        os.environ.pop(var, None)
    os.environ["NO_PROXY"] = "*"


def _normalize_cn_symbol(symbol: str) -> str:
    text = symbol.strip().upper()
    if text.startswith(("SH", "SZ", "BJ")):
        text = text[2:]
    if not text.isdigit():
        raise ValueError(f"无法识别 A 股代码: {symbol}")
    return text.zfill(6)


def _coerce_float(value: object) -> Optional[float]:
    if value is None:
        return None
    if value is pd.NA:
        return None
    if isinstance(value, float) and np.isnan(value):
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text or text in {"False", "None", "nan", "NaN", "<NA>"}:
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


def _fetch_cn_financial_abstract_df(symbol: str) -> pd.DataFrame:
    _clear_proxy_env()
    import akshare as ak  # type: ignore

    return ak.stock_financial_abstract_ths(symbol=symbol, indicator="按报告期")


def _fetch_cn_financial_debt_df(symbol: str) -> pd.DataFrame:
    _clear_proxy_env()
    import akshare as ak  # type: ignore

    return ak.stock_financial_debt_new_ths(symbol=symbol)


def _fetch_cn_financial_cash_df(symbol: str) -> pd.DataFrame:
    _clear_proxy_env()
    import akshare as ak  # type: ignore

    return ak.stock_financial_cash_new_ths(symbol=symbol)


def _fetch_cn_valuation_series(symbol: str, indicator: str, period: str = "近五年") -> pd.DataFrame:
    _clear_proxy_env()
    import akshare as ak  # type: ignore

    return ak.stock_zh_valuation_baidu(symbol=symbol, indicator=indicator, period=period)


def _safe_fetch_cn_valuation_series(symbol: str, indicator: str, period: str = "近五年") -> tuple[pd.DataFrame, Optional[str]]:
    try:
        return _fetch_cn_valuation_series(symbol=symbol, indicator=indicator, period=period), None
    except Exception as exc:
        return pd.DataFrame(), f"Baidu valuation fetch failed for {indicator}/{period}: {exc}."


def _format_cn_em_symbol(symbol: str) -> str:
    if symbol.startswith(("6", "9")):
        return f"{symbol}.SH"
    if symbol.startswith(("8", "4")):
        return f"{symbol}.BJ"
    return f"{symbol}.SZ"


def _fetch_cn_financial_analysis_indicator_df(symbol: str) -> pd.DataFrame:
    _clear_proxy_env()
    import akshare as ak  # type: ignore

    return ak.stock_financial_analysis_indicator_em(symbol=_format_cn_em_symbol(symbol), indicator="按报告期")


def _fetch_cn_dividend_history_df(symbol: str) -> pd.DataFrame:
    _clear_proxy_env()
    import akshare as ak  # type: ignore

    return ak.stock_dividend_cninfo(symbol=symbol)


def _fetch_cn_daily_price_df(symbol: str) -> pd.DataFrame:
    _clear_proxy_env()
    import akshare as ak  # type: ignore

    return ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date="19700101", end_date="20500101", adjust="")


_ABSTRACT_INDEX = {
    "report_period": 0,
    "net_profit": 1,
    "net_profit_growth": 2,
    "revenue": 5,
    "revenue_growth": 6,
    "book_value_per_share": 8,
    "operating_cashflow_per_share": 11,
    "roe": 12,
    "gross_margin": 13,
    "current_ratio": 20,
    "debt_to_asset": 24,
}


_ABSTRACT_FIELD_CANDIDATES = {
    "report_period": ("报告期", "REPORT_DATE", "report_date"),
    "net_profit_growth": ("净利润同比增长率", "归母净利润同比增长率"),
    "revenue_growth": ("营业总收入同比增长率", "营业收入同比增长率"),
    "book_value_per_share": ("每股净资产", "每股净资产_调整后"),
    "roe": ("净资产收益率", "净资产收益率-摊薄"),
    "gross_margin": ("毛利率", "销售毛利率", "销售净利率"),
    "current_ratio": ("流动比率",),
    "debt_to_asset": ("资产负债率",),
}


def _abstract_column_lookup(df: pd.DataFrame) -> dict[str, str]:
    return {_normalize_field_name(column): str(column) for column in df.columns}


def _abstract_series_value(series: pd.Series, field_name: str) -> object:
    lookup = {_normalize_field_name(column): column for column in series.index}
    for candidate in _ABSTRACT_FIELD_CANDIDATES.get(field_name, ()):  # pragma: no branch - tiny loop
        column = lookup.get(_normalize_field_name(candidate))
        if column is not None:
            return series[column]

    fallback_index = _ABSTRACT_INDEX.get(field_name)
    if fallback_index is not None and fallback_index < len(series):
        return series.iloc[fallback_index]
    return None


def _abstract_series_float(series: pd.Series, field_name: str) -> Optional[float]:
    return _coerce_float(_abstract_series_value(series, field_name))


def _abstract_report_period_series(df: pd.DataFrame) -> pd.Series:
    lookup = _abstract_column_lookup(df)
    for candidate in _ABSTRACT_FIELD_CANDIDATES["report_period"]:
        column = lookup.get(_normalize_field_name(candidate))
        if column is not None:
            return pd.to_datetime(df[column], errors="coerce")

    fallback_index = _ABSTRACT_INDEX["report_period"]
    return pd.to_datetime(df.iloc[:, fallback_index], errors="coerce")


def _is_annual_report_timestamp(value: object) -> bool:
    timestamp = pd.to_datetime(value, errors="coerce")
    return pd.notna(timestamp) and timestamp.month == 12 and timestamp.day == 31


def _prefer_annual_rows(df: pd.DataFrame, date_column: str) -> pd.DataFrame:
    working_df = df.copy()
    working_df[date_column] = pd.to_datetime(working_df[date_column], errors="coerce")
    annual_df = working_df[working_df[date_column].apply(_is_annual_report_timestamp)]
    if not annual_df.empty:
        return annual_df
    return working_df


def _latest_abstract_row(abstract_df: pd.DataFrame) -> pd.Series:
    if abstract_df.empty:
        raise RuntimeError("未取到 A 股财务摘要数据")
    prepared_df = abstract_df.assign(_report_period=_abstract_report_period_series(abstract_df))
    prepared_df = _prefer_annual_rows(prepared_df, "_report_period")
    return prepared_df.sort_values(by="_report_period").iloc[-1]


def _abstract_history(abstract_df: pd.DataFrame, periods: int = 3, annual_only: bool = True) -> pd.DataFrame:
    sorted_df = abstract_df.assign(_report_period=_abstract_report_period_series(abstract_df))
    if annual_only:
        sorted_df = _prefer_annual_rows(sorted_df, "_report_period")
    sorted_df = sorted_df.sort_values(by="_report_period", ascending=False)
    return sorted_df.head(periods).reset_index(drop=True)


def _latest_non_annual_abstract_row(abstract_df: pd.DataFrame) -> pd.Series:
    if abstract_df.empty:
        raise RuntimeError("未取到 A 股财务摘要数据")
    prepared_df = abstract_df.assign(_report_period=_abstract_report_period_series(abstract_df))
    non_annual_df = prepared_df[~prepared_df["_report_period"].apply(_is_annual_report_timestamp)]
    if non_annual_df.empty:
        raise RuntimeError("未取到更新于最近年报之后的 A 股中间报告期")
    return non_annual_df.sort_values(by="_report_period").iloc[-1]


def _latest_metric_row(df: pd.DataFrame, metric_name: str) -> pd.Series:
    metric_df = df[df["metric_name"] == metric_name].copy()
    if metric_df.empty:
        raise RuntimeError(f"未取到指标 {metric_name}")
    metric_df["report_date"] = pd.to_datetime(metric_df["report_date"])
    return metric_df.sort_values("report_date").iloc[-1]


def _metric_history(df: pd.DataFrame, metric_name: str, periods: int = 3, annual_only: bool = False) -> pd.DataFrame:
    metric_df = df[df["metric_name"] == metric_name].copy()
    if metric_df.empty:
        return pd.DataFrame(columns=df.columns)
    metric_df["report_date"] = pd.to_datetime(metric_df["report_date"])
    if annual_only:
        annual_metric_df = metric_df[metric_df["report_date"].apply(_is_annual_report_timestamp)]
        if not annual_metric_df.empty:
            metric_df = annual_metric_df
    return metric_df.sort_values("report_date", ascending=False).head(periods).reset_index(drop=True)


def _latest_value(df: pd.DataFrame, metric_name: str, annual_only: bool = False) -> Optional[float]:
    history = _metric_history(df, metric_name, periods=1, annual_only=annual_only)
    if history.empty:
        return None
    return _coerce_float(history.iloc[0]["value"])


def _latest_yoy(df: pd.DataFrame, metric_name: str, annual_only: bool = False) -> Optional[float]:
    history = _metric_history(df, metric_name, periods=1, annual_only=annual_only)
    if history.empty:
        return None
    return _coerce_float(history.iloc[0]["yoy"])


def _build_ocf_profit_history(cash_df: pd.DataFrame, profit_df: pd.DataFrame, annual_only: bool = False) -> list[Optional[float]]:
    cash_history = _metric_history(cash_df, "act_cash_flow_net", periods=3, annual_only=annual_only)
    profit_history = _metric_history(profit_df, "parent_holder_net_profit", periods=3, annual_only=annual_only)
    if cash_history.empty or profit_history.empty:
        return []

    cash_by_date = {
        row["report_date"].date(): _coerce_float(row["value"])
        for _, row in cash_history.iterrows()
    }
    profit_by_date = {
        row["report_date"].date(): _coerce_float(row["value"])
        for _, row in profit_history.iterrows()
    }

    history: list[Optional[float]] = []
    ordered_dates = sorted(set(cash_by_date) & set(profit_by_date), reverse=True)[:3]
    for report_date in ordered_dates:
        ocf = cash_by_date.get(report_date)
        profit = profit_by_date.get(report_date)
        if ocf is None or profit in (None, 0):
            history.append(None)
            continue
        history.append(round(ocf / profit, 4))
    return history


def _growth_from_metric_history(df: pd.DataFrame, metric_name: str, annual_only: bool = False) -> Optional[float]:
    history = _metric_history(df, metric_name, periods=2, annual_only=annual_only)
    if len(history) < 2:
        return None

    latest = _coerce_float(history.iloc[0]["value"])
    previous = _coerce_float(history.iloc[1]["value"])
    if latest is None or previous in (None, 0):
        return None
    return round((latest - previous) / abs(previous) * 100.0, 4)


def _derive_margin_trend(latest_margin: Optional[float], previous_margin: Optional[float]) -> Optional[str]:
    if latest_margin is None or previous_margin is None:
        return None
    delta = latest_margin - previous_margin
    if delta >= 0.05:
        return "improving"
    if delta <= -0.05:
        return "weakening"
    return "stable"


def _sum_metric_values(
    df: pd.DataFrame,
    metric_names: tuple[str, ...],
    periods: int = 2,
    annual_only: bool = False,
) -> dict[object, float]:
    totals: dict[object, float] = {}
    for metric_name in metric_names:
        history = _metric_history(df, metric_name, periods=periods, annual_only=annual_only)
        if history.empty:
            continue
        for _, row in history.iterrows():
            report_date = row["report_date"].date()
            value = _coerce_float(row["value"])
            if value is None:
                continue
            totals[report_date] = totals.get(report_date, 0.0) + value
    return totals


def _derive_interest_bearing_debt_growth(df: pd.DataFrame, annual_only: bool = False) -> Optional[float]:
    totals = _sum_metric_values(
        df,
        metric_names=(
            "short_term_loans",
            "long_term_loan",
            "bonds_payable",
            "lease_debt",
            "payable_short_term_bonds",
        ),
        periods=2,
        annual_only=annual_only,
    )
    if len(totals) < 2:
        return None

    ordered_dates = sorted(totals.keys(), reverse=True)[:2]
    latest = totals.get(ordered_dates[0])
    previous = totals.get(ordered_dates[1])
    if latest is None or previous in (None, 0):
        return None
    return round((latest - previous) / abs(previous) * 100.0, 4)


def _derive_capex_to_operating_cashflow(operating_cashflow: Optional[float], capex: Optional[float]) -> Optional[float]:
    if operating_cashflow in (None, 0) or capex is None:
        return None
    if operating_cashflow <= 0:
        return None
    return round(abs(capex) / operating_cashflow, 4)


def _derive_free_cashflow_yield(
    operating_cashflow: Optional[float],
    capex: Optional[float],
    market_cap: Optional[float],
    market_cap_multiplier: float = 1.0,
) -> Optional[float]:
    if operating_cashflow is None or capex is None or market_cap in (None, 0):
        return None
    normalized_market_cap = market_cap * market_cap_multiplier
    if normalized_market_cap <= 0:
        return None
    return round(((operating_cashflow - abs(capex)) / normalized_market_cap) * 100.0, 4)


def _compute_percentile(series_df: pd.DataFrame) -> Optional[float]:
    if series_df.empty:
        return None
    values = pd.to_numeric(series_df["value"], errors="coerce").dropna()
    if values.empty:
        return None
    latest = float(values.iloc[-1])
    return round(float((values <= latest).mean() * 100), 4)


def _normalize_field_name(name: object) -> str:
    return "".join(char for char in str(name).strip().lower() if char.isalnum())


def _latest_indicator_row(
    df: pd.DataFrame,
    annual_only: bool = False,
    target_report_period: Optional[object] = None,
) -> Optional[pd.Series]:
    if df.empty:
        return None
    for column in ("REPORT_DATE", "STD_REPORT_DATE", "report_date", "报告期", "日期"):
        if column in df.columns:
            indicator_df = df.copy()
            indicator_df[column] = pd.to_datetime(indicator_df[column], errors="coerce")
            if target_report_period is not None:
                target_timestamp = pd.to_datetime(target_report_period, errors="coerce")
                if pd.notna(target_timestamp):
                    matched_indicator_df = indicator_df[
                        indicator_df[column].dt.date == target_timestamp.date()
                    ]
                    if not matched_indicator_df.empty:
                        indicator_df = matched_indicator_df
                        indicator_df = indicator_df.sort_values(column, ascending=False, na_position="last")
                        return indicator_df.iloc[0]
            if annual_only:
                annual_indicator_df = indicator_df[indicator_df[column].apply(_is_annual_report_timestamp)]
                if not annual_indicator_df.empty:
                    indicator_df = annual_indicator_df
            indicator_df = indicator_df.sort_values(column, ascending=False, na_position="last")
            return indicator_df.iloc[0]
    return df.iloc[0]


def _pick_series_float(series: Optional[pd.Series], *candidates: str) -> Optional[float]:
    if series is None:
        return None
    lookup = {_normalize_field_name(column): column for column in series.index}
    for candidate in candidates:
        column = lookup.get(_normalize_field_name(candidate))
        if column is None:
            continue
        value = _coerce_float(series[column])
        if value is not None:
            return value
    return None


def _extract_cn_financial_indicator_fields(
    indicator_df: pd.DataFrame,
    annual_only: bool = True,
    target_report_period: Optional[object] = None,
) -> dict[str, float]:
    latest = _latest_indicator_row(
        indicator_df,
        annual_only=annual_only,
        target_report_period=target_report_period,
    )
    if latest is None:
        return {}

    loan_deposit_growth_gap = _pick_series_float(
        latest,
        "贷款存款增速缺口",
        "贷款-存款增速差",
        "LOAN_DEPOSIT_GROWTH_GAP",
    )
    if loan_deposit_growth_gap is None:
        loan_growth = _pick_series_float(latest, "贷款增速", "贷款同比增速", "贷款增长率", "LOAN_GROWTH")
        deposit_growth = _pick_series_float(latest, "存款增速", "存款同比增速", "存款增长率", "DEPOSIT_GROWTH")
        if loan_growth is not None and deposit_growth is not None:
            loan_deposit_growth_gap = round(loan_growth - deposit_growth, 4)
    if loan_deposit_growth_gap is None:
        comparable_df = indicator_df.copy()
        if "REPORT_DATE" in comparable_df.columns:
            comparable_df["REPORT_DATE"] = pd.to_datetime(comparable_df["REPORT_DATE"], errors="coerce")
            comparable_df = comparable_df.sort_values("REPORT_DATE", ascending=False).reset_index(drop=True)
            if len(comparable_df) >= 2:
                latest_row = comparable_df.iloc[0]
                latest_date = comparable_df.iloc[0]["REPORT_DATE"]
                previous_candidates = comparable_df.iloc[1:]
                same_period = previous_candidates[
                    previous_candidates["REPORT_DATE"].dt.strftime("%m-%d") == latest_date.strftime("%m-%d")
                ]
                previous_row = same_period.iloc[0] if not same_period.empty else previous_candidates.iloc[0]
                latest_loans = _pick_series_float(latest_row, "GROSSLOANS")
                previous_loans = _pick_series_float(previous_row, "GROSSLOANS")
                latest_deposits = _pick_series_float(latest_row, "TOTALDEPOSITS")
                previous_deposits = _pick_series_float(previous_row, "TOTALDEPOSITS")
                if previous_loans not in (None, 0) and previous_deposits not in (None, 0):
                    loan_growth = ((latest_loans - previous_loans) / abs(previous_loans) * 100) if latest_loans is not None else None
                    deposit_growth = ((latest_deposits - previous_deposits) / abs(previous_deposits) * 100) if latest_deposits is not None else None
                    if loan_growth is not None and deposit_growth is not None:
                        loan_deposit_growth_gap = round(float(loan_growth - deposit_growth), 4)

    extracted = {
        "capital_adequacy_ratio": _pick_series_float(
            latest,
            "资本充足率",
            "资本充足率(%)",
            "CAPITAL_ADEQUACY_RATIO",
            "NEWCAPITALADER",
        ),
        "core_tier1_ratio": _pick_series_float(
            latest,
            "核心一级资本充足率",
            "核心一级资本充足率(%)",
            "一级资本充足率",
            "CORE_TIER1_RATIO",
            "HXYJBCZL",
            "FIRST_ADEQUACY_RATIO",
        ),
        "npl_ratio": _pick_series_float(latest, "不良贷款率", "不良率", "不良贷款率(%)", "NPL_RATIO", "NONPERLOAN"),
        "provision_coverage_ratio": _pick_series_float(
            latest,
            "拨备覆盖率",
            "拨备覆盖率(%)",
            "贷款拨备覆盖率",
            "PROVISION_COVERAGE_RATIO",
            "BLDKBBL",
        ),
        "net_interest_margin": _pick_series_float(
            latest,
            "净息差",
            "净息差(%)",
            "净利差",
            "NET_INTEREST_MARGIN",
        ),
        "loan_deposit_growth_gap": loan_deposit_growth_gap,
        "dividend_yield": _pick_series_float(
            latest,
            "股息率TTM",
            "股息率TTM(%)",
            "股息率",
            "股息率(%)",
            "DIVIDEND_RATE",
            "DIVIDEND_YIELD",
        ),
    }
    return {field_name: value for field_name, value in extracted.items() if value is not None}


def _extract_cn_common_indicator_fields(
    indicator_df: pd.DataFrame,
    annual_only: bool = True,
    target_report_period: Optional[object] = None,
) -> dict[str, float]:
    latest = _latest_indicator_row(
        indicator_df,
        annual_only=annual_only,
        target_report_period=target_report_period,
    )
    if latest is None:
        return {}

    dividend_yield = _pick_series_float(
        latest,
        "股息率TTM",
        "股息率TTM(%)",
        "股息率",
        "股息率(%)",
        "DIVIDEND_RATE",
        "DIVIDEND_YIELD",
    )
    if dividend_yield is None:
        return {}
    return {"dividend_yield": dividend_yield}


def _derive_cn_dividend_yield_from_history(dividend_df: pd.DataFrame, price_df: pd.DataFrame) -> Optional[float]:
    if dividend_df.empty or price_df.empty:
        return None

    working_dividend_df = dividend_df.copy()
    working_dividend_df["除权日"] = pd.to_datetime(working_dividend_df.get("除权日"), errors="coerce")
    working_dividend_df["派息比例"] = pd.to_numeric(working_dividend_df.get("派息比例"), errors="coerce")

    working_price_df = price_df.copy()
    working_price_df["日期"] = pd.to_datetime(working_price_df.get("日期"), errors="coerce")
    working_price_df["收盘"] = pd.to_numeric(working_price_df.get("收盘"), errors="coerce")
    working_price_df = working_price_df.dropna(subset=["日期", "收盘"])
    if working_price_df.empty:
        return None

    latest_price_row = working_price_df.sort_values("日期").iloc[-1]
    latest_trade_date = latest_price_row["日期"]
    latest_close = _coerce_float(latest_price_row["收盘"])
    if latest_close in (None, 0):
        return None

    trailing_dividend_df = working_dividend_df[
        (working_dividend_df["除权日"].notna())
        & (working_dividend_df["除权日"] <= latest_trade_date)
        & (working_dividend_df["除权日"] > latest_trade_date - pd.Timedelta(days=365))
        & (working_dividend_df["派息比例"].notna())
    ]
    if trailing_dividend_df.empty:
        return None

    cash_dividend_per_share = float(trailing_dividend_df["派息比例"].sum()) / 10.0
    if cash_dividend_per_share <= 0:
        return None
    return round(cash_dividend_per_share / latest_close * 100.0, 4)


def _estimate_cn_latest_close_from_pb(pb: Optional[float], latest_abstract: pd.Series) -> Optional[float]:
    if pb in (None, 0):
        return None
    book_value_per_share = _abstract_series_float(latest_abstract, "book_value_per_share")
    if book_value_per_share in (None, 0):
        return None
    return round(float(pb) * float(book_value_per_share), 4)


def _should_include_financial_indicators(symbol: str) -> bool:
    submodel = get_submodel_for_symbol(symbol)
    return submodel is not None and submodel.industry_bucket == "financial"


def _should_include_interest_bearing_debt_growth(symbol: str) -> bool:
    submodel = get_submodel_for_symbol(symbol)
    return submodel is None or submodel.industry_bucket != "financial"


def fetch_cn_fundamental_snapshot(
    symbol: str,
    name: Optional[str] = None,
    report_period_preference: str = "annual_preferred",
) -> FundamentalSnapshotFetchResult:
    code = _normalize_cn_symbol(symbol)
    abstract_df = _fetch_cn_financial_abstract_df(code)

    if report_period_preference == "annual_preferred":
        latest_abstract = _latest_abstract_row(abstract_df)
        report_period = pd.Timestamp(_abstract_series_value(latest_abstract, "report_period")).date()
        annual_only = _is_annual_report_timestamp(report_period)
        abstract_history = _abstract_history(abstract_df, periods=3, annual_only=annual_only)
        selection_assumptions = (
            "A-share snapshot prefers the latest annual report period across abstract and detailed statements when annual rows are available.",
        )
    elif report_period_preference == "latest_interim":
        latest_abstract = _latest_non_annual_abstract_row(abstract_df)
        report_period = pd.Timestamp(_abstract_series_value(latest_abstract, "report_period")).date()
        annual_only = False
        abstract_history = _abstract_history(abstract_df, periods=3, annual_only=False)
        selection_assumptions = (
            "A-share interim snapshot selects the latest non-annual report period when available.",
        )
    else:
        raise ValueError(f"Unsupported CN report_period_preference: {report_period_preference}")

    debt_df = _fetch_cn_financial_debt_df(code)
    cash_df = _fetch_cn_financial_cash_df(code)
    pe_series, pe_fetch_error = _safe_fetch_cn_valuation_series(code, indicator="市盈率(TTM)", period="近五年")
    pb_series, pb_fetch_error = _safe_fetch_cn_valuation_series(code, indicator="市净率", period="近五年")
    market_cap_series, market_cap_fetch_error = _safe_fetch_cn_valuation_series(code, indicator="总市值", period="近一年")

    period_type = "annual" if _is_annual_report_timestamp(report_period) else "report"
    pe_ttm = _coerce_float(pe_series.iloc[-1]["value"]) if not pe_series.empty else None
    pb = _coerce_float(pb_series.iloc[-1]["value"]) if not pb_series.empty else None
    market_cap = _coerce_float(market_cap_series.iloc[-1]["value"]) if not market_cap_series.empty else None
    pe_percentile_5y = _compute_percentile(pe_series)
    latest_net_profit = _abstract_series_float(latest_abstract, "net_profit")
    latest_revenue = _abstract_series_float(latest_abstract, "revenue")
    latest_net_profit_growth = _abstract_series_float(latest_abstract, "net_profit_growth")
    latest_debt_to_asset = _abstract_series_float(latest_abstract, "debt_to_asset")
    latest_roe = _abstract_series_float(latest_abstract, "roe")
    latest_gross_margin = _abstract_series_float(latest_abstract, "gross_margin")
    previous_gross_margin = (
        _abstract_series_float(abstract_history.iloc[1], "gross_margin")
        if len(abstract_history) > 1
        else None
    )
    gross_margin_trend = _derive_margin_trend(latest_gross_margin, previous_gross_margin)
    net_margin = derive_net_margin(latest_net_profit, latest_revenue)
    equity_multiplier = derive_equity_multiplier(latest_debt_to_asset)
    asset_turnover = derive_asset_turnover(latest_roe, net_margin, equity_multiplier)
    peg = derive_peg(pe_ttm, latest_net_profit_growth)
    dupont_driver = derive_dupont_driver(latest_roe, net_margin, latest_debt_to_asset)

    roe_series = [
        value
        for value in (_abstract_series_float(abstract_history.iloc[index], "roe") for index in range(len(abstract_history)))
        if value is not None
    ]
    roe_mean = float(np.mean(roe_series)) if roe_series else None
    roe_std = float(np.std(roe_series, ddof=0)) if roe_series else None
    roe_3y_cv = None
    if roe_mean not in (None, 0) and roe_std is not None:
        roe_3y_cv = round(abs(roe_std / roe_mean), 4)

    benefit_df = _fetch_cn_financial_benefit_df(code)
    profit_df = _metric_history(benefit_df, "parent_holder_net_profit", periods=3, annual_only=annual_only)
    ocf_profit_history = _build_ocf_profit_history(cash_df, benefit_df, annual_only=annual_only)
    operating_cashflow_to_profit = ocf_profit_history[0] if ocf_profit_history else None
    latest_operating_cashflow = _latest_value(cash_df, "act_cash_flow_net", annual_only=annual_only)
    operating_cashflow_growth = _growth_from_metric_history(cash_df, "act_cash_flow_net", annual_only=annual_only)
    interest_bearing_debt_growth = None
    if _should_include_interest_bearing_debt_growth(code):
        interest_bearing_debt_growth = _derive_interest_bearing_debt_growth(debt_df, annual_only=annual_only)
    capex = _latest_value(cash_df, "pay_fixed_assets_etc_cash", annual_only=annual_only)
    capex_to_operating_cashflow = _derive_capex_to_operating_cashflow(latest_operating_cashflow, capex)
    free_cashflow_yield = _derive_free_cashflow_yield(
        latest_operating_cashflow,
        capex,
        market_cap,
        market_cap_multiplier=100000000.0,
    )

    assumptions = [
        "pe_percentile_5y uses Baidu valuation history percentile over the recent five-year window.",
        "A-share snapshot uses THS financial abstract/debt/cash tables as the primary public source.",
        *selection_assumptions,
    ]
    if gross_margin_trend is not None:
        assumptions.append("gross_margin_trend is derived from THS A-share abstract gross margin history.")
    for valuation_fetch_error in (pe_fetch_error, pb_fetch_error, market_cap_fetch_error):
        if valuation_fetch_error:
            assumptions.append(valuation_fetch_error)
    if peg is None:
        assumptions.append("PEG is omitted because current TTM PE or net profit growth is non-positive or unavailable.")
    raw_payload_refs = [
        f"ths-abstract:{code}",
        f"ths-debt:{code}",
        f"ths-cash:{code}",
        f"baidu-valuation:{code}",
    ]

    snapshot = FundamentalSnapshot(
        symbol=code,
        name=name or code,
        market="CN",
        report_period=report_period,
        currency="CNY",
        source="ths+baidu",
        updated_at=datetime.now(),
        market_cap=market_cap,
        pe_ttm=pe_ttm,
        pe_percentile_5y=pe_percentile_5y,
        pb=pb,
        peg=peg,
        roe=latest_roe,
        roe_3y_mean=round(roe_mean, 4) if roe_mean is not None else None,
        roe_3y_cv=roe_3y_cv,
        dupont_driver=dupont_driver,
        asset_turnover=asset_turnover,
        equity_multiplier=equity_multiplier,
        revenue_growth=_abstract_series_float(latest_abstract, "revenue_growth"),
        net_profit_growth=latest_net_profit_growth,
        gross_margin=latest_gross_margin,
        gross_margin_trend=gross_margin_trend,
        net_margin=net_margin,
        current_ratio=_abstract_series_float(latest_abstract, "current_ratio"),
        debt_to_asset=latest_debt_to_asset,
        operating_cashflow_to_profit=operating_cashflow_to_profit,
        operating_cashflow_to_profit_history=ocf_profit_history,
        interest_bearing_debt_growth=interest_bearing_debt_growth,
        operating_cashflow_growth=operating_cashflow_growth,
        free_cashflow_yield=free_cashflow_yield,
        capex_to_operating_cashflow=capex_to_operating_cashflow,
        accounts_receivable_growth=_latest_yoy(debt_df, "accounts_receivable", annual_only=True),
        inventory_growth=_latest_yoy(debt_df, "inventory", annual_only=True),
        period_type=period_type,
        raw_payload_ref=f"ths-cn:{code}:{report_period.isoformat()}",
    )

    analysis_indicator_field_sources: dict[str, str] = {}
    financial_indicator_df = pd.DataFrame()
    analysis_indicator_loaded = False
    try:
        financial_indicator_df = _fetch_cn_financial_analysis_indicator_df(code)
        analysis_indicator_loaded = True
        common_indicator_updates = {
            field_name: value
            for field_name, value in _extract_cn_common_indicator_fields(
                financial_indicator_df,
                annual_only=annual_only,
                target_report_period=report_period,
            ).items()
            if getattr(snapshot, field_name) is None
        }
        if common_indicator_updates:
            snapshot = snapshot.model_copy(update=common_indicator_updates)
            analysis_indicator_field_sources.update(
                {
                    field_name: "eastmoney.analysis_indicator"
                    for field_name in common_indicator_updates
                }
            )
            assumptions.append(
                "A-share main indicator data supplements point-in-time fields such as dividend_yield when available."
            )
    except Exception as exc:
        assumptions.append(f"A-share main indicator supplement fetch failed: {exc}.")

    if _should_include_financial_indicators(code) and analysis_indicator_loaded:
        financial_updates = {
            field_name: value
            for field_name, value in _extract_cn_financial_indicator_fields(
                financial_indicator_df,
                annual_only=annual_only,
                target_report_period=report_period,
            ).items()
            if getattr(snapshot, field_name) is None
        }
        if financial_updates:
            snapshot = snapshot.model_copy(update=financial_updates)
            analysis_indicator_field_sources.update(
                {
                    field_name: "eastmoney.analysis_indicator"
                    for field_name in financial_updates
                }
            )
            assumptions.append(
                "Financial-sector fields are supplemented from Eastmoney A-share main indicator data when available."
            )

    if snapshot.dividend_yield is None:
        try:
            dividend_history_df = _fetch_cn_dividend_history_df(code)
            derived_dividend_yield = None
            dividend_yield_source = None
            try:
                daily_price_df = _fetch_cn_daily_price_df(code)
                derived_dividend_yield = _derive_cn_dividend_yield_from_history(dividend_history_df, daily_price_df)
                if derived_dividend_yield is not None:
                    dividend_yield_source = "cninfo.dividend_history+eastmoney.daily_price"
            except Exception as exc:
                assumptions.append(f"A-share daily price fetch for dividend_yield fallback failed: {exc}.")

            if derived_dividend_yield is None:
                pb_implied_price = _estimate_cn_latest_close_from_pb(pb, latest_abstract)
                if pb_implied_price is not None:
                    pb_implied_price_df = pd.DataFrame(
                        [{"日期": datetime.now().date().isoformat(), "收盘": pb_implied_price}]
                    )
                    derived_dividend_yield = _derive_cn_dividend_yield_from_history(
                        dividend_history_df,
                        pb_implied_price_df,
                    )
                    if derived_dividend_yield is not None:
                        dividend_yield_source = "cninfo.dividend_history+baidu.pb+ths.abstract.book_value_per_share"

            if derived_dividend_yield is not None:
                snapshot = snapshot.model_copy(update={"dividend_yield": derived_dividend_yield})
                analysis_indicator_field_sources["dividend_yield"] = dividend_yield_source or "cninfo.dividend_history"
                assumptions.append(
                    "A-share dividend_yield is derived from CNInfo cash dividend records over the trailing 12 months and a current price proxy when Eastmoney analysis indicators omit the field."
                )
        except Exception as exc:
            assumptions.append(f"A-share dividend_yield fallback derivation failed: {exc}.")

    if analysis_indicator_loaded:
        raw_payload_refs.append(f"eastmoney-analysis-indicator:{code}")
    if analysis_indicator_field_sources.get("dividend_yield") in {
        "cninfo.dividend_history+eastmoney.daily_price",
        "cninfo.dividend_history+baidu.pb+ths.abstract.book_value_per_share",
    }:
        raw_payload_refs.append(f"cninfo-dividend:{code}")

    field_sources = {
        field: source
        for field, source in {
            "market_cap": "baidu.valuation",
            "pe_ttm": "baidu.valuation",
            "pe_percentile_5y": "baidu.valuation",
            "pb": "baidu.valuation",
            "peg": "derived.pe_ttm+net_profit_growth",
            "roe": "ths.abstract",
            "roe_3y_mean": "ths.abstract",
            "roe_3y_cv": "ths.abstract",
            "dupont_driver": "derived.roe+net_margin+debt_to_asset",
            "asset_turnover": "derived.roe+net_margin+debt_to_asset",
            "equity_multiplier": "derived.debt_to_asset",
            "revenue_growth": "ths.abstract",
            "net_profit_growth": "ths.abstract",
            "gross_margin": "ths.abstract",
            "gross_margin_trend": "derived.ths.abstract.gross_margin_history",
            "net_margin": "derived.net_profit+revenue",
            "current_ratio": "ths.abstract",
            "debt_to_asset": "ths.abstract",
            "operating_cashflow_to_profit": "ths.cash+ths.benefit",
            "operating_cashflow_to_profit_history": "ths.cash+ths.benefit",
            "interest_bearing_debt_growth": "derived.ths.debt",
            "operating_cashflow_growth": "derived.ths.cash",
            "free_cashflow_yield": "derived.ths.cash+baidu.valuation",
            "capex_to_operating_cashflow": "derived.ths.cash",
            "accounts_receivable_growth": "ths.debt",
            "inventory_growth": "ths.debt",
        }.items()
        if getattr(snapshot, field) is not None
    }
    field_sources.update(analysis_indicator_field_sources)

    return FundamentalSnapshotFetchResult(
        snapshot=snapshot,
        assumptions=tuple(assumptions),
        raw_payload_refs=tuple(raw_payload_refs),
        field_sources=field_sources,
    )


def fetch_cn_period_snapshots(
    symbol: str,
    name: Optional[str] = None,
) -> CnPeriodSnapshotsFetchResult:
    annual = fetch_cn_fundamental_snapshot(symbol=symbol, name=name, report_period_preference="annual_preferred")
    try:
        interim = fetch_cn_fundamental_snapshot(symbol=symbol, name=name, report_period_preference="latest_interim")
    except RuntimeError:
        interim = None

    if interim is not None and interim.snapshot.report_period <= annual.snapshot.report_period:
        interim = None

    return CnPeriodSnapshotsFetchResult(annual=annual, interim=interim)


def fetch_cn_available_report_periods(symbol: str) -> CnAvailableReportPeriods:
    code = _normalize_cn_symbol(symbol)
    abstract_df = _fetch_cn_financial_abstract_df(code)
    annual_row = _latest_abstract_row(abstract_df)
    annual_period = pd.Timestamp(_abstract_series_value(annual_row, "report_period")).date()

    try:
        interim_row = _latest_non_annual_abstract_row(abstract_df)
    except RuntimeError:
        interim_period = None
    else:
        interim_period = pd.Timestamp(_abstract_series_value(interim_row, "report_period")).date()
        if interim_period <= annual_period:
            interim_period = None

    return CnAvailableReportPeriods(annual=annual_period, interim=interim_period)


def _fetch_cn_financial_benefit_df(symbol: str) -> pd.DataFrame:
    _clear_proxy_env()
    import akshare as ak  # type: ignore

    return ak.stock_financial_benefit_new_ths(symbol=symbol)
