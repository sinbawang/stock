"""Shared helpers for source-related scorecard warnings."""

from __future__ import annotations

from datetime import date
from typing import Mapping, Optional


FIELD_LABELS = {
    "dividend_yield": "股息率",
    "solvency_adequacy_ratio": "综合偿付能力充足率",
    "combined_ratio": "综合成本率",
    "investment_return": "投资收益率",
    "embedded_value_growth": "内含价值增长率",
    "new_business_value_growth": "新业务价值增长率",
    "net_capital_ratio": "净资本比率",
    "revenue_growth": "营收增速",
    "net_profit_growth": "净利增速",
    "capex_to_operating_cashflow": "资本开支/经营现金流",
    "unit_cost_position": "单位成本位置",
    "reserve_life_index": "储量寿命指数",
    "commodity_price_sensitivity": "商品价格敏感度",
    "free_cashflow_yield": "自由现金流收益率",
}


def format_field_labels(field_names: list[str], labels: Optional[Mapping[str, str]] = None) -> str:
    mapping = dict(FIELD_LABELS)
    if labels:
        mapping.update(labels)
    return "、".join(mapping.get(field_name, field_name) for field_name in field_names)


def get_manual_supplement_fields(field_sources: Optional[Mapping[str, str]]) -> list[str]:
    if not field_sources:
        return []
    return sorted(
        field_name
        for field_name, source in field_sources.items()
        if source == "manual.supplement" and field_name != "notes"
    )


def build_manual_supplement_warning(
    field_sources: Optional[Mapping[str, str]],
    labels: Optional[Mapping[str, str]] = None,
) -> Optional[str]:
    manual_fields = get_manual_supplement_fields(field_sources)
    if not manual_fields:
        return None
    return f"以下字段当前使用手工补充口径: {format_field_labels(manual_fields, labels)}。"


def normalize_warnings(warnings: list[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for item in warnings:
        stripped = item.strip()
        if stripped and stripped not in normalized:
            normalized.append(stripped)
    return tuple(normalized)


def build_reporting_period_warning(report_period: date, period_type: Optional[str]) -> Optional[str]:
    if period_type == "annual" or (report_period.month == 12 and report_period.day == 31):
        return None

    period_label = "非年报"
    if report_period.month == 3 and report_period.day == 31:
        period_label = "一季报"
    elif report_period.month == 6 and report_period.day == 30:
        period_label = "中报"
    elif report_period.month == 9 and report_period.day == 30:
        period_label = "三季报"

    return (
        f"当前基本面评分基于 {report_period.isoformat()} 的{period_label}口径，"
        "不要直接与年报口径标的横向比较。"
    )