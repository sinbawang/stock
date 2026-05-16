"""Render a FundamentalScoreCard into a readable text summary."""

from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from fundamental.models.common import format_display_literal
from fundamental.models.scorecard import FundamentalScoreCard
from fundamental.models.snapshot import FundamentalSnapshot


DIMENSION_LABELS = {
    "capital_safety_and_asset_quality": "资本安全与资产质量",
    "profitability_and_stability": "盈利能力与稳定性",
    "business_growth_and_quality": "增长与业务质量",
    "shareholder_return_and_valuation": "估值与股东回报",
    "profit_quality": "盈利质量",
    "growth_delivery": "成长兑现",
    "cashflow_and_operating_efficiency": "现金流与运营效率",
    "valuation_fit": "估值匹配",
    "yield_and_valuation": "股息与估值",
    "growth_and_cycle": "成长与景气度",
    "operating_and_inventory_cycle": "营运与库存周期",
    "inventory_channel_and_turnover": "渠道与周转效率",
    "resource_cycle_resilience": "资源周期韧性",
}

METRIC_DISPLAY_NAMES = {
    "peg": "PEG",
    "dupont_driver": "杜邦驱动",
    "guidance_attainment": "指引兑现",
    "user_growth": "用户增长",
    "arpu_growth": "ARPU增长",
    "deferred_revenue_growth": "递延收入增长",
    "marketing_expense_ratio": "营销费用率",
    "dividend_yield": "股息率",
    "new_game_pipeline_strength": "新游储备强度",
    "overseas_revenue_growth": "海外收入增长",
    "overseas_revenue_share": "海外收入占比",
    "order_backlog_growth": "订单增长",
    "capacity_utilization": "产能利用率",
    "capex_growth": "资本开支增长",
    "wafer_price_trend": "晶圆价格趋势",
    "inventory_growth_history": "存货增长历史",
    "accounts_receivable_growth_history": "应收增长历史",
    "order_backlog_history": "订单历史",
}


def _display_metric_name(metric_name: str) -> str:
    return METRIC_DISPLAY_NAMES.get(metric_name, metric_name)


def _format_dimension_name(name: str) -> str:
    return DIMENSION_LABELS.get(name, name)


def _normalize_items(values: list[str]) -> list[str]:
    normalized = []
    for value in values:
        stripped = value.strip()
        if stripped and stripped not in normalized:
            normalized.append(stripped)
    return normalized


def _sort_missing_metrics(values: list[str]) -> list[str]:
    return sorted(value for value in _normalize_items(values) if value != "notes")


def _metric_unavailable_reason(metric_name: str, snapshot: Optional[FundamentalSnapshot]) -> Optional[str]:
    if snapshot is None:
        return None
    if metric_name == "peg":
        if (snapshot.pe_ttm is not None and snapshot.pe_ttm <= 0) or (
            snapshot.net_profit_growth is not None and snapshot.net_profit_growth <= 0
        ):
            return "PE或净利增速为负"
    if metric_name == "dupont_driver":
        if (snapshot.roe is not None and snapshot.roe <= 0) or (
            snapshot.net_margin is not None and snapshot.net_margin <= 0
        ):
            return "ROE或净利率为负"
    return None


def _partition_missing_metrics(
    values: list[str],
    snapshot: Optional[FundamentalSnapshot],
) -> tuple[list[str], list[str]]:
    missing: list[str] = []
    unavailable: list[str] = []
    for value in _sort_missing_metrics(values):
        reason = _metric_unavailable_reason(value, snapshot)
        if reason is None:
            missing.append(_display_metric_name(value))
            continue
        display_name = _display_metric_name(value)
        unavailable.append(f"{display_name}（当前不适用：{reason}）")
    return missing, unavailable


def _format_score_basis_for_display(
    score_basis: Optional[str],
    snapshot: Optional[FundamentalSnapshot],
) -> Optional[str]:
    if not score_basis:
        return None

    formatted_parts: list[str] = []
    for part in (item.strip() for item in score_basis.split(";")):
        if not part:
            continue
        if part.startswith("缺失[") and part.endswith("]"):
            raw_items = [item.strip() for item in part[3:-1].split(",") if item.strip()]
            missing_items: list[str] = []
            unavailable_items: list[str] = []
            for item in raw_items:
                label = item.replace(" NA", "")
                metric_name = None
                if label == "PEG":
                    metric_name = "peg"
                elif label == "杜邦驱动":
                    metric_name = "dupont_driver"
                reason = _metric_unavailable_reason(metric_name, snapshot) if metric_name else None
                if reason is None:
                    missing_items.append(item)
                    continue
                unavailable_items.append(f"{label}: {reason}")
            if missing_items:
                formatted_parts.append(f"缺失[{', '.join(missing_items)}]")
            if unavailable_items:
                formatted_parts.append(f"不适用[{', '.join(unavailable_items)}]")
            continue
        formatted_parts.append(part)
    return "; ".join(formatted_parts)


def _render_lines(title: str, values: list[str]) -> list[str]:
    if not values:
        return []
    lines = [title]
    lines.extend(f"- {value}" for value in values)
    return lines


def _render_numbered_lines(title: str, values: list[str]) -> list[str]:
    if not values:
        return []
    lines = [title]
    lines.extend(f"{index}. {value}" for index, value in enumerate(values, start=1))
    return lines


def _format_scalar(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return format(value, ".12g")
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_format_scalar(item) for item in value) + "]"
    if isinstance(value, str):
        text = format_display_literal(value) or value
    else:
        text = str(value)
    if any(char in text for char in [",", "，", "=", '"']):
        return '"' + text.replace('"', '\\"') + '"'
    return text


