"""First-version configurable fundamental scoring engine."""

from typing import Callable, List, Optional, Sequence, Tuple

from fundamental.config.models import DimensionConfig, SubmodelConfig
from fundamental.models.common import Rating
from fundamental.models.scorecard import (
    FundamentalDimensionScore,
    FundamentalScoreCard,
    TriggeredRule,
)
from fundamental.models.snapshot import FundamentalSnapshot
from fundamental.scoring.common_rules import (
    score_debt_to_asset,
    score_dupont_driver,
    score_guidance_attainment,
    score_net_profit_growth,
    score_operating_cashflow_to_profit,
    score_pe_percentile,
    score_peg,
    score_relative_pressure,
    score_revenue_growth,
    score_roe,
    score_roe_stability,
)
from fundamental.scoring.risk_rules import evaluate_automated_risk_rules


def _average(values: Sequence[Optional[float]]) -> Optional[float]:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present) / len(present)


def _weight_score(normalized_score: Optional[float], weight: int) -> float:
    if normalized_score is None:
        return 0.0
    return round((normalized_score / 100.0) * weight, 2)


def _build_metric_lists(
    snapshot: FundamentalSnapshot, dimension: DimensionConfig
) -> Tuple[List[str], List[str]]:
    used: List[str] = []
    missing: List[str] = []
    for metric in dimension.primary_metrics + dimension.optional_metrics:
        if getattr(snapshot, metric, None) is None:
            missing.append(metric)
        else:
            used.append(metric)
    return used, missing


def _score_profit_quality(snapshot: FundamentalSnapshot) -> Optional[float]:
    return _average(
        (
            score_roe(snapshot.roe),
            score_roe_stability(snapshot.roe_3y_cv),
            score_operating_cashflow_to_profit(snapshot.operating_cashflow_to_profit),
            score_dupont_driver(snapshot.dupont_driver),
        )
    )


def _score_growth_delivery(snapshot: FundamentalSnapshot) -> Optional[float]:
    return _average(
        (
            score_revenue_growth(snapshot.revenue_growth),
            score_net_profit_growth(snapshot.net_profit_growth),
            score_guidance_attainment(snapshot.guidance_attainment),
        )
    )


def _score_cashflow_efficiency(snapshot: FundamentalSnapshot) -> Optional[float]:
    return score_operating_cashflow_to_profit(snapshot.operating_cashflow_to_profit)


def _score_valuation_fit(snapshot: FundamentalSnapshot) -> Optional[float]:
    return _average((score_pe_percentile(snapshot.pe_percentile_5y), score_peg(snapshot.peg)))


def _score_growth_and_cycle(snapshot: FundamentalSnapshot) -> Optional[float]:
    return _average(
        (
            score_revenue_growth(snapshot.revenue_growth),
            score_net_profit_growth(snapshot.net_profit_growth),
        )
    )


def _score_operating_and_inventory_cycle(snapshot: FundamentalSnapshot) -> Optional[float]:
    return _average(
        (
            score_relative_pressure(snapshot.accounts_receivable_growth, snapshot.revenue_growth),
            score_relative_pressure(snapshot.inventory_growth, snapshot.revenue_growth),
            score_debt_to_asset(snapshot.debt_to_asset),
        )
    )


DIMENSION_SCORERS: dict[str, Callable[[FundamentalSnapshot], Optional[float]]] = {
    "profit_quality": _score_profit_quality,
    "growth_delivery": _score_growth_delivery,
    "cashflow_and_operating_efficiency": _score_cashflow_efficiency,
    "valuation_fit": _score_valuation_fit,
    "growth_and_cycle": _score_growth_and_cycle,
    "operating_and_inventory_cycle": _score_operating_and_inventory_cycle,
}


def _build_dimension_score(
    snapshot: FundamentalSnapshot, dimension: DimensionConfig
) -> FundamentalDimensionScore:
    used_metrics, missing_metrics = _build_metric_lists(snapshot, dimension)
    scorer = DIMENSION_SCORERS.get(dimension.name)
    normalized = scorer(snapshot) if scorer is not None else None
    score = _weight_score(normalized, dimension.weight)
    notes: List[str] = []
    if dimension.notes:
        notes.append(dimension.notes)
    if missing_metrics:
        notes.append("Missing metrics: {}".format(", ".join(missing_metrics)))

    return FundamentalDimensionScore(
        dimension=dimension.name,
        score=score,
        weight=dimension.weight,
        max_score=float(dimension.weight),
        used_metrics=used_metrics,
        missing_metrics=missing_metrics,
        notes=notes,
    )


def _map_rating(total_score: float, red_flag: bool) -> Rating:
    if red_flag:
        return "D"
    if total_score >= 80:
        return "A"
    if total_score >= 65:
        return "B"
    if total_score >= 45:
        return "C"
    return "D"


STRENGTH_MESSAGES = {
    "profit_quality": "盈利质量较好，利润与现金流匹配度较高。",
    "growth_delivery": "成长兑现较好，营收与利润增长质量较强。",
    "cashflow_and_operating_efficiency": "现金流兑现较好，经营效率表现稳定。",
    "valuation_fit": "当前估值匹配度较好，估值压力相对可控。",
    "growth_and_cycle": "景气与成长匹配较好，增长质量处于可接受区间。",
    "operating_and_inventory_cycle": "营运与库存压力可控，经营质量相对稳定。",
}


