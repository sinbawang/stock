"""Fetch standardized HK fundamental snapshots from public data sources."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
import os
import re
from typing import Any, Optional, Sequence
from urllib.parse import urljoin

import numpy as np
import pandas as pd
import requests

from fundamental.config.registry import get_submodel_for_symbol
from fundamental.data.derived_metrics import (
    derive_asset_turnover,
    derive_dupont_driver,
    derive_equity_multiplier,
    derive_net_margin,
    derive_peg,
)
from fundamental.models.snapshot import FundamentalSnapshot


@dataclass(frozen=True)
class FundamentalSnapshotFetchResult:
    snapshot: FundamentalSnapshot
    assumptions: tuple[str, ...] = ()
    raw_payload_refs: tuple[str, ...] = ()
    field_sources: dict[str, str] | None = None


@dataclass(frozen=True)
class HkPeriodSnapshotsFetchResult:
    annual: FundamentalSnapshotFetchResult
    interim: Optional[FundamentalSnapshotFetchResult] = None


def _clear_proxy_env() -> None:
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        os.environ.pop(var, None)
    os.environ["NO_PROXY"] = "*"


def _normalize_hk_symbol(symbol: str) -> str:
    text = symbol.strip().upper()
    if text.endswith(".HK"):
        text = text[:-3]
    if text.startswith("HK"):
        text = text[2:]
    if not text.isdigit():
        raise ValueError(f"无法识别港股代码: {symbol}")
    return text.zfill(5)


def _fetch_hk_analysis_indicator_df(symbol: str) -> pd.DataFrame:
    _clear_proxy_env()
    import akshare as ak  # type: ignore

    return ak.stock_financial_hk_analysis_indicator_em(symbol=symbol, indicator="报告期")


def _fetch_hk_valuation_comparison_df(symbol: str) -> pd.DataFrame:
    _clear_proxy_env()
    import akshare as ak  # type: ignore

    return ak.stock_hk_valuation_comparison_em(symbol=symbol)


def _fetch_hk_cashflow_df(symbol: str, report_dates: Sequence[str]) -> pd.DataFrame:
    _clear_proxy_env()
    session = requests.Session()
    session.trust_env = False

    joined_dates = "','".join(report_dates)
    response = session.get(
        "https://datacenter.eastmoney.com/securities/api/data/v1/get",
        params={
            "reportName": "RPT_HKF10_FN_CASHFLOW_PC",
            "columns": (
                "SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,ORG_CODE,REPORT_DATE,DATE_TYPE_CODE,"
                "FISCAL_YEAR,START_DATE,STD_ITEM_CODE,STD_ITEM_NAME,AMOUNT"
            ),
            "quoteColumns": "",
            "filter": f"(SECUCODE=\"{symbol}.HK\")(REPORT_DATE in ('{joined_dates}'))",
            "pageNumber": "1",
            "pageSize": "500",
            "sortTypes": "-1,1",
            "sortColumns": "REPORT_DATE,STD_ITEM_CODE",
            "source": "F10",
            "client": "PC",
            "v": "01975982096513973",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("result", {}).get("data") or []
    return pd.DataFrame(data)


def _fetch_hk_balance_df(symbol: str, report_dates: Sequence[str]) -> pd.DataFrame:
    _clear_proxy_env()
    session = requests.Session()
    session.trust_env = False

    joined_dates = "','".join(report_dates)
    response = session.get(
        "https://datacenter.eastmoney.com/securities/api/data/v1/get",
        params={
            "reportName": "RPT_HKF10_FN_BALANCE_PC",
            "columns": (
                "SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,ORG_CODE,REPORT_DATE,DATE_TYPE_CODE,"
                "FISCAL_YEAR,STD_ITEM_CODE,STD_ITEM_NAME,AMOUNT,STD_REPORT_DATE"
            ),
            "quoteColumns": "",
            "filter": f"(SECUCODE=\"{symbol}.HK\")(REPORT_DATE in ('{joined_dates}'))",
            "pageNumber": "1",
            "pageSize": "500",
            "sortTypes": "-1,1",
            "sortColumns": "REPORT_DATE,STD_ITEM_CODE",
            "source": "F10",
            "client": "PC",
            "v": "01975982096513973",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("result", {}).get("data") or []
    return pd.DataFrame(data)


def _fetch_hk_dividend_payout_df(symbol: str) -> pd.DataFrame:
    _clear_proxy_env()
    session = requests.Session()
    session.trust_env = False

    response = session.get(
        "https://datacenter.eastmoney.com/securities/api/data/v1/get",
        params={
            "reportName": "RPT_HKF10_MAIN_DIVBASIC",
            "columns": (
                "SECURITY_CODE,UPDATE_DATE,REPORT_TYPE,EX_DIVIDEND_DATE,DIVIDEND_DATE,"
                "TRANSFER_END_DATE,YEAR,PLAN_EXPLAIN,IS_BFP"
            ),
            "quoteColumns": "",
            "filter": f'(SECURITY_CODE="{symbol}")(IS_BFP="0")',
            "pageNumber": "1",
            "pageSize": "200",
            "sortTypes": "-1,-1",
            "sortColumns": "NOTICE_DATE,EX_DIVIDEND_DATE",
            "source": "F10",
            "client": "PC",
            "v": "035584639294227527",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("result", {}).get("data") or []
    return pd.DataFrame(data)


def _fetch_hk_quote_xueqiu(symbol: str) -> dict[str, Any]:
    from chanlun.data.hk_minute_fetcher import _build_xueqiu_session

    session, _cookie_source = _build_xueqiu_session(symbol)
    response = session.get(
        "https://stock.xueqiu.com/v5/stock/quote.json",
        params={"symbol": symbol, "extend": "detail"},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error_code") not in (None, 0):
        raise RuntimeError(f"雪球 quote 抓取失败: {payload}")

    data = payload.get("data") or {}
    quote = data.get("quote") or {}
    if not quote:
        raise RuntimeError(f"未取到港股 {symbol} 的雪球 quote 数据")
    return quote


def _fetch_hk_financial_indicator_df(symbol: str) -> pd.DataFrame:
    _clear_proxy_env()
    import akshare as ak  # type: ignore

    return ak.stock_hk_financial_indicator_em(symbol=symbol)


def _derive_margin_trend(latest_margin: Optional[float], previous_margin: Optional[float]) -> Optional[str]:
    if latest_margin is None or previous_margin is None:
        return None
    delta = latest_margin - previous_margin
    if delta >= 0.05:
        return "improving"
    if delta <= -0.05:
        return "weakening"
    return "stable"


def _extract_hk_auto_specialist_fields_from_analysis(
    annual_df: pd.DataFrame,
    history_scope_label: str = "annual",
) -> tuple[dict[str, Any], tuple[str, ...], dict[str, str]]:
    if annual_df.empty:
        return {}, (), {}

    latest = annual_df.iloc[0]
    previous = annual_df.iloc[1] if len(annual_df) > 1 else None
    gross_margin = _pick_series_float(latest, "GROSS_PROFIT_RATIO", "毛利率", "gross_profit_ratio")
    previous_gross_margin = _pick_series_float(previous, "GROSS_PROFIT_RATIO", "毛利率", "gross_profit_ratio")
    gross_margin_trend = _derive_margin_trend(gross_margin, previous_gross_margin)

    updates: dict[str, Any] = {}
    assumptions: list[str] = []
    field_sources: dict[str, str] = {}

    if gross_margin is not None:
        updates["gross_margin"] = round(gross_margin, 6)
        field_sources["gross_margin"] = "eastmoney.analysis"
    if gross_margin_trend is not None:
        updates["gross_margin_trend"] = gross_margin_trend
        field_sources["gross_margin_trend"] = "derived.eastmoney.gross_margin_history"
        assumptions.append(
            f"gross_margin_trend is derived from Eastmoney HK {history_scope_label} gross profit ratio history."
        )

    return updates, tuple(assumptions), field_sources


def _select_hk_analysis_rows(
    analysis_df: pd.DataFrame,
    report_period_preference: str,
) -> tuple[pd.DataFrame, str, tuple[str, ...], str]:
    if analysis_df.empty:
        raise RuntimeError("未取到港股核心指标")

    working_df = analysis_df.copy()
    working_df["REPORT_DATE"] = pd.to_datetime(working_df["REPORT_DATE"], errors="coerce")
    working_df = working_df.dropna(subset=["REPORT_DATE"]).sort_values("REPORT_DATE", ascending=False).reset_index(drop=True)
    if working_df.empty:
        raise RuntimeError("港股核心指标缺少可解析的报告期")

    annual_df = working_df[working_df["DATE_TYPE_CODE"].astype(str) == "001"].copy().reset_index(drop=True)
    if report_period_preference == "annual_preferred":
        if not annual_df.empty:
            return annual_df, "annual", (), "annual"

        latest_period = pd.Timestamp(working_df.iloc[0]["REPORT_DATE"]).date().isoformat()
        return (
            working_df,
            "report",
            (
                f"HK snapshot fallback: annual rows unavailable; using the latest available report period {latest_period}.",
            ),
            "latest available",
        )

    if report_period_preference == "latest_interim":
        interim_df = working_df[working_df["DATE_TYPE_CODE"].astype(str) != "001"].copy().reset_index(drop=True)
        if interim_df.empty:
            raise RuntimeError("港股暂未披露比最新年报更近的中间报告期")
        latest_period = pd.Timestamp(interim_df.iloc[0]["REPORT_DATE"]).date().isoformat()
        return (
            interim_df,
            "report",
            (
                f"HK interim snapshot selects the latest non-annual report period {latest_period} when available.",
            ),
            "interim",
        )

    raise ValueError(f"Unsupported HK report_period_preference: {report_period_preference}")


def _hk_period_label(date_type_code: object) -> str:
    code = str(date_type_code or "").strip()
    return {
        "001": "年报",
        "002": "中报",
        "003": "一季报",
        "004": "三季报",
    }.get(code, "中间报告期")


def _fetch_geely_latest_annual_report_pdf_url() -> str:
    _clear_proxy_env()
    session = requests.Session()
    session.trust_env = False
    listing_url = "https://www.geelyauto.com.hk/"
    response = session.get(listing_url, timeout=30)
    response.raise_for_status()

    match = re.search(r'href="(?P<href>[^"]*annual-report[^"]*\.pdf)"', response.text, flags=re.IGNORECASE)
    if match is None:
        raise RuntimeError("Geely official site did not expose a parsable annual report PDF link")
    return urljoin(listing_url, match.group("href"))


def _extract_geely_auto_official_fields_from_text(text: str) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    section_match = re.search(
        r"Revenue from external customers\s+The PRC(?P<section>.*?)Specified non-current assets",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if section_match is not None:
        number_strings = re.findall(r"\d[\d,]*", section_match.group("section"))
        if len(number_strings) >= 16:
            prc_revenue = int(number_strings[0].replace(",", ""))
            total_revenue = int(number_strings[-2].replace(",", ""))
            if total_revenue > 0 and total_revenue >= prc_revenue:
                updates["overseas_revenue_share"] = round((total_revenue - prc_revenue) / total_revenue * 100.0, 2)

    lowered = text.lower()
    if "fierce price competition" in lowered:
        updates["price_war_pressure"] = "high"
    elif "intense price competition" in lowered or "price competition" in lowered:
        updates["price_war_pressure"] = "medium"

    return updates


def _fetch_geely_official_auto_fields() -> tuple[dict[str, Any], tuple[str, ...], tuple[str, ...], dict[str, str]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pypdf is required for the Geely official annual report fallback") from exc

    pdf_url = _fetch_geely_latest_annual_report_pdf_url()
    _clear_proxy_env()
    session = requests.Session()
    session.trust_env = False
    response = session.get(pdf_url, timeout=60)
    response.raise_for_status()

    reader = PdfReader(BytesIO(response.content))
    full_text = "\n".join((page.extract_text() or "") for page in reader.pages)
    updates = _extract_geely_auto_official_fields_from_text(full_text)

    assumptions: list[str] = []
    field_sources: dict[str, str] = {}
    if "overseas_revenue_share" in updates:
        assumptions.append(
            "overseas_revenue_share is computed from Geely official annual report geographical revenue disclosure as (total revenue - PRC revenue) / total revenue."
        )
        field_sources["overseas_revenue_share"] = "official.annual_report_geo_revenue"
    if "price_war_pressure" in updates:
        assumptions.append(
            "price_war_pressure is proxied from Geely official annual report wording about industry price competition intensity."
        )
        field_sources["price_war_pressure"] = "official.annual_report_text_proxy"

    raw_payload_refs = (
        "official-site:00175:https://www.geelyauto.com.hk/",
        f"official-annual-report:00175:{pdf_url}",
    )
    return updates, tuple(assumptions), raw_payload_refs, field_sources


def _extract_first_percentage_after_keyword(text: str, keyword: str, max_window: int = 240) -> Optional[float]:
    index = text.find(keyword)
    if index == -1:
        return None

    snippet = text[index : index + max_window].replace("\n", " ")
    matches = re.findall(r"(\d+\.\d+)", snippet)
    if not matches:
        matches = re.findall(r"(\d+(?:\.\d+)?)", snippet)
    if not matches:
        return None
    return _coerce_float(matches[0])


def _fetch_huatai_official_broker_fields() -> tuple[dict[str, float], tuple[str, ...], tuple[str, ...], dict[str, str]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency validation belongs to packaging/runtime
        raise RuntimeError("pypdf is required for the Huatai official annual report fallback") from exc

    session = requests.Session()
    session.trust_env = False
    pdf_url = "https://crm.htsc.com.cn/pdf_finchina/CNSESH_STOCK/2026/2026-3/2026-03-31/12036131.pdf"
    response = session.get(pdf_url, timeout=60)
    response.raise_for_status()

    reader = PdfReader(BytesIO(response.content))
    net_capital_ratio = None
    for page in reader.pages:
        page_text = page.extract_text() or ""
        net_capital_ratio = _extract_first_percentage_after_keyword(page_text, "风险覆盖率")
        if net_capital_ratio is not None:
            break

    if net_capital_ratio is None:
        raise RuntimeError("Huatai annual report did not expose a parsable 风险覆盖率 value")

    assumptions = (
        "Huatai official annual report fallback mapped 风险覆盖率 to net_capital_ratio because current public HK APIs do not expose a direct broker net capital ratio field.",
    )
    raw_payload_refs = (f"official-annual-report:06886:{pdf_url}",)
    field_sources = {"net_capital_ratio": "official.annual_report_proxy"}
    return {"net_capital_ratio": net_capital_ratio}, assumptions, raw_payload_refs, field_sources


def _fetch_picc_latest_solvency_report_pdf_url() -> tuple[str, Optional[str]]:
    session = requests.Session()
    session.trust_env = False
    listing_url = "https://www.picc.com.cn/xwzx/gkxx/zxxx/jtcfnl/"
    response = session.get(listing_url, timeout=30)
    response.raise_for_status()

    match = re.search(
        r'<li>\s*<a href="(?P<href>[^"]+\.pdf)"[^>]*><span>(?P<title>[^<]+)</span><tt>(?P<date>[^<]+)</tt>',
        response.text,
    )
    if match is None:
        raise RuntimeError("PICC solvency disclosure page did not expose a parsable PDF link")
    return urljoin(listing_url, match.group("href")), match.group("date")


def _fetch_picc_official_insurance_fields() -> tuple[dict[str, float], tuple[str, ...], tuple[str, ...], dict[str, str]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency validation belongs to packaging/runtime
        raise RuntimeError("pypdf is required for the PICC official solvency report fallback") from exc

    pdf_url, published_date = _fetch_picc_latest_solvency_report_pdf_url()
    session = requests.Session()
    session.trust_env = False
    response = session.get(pdf_url, timeout=60)
    response.raise_for_status()

    reader = PdfReader(BytesIO(response.content))
    solvency_adequacy_ratio = None
    for page in reader.pages:
        page_text = page.extract_text() or ""
        solvency_adequacy_ratio = _extract_first_percentage_after_keyword(page_text, "综合偿付能力充足率")
        if solvency_adequacy_ratio is not None:
            break

    if solvency_adequacy_ratio is None:
        raise RuntimeError("PICC solvency report did not expose a parsable 综合偿付能力充足率 value")

    assumptions = (
        "PICC official solvency report fallback supplemented solvency_adequacy_ratio from the latest public solvency report disclosure; this official source can lag the annual report period.",
    )
    if published_date:
        assumptions += (f"Latest PICC solvency report disclosure date used for fallback: {published_date}.",)
    raw_payload_refs = (
        "official-solvency-listing:01339:https://www.picc.com.cn/xwzx/gkxx/zxxx/jtcfnl/",
        f"official-solvency-report:01339:{pdf_url}",
    )
    field_sources = {"solvency_adequacy_ratio": "official.solvency_report"}
    return {"solvency_adequacy_ratio": solvency_adequacy_ratio}, assumptions, raw_payload_refs, field_sources


def _fetch_hk_official_financial_fields(
    symbol: str,
) -> tuple[dict[str, float], tuple[str, ...], tuple[str, ...], dict[str, str]]:
    code = _normalize_hk_symbol(symbol)
    if code == "06886":
        return _fetch_huatai_official_broker_fields()
    if code == "01339":
        return _fetch_picc_official_insurance_fields()
    return {}, (), (), {}


def _coerce_float(value: object) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, float) and np.isnan(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_field_name(name: object) -> str:
    return "".join(char for char in str(name).strip().lower() if char.isalnum())


def _latest_indicator_row(df: pd.DataFrame) -> Optional[pd.Series]:
    if df.empty:
        return None
    for column in ("REPORT_DATE", "STD_REPORT_DATE", "report_date", "报告期", "日期"):
        if column in df.columns:
            indicator_df = df.copy()
            indicator_df[column] = pd.to_datetime(indicator_df[column], errors="coerce")
            indicator_df = indicator_df.sort_values(column, ascending=False, na_position="last")
            return indicator_df.iloc[0]
    return df.iloc[0]


def _select_indicator_row_for_report_period(
    df: pd.DataFrame,
    report_period: date,
) -> tuple[Optional[pd.Series], tuple[str, ...]]:
    if df.empty:
        return None, ()

    for column in ("REPORT_DATE", "STD_REPORT_DATE", "report_date", "报告期", "日期"):
        if column not in df.columns:
            continue

        indicator_df = df.copy()
        indicator_df[column] = pd.to_datetime(indicator_df[column], errors="coerce")
        indicator_df = indicator_df.dropna(subset=[column]).sort_values(column, ascending=False, na_position="last")
        if indicator_df.empty:
            return None, ()

        target_timestamp = pd.Timestamp(report_period)
        matched_df = indicator_df[indicator_df[column] == target_timestamp]
        if not matched_df.empty:
            return matched_df.iloc[0], ()

        fallback_row = indicator_df.iloc[0]
        fallback_period = pd.Timestamp(fallback_row[column]).date().isoformat()
        return (
            fallback_row,
            (
                f"HK financial indicator fallback: no exact row for {report_period.isoformat()}; using latest available indicator period {fallback_period}.",
            ),
        )

    return _latest_indicator_row(df), ()


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


def _pick_first_float(records: Sequence[Optional[pd.Series]], *candidates: str) -> Optional[float]:
    for record in records:
        value = _pick_series_float(record, *candidates)
        if value is not None:
            return value
    return None


def _pick_first_float_with_source(
    analysis_row: Optional[pd.Series],
    indicator_row: Optional[pd.Series],
    *candidates: str,
) -> tuple[Optional[float], Optional[str]]:
    analysis_value = _pick_series_float(analysis_row, *candidates)
    if analysis_value is not None:
        return analysis_value, "eastmoney.analysis"

    indicator_value = _pick_series_float(indicator_row, *candidates)
    if indicator_value is not None:
        return indicator_value, "eastmoney.financial_indicator"

    return None, None


def _extract_hk_financial_indicator_fields(
    analysis_row: Optional[pd.Series],
    financial_indicator_df: pd.DataFrame,
    report_period: date,
) -> tuple[dict[str, float], tuple[str, ...], dict[str, str]]:
    indicator_row, indicator_assumptions = _select_indicator_row_for_report_period(
        financial_indicator_df,
        report_period,
    )
    extracted_with_source = {
        "solvency_adequacy_ratio": _pick_first_float_with_source(
            analysis_row,
            indicator_row,
            "综合偿付能力充足率",
            "偿付能力充足率",
            "核心偿付能力充足率",
            "SOLVENCY_ADEQUACY_RATIO",
            "CORE_SOLVENCY_RATIO",
        ),
        "combined_ratio": _pick_first_float_with_source(
            analysis_row,
            indicator_row,
            "综合成本率",
            "综合成本率(%)",
            "COMBINED_RATIO",
        ),
        "investment_return": _pick_first_float_with_source(
            analysis_row,
            indicator_row,
            "总投资收益率",
            "总投资收益率(%)",
            "投资收益率",
            "INVESTMENT_RETURN",
        ),
        "embedded_value_growth": _pick_first_float_with_source(
            analysis_row,
            indicator_row,
            "内含价值增长率",
            "EV增长率",
            "EMBEDDED_VALUE_GROWTH",
        ),
        "new_business_value_growth": _pick_first_float_with_source(
            analysis_row,
            indicator_row,
            "新业务价值增长率",
            "NBV增长率",
            "NEW_BUSINESS_VALUE_GROWTH",
        ),
        "net_capital_ratio": _pick_first_float_with_source(
            analysis_row,
            indicator_row,
            "净资本比率",
            "净资本充足率",
            "净资本/净资产",
            "NET_CAPITAL_RATIO",
        ),
        "dividend_yield": _pick_first_float_with_source(
            analysis_row,
            indicator_row,
            "股息率TTM(%)",
            "股息率TTM",
            "股息率(%)",
            "DIVIDEND_RATE",
            "DIVIDEND_YIELD",
        ),
    }
    extracted = {
        field_name: value
        for field_name, (value, _source) in extracted_with_source.items()
        if value is not None
    }
    field_sources = {
        field_name: source
        for field_name, (_value, source) in extracted_with_source.items()
        if source is not None
    }
    return extracted, indicator_assumptions, field_sources


def _extract_dividend_yield_from_plan_explain(plan_explain: object) -> Optional[float]:
    text = str(plan_explain or "").strip()
    if not text:
        return None

    patterns = (
        r"(?:股息率|派息率|息率)\s*[=:：]?[约近]?\s*(\d+(?:\.\d+)?)\s*%",
        r"(\d+(?:\.\d+)?)\s*%\s*(?:股息率|派息率|息率)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match is None:
            continue
        return _coerce_float(match.group(1))
    return None


def _overlay_snapshot_with_dividend_payout(
    snapshot: FundamentalSnapshot,
    dividend_df: pd.DataFrame,
) -> tuple[FundamentalSnapshot, tuple[str, ...], dict[str, str]]:
    if dividend_df.empty:
        return snapshot, (), {}

    working_df = dividend_df.copy()
    sort_column = None
    for candidate in ("UPDATE_DATE", "EX_DIVIDEND_DATE", "DIVIDEND_DATE"):
        if candidate in working_df.columns:
            working_df[candidate] = pd.to_datetime(working_df[candidate], errors="coerce")
            sort_column = candidate
            break
    if sort_column is not None:
        working_df = working_df.sort_values(sort_column, ascending=False, na_position="last")

    latest_row = working_df.iloc[0]
    latest_plan = str(latest_row.get("PLAN_EXPLAIN") or "").strip()
    assumptions: list[str] = []

    payout_dividend_yield = _extract_dividend_yield_from_plan_explain(latest_plan)
    if snapshot.dividend_yield is None and payout_dividend_yield is not None:
        updated_snapshot = snapshot.model_copy(update={"dividend_yield": payout_dividend_yield})
        assumptions.append(
            "Dividend yield is supplemented from the Eastmoney HK dividend payout table when the latest plan text includes an explicit yield percentage."
        )
        return updated_snapshot, tuple(assumptions), {"dividend_yield": "eastmoney.hk_dividend_payout"}

    if snapshot.dividend_yield is None and latest_plan:
        assumptions.append(
            "Eastmoney HK dividend payout rows are available, but the latest plan text does not expose an explicit dividend yield percentage."
        )
    return snapshot, tuple(assumptions), {}


def _should_include_financial_indicators(symbol: str) -> bool:
    submodel = get_submodel_for_symbol(symbol)
    return submodel is not None and submodel.industry_bucket == "financial"


def _overlay_snapshot_with_xueqiu_quote(
    snapshot: FundamentalSnapshot,
    quote: dict[str, Any],
) -> tuple[FundamentalSnapshot, tuple[str, ...], dict[str, str]]:
    overlay_fields = {
        "market_cap": _coerce_float(quote.get("market_capital")),
        "pe_ttm": _coerce_float(quote.get("pe_ttm")),
        "pb": _coerce_float(quote.get("pb")),
        "ps_ttm": _coerce_float(quote.get("psr")),
        "dividend_yield": _coerce_float(quote.get("dividend_yield")),
    }
    updates: dict[str, Optional[float]] = {}
    applied_fields: list[str] = []
    for field_name, overlay_value in overlay_fields.items():
        if overlay_value is None:
            continue
        if getattr(snapshot, field_name) is None:
            updates[field_name] = overlay_value
            applied_fields.append(field_name)

    if not updates:
        return snapshot, (), {}

    updated_snapshot = snapshot.model_copy(update=updates)
    return (
        updated_snapshot,
        (
            "Xueqiu quote overlay supplemented missing fields: " + ", ".join(applied_fields) + ".",
        ),
        {field_name: "xueqiu.quote" for field_name in applied_fields},
    )


def _should_include_interest_bearing_debt_growth(symbol: str) -> bool:
    submodel = get_submodel_for_symbol(symbol)
    return submodel is None or submodel.industry_bucket != "financial"


def _initial_field_sources(snapshot: FundamentalSnapshot) -> dict[str, str]:
    field_sources: dict[str, str] = {}

    def _mark(fields: Sequence[str], source: str) -> None:
        for field_name in fields:
            if getattr(snapshot, field_name) is not None:
                field_sources[field_name] = source

    _mark(
        (
            "roe",
            "revenue_growth",
            "net_profit_growth",
            "gross_margin",
            "net_margin",
            "debt_to_asset",
            "current_ratio",
            "accounts_receivable_growth",
            "inventory_growth",
        ),
        "eastmoney.analysis",
    )
    _mark(("dupont_driver",), "derived.roe+net_margin+debt_to_asset")
    _mark(("asset_turnover",), "derived.roe+net_margin+debt_to_asset")
    _mark(("equity_multiplier",), "derived.debt_to_asset")
    _mark(("peg",), "derived.pe_ttm+net_profit_growth")
    _mark(("operating_cashflow_to_profit", "operating_cashflow_to_profit_history"), "eastmoney.cashflow")
    _mark(("operating_cashflow_growth",), "derived.eastmoney.cashflow")
    _mark(("interest_bearing_debt_growth",), "derived.eastmoney.balance")
    _mark(("capex_to_operating_cashflow",), "derived.eastmoney.cashflow")
    _mark(("pe_ttm", "pe_percentile_5y", "pb", "ps_ttm"), "eastmoney+akshare.valuation")
    return field_sources


def _report_date_text(value: object) -> str:
    return str(pd.Timestamp(value).strftime("%Y-%m-%d 00:00:00"))


def _build_ocf_profit_history(annual_df: pd.DataFrame, cashflow_df: pd.DataFrame) -> list[Optional[float]]:
    cash_by_date = {
        str(row["REPORT_DATE"]): float(row["AMOUNT"])
        for _, row in cashflow_df[cashflow_df["STD_ITEM_CODE"] == "003999"].iterrows()
    }
    profit_by_date = {
        _report_date_text(row["REPORT_DATE"]): float(row["HOLDER_PROFIT"])
        for _, row in annual_df.iterrows()
    }

    history: list[Optional[float]] = []
    for report_date in annual_df["REPORT_DATE"].head(3):
        report_key = _report_date_text(report_date)
        ocf = cash_by_date.get(report_key)
        profit = profit_by_date.get(report_key)
        if ocf is None or profit in (None, 0):
            history.append(None)
            continue
        history.append(round(ocf / profit, 4))
    return history


def _build_cashflow_metric_growth(cashflow_df: pd.DataFrame, metric_code: str) -> Optional[float]:
    metric_df = cashflow_df[cashflow_df["STD_ITEM_CODE"] == metric_code].copy()
    if metric_df.empty:
        return None
    metric_df["REPORT_DATE"] = pd.to_datetime(metric_df["REPORT_DATE"], errors="coerce")
    metric_df = metric_df.dropna(subset=["REPORT_DATE"]).sort_values("REPORT_DATE", ascending=False).reset_index(drop=True)
    if len(metric_df) < 2:
        return None

    latest = _coerce_float(metric_df.iloc[0]["AMOUNT"])
    previous = _coerce_float(metric_df.iloc[1]["AMOUNT"])
    if latest is None or previous in (None, 0):
        return None
    return round((latest - previous) / abs(previous) * 100.0, 4)


def _build_balance_metric_growth(balance_df: pd.DataFrame, metric_code: str) -> Optional[float]:
    metric_df = balance_df[balance_df["STD_ITEM_CODE"] == metric_code].copy()
    if metric_df.empty:
        return None
    metric_df["REPORT_DATE"] = pd.to_datetime(metric_df["REPORT_DATE"])
    metric_df = metric_df.sort_values("REPORT_DATE", ascending=False).reset_index(drop=True)
    if len(metric_df) < 2:
        return None

    latest = _coerce_float(metric_df.iloc[0]["AMOUNT"])
    previous = _coerce_float(metric_df.iloc[1]["AMOUNT"])
    if latest is None or previous in (None, 0):
        return None
    return round((latest - previous) / abs(previous), 8)


def _build_balance_metric_sum_growth(balance_df: pd.DataFrame, metric_codes: tuple[str, ...]) -> Optional[float]:
    working_df = balance_df[balance_df["STD_ITEM_CODE"].isin(metric_codes)].copy()
    if working_df.empty:
        return None
    working_df["REPORT_DATE"] = pd.to_datetime(working_df["REPORT_DATE"], errors="coerce")
    working_df = working_df.dropna(subset=["REPORT_DATE"])
    if working_df.empty:
        return None

    totals: dict[date, float] = {}
    for _, row in working_df.iterrows():
        report_date = row["REPORT_DATE"].date()
        amount = _coerce_float(row["AMOUNT"])
        if amount is None:
            continue
        totals[report_date] = totals.get(report_date, 0.0) + amount

    if len(totals) < 2:
        return None

    ordered_dates = sorted(totals.keys(), reverse=True)[:2]
    latest = totals.get(ordered_dates[0])
    previous = totals.get(ordered_dates[1])
    if latest is None or previous in (None, 0):
        return None
    return round((latest - previous) / abs(previous) * 100.0, 4)


def _latest_cashflow_metric_sum(cashflow_df: pd.DataFrame, metric_codes: tuple[str, ...]) -> Optional[float]:
    working_df = cashflow_df[cashflow_df["STD_ITEM_CODE"].isin(metric_codes)].copy()
    if working_df.empty:
        return None
    working_df["REPORT_DATE"] = pd.to_datetime(working_df["REPORT_DATE"], errors="coerce")
    working_df = working_df.dropna(subset=["REPORT_DATE"])
    if working_df.empty:
        return None

    latest_date = working_df["REPORT_DATE"].max()
    latest_df = working_df[working_df["REPORT_DATE"] == latest_date]
    total = 0.0
    found = False
    for _, row in latest_df.iterrows():
        amount = _coerce_float(row["AMOUNT"])
        if amount is None:
            continue
        total += abs(amount)
        found = True
    if not found:
        return None
    return round(total, 4)


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
) -> Optional[float]:
    if operating_cashflow is None or capex is None or market_cap in (None, 0):
        return None
    if market_cap <= 0:
        return None
    return round(((operating_cashflow - abs(capex)) / market_cap) * 100.0, 4)


def _apply_derived_cashflow_metrics(
    snapshot: FundamentalSnapshot,
    field_sources: dict[str, str],
    operating_cashflow: Optional[float],
    capex: Optional[float],
) -> tuple[FundamentalSnapshot, dict[str, str]]:
    updates: dict[str, float] = {}
    updated_field_sources = dict(field_sources)

    capex_to_operating_cashflow = _derive_capex_to_operating_cashflow(operating_cashflow, capex)
    if capex_to_operating_cashflow is not None:
        updates["capex_to_operating_cashflow"] = capex_to_operating_cashflow
        updated_field_sources["capex_to_operating_cashflow"] = "derived.eastmoney.cashflow"

    free_cashflow_yield = _derive_free_cashflow_yield(operating_cashflow, capex, snapshot.market_cap)
    if free_cashflow_yield is not None:
        updates["free_cashflow_yield"] = free_cashflow_yield
        market_cap_source = updated_field_sources.get("market_cap", field_sources.get("market_cap", "market_cap"))
        updated_field_sources["free_cashflow_yield"] = f"derived.eastmoney.cashflow+{market_cap_source}"

    if not updates:
        return snapshot, updated_field_sources
    return snapshot.model_copy(update=updates), updated_field_sources


def fetch_hk_fundamental_snapshot(
    symbol: str,
    name: Optional[str] = None,
    report_period_preference: str = "annual_preferred",
    quote_overlay_source: Optional[str] = None,
) -> FundamentalSnapshotFetchResult:
    code = _normalize_hk_symbol(symbol)
    analysis_df = _fetch_hk_analysis_indicator_df(code)
    selected_df, period_type, period_assumptions, history_scope_label = _select_hk_analysis_rows(
        analysis_df,
        report_period_preference=report_period_preference,
    )
    latest = selected_df.iloc[0]
    report_dates = [pd.Timestamp(value).strftime("%Y-%m-%d") for value in selected_df["REPORT_DATE"].head(3)]
    cashflow_df = _fetch_hk_cashflow_df(code, report_dates)
    balance_df = _fetch_hk_balance_df(code, report_dates)
    valuation_df = _fetch_hk_valuation_comparison_df(code)
    if valuation_df.empty:
        raise RuntimeError(f"未取到港股 {code} 的估值对比数据")

    valuation_row = valuation_df.iloc[0]
    roe_series = [float(value) for value in selected_df["ROE_AVG"].astype(float).head(3).tolist()]
    roe_mean = float(np.mean(roe_series)) if roe_series else None
    roe_std = float(np.std(roe_series, ddof=0)) if roe_series else None
    roe_3y_cv = None
    if roe_series and roe_mean not in (None, 0):
        roe_3y_cv = round(abs(roe_std / roe_mean), 4)

    ocf_profit_history = _build_ocf_profit_history(selected_df, cashflow_df)
    latest_operating_cashflow = _latest_cashflow_metric_sum(cashflow_df, ("003999",))
    operating_cashflow_growth = _build_cashflow_metric_growth(cashflow_df, "003999")
    interest_bearing_debt_growth = None
    if _should_include_interest_bearing_debt_growth(code):
        interest_bearing_debt_growth = _build_balance_metric_sum_growth(
            balance_df,
            ("004011006", "004011010", "004020001", "004020005"),
        )
    capex = _latest_cashflow_metric_sum(cashflow_df, ("005005", "005007"))
    assumptions = [
        "pe_percentile_5y uses Eastmoney valuation comparison TTM PE percentile as a proxy.",
        "operating_cashflow_to_profit is computed as Eastmoney operating cashflow / holder profit.",
        *period_assumptions,
    ]

    pe_ttm = _coerce_float(valuation_row.iloc[2])
    net_profit_growth = _coerce_float(latest.get("HOLDER_PROFIT_YOY"))
    peg = derive_peg(pe_ttm, net_profit_growth)
    net_margin = derive_net_margin(
        _coerce_float(latest.get("HOLDER_PROFIT")),
        _pick_series_float(latest, "OPERATE_INCOME", "TOTAL_OPERATE_INCOME", "营业收入", "营业总收入"),
    )
    equity_multiplier = derive_equity_multiplier(_coerce_float(latest.get("DEBT_ASSET_RATIO")))
    asset_turnover = derive_asset_turnover(
        _coerce_float(latest.get("ROE_AVG")),
        net_margin,
        equity_multiplier,
    )
    dupont_driver = derive_dupont_driver(
        _coerce_float(latest.get("ROE_AVG")),
        net_margin,
        _coerce_float(latest.get("DEBT_ASSET_RATIO")),
    )
    if peg is None:
        assumptions.append("PEG is omitted because current TTM PE or net profit growth is non-positive or unavailable.")

    snapshot = FundamentalSnapshot(
        symbol=code,
        name=name or code,
        market="HK",
        report_period=pd.Timestamp(latest["REPORT_DATE"]).date(),
        currency=str(latest.get("CURRENCY") or "HKD"),
        source="eastmoney+akshare",
        updated_at=datetime.now(),
        pe_ttm=pe_ttm,
        pe_percentile_5y=_coerce_float(valuation_row.iloc[3]),
        pb=_coerce_float(valuation_row.iloc[6]),
        ps_ttm=_coerce_float(valuation_row.iloc[10]),
        peg=peg,
        roe=_coerce_float(latest.get("ROE_AVG")),
        roe_3y_mean=round(roe_mean, 4) if roe_mean is not None else None,
        roe_3y_cv=roe_3y_cv,
        dupont_driver=dupont_driver,
        asset_turnover=asset_turnover,
        equity_multiplier=equity_multiplier,
        gross_margin=_pick_series_float(latest, "GROSS_PROFIT_RATIO", "毛利率", "gross_profit_ratio"),
        net_margin=net_margin,
        revenue_growth=_coerce_float(latest.get("OPERATE_INCOME_YOY")),
        net_profit_growth=net_profit_growth,
        debt_to_asset=_coerce_float(latest.get("DEBT_ASSET_RATIO")),
        current_ratio=_coerce_float(latest.get("CURRENT_RATIO")),
        operating_cashflow_to_profit=ocf_profit_history[0] if ocf_profit_history else None,
        operating_cashflow_to_profit_history=ocf_profit_history,
        interest_bearing_debt_growth=interest_bearing_debt_growth,
        operating_cashflow_growth=operating_cashflow_growth,
        accounts_receivable_growth=_build_balance_metric_growth(balance_df, "004002003"),
        inventory_growth=_build_balance_metric_growth(balance_df, "004002001"),
        period_type=period_type,
        period_label=_hk_period_label(latest.get("DATE_TYPE_CODE")),
        raw_payload_ref=f"eastmoney-hk:{code}:{pd.Timestamp(latest['REPORT_DATE']).date().isoformat()}",
    )

    raw_payload_refs = [
        f"eastmoney-analysis:{code}",
        f"eastmoney-cashflow:{code}",
        f"eastmoney-balance:{code}",
        f"eastmoney-valuation:{code}",
    ]
    field_sources = _initial_field_sources(snapshot)
    snapshot, field_sources = _apply_derived_cashflow_metrics(
        snapshot,
        field_sources,
        latest_operating_cashflow,
        capex,
    )
    auto_analysis_updates, auto_analysis_assumptions, auto_analysis_field_sources = _extract_hk_auto_specialist_fields_from_analysis(
        selected_df,
        history_scope_label=history_scope_label,
    )
    if auto_analysis_updates:
        snapshot = snapshot.model_copy(update=auto_analysis_updates)
        assumptions.extend(auto_analysis_assumptions)
        field_sources.update(auto_analysis_field_sources)

    if code == "00175" and (
        snapshot.overseas_revenue_share is None or snapshot.price_war_pressure is None
    ):
        try:
            official_auto_updates, official_auto_assumptions, official_auto_raw_refs, official_auto_field_sources = (
                _fetch_geely_official_auto_fields()
            )
            applicable_official_updates = {
                field_name: value
                for field_name, value in official_auto_updates.items()
                if getattr(snapshot, field_name) is None
            }
            if applicable_official_updates:
                snapshot = snapshot.model_copy(update=applicable_official_updates)
                assumptions.extend(official_auto_assumptions)
                raw_payload_refs.extend(official_auto_raw_refs)
                field_sources.update(
                    {
                        field_name: official_auto_field_sources[field_name]
                        for field_name in applicable_official_updates
                        if field_name in official_auto_field_sources
                    }
                )
        except Exception as exc:
            assumptions.append(f"Geely official auto supplement failed: {exc}.")

    if _should_include_financial_indicators(code):
        try:
            financial_indicator_df = _fetch_hk_financial_indicator_df(code)
            financial_updates, financial_indicator_assumptions, financial_field_sources = _extract_hk_financial_indicator_fields(
                latest,
                financial_indicator_df,
                pd.Timestamp(latest["REPORT_DATE"]).date(),
            )
            if financial_updates:
                snapshot = snapshot.model_copy(update=financial_updates)
                field_sources.update(financial_field_sources)
                raw_payload_refs.append(f"eastmoney-hk-financial-indicator:{code}")
                assumptions.append(
                    "Financial-sector fields are supplemented from Eastmoney HK indicator tables when available."
                )
                assumptions.extend(financial_indicator_assumptions)
        except Exception as exc:
            assumptions.append(f"Financial-sector supplement fetch failed: {exc}.")
            analysis_only_updates, _, analysis_only_field_sources = _extract_hk_financial_indicator_fields(
                latest,
                pd.DataFrame(),
                pd.Timestamp(latest["REPORT_DATE"]).date(),
            )
            if analysis_only_updates:
                snapshot = snapshot.model_copy(update=analysis_only_updates)
                field_sources.update(analysis_only_field_sources)
                assumptions.append(
                    "Financial-sector fields available on the Eastmoney HK analysis table are retained even when the indicator endpoint is unavailable."
                )

        if snapshot.net_capital_ratio is None or snapshot.solvency_adequacy_ratio is None:
            try:
                official_updates, official_assumptions, official_raw_refs, official_field_sources = (
                    _fetch_hk_official_financial_fields(code)
                )
                if code == "06886" and snapshot.period_type != "annual":
                    official_updates = {
                        field_name: value for field_name, value in official_updates.items() if field_name != "net_capital_ratio"
                    }
                    official_field_sources = {
                        field_name: value for field_name, value in official_field_sources.items() if field_name != "net_capital_ratio"
                    }
                    if not official_updates:
                        official_assumptions = ()
                        official_raw_refs = ()
                applicable_official_updates = {
                    field_name: value
                    for field_name, value in official_updates.items()
                    if getattr(snapshot, field_name) is None
                }
                if applicable_official_updates:
                    snapshot = snapshot.model_copy(update=applicable_official_updates)
                    assumptions.extend(official_assumptions)
                    raw_payload_refs.extend(official_raw_refs)
                    field_sources.update(
                        {
                            field_name: official_field_sources[field_name]
                            for field_name in applicable_official_updates
                            if field_name in official_field_sources
                        }
                    )
            except Exception as exc:
                assumptions.append(f"Official HK financial fallback failed: {exc}.")

    if snapshot.dividend_yield is None:
        try:
            dividend_payout_df = _fetch_hk_dividend_payout_df(code)
            snapshot, payout_assumptions, payout_field_sources = _overlay_snapshot_with_dividend_payout(
                snapshot,
                dividend_payout_df,
            )
            assumptions.extend(payout_assumptions)
            field_sources.update(payout_field_sources)
            if not dividend_payout_df.empty:
                raw_payload_refs.append(f"eastmoney-hk-dividend-payout:{code}")
        except Exception as exc:
            assumptions.append(f"HK dividend payout supplement fetch failed: {exc}.")

    if quote_overlay_source is not None:
        normalized_overlay_source = quote_overlay_source.strip().lower()
        if normalized_overlay_source != "xueqiu":
            raise ValueError(f"不支持的港股 quote overlay 数据源: {quote_overlay_source}")

        xueqiu_quote = _fetch_hk_quote_xueqiu(code)
        snapshot, overlay_assumptions, overlay_field_sources = _overlay_snapshot_with_xueqiu_quote(snapshot, xueqiu_quote)
        assumptions.extend(overlay_assumptions)
        field_sources.update(overlay_field_sources)
        snapshot, field_sources = _apply_derived_cashflow_metrics(
            snapshot,
            field_sources,
            latest_operating_cashflow,
            capex,
        )
        raw_payload_refs.append(f"xueqiu-quote:{code}")

    return FundamentalSnapshotFetchResult(
        snapshot=snapshot,
        assumptions=tuple(assumptions),
        raw_payload_refs=tuple(raw_payload_refs),
        field_sources=field_sources,
    )


def fetch_hk_period_snapshots(
    symbol: str,
    name: Optional[str] = None,
    quote_overlay_source: Optional[str] = None,
) -> HkPeriodSnapshotsFetchResult:
    annual = fetch_hk_fundamental_snapshot(
        symbol=symbol,
        name=name,
        report_period_preference="annual_preferred",
        quote_overlay_source=quote_overlay_source,
    )
    try:
        interim = fetch_hk_fundamental_snapshot(
            symbol=symbol,
            name=name,
            report_period_preference="latest_interim",
            quote_overlay_source=quote_overlay_source,
        )
    except RuntimeError:
        interim = None

    if interim is not None and interim.snapshot.report_period <= annual.snapshot.report_period:
        interim = None

    return HkPeriodSnapshotsFetchResult(annual=annual, interim=interim)