def _should_include_auto_specialist_summary(
    snapshot: FundamentalSnapshot,
    scorecard: FundamentalScoreCard,
) -> bool:
    if scorecard.submodel_id.startswith("auto_"):
        return True
    return any(
        getattr(snapshot, field_name, None) is not None
        for field_name in ("overseas_revenue_share", "price_war_pressure")
    )


def _render_snapshot_metric_lines(
    snapshot: Optional[FundamentalSnapshot],
    scorecard: Optional[FundamentalScoreCard] = None,
) -> list[str]:
    if snapshot is None:
        return []

    groups = (
        ("关键指标", ("pe_ttm", "pb", "ps_ttm", "peg", "dividend_yield")),
        (
            "成长兑现指标",
            ("revenue_growth", "net_profit_growth", "guidance_attainment"),
        ),
        (
            "质量与稳健指标",
            (
                "roe",
                "roe_3y_mean",
                "roe_3y_cv",
                "gross_margin",
                "gross_margin_trend",
                "operating_cashflow_to_profit",
                "operating_cashflow_to_profit_history",
                "current_ratio",
                "debt_to_asset",
            ),
        ),
        (
            "现金流与杠杆指标",
            (
                "operating_cashflow_growth",
                "interest_bearing_debt_growth",
                "capex_to_operating_cashflow",
                "free_cashflow_yield",
            ),
        ),
        (
            "汽车经营专项指标",
            (
                "overseas_revenue_share",
                "price_war_pressure",
            ),
        ),
        (
            "资源经营专项指标",
            (
                "unit_cost_position",
                "reserve_life_index",
                "commodity_price_sensitivity",
            ),
        ),
        (
            "银行监管与息差指标",
            (
                "capital_adequacy_ratio",
                "core_tier1_ratio",
                "npl_ratio",
                "provision_coverage_ratio",
                "net_interest_margin",
                "loan_deposit_growth_gap",
            ),
        ),
        (
            "保险经营与偿付指标",
            (
                "solvency_adequacy_ratio",
                "combined_ratio",
                "investment_return",
                "embedded_value_growth",
                "new_business_value_growth",
            ),
        ),
        ("券商监管指标", ("net_capital_ratio",)),
    )

    lines: list[str] = []
    for title, field_names in groups:
        if (
            title == "汽车经营专项指标"
            and scorecard is not None
            and not _should_include_auto_specialist_summary(snapshot, scorecard)
        ):
            continue
        parts = []
        for field_name in field_names:
            value = getattr(snapshot, field_name, None)
            if value is not None:
                parts.append(f"{field_name}={_format_scalar(value)}")
        if parts:
            lines.extend(["", title, f"- {', '.join(parts)}"])
    return lines


def render_scorecard_text(scorecard: FundamentalScoreCard, snapshot: Optional[FundamentalSnapshot] = None) -> str:
    header = (
        f"{scorecard.name} ({scorecard.symbol}) | "
        f"{scorecard.industry_bucket}/{scorecard.submodel_id} | {scorecard.report_period.isoformat()}"
    )
    summary = (
        f"总分: {scorecard.total_score:.2f} | "
        f"评级: {scorecard.rating} | "
        f"红线: {'是' if scorecard.red_flag else '否'}"
    )

    focus_questions = _normalize_items(scorecard.focus_questions)

    body: list[str] = [header, summary]
    focus_question_lines = _render_numbered_lines("关注问题", focus_questions)
    if focus_question_lines:
        body.extend(["", *focus_question_lines])

    dimension_lines = ["维度得分"]
    for dimension in scorecard.dimension_scores:
        dimension_lines.append(
            f"- {_format_dimension_name(dimension.dimension)}: "
            f"{dimension.score:.2f}/{dimension.weight:.2f}"
        )
        score_basis = _format_score_basis_for_display(dimension.score_basis, snapshot)
        if score_basis:
            dimension_lines.append(f"  计算: {score_basis}")

    body.extend(["", *dimension_lines])

    strengths = _normalize_items(scorecard.strengths)
    risks = _normalize_items(scorecard.risks)
    warnings = _normalize_items(scorecard.warnings)
    missing_metrics, unavailable_metrics = _partition_missing_metrics(scorecard.missing_metrics, snapshot)

    for title, values in (
        ("优势", strengths),
        ("风险", risks),
        ("警告", warnings),
        ("当前不适用字段", unavailable_metrics),
        ("缺失指标", missing_metrics),
    ):
        section_lines = _render_lines(title, values)
        if section_lines:
            body.extend(["", *section_lines])

    body.extend(_render_snapshot_metric_lines(snapshot, scorecard=scorecard))

    if scorecard.combined_comment:
        body.extend(["", "综合说明", f"- {scorecard.combined_comment}"])

    return "\n".join(line for line in body if line is not None).strip()


def save_scorecard_text(
    scorecard: FundamentalScoreCard,
    snapshot: Optional[FundamentalSnapshot] = None,
    output_dir: Union[str, Path] = "data/_meta",
    generated_at: Optional[datetime] = None,
) -> Path:
    generated = generated_at or datetime.now()
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    file_name = (
        f"{scorecard.symbol}_{scorecard.name}_{scorecard.submodel_id}_scorecard_"
        f"{generated.strftime('%Y%m%d_%H%M%S')}.txt"
    )
    output_path = target_dir / file_name
    output_path.write_text(
        render_scorecard_text(scorecard=scorecard, snapshot=snapshot) + "\n",
        encoding="utf-8",
    )
    return output_path
