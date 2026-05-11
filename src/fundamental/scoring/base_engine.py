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
    score_asset_turnover,
    score_combined_ratio,
    score_capex_to_operating_cashflow,
    score_commodity_price_sensitivity,
    score_core_tier1_ratio,
    score_dividend_yield,
    score_debt_to_asset,
    score_dupont_driver,
    score_guidance_attainment,
    score_investment_return,
    score_loan_deposit_growth_gap,
    score_gross_margin_trend,
    score_net_profit_growth,
    score_net_capital_ratio,
    score_net_interest_margin,
    score_npl_ratio,
    score_operating_cashflow_to_profit,
    score_overseas_revenue_share,
    score_pe_percentile,
    score_peg,
    score_pb_financial,
    score_price_war_pressure,
    score_provision_coverage_ratio,
    score_relative_pressure,
    score_reserve_life_index,
    score_revenue_growth,
    score_roe,
    score_roe_stability,
    score_solvency_adequacy_ratio,
    score_unit_cost_position,
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


def _format_metric_value(value: object) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _format_score_basis(parts: Sequence[tuple[str, Optional[float]]], normalized_score: Optional[float], weight: int) -> Optional[str]:
    present_parts = [(label, score) for label, score in parts if score is not None]
    missing_parts = [label for label, score in parts if score is None]
    if not present_parts and not missing_parts:
        return None

    total_parts = len(parts)
    segments: List[str] = []
    if present_parts:
        joined = ", ".join(f"{label}->{score:.1f}" for label, score in present_parts)
        segments.append(f"已计分{len(present_parts)}/{total_parts}项[{joined}]")
        if normalized_score is not None:
            segments.append(f"平均={normalized_score:.1f}")
    else:
        segments.append(f"已计分0/{total_parts}项")

    if missing_parts:
        segments.append(f"缺失[{', '.join(missing_parts)}]")

    if normalized_score is not None:
        weighted_score = _weight_score(normalized_score, weight)
        segments.append(f"×{weight}/100={weighted_score:.2f}")
    else:
        segments.append("维度分=0.00")

    return "; ".join(segments)


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
            score_gross_margin_trend(snapshot.gross_margin_trend),
        )
    )


def _score_growth_delivery(snapshot: FundamentalSnapshot) -> Optional[float]:
    return _average(
        (
            score_revenue_growth(snapshot.revenue_growth),
            score_net_profit_growth(snapshot.net_profit_growth),
            score_guidance_attainment(snapshot.guidance_attainment),
            score_overseas_revenue_share(snapshot.overseas_revenue_share),
        )
    )


def _score_cashflow_efficiency(snapshot: FundamentalSnapshot) -> Optional[float]:
    return score_operating_cashflow_to_profit(snapshot.operating_cashflow_to_profit)


def _score_valuation_fit(snapshot: FundamentalSnapshot) -> Optional[float]:
    return _average((score_pe_percentile(snapshot.pe_percentile_5y), score_peg(snapshot.peg)))


def _score_yield_and_valuation(snapshot: FundamentalSnapshot) -> Optional[float]:
    return _average((score_dividend_yield(snapshot.dividend_yield), score_pe_percentile(snapshot.pe_percentile_5y)))


def _score_resource_cycle_resilience(snapshot: FundamentalSnapshot) -> Optional[float]:
    return _average(
        (
            score_debt_to_asset(snapshot.debt_to_asset),
            score_capex_to_operating_cashflow(snapshot.capex_to_operating_cashflow),
            score_unit_cost_position(snapshot.unit_cost_position),
            score_reserve_life_index(snapshot.reserve_life_index),
            score_commodity_price_sensitivity(snapshot.commodity_price_sensitivity),
        )
    )


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