RISK_MESSAGES = {
    "profit_quality": "盈利质量偏弱，利润稳定性或现金流兑现存在压力。",
    "growth_delivery": "成长兑现偏弱，营收或利润增长支撑不足。",
    "cashflow_and_operating_efficiency": "现金流兑现偏弱，经营效率有待确认。",
    "valuation_fit": "估值匹配偏弱，当前价格对基本面要求较高。",
    "growth_and_cycle": "成长与景气支撑偏弱，周期位置仍需确认。",
    "operating_and_inventory_cycle": "营运与库存压力偏大，应收或存货质量需要警惕。",
}


def _message_for_dimension(
    mapping: dict[str, str],
    dimension_name: str,
    custom_mapping: Optional[dict[str, str]] = None,
) -> str:
    if custom_mapping is not None and dimension_name in custom_mapping:
        return custom_mapping[dimension_name]
    return mapping.get(dimension_name, f"{dimension_name} 表现需要进一步确认。")


def _build_strengths(
    dimension_scores: Sequence[FundamentalDimensionScore],
    submodel: SubmodelConfig,
) -> List[str]:
    strengths: List[str] = []
    for dimension in dimension_scores:
        if dimension.weight and dimension.score >= dimension.weight * 0.75:
            strengths.append(
                _message_for_dimension(
                    STRENGTH_MESSAGES,
                    dimension.dimension,
                    custom_mapping=submodel.explanation.strength_messages,
                )
            )
    return strengths[:3]


def _build_risks(
    dimension_scores: Sequence[FundamentalDimensionScore],
    triggered_rules: Sequence[TriggeredRule],
    submodel: SubmodelConfig,
) -> List[str]:
    risks: List[str] = []
    triggered_rule_ids = {rule.rule_id for rule in triggered_rules if rule.severity in ("risk", "red_flag")}

    for rule_ids, message in submodel.explanation.bundled_risk_messages.items():
        if set(rule_ids).issubset(triggered_rule_ids):
            risks.append(message)

    risks.extend(rule.message for rule in triggered_rules if rule.severity in ("risk", "red_flag"))
    for dimension in dimension_scores:
        if dimension.weight and dimension.score <= dimension.weight * 0.4:
            risks.append(
                _message_for_dimension(
                    RISK_MESSAGES,
                    dimension.dimension,
                    custom_mapping=submodel.explanation.risk_messages,
                )
            )

    deduped: List[str] = []
    for risk in risks:
        if risk not in deduped:
            deduped.append(risk)
    return deduped[:3]


def _build_warnings(triggered_rules: Sequence[TriggeredRule]) -> List[str]:
    return [rule.message for rule in triggered_rules if rule.severity == "warning"][:3]


def _build_combined_comment(
    submodel: SubmodelConfig,
    output_style: str,
    rating: Rating,
    red_flag: bool,
    strengths: Sequence[str],
    risks: Sequence[str],
) -> str:
    explanation = submodel.explanation
    if red_flag:
        summary = explanation.summary_when_red_flag.format(rating=rating)
    else:
        summary = explanation.summary_when_stable.format(rating=rating)

    highlight_part = (
        f"主要亮点是{strengths[0].rstrip('。')}。"
        if strengths
        else f"主要亮点是{explanation.fallback_highlight.rstrip('。')}。"
    )
    risk_part = (
        f"当前最需要跟踪的是{risks[0].rstrip('。')}。"
        if risks
        else f"当前最需要跟踪的是{explanation.fallback_risk.rstrip('。')}。"
    )

    if output_style == "cycle_inventory_cashflow_first":
        ordered_parts = [summary, risk_part, highlight_part]
    else:
        ordered_parts = [summary, highlight_part, risk_part]

    parts = [part for part in ordered_parts if part]
    return "".join(parts)


def score_snapshot(
    snapshot: FundamentalSnapshot,
    submodel: SubmodelConfig,
    missing_metrics: Optional[Sequence[str]] = None,
) -> FundamentalScoreCard:
    dimension_scores = [
        _build_dimension_score(snapshot, dimension) for dimension in submodel.dimensions
    ]
    triggered_rules = evaluate_automated_risk_rules(snapshot, submodel)
    red_flag = any(rule.severity == "red_flag" for rule in triggered_rules)
    total_score = round(sum(dimension.score for dimension in dimension_scores), 2)
    rating = _map_rating(total_score, red_flag)
    strengths = _build_strengths(dimension_scores, submodel)
    risks = _build_risks(dimension_scores, triggered_rules, submodel)
    warnings = _build_warnings(triggered_rules)

    return FundamentalScoreCard(
        symbol=snapshot.symbol,
        name=snapshot.name,
        market=snapshot.market,
        report_period=snapshot.report_period,
        industry_bucket=submodel.industry_bucket,
        submodel_id=submodel.submodel_id,
        submodel_version=submodel.version,
        total_score=total_score,
        rating=rating,
        red_flag=red_flag,
        dimension_scores=dimension_scores,
        strengths=strengths,
        risks=risks,
        warnings=warnings,
        focus_questions=list(submodel.explanation.focus_questions),
        missing_metrics=list(missing_metrics or []),
        triggered_rules=list(triggered_rules),
        combined_comment=_build_combined_comment(
            submodel,
            submodel.output_style,
            rating,
            red_flag,
            strengths,
            risks,
        ),
    )
