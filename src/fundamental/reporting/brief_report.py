"""Render and save user-facing fundamental brief text files."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from typing import Any, Mapping, Optional, Sequence

from fundamental.models.blended import BlendedFundamentalScoreCard, OverlayComponent
from fundamental.models.common import format_display_literal
from fundamental.models.scorecard import FundamentalScoreCard
from fundamental.models.snapshot import FundamentalSnapshot
from report_retention import prune_older_outputs

from .text_report import (
    DIMENSION_LABELS,
    _build_overlay_coverage_lines,
    _display_metric_name,
    _format_score_basis_for_display,
    _metric_unavailable_reason,
    _partition_missing_metrics,
)


COMMON_METRIC_DISPLAY_NAMES = {
    "roe": "ROE",
    "roe_3y_mean": "3年ROE均值",
    "roe_3y_cv": "ROE波动CV",
    "gross_margin": "毛利率",
    "gross_margin_trend": "毛利率趋势",
    "operating_cashflow_to_profit": "经营现金流/利润",
    "operating_cashflow_to_profit_history": "经营现金流/利润历史",
    "revenue_growth": "营收增速",
    "net_profit_growth": "净利增速",
    "accounts_receivable_growth": "应收增速",
    "inventory_growth": "存货增速",
    "asset_turnover": "资产周转率",
    "current_ratio": "流动比率",
    "debt_to_asset": "资产负债率",
    "pe_ttm": "PE(TTM)",
    "pe_percentile_5y": "5年PE分位",
    "pb": "PB",
    "ps_ttm": "PS(TTM)",
    "dividend_yield": "股息率",
    "core_tier1_ratio": "核心一级资本充足率",
    "npl_ratio": "不良率",
    "provision_coverage_ratio": "拨备覆盖率",
    "net_interest_margin": "净息差",
    "loan_deposit_growth_gap": "存贷增速缺口",
}

INTERIM_COMPONENT_LABELS = {
    "growth_refresh": "成长刷新",
    "cashflow_refresh": "现金流刷新",
    "resilience_refresh": "韧性刷新",
    "operating_cycle_refresh": "营运周期刷新",
    "channel_cycle_refresh": "渠道周期刷新",
    "profit_quality_refresh": "盈利质量刷新",
    "capital_refresh": "资本刷新",
    "profitability_refresh": "盈利刷新",
    "business_quality_refresh": "业务质量刷新",
    "business_growth_refresh": "业务增长刷新",
    "shareholder_return_refresh": "股东回报刷新",
}


def _format_dimension_name(name: str) -> str:
    return DIMENSION_LABELS.get(name, name.replace("_", " ").title())


def _normalize_items(values: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        stripped = value.strip()
        if stripped and stripped not in normalized:
            normalized.append(stripped)
    return normalized


def _format_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_format_scalar(item) for item in value) + "]"
    if isinstance(value, str):
        text = format_display_literal(value) or value
    else:
        text = str(value)
    if any(char in text for char in [",", "，", "=", '"']):
        return '"' + text.replace('"', '\\"') + '"'
    return text


def _manual_supplement_lines(snapshot: FundamentalSnapshot, field_sources: Optional[Mapping[str, str]]) -> list[str]:
    if not field_sources:
        return []

    lines: list[str] = []
    for field_name in sorted(field_name for field_name, source in field_sources.items() if source == "manual.supplement"):
        value = getattr(snapshot, field_name, None)
        lines.append(f"- {field_name}={_format_scalar(value)}")
    return lines


def _dupont_summary_line(snapshot: FundamentalSnapshot) -> Optional[str]:
    return _dupont_summary_line_filtered(snapshot, excluded_metrics=None)


def _dupont_summary_line_filtered(
    snapshot: FundamentalSnapshot,
    excluded_metrics: Optional[set[str]],
) -> Optional[str]:
    items: list[str] = []
    for label, field_name in (
        ("净利率", "net_margin"),
        ("总资产周转率", "asset_turnover"),
        ("权益乘数", "equity_multiplier"),
        ("杜邦驱动", "dupont_driver"),
    ):
        if excluded_metrics and field_name in excluded_metrics:
            continue
        value = getattr(snapshot, field_name, None)
        if value is not None:
            items.append(f"{label}={_format_scalar(value)}")
    if not items:
        return None
    return "- 杜邦拆解: " + ", ".join(items)


def _should_include_auto_specialist_summary(
    snapshot: FundamentalSnapshot,
    scorecard: Optional[FundamentalScoreCard],
) -> bool:
    if scorecard is not None and scorecard.submodel_id.startswith("auto_"):
        return True
    return any(
        getattr(snapshot, field_name, None) is not None
        for field_name in ("overseas_revenue_share", "price_war_pressure")
    )


def _key_metric_summary_lines(
    snapshot: FundamentalSnapshot,
    scorecard: Optional[FundamentalScoreCard] = None,
    excluded_metrics: Optional[set[str]] = None,
) -> list[str]:
    return [
        f"- {label}: " + ", ".join(parts)
        for label, parts in _key_metric_summary_groups(
            snapshot,
            scorecard=scorecard,
            excluded_metrics=excluded_metrics,
        )
    ]


def _key_metric_summary_groups(
    snapshot: FundamentalSnapshot,
    scorecard: Optional[FundamentalScoreCard] = None,
    excluded_metrics: Optional[set[str]] = None,
) -> list[tuple[str, list[str]]]:
    groups = (
        ("估值与回报", ("pe_ttm", "pb", "ps_ttm", "peg", "dividend_yield")),
        (
            "成长兑现",
            (
                "revenue_growth",
                "net_profit_growth",
                "guidance_attainment",
            ),
        ),
        (
            "质量与稳健",
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
            "现金流与杠杆",
            (
                "operating_cashflow_growth",
                "interest_bearing_debt_growth",
                "capex_to_operating_cashflow",
                "free_cashflow_yield",
            ),
        ),
        (
            "汽车经营专项",
            (
                "overseas_revenue_share",
                "price_war_pressure",
            ),
        ),
        (
            "资源经营专项",
            (
                "unit_cost_position",
                "reserve_life_index",
                "commodity_price_sensitivity",
            ),
        ),
        (
            "银行监管与息差",
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
            "保险经营与偿付",
            (
                "solvency_adequacy_ratio",
                "combined_ratio",
                "investment_return",
                "embedded_value_growth",
                "new_business_value_growth",
            ),
        ),
        ("券商监管", ("net_capital_ratio",)),
    )

    lines: list[tuple[str, list[str]]] = []
    for label, field_names in groups:
        if label == "汽车经营专项" and not _should_include_auto_specialist_summary(snapshot, scorecard):
            continue
        parts = []
        for field_name in field_names:
            if excluded_metrics and field_name in excluded_metrics:
                continue
            value = getattr(snapshot, field_name, None)
            if value is not None:
                parts.append(f"{field_name}={_format_scalar(value)}")
        if parts:
            lines.append((label, parts))
    return lines


def _key_metric_summary_block_lines(
    snapshot: FundamentalSnapshot,
    scorecard: Optional[FundamentalScoreCard] = None,
    excluded_metrics: Optional[set[str]] = None,
) -> list[str]:
    lines: list[str] = []
    for label, parts in _key_metric_summary_groups(
        snapshot,
        scorecard=scorecard,
        excluded_metrics=excluded_metrics,
    ):
        lines.append(f"- {label}:")
        lines.extend(f"  {part}" for part in parts)
    return lines


def _dupont_summary_block_lines(
    snapshot: FundamentalSnapshot,
    excluded_metrics: Optional[set[str]],
) -> list[str]:
    items: list[str] = []
    for label, field_name in (
        ("净利率", "net_margin"),
        ("总资产周转率", "asset_turnover"),
        ("权益乘数", "equity_multiplier"),
        ("杜邦驱动", "dupont_driver"),
    ):
        if excluded_metrics and field_name in excluded_metrics:
            continue
        value = getattr(snapshot, field_name, None)
        if value is not None:
            items.append(f"{label}={_format_scalar(value)}")
    if not items:
        return []
    return ["- 杜邦拆解:", *[f"  {item}" for item in items]]


def _collect_blended_covered_metrics(blended: BlendedFundamentalScoreCard) -> set[str]:
    covered_metrics: set[str] = set()
    for dimension in blended.annual_anchor.scorecard.dimension_scores:
        covered_metrics.update(metric_name for metric_name in dimension.used_metrics if metric_name)
    if blended.interim_overlay is not None:
        for component in blended.interim_overlay.components:
            covered_metrics.update(metric_name for metric_name in component.covered_metrics if metric_name)
    return covered_metrics


def _format_score_basis_summary(score_basis: Optional[str]) -> Optional[str]:
    if not score_basis:
        return None

    normalized_parts: list[str] = []
    for part in (item.strip() for item in score_basis.split(";")):
        if not part:
            continue
        scored_match = re.fullmatch(r"已计分(\d+/\d+)项\[(.*)\]", part)
        if scored_match:
            normalized_parts.append(f"{scored_match.group(1)}项 {scored_match.group(2)}")
            continue
        if part.startswith("已计分") and part.endswith("项"):
            normalized_parts.append(part.replace("已计分", ""))
            continue
        if part.startswith("平均="):
            normalized_parts.append("平均" + part[len("平均=") :])
            continue
        if part.startswith("缺失[") and part.endswith("]"):
            missing_text = part[3:-1].replace(" NA", "")
            normalized_parts.append("缺失 " + missing_text)
            continue
        if part.startswith("不适用[") and part.endswith("]"):
            unavailable_text = part[4:-1].replace(": ", "（")
            unavailable_text = unavailable_text + "）" if "（" in unavailable_text else unavailable_text
            normalized_parts.append("不适用 " + unavailable_text)
            continue
        weighted_match = re.fullmatch(r"×\d+/100=(.*)", part)
        if weighted_match:
            normalized_parts.append(f"折算{weighted_match.group(1)}")
            continue
        if part.startswith("维度分="):
            normalized_parts.append("维度分" + part[len("维度分=") :])
            continue
        normalized_parts.append(part)

    if not normalized_parts:
        return None

    summary = "; ".join(normalized_parts)
    summary = re.sub(r"->(-?\d+(?:\.\d+)?)", lambda match: f"->{float(match.group(1)):.2f}", summary)
    summary = re.sub(r"平均(-?\d+(?:\.\d+)?)", lambda match: f"平均{float(match.group(1)):.2f}", summary)
    summary = re.sub(r"维度分(-?\d+(?:\.\d+)?)", lambda match: f"维度分{float(match.group(1)):.2f}", summary)
    return summary


def _format_metric_name(metric_name: str) -> str:
    return COMMON_METRIC_DISPLAY_NAMES.get(metric_name, _display_metric_name(metric_name))


def _format_metric_list(metric_names: Sequence[str]) -> Optional[str]:
    items = [_format_metric_name(metric_name) for metric_name in metric_names if metric_name]
    if not items:
        return None
    return "、".join(items)


def _format_metric_value_pair(snapshot: FundamentalSnapshot, metric_name: str) -> str:
    return f"{_format_metric_name(metric_name)}={_format_scalar(getattr(snapshot, metric_name, None))}"


def _format_metric_value_list(snapshot: FundamentalSnapshot, metric_names: Sequence[str]) -> Optional[str]:
    items = [_format_metric_value_pair(snapshot, metric_name) for metric_name in metric_names if metric_name]
    if not items:
        return None
    return "、".join(items)


def _split_dimension_summary_lines(summary: str) -> list[str]:
    lines: list[str] = []
    parts = [part.strip() for part in summary.split(";") if part.strip()]
    if not parts:
        return lines

    first_part = parts[0]
    first_match = re.match(r"^(\d+/\d+项)\s+(.*)$", first_part)
    if first_match:
        lines.append(first_match.group(1))
        scored_items = [item.strip() for item in first_match.group(2).split(",") if item.strip()]
        lines.extend(scored_items)
    else:
        lines.append(first_part)

    for part in parts[1:]:
        lines.append(part)
    return lines


def _build_dimension_calculation_lines(
    scorecard: FundamentalScoreCard,
    snapshot: FundamentalSnapshot,
) -> list[str]:
    lines: list[str] = []

    for dimension in scorecard.dimension_scores:
        summary = _format_score_basis_summary(
            _format_score_basis_for_display(dimension.score_basis, snapshot)
        )
        if summary:
            summary_lines = _split_dimension_summary_lines(summary)
            if summary_lines:
                lines.append(f"- {_format_dimension_name(dimension.dimension)}: {summary_lines[0]}")
                lines.extend(f"  {line}" for line in summary_lines[1:])
            else:
                lines.append(f"- {_format_dimension_name(dimension.dimension)}:")
        else:
            lines.append(
                f"- {_format_dimension_name(dimension.dimension)}: {dimension.score:.2f}/{dimension.weight:.2f}"
            )

    return lines


def _format_component_name(name: str) -> str:
    return INTERIM_COMPONENT_LABELS.get(name, name.replace("_", " ").title())


def _build_interim_calculation_lines(
    components: Sequence[OverlayComponent],
    snapshot: FundamentalSnapshot,
) -> list[str]:
    lines: list[str] = []
    for component in components:
        contribution = component.score * component.weight
        metric_names = list(component.covered_metrics) + [
            metric_name for metric_name in component.missing_metrics if metric_name not in component.covered_metrics
        ]
        formula = "单指标刷新" if len(component.covered_metrics) <= 1 else "覆盖指标均值刷新"
        if component.missing_metrics:
            missing_text = _format_metric_list(component.missing_metrics)
            if missing_text:
                formula += f"；缺失 {missing_text}"
        lines.append(f"- {_format_component_name(component.component)}:")

        for metric_name in metric_names:
            lines.append(f"  {_format_metric_value_pair(snapshot, metric_name)}")

        lines.append(f"  {formula}")
        lines.append(f"  折算{contribution:.2f}")

        if component.note:
            lines.append(f"  说明: {component.note}")

    return lines


def _render_interim_breakdown_line(component: OverlayComponent) -> str:
    return f"- {_format_component_name(component.component)}: {component.score:.2f} x {component.weight:.0%}"


def render_fundamental_brief(
    scorecard: FundamentalScoreCard,
    snapshot: FundamentalSnapshot,
    field_sources: Optional[Mapping[str, str]] = None,
    generated_at: Optional[datetime] = None,
) -> str:
    generated = generated_at or datetime.now()
    strengths = _normalize_items(scorecard.strengths)
    risks = _normalize_items(scorecard.risks)
    warnings = _normalize_items(scorecard.warnings)
    missing_metrics, unavailable_metrics = _partition_missing_metrics(list(scorecard.missing_metrics), snapshot)
    supplement_lines = _manual_supplement_lines(snapshot, field_sources)

    lines = [
        f"{scorecard.name}基本面简报",
        f"时间: {generated.strftime('%Y-%m-%d %H:%M')}",
        f"标的: {scorecard.name}({scorecard.symbol})  报告期: {scorecard.report_period.isoformat()}",
        f"评级: {scorecard.rating}  总分: {scorecard.total_score:.2f}  红线: {'有' if scorecard.red_flag else '无'}",
        f"子模型: {scorecard.submodel_id}",
        "",
        "核心结论:",
    ]
    lines.extend(
        f"- {_format_dimension_name(dimension.dimension)} {dimension.score:.2f}/{dimension.weight:.2f}。"
        for dimension in scorecard.dimension_scores
    )
    calculation_lines = [
        f"- {_format_dimension_name(dimension.dimension)}: {summary}"
        for dimension in scorecard.dimension_scores
        for summary in [
            _format_score_basis_summary(
                _format_score_basis_for_display(dimension.score_basis, snapshot)
            )
        ]
        if summary
    ]
    if calculation_lines:
        lines.extend(["", "计算说明:", *calculation_lines])

    if strengths:
        lines.extend(["", "亮点:"])
        lines.extend(f"- {item}" for item in strengths)
    if risks:
        lines.extend(["", "风险:"])
        lines.extend(f"- {item}" for item in risks)
    if warnings:
        lines.extend(["", "警告:"])
        lines.extend(f"- {item}" for item in warnings)
    if unavailable_metrics:
        lines.extend(["", "当前不适用字段:"])
        lines.extend(f"- {item}" for item in unavailable_metrics)
    if missing_metrics:
        lines.extend(["", "当前缺失字段:"])
        lines.extend(f"- {item}" for item in missing_metrics)

    lines.extend(["", "补充说明:"])
    lines.extend(_key_metric_summary_lines(snapshot, scorecard=scorecard))
    dupont_summary = _dupont_summary_line(snapshot)
    if dupont_summary:
        lines.append(dupont_summary)
    if field_sources and field_sources.get("market_cap"):
        lines.append(f"- market_cap 来源: {field_sources['market_cap']}")
    if scorecard.combined_comment:
        lines.append(f"- 综合说明: {scorecard.combined_comment}")

    if supplement_lines:
        lines.extend(["", "手工补充字段:", *supplement_lines])

    return "\n".join(lines).strip() + "\n"


def save_fundamental_brief(
    scorecard: FundamentalScoreCard,
    snapshot: FundamentalSnapshot,
    field_sources: Optional[Mapping[str, str]] = None,
    output_dir: str | Path = "data/_meta",
    generated_at: Optional[datetime] = None,
) -> Path:
    generated = generated_at or datetime.now()
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    file_prefix = f"{scorecard.symbol}_{scorecard.name}_{scorecard.submodel_id}_fundamental_brief_"
    file_name = f"{file_prefix}{generated.strftime('%Y%m%d_%H%M%S')}.txt"
    output_path = target_dir / file_name
    output_path.write_text(
        render_fundamental_brief(
            scorecard=scorecard,
            snapshot=snapshot,
            field_sources=field_sources,
            generated_at=generated,
        ),
        encoding="utf-8",
    )
    prune_older_outputs(target_dir, f"{file_prefix}*.txt", keep_path=output_path)
    return output_path


def render_blended_fundamental_brief(
    blended: BlendedFundamentalScoreCard,
    generated_at: Optional[datetime] = None,
) -> str:
    generated = generated_at or datetime.now()
    annual_anchor = blended.annual_anchor
    interim_overlay = blended.interim_overlay
    annual_scorecard = annual_anchor.scorecard
    strengths = _normalize_items(annual_scorecard.strengths)
    risks = _normalize_items(annual_scorecard.risks)
    warnings = _normalize_items(list(blended.warnings))
    missing_metrics, unavailable_metrics = _partition_missing_metrics(
        list(annual_scorecard.missing_metrics),
        annual_anchor.snapshot,
    )

    lines = [
        f"{blended.name}基本面混合简报",
        f"时间: {generated.strftime('%Y-%m-%d %H:%M')}",
        f"标的: {blended.name}({blended.symbol})",
        "报告期:",
        f"- 年报: {annual_anchor.snapshot.report_period.isoformat()}",
        (
            f"- 季报: {interim_overlay.snapshot.report_period.isoformat()}"
            if interim_overlay is not None
            else "- 季报: 暂无"
        ),
        "评分概览:",
        f"- 评级: {blended.blended_rating}",
        f"- 总分: {blended.blended_total_score:.2f}",
    ]
    lines.append(f"- 年报锚定分: {annual_scorecard.total_score:.2f} ({annual_scorecard.rating})。")
    if interim_overlay is None:
        lines.append("- 季报刷新层: 暂无更新的中间报告期。")
    else:
        lines.append(
            f"- 季报刷新层: {interim_overlay.overlay_score:.2f} ({interim_overlay.rating_hint or 'NA'})。"
        )
    lines.extend(
        [
            f"- 年报权重: {blended.annual_weight:.0%}",
            f"- 季报权重: {blended.interim_weight:.0%}",
            f"- 子模型: {blended.submodel_id}",
            f"- 刷新标签: {blended.freshness_label}",
        ]
    )

    lines.extend(["", "年报维度结论:"])
    lines.extend(
        f"- {_format_dimension_name(dimension.dimension)} {dimension.score:.2f}/{dimension.weight:.2f}。"
        for dimension in annual_scorecard.dimension_scores
    )
    annual_calculation_lines = _build_dimension_calculation_lines(annual_scorecard, annual_anchor.snapshot)
    if annual_calculation_lines:
        lines.extend(["", "年报维度分计算:", *annual_calculation_lines])

    if interim_overlay is not None:
        lines.extend(["", "季报刷新层拆解:"])
        lines.extend(_build_overlay_coverage_lines(interim_overlay, blended.submodel_id))
        for component in interim_overlay.components:
            lines.append(_render_interim_breakdown_line(component))
        interim_calculation_lines = _build_interim_calculation_lines(
            interim_overlay.components,
            interim_overlay.snapshot,
        )
        if interim_calculation_lines:
            lines.extend(["", "季报维度分计算:", *interim_calculation_lines])

    if strengths:
        lines.extend(["", "亮点:"])
        lines.extend(f"- {item}" for item in strengths)
    if risks:
        lines.extend(["", "风险:"])
        lines.extend(f"- {item}" for item in risks)
    if warnings:
        lines.extend(["", "警告:"])
        lines.extend(f"- {item}" for item in warnings)
    if unavailable_metrics:
        lines.extend(["", "当前不适用字段:"])
        lines.extend(f"- {item}" for item in unavailable_metrics)
    if missing_metrics:
        lines.extend(["", "当前缺失字段:"])
        lines.extend(f"- {item}" for item in missing_metrics)

    covered_metrics = _collect_blended_covered_metrics(blended)
    supplemental_lines = _key_metric_summary_block_lines(
        annual_anchor.snapshot,
        scorecard=annual_scorecard,
        excluded_metrics=covered_metrics,
    )
    dupont_lines = _dupont_summary_block_lines(annual_anchor.snapshot, excluded_metrics=covered_metrics)
    if supplemental_lines or dupont_lines:
        lines.extend(["", "年报补充指标:"])
        lines.extend(supplemental_lines)
        lines.extend(dupont_lines)

    return "\n".join(lines).strip() + "\n"


def save_blended_fundamental_brief(
    blended: BlendedFundamentalScoreCard,
    output_dir: str | Path = "data/_meta",
    generated_at: Optional[datetime] = None,
) -> Path:
    generated = generated_at or datetime.now()
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    file_prefix = f"{blended.symbol}_{blended.name}_{blended.submodel_id}_blended_fundamental_brief_"
    file_name = f"{file_prefix}{generated.strftime('%Y%m%d_%H%M%S')}.txt"
    output_path = target_dir / file_name
    output_path.write_text(
        render_blended_fundamental_brief(blended=blended, generated_at=generated),
        encoding="utf-8",
    )
    prune_older_outputs(target_dir, f"{file_prefix}*.txt", keep_path=output_path)
    return output_path