def _score_inventory_channel_and_turnover(snapshot: FundamentalSnapshot) -> Optional[float]:
    return _average(
        (
            score_relative_pressure(snapshot.accounts_receivable_growth, snapshot.revenue_growth),
            score_relative_pressure(snapshot.inventory_growth, snapshot.revenue_growth),
            score_asset_turnover(snapshot.asset_turnover),
            score_price_war_pressure(snapshot.price_war_pressure),
        )
    )


def _score_capital_safety_and_asset_quality(snapshot: FundamentalSnapshot) -> Optional[float]:
    return _average(
        (
            score_core_tier1_ratio(snapshot.core_tier1_ratio),
            score_npl_ratio(snapshot.npl_ratio),
            score_provision_coverage_ratio(snapshot.provision_coverage_ratio),
            score_solvency_adequacy_ratio(snapshot.solvency_adequacy_ratio),
            score_combined_ratio(snapshot.combined_ratio),
            score_net_capital_ratio(snapshot.net_capital_ratio),
        )
    )


def _score_profitability_and_stability(snapshot: FundamentalSnapshot) -> Optional[float]:
    return _average(
        (
            score_roe(snapshot.roe),
            score_roe_stability(snapshot.roe_3y_cv),
            score_net_interest_margin(snapshot.net_interest_margin),
            score_investment_return(snapshot.investment_return),
        )
    )


def _score_business_growth_and_quality(snapshot: FundamentalSnapshot) -> Optional[float]:
    return _average(
        (
            score_loan_deposit_growth_gap(snapshot.loan_deposit_growth_gap),
            score_revenue_growth(snapshot.revenue_growth),
            score_net_profit_growth(snapshot.net_profit_growth),
            score_revenue_growth(snapshot.embedded_value_growth),
            score_revenue_growth(snapshot.new_business_value_growth),
        )
    )


def _score_shareholder_return_and_valuation(snapshot: FundamentalSnapshot) -> Optional[float]:
    return _average((score_pb_financial(snapshot.pb), score_dividend_yield(snapshot.dividend_yield)))


def _build_dimension_score_basis(
    snapshot: FundamentalSnapshot,
    dimension: DimensionConfig,
    normalized_score: Optional[float],
) -> Optional[str]:
    if dimension.name == "profit_quality":
        return _format_score_basis(
            (
                (f"ROE {_format_metric_value(snapshot.roe)}", score_roe(snapshot.roe)),
                (f"ROE波动CV {_format_metric_value(snapshot.roe_3y_cv)}", score_roe_stability(snapshot.roe_3y_cv)),
                (
                    f"经营现金流/利润 {_format_metric_value(snapshot.operating_cashflow_to_profit)}",
                    score_operating_cashflow_to_profit(snapshot.operating_cashflow_to_profit),
                ),
                (f"杜邦驱动 {_format_metric_value(snapshot.dupont_driver)}", score_dupont_driver(snapshot.dupont_driver)),
                (f"毛利率趋势 {_format_metric_value(snapshot.gross_margin_trend)}", score_gross_margin_trend(snapshot.gross_margin_trend)),
            ),
            normalized_score,
            dimension.weight,
        )

    if dimension.name == "growth_delivery":
        return _format_score_basis(
            (
                (f"营收增速 {_format_metric_value(snapshot.revenue_growth)}", score_revenue_growth(snapshot.revenue_growth)),
                (f"净利增速 {_format_metric_value(snapshot.net_profit_growth)}", score_net_profit_growth(snapshot.net_profit_growth)),
                (f"指引兑现 {_format_metric_value(snapshot.guidance_attainment)}", score_guidance_attainment(snapshot.guidance_attainment)),
                (
                    f"海外收入占比 {_format_metric_value(snapshot.overseas_revenue_share)}",
                    score_overseas_revenue_share(snapshot.overseas_revenue_share),
                ),
            ),
            normalized_score,
            dimension.weight,
        )

    if dimension.name == "cashflow_and_operating_efficiency":
        return _format_score_basis(
            (
                (
                    f"经营现金流/利润 {_format_metric_value(snapshot.operating_cashflow_to_profit)}",
                    score_operating_cashflow_to_profit(snapshot.operating_cashflow_to_profit),
                ),
            ),
            normalized_score,
            dimension.weight,
        )

    if dimension.name == "valuation_fit":
        return _format_score_basis(
            (
                (f"PE分位 {_format_metric_value(snapshot.pe_percentile_5y)}", score_pe_percentile(snapshot.pe_percentile_5y)),
                (f"PEG {_format_metric_value(snapshot.peg)}", score_peg(snapshot.peg)),
            ),
            normalized_score,
            dimension.weight,
        )

    if dimension.name == "yield_and_valuation":
        return _format_score_basis(
            (
                (f"股息率 {_format_metric_value(snapshot.dividend_yield)}", score_dividend_yield(snapshot.dividend_yield)),
                (f"PE分位 {_format_metric_value(snapshot.pe_percentile_5y)}", score_pe_percentile(snapshot.pe_percentile_5y)),
            ),
            normalized_score,
            dimension.weight,
        )

    if dimension.name == "resource_cycle_resilience":
        return _format_score_basis(
            (
                (
                    f"资产负债率 {_format_metric_value(snapshot.debt_to_asset)}",
                    score_debt_to_asset(snapshot.debt_to_asset),
                ),
                (
                    f"资本开支/经营现金流 {_format_metric_value(snapshot.capex_to_operating_cashflow)}",
                    score_capex_to_operating_cashflow(snapshot.capex_to_operating_cashflow),
                ),
                (
                    f"单位成本位置 {_format_metric_value(snapshot.unit_cost_position)}",
                    score_unit_cost_position(snapshot.unit_cost_position),
                ),
                (
                    f"储量寿命指数 {_format_metric_value(snapshot.reserve_life_index)}",
                    score_reserve_life_index(snapshot.reserve_life_index),
                ),
                (
                    f"商品价格敏感度 {_format_metric_value(snapshot.commodity_price_sensitivity)}",
                    score_commodity_price_sensitivity(snapshot.commodity_price_sensitivity),
                ),
            ),
            normalized_score,
            dimension.weight,
        )

    if dimension.name == "growth_and_cycle":
        return _format_score_basis(
            (
                (f"营收增速 {_format_metric_value(snapshot.revenue_growth)}", score_revenue_growth(snapshot.revenue_growth)),
                (f"净利增速 {_format_metric_value(snapshot.net_profit_growth)}", score_net_profit_growth(snapshot.net_profit_growth)),
            ),
            normalized_score,
            dimension.weight,
        )

    if dimension.name == "operating_and_inventory_cycle":
        receivable_delta = None
        if snapshot.accounts_receivable_growth is not None and snapshot.revenue_growth is not None:
            receivable_delta = snapshot.accounts_receivable_growth - snapshot.revenue_growth
        inventory_delta = None
        if snapshot.inventory_growth is not None and snapshot.revenue_growth is not None:
            inventory_delta = snapshot.inventory_growth - snapshot.revenue_growth
        return _format_score_basis(
            (
                (
                    f"应收压力差 {_format_metric_value(receivable_delta)}",
                    score_relative_pressure(snapshot.accounts_receivable_growth, snapshot.revenue_growth),
                ),
                (
                    f"库存压力差 {_format_metric_value(inventory_delta)}",
                    score_relative_pressure(snapshot.inventory_growth, snapshot.revenue_growth),
                ),
                (f"资产负债率 {_format_metric_value(snapshot.debt_to_asset)}", score_debt_to_asset(snapshot.debt_to_asset)),
            ),
            normalized_score,
            dimension.weight,
        )

    if dimension.name == "inventory_channel_and_turnover":
        receivable_delta = None
        if snapshot.accounts_receivable_growth is not None and snapshot.revenue_growth is not None:
            receivable_delta = snapshot.accounts_receivable_growth - snapshot.revenue_growth
        inventory_delta = None
        if snapshot.inventory_growth is not None and snapshot.revenue_growth is not None:
            inventory_delta = snapshot.inventory_growth - snapshot.revenue_growth
        return _format_score_basis(
            (
                (
                    f"应收压力差 {_format_metric_value(receivable_delta)}",
                    score_relative_pressure(snapshot.accounts_receivable_growth, snapshot.revenue_growth),
                ),
                (
                    f"库存压力差 {_format_metric_value(inventory_delta)}",
                    score_relative_pressure(snapshot.inventory_growth, snapshot.revenue_growth),
                ),
                (
                    f"总资产周转率 {_format_metric_value(snapshot.asset_turnover)}",
                    score_asset_turnover(snapshot.asset_turnover),
                ),
                (
                    f"价格战压力 {_format_metric_value(snapshot.price_war_pressure)}",
                    score_price_war_pressure(snapshot.price_war_pressure),
                ),
            ),
            normalized_score,
            dimension.weight,
        )

    if dimension.name == "capital_safety_and_asset_quality":
        return _format_score_basis(
            (
                (f"核心一级资本充足率 {_format_metric_value(snapshot.core_tier1_ratio)}", score_core_tier1_ratio(snapshot.core_tier1_ratio)),
                (f"不良率 {_format_metric_value(snapshot.npl_ratio)}", score_npl_ratio(snapshot.npl_ratio)),
                (
                    f"拨备覆盖率 {_format_metric_value(snapshot.provision_coverage_ratio)}",
                    score_provision_coverage_ratio(snapshot.provision_coverage_ratio),
                ),
                (
                    f"综合偿付能力充足率 {_format_metric_value(snapshot.solvency_adequacy_ratio)}",
                    score_solvency_adequacy_ratio(snapshot.solvency_adequacy_ratio),
                ),
                (f"综合成本率 {_format_metric_value(snapshot.combined_ratio)}", score_combined_ratio(snapshot.combined_ratio)),
                (f"净资本比率 {_format_metric_value(snapshot.net_capital_ratio)}", score_net_capital_ratio(snapshot.net_capital_ratio)),
            ),
            normalized_score,
            dimension.weight,
        )

    if dimension.name == "profitability_and_stability":
        return _format_score_basis(
            (
                (f"ROE {_format_metric_value(snapshot.roe)}", score_roe(snapshot.roe)),
                (f"ROE波动CV {_format_metric_value(snapshot.roe_3y_cv)}", score_roe_stability(snapshot.roe_3y_cv)),
                (f"净息差 {_format_metric_value(snapshot.net_interest_margin)}", score_net_interest_margin(snapshot.net_interest_margin)),
                (f"投资收益率 {_format_metric_value(snapshot.investment_return)}", score_investment_return(snapshot.investment_return)),
            ),
            normalized_score,
            dimension.weight,
        )

    if dimension.name == "business_growth_and_quality":
        return _format_score_basis(
            (
                (
                    f"存贷增速缺口 {_format_metric_value(snapshot.loan_deposit_growth_gap)}",
                    score_loan_deposit_growth_gap(snapshot.loan_deposit_growth_gap),
                ),
                (f"营收增速 {_format_metric_value(snapshot.revenue_growth)}", score_revenue_growth(snapshot.revenue_growth)),
                (f"净利增速 {_format_metric_value(snapshot.net_profit_growth)}", score_net_profit_growth(snapshot.net_profit_growth)),
                (f"内含价值增速 {_format_metric_value(snapshot.embedded_value_growth)}", score_revenue_growth(snapshot.embedded_value_growth)),
                (f"新业务价值增速 {_format_metric_value(snapshot.new_business_value_growth)}", score_revenue_growth(snapshot.new_business_value_growth)),
            ),
            normalized_score,
            dimension.weight,
        )

    if dimension.name == "shareholder_return_and_valuation":
        return _format_score_basis(
            (
                (f"PB {_format_metric_value(snapshot.pb)}", score_pb_financial(snapshot.pb)),
                (f"股息率 {_format_metric_value(snapshot.dividend_yield)}", score_dividend_yield(snapshot.dividend_yield)),
            ),
            normalized_score,
            dimension.weight,
        )

    return None


DIMENSION_SCORERS: dict[str, Callable[[FundamentalSnapshot], Optional[float]]] = {
    "profit_quality": _score_profit_quality,
    "growth_delivery": _score_growth_delivery,
    "cashflow_and_operating_efficiency": _score_cashflow_efficiency,
    "valuation_fit": _score_valuation_fit,
    "yield_and_valuation": _score_yield_and_valuation,
    "resource_cycle_resilience": _score_resource_cycle_resilience,
    "growth_and_cycle": _score_growth_and_cycle,
    "operating_and_inventory_cycle": _score_operating_and_inventory_cycle,
    "inventory_channel_and_turnover": _score_inventory_channel_and_turnover,
    "capital_safety_and_asset_quality": _score_capital_safety_and_asset_quality,
    "profitability_and_stability": _score_profitability_and_stability,
    "business_growth_and_quality": _score_business_growth_and_quality,
    "shareholder_return_and_valuation": _score_shareholder_return_and_valuation,
}


def _build_dimension_score(
    snapshot: FundamentalSnapshot, dimension: DimensionConfig
) -> FundamentalDimensionScore:
    used_metrics, missing_metrics = _build_metric_lists(snapshot, dimension)
    scorer = DIMENSION_SCORERS.get(dimension.name)
    normalized = scorer(snapshot) if scorer is not None else None
    score = _weight_score(normalized, dimension.weight)
    score_basis = _build_dimension_score_basis(snapshot, dimension, normalized)
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
        score_basis=score_basis,
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
    "yield_and_valuation": "股东回报与估值匹配度较好，收益型安全边际相对充足。",
    "resource_cycle_resilience": "成本曲线、资本开支与储量韧性较好，周期承压能力相对稳健。",
    "growth_and_cycle": "景气与成长匹配较好，增长质量处于可接受区间。",
    "operating_and_inventory_cycle": "营运与库存压力可控，经营质量相对稳定。",
    "capital_safety_and_asset_quality": "资本安全与资产质量较稳，安全边际处于可跟踪区间。",
    "profitability_and_stability": "盈利稳定性较好，利润韧性仍处于可跟踪区间。",
    "business_growth_and_quality": "业务增长质量较好，扩张节奏与经营质量基本匹配。",
    "shareholder_return_and_valuation": "股东回报与估值匹配度较好，安全边际相对充足。",
}


RISK_MESSAGES = {
    "profit_quality": "盈利质量偏弱，利润稳定性或现金流兑现存在压力。",
    "growth_delivery": "成长兑现偏弱，营收或利润增长支撑不足。",
    "cashflow_and_operating_efficiency": "现金流兑现偏弱，经营效率有待确认。",
    "valuation_fit": "估值匹配偏弱，当前价格对基本面要求较高。",
    "yield_and_valuation": "股东回报与估值保护偏弱，收益型安全边际仍需确认。",
    "resource_cycle_resilience": "成本曲线、资本开支或储量韧性偏弱，周期承压能力需要警惕。",
    "growth_and_cycle": "成长与景气支撑偏弱，周期位置仍需确认。",
    "operating_and_inventory_cycle": "营运与库存压力偏大，应收或存货质量需要警惕。",
    "capital_safety_and_asset_quality": "资本安全或资产质量偏弱，安全边际需要优先确认。",
    "profitability_and_stability": "盈利稳定性偏弱，利润韧性仍需继续验证。",
    "business_growth_and_quality": "业务增长质量偏弱，扩张与经营健康度不够匹配。",
    "shareholder_return_and_valuation": "股东回报与估值保护偏弱，当前安全边际并不充分。",
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

    if output_style in ("cycle_inventory_cashflow_first", "risk_first"):
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
