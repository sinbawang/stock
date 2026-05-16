"""Fetch CN annual and interim snapshots, then build a blended score view."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from fundamental.config.models import SubmodelConfig
from fundamental.data.cn_snapshot_fetcher import CnPeriodSnapshotsFetchResult, fetch_cn_period_snapshots
from fundamental.models.blended import (
    AnnualAnchorScore,
    BlendedFundamentalScoreCard,
    InterimOverlayScore,
    InterimWeightingProfile,
    OverlayComponent,
)
from fundamental.models.common import Rating
from fundamental.models.snapshot import FundamentalSnapshot
from fundamental.scoring.common_rules import (
    score_core_tier1_ratio,
    score_debt_to_asset,
    score_dividend_yield,
    score_asset_turnover,
    score_combined_ratio,
    score_investment_return,
    score_overseas_revenue_share,
    score_loan_deposit_growth_gap,
    score_net_interest_margin,
    score_net_capital_ratio,
    score_net_profit_growth,
    score_npl_ratio,
    score_operating_cashflow_to_profit,
    score_pb_financial,
    score_price_war_pressure,
    score_provision_coverage_ratio,
    score_relative_pressure,
    score_revenue_growth,
    score_roe,
    score_solvency_adequacy_ratio,
)

from .analyze_snapshot import resolve_submodel_for_symbol
from .fetch_and_analyze_cn_snapshot import (
    FetchedCnFundamentalAnalysis,
    _analyze_cn_fetched_snapshot,
    _derive_cn_source_warnings,
)
from .manual_supplement_helpers import apply_manual_supplement, resolve_manual_supplement


DEFAULT_INTERIM_WEIGHTING_PROFILE = InterimWeightingProfile(profile_id="default")


@dataclass(frozen=True)
class BlendedCnFundamentalAnalysis:
    blended: BlendedFundamentalScoreCard
    annual_anchor: AnnualAnchorScore
    interim_overlay: Optional[InterimOverlayScore]
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def _average_present(values: Sequence[Optional[float]]) -> Optional[float]:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return round(sum(present) / len(present), 4)


def _annualization_factor(snapshot: FundamentalSnapshot) -> Optional[float]:
    month_day = (snapshot.report_period.month, snapshot.report_period.day)
    if month_day == (3, 31):
        return 4.0
    if month_day == (6, 30):
        return 2.0
    if month_day == (9, 30):
        return 4.0 / 3.0
    return None


def _annualized_roe_proxy(snapshot: FundamentalSnapshot) -> Optional[float]:
    if snapshot.roe is None:
        return None
    annualization_factor = _annualization_factor(snapshot)
    if annualization_factor is None:
        return snapshot.roe
    return round(snapshot.roe * annualization_factor, 4)


def _smoothed_ocf_profit_proxy(snapshot: FundamentalSnapshot) -> Optional[float]:
    history = snapshot.operating_cashflow_to_profit_history or []
    present_history = [value for value in history if value is not None]
    if len(present_history) >= 3:
        return round(sum(present_history[:3]) / 3.0, 4)
    if len(present_history) >= 2:
        return round(sum(present_history[:2]) / 2.0, 4)
    if len(present_history) == 1:
        return round(present_history[0], 4)
    return snapshot.operating_cashflow_to_profit


def _map_rating(total_score: float) -> Rating:
    if total_score >= 80:
        return "A"
    if total_score >= 65:
        return "B"
    if total_score >= 45:
        return "C"
    return "D"


def _component_from_scores(
    name: str,
    weight: float,
    metric_scores: Sequence[tuple[str, Optional[float]]],
    note: Optional[str] = None,
) -> Optional[OverlayComponent]:
    score = _average_present([value for _, value in metric_scores])
    if score is None:
        return None
    return OverlayComponent(
        component=name,
        score=score,
        weight=weight,
        covered_metrics=tuple(metric_name for metric_name, value in metric_scores if value is not None),
        missing_metrics=tuple(metric_name for metric_name, value in metric_scores if value is None),
        note=note,
    )


def _weighted_component_from_scores(
    name: str,
    weight: float,
    metric_scores: Sequence[tuple[str, Optional[float], float]],
    note: Optional[str] = None,
) -> Optional[OverlayComponent]:
    present = [(metric_name, value, metric_weight) for metric_name, value, metric_weight in metric_scores if value is not None]
    if not present:
        return None
    total_metric_weight = sum(metric_weight for _, _, metric_weight in present)
    score = round(sum(value * metric_weight for _, value, metric_weight in present) / total_metric_weight, 4)
    return OverlayComponent(
        component=name,
        score=score,
        weight=weight,
        covered_metrics=tuple(metric_name for metric_name, value, _ in metric_scores if value is not None),
        missing_metrics=tuple(metric_name for metric_name, value, _ in metric_scores if value is None),
        note=note,
    )


def _build_interim_overlay_components(snapshot: FundamentalSnapshot, submodel: SubmodelConfig) -> tuple[OverlayComponent, ...]:
    if submodel.submodel_id == "utility_operator_v1":
        smoothed_ocf_profit = _smoothed_ocf_profit_proxy(snapshot)
        components = (
            _component_from_scores(
                "growth_refresh",
                0.35,
                (
                    ("revenue_growth", score_revenue_growth(snapshot.revenue_growth)),
                    ("net_profit_growth", score_net_profit_growth(snapshot.net_profit_growth)),
                ),
            ),
            _component_from_scores(
                "cashflow_refresh",
                0.4,
                (
                    ("operating_cashflow_to_profit", score_operating_cashflow_to_profit(smoothed_ocf_profit)),
                ),
                note="为降低 Q1 季节性噪音，优先用经营现金流/利润历史均值做刷新。",
            ),
            _component_from_scores(
                "resilience_refresh",
                0.25,
                (("debt_to_asset", score_debt_to_asset(snapshot.debt_to_asset)),),
            ),
        )
    elif submodel.submodel_id == "home_appliance_v1":
        components = (
            _component_from_scores(
                "growth_refresh",
                0.3,
                (
                    ("revenue_growth", score_revenue_growth(snapshot.revenue_growth)),
                    ("net_profit_growth", score_net_profit_growth(snapshot.net_profit_growth)),
                ),
            ),
            _component_from_scores(
                "cashflow_refresh",
                0.3,
                (("operating_cashflow_to_profit", score_operating_cashflow_to_profit(snapshot.operating_cashflow_to_profit)),),
            ),
            _component_from_scores(
                "channel_cycle_refresh",
                0.4,
                (
                    (
                        "accounts_receivable_growth",
                        score_relative_pressure(snapshot.accounts_receivable_growth, snapshot.revenue_growth),
                    ),
                    (
                        "inventory_growth",
                        score_relative_pressure(snapshot.inventory_growth, snapshot.revenue_growth),
                    ),
                ),
            ),
        )
    elif submodel.submodel_id == "bank_v1":
        annualized_roe = _annualized_roe_proxy(snapshot)
        components = (
            _component_from_scores(
                "capital_refresh",
                0.45,
                (
                    ("core_tier1_ratio", score_core_tier1_ratio(snapshot.core_tier1_ratio)),
                    ("npl_ratio", score_npl_ratio(snapshot.npl_ratio)),
                    ("provision_coverage_ratio", score_provision_coverage_ratio(snapshot.provision_coverage_ratio)),
                ),
            ),
            _weighted_component_from_scores(
                "profitability_refresh",
                0.25,
                (
                    ("roe", score_roe(annualized_roe), 0.35),
                    ("net_interest_margin", score_net_interest_margin(snapshot.net_interest_margin), 0.65),
                ),
                note="银行盈利刷新优先使用年化 ROE 代理值，并与净息差按银行语义组合。",
            ),
            _component_from_scores(
                "business_quality_refresh",
                0.3,
                (("loan_deposit_growth_gap", score_loan_deposit_growth_gap(snapshot.loan_deposit_growth_gap)),),
            ),
        )
    elif submodel.submodel_id == "industrial_automation_v1":
        smoothed_ocf_profit = _smoothed_ocf_profit_proxy(snapshot)
        components = (
            _component_from_scores(
                "growth_refresh",
                0.3,
                (
                    ("revenue_growth", score_revenue_growth(snapshot.revenue_growth)),
                    ("net_profit_growth", score_net_profit_growth(snapshot.net_profit_growth)),
                ),
                note="订单与下游景气度在 v1 里仍以收入和利润兑现做近似刷新。",
            ),
            _component_from_scores(
                "cashflow_refresh",
                0.25,
                (("operating_cashflow_to_profit", score_operating_cashflow_to_profit(smoothed_ocf_profit)),),
                note="为降低 Q1 季节性噪音，优先用经营现金流/利润历史均值确认利润质量。",
            ),
            _component_from_scores(
                "operating_cycle_refresh",
                0.45,
                (
                    (
                        "accounts_receivable_growth",
                        score_relative_pressure(snapshot.accounts_receivable_growth, snapshot.revenue_growth),
                    ),
                    (
                        "inventory_growth",
                        score_relative_pressure(snapshot.inventory_growth, snapshot.revenue_growth),
                    ),
                ),
                note="应收和存货相对收入的压力，继续作为订单与营运质量的 v1 代理。",
            ),
        )
    elif submodel.submodel_id == "game_content_v1":
        smoothed_ocf_profit = _smoothed_ocf_profit_proxy(snapshot)
        annualized_roe = _annualized_roe_proxy(snapshot)
        components = (
            _component_from_scores(
                "growth_refresh",
                0.4,
                (
                    ("revenue_growth", score_revenue_growth(snapshot.revenue_growth)),
                    ("net_profit_growth", score_net_profit_growth(snapshot.net_profit_growth)),
                ),
                note="产品周期持续性在 v1 里先用收入和利润增长刷新。",
            ),
            _component_from_scores(
                "cashflow_refresh",
                0.35,
                (("operating_cashflow_to_profit", score_operating_cashflow_to_profit(smoothed_ocf_profit)),),
                note="为降低 Q1 季节性噪音，优先用经营现金流/利润历史均值做刷新。",
            ),
            _component_from_scores(
                "profit_quality_refresh",
                0.25,
                (("roe", score_roe(annualized_roe)),),
                note="为降低中间报告期失真，优先用年化 ROE 近似维持盈利质量刷新。",
            ),
        )
    elif submodel.submodel_id == "platform_internet_v1":
        smoothed_ocf_profit = _smoothed_ocf_profit_proxy(snapshot)
        annualized_roe = _annualized_roe_proxy(snapshot)
        components = (
            _component_from_scores(
                "growth_refresh",
                0.4,
                (
                    ("revenue_growth", score_revenue_growth(snapshot.revenue_growth)),
                    ("net_profit_growth", score_net_profit_growth(snapshot.net_profit_growth)),
                ),
                note="平台业务季报刷新先看收入与利润兑现。",
            ),
            _component_from_scores(
                "cashflow_refresh",
                0.35,
                (("operating_cashflow_to_profit", score_operating_cashflow_to_profit(smoothed_ocf_profit)),),
                note="为降低中间报告期噪音，优先用经营现金流/利润历史均值确认变现质量。",
            ),
            _component_from_scores(
                "profit_quality_refresh",
                0.25,
                (("roe", score_roe(annualized_roe)),),
                note="为降低中间报告期失真，优先用年化 ROE 近似维持平台盈利质量刷新。",
            ),
        )
    elif submodel.submodel_id == "digital_infra_v1":
        smoothed_ocf_profit = _smoothed_ocf_profit_proxy(snapshot)
        components = (
            _component_from_scores(
                "growth_refresh",
                0.25,
                (
                    ("revenue_growth", score_revenue_growth(snapshot.revenue_growth)),
                    ("net_profit_growth", score_net_profit_growth(snapshot.net_profit_growth)),
                ),
                note="数字基础设施季报刷新先看主业收入与利润兑现，但权重低于现金流与股东回报。",
            ),
            _component_from_scores(
                "cashflow_refresh",
                0.45,
                (("operating_cashflow_to_profit", score_operating_cashflow_to_profit(smoothed_ocf_profit)),),
                note="为降低中间报告期噪音，优先用经营现金流/利润历史均值确认通信主业现金回笼质量。",
            ),
            _component_from_scores(
                "shareholder_return_refresh",
                0.3,
                (
                    ("pb", score_pb_financial(snapshot.pb)),
                    ("dividend_yield", score_dividend_yield(snapshot.dividend_yield)),
                ),
                note="数字基础设施继续用 PB 与股息率近似刻画股东回报与防御性估值锚。",
            ),
        )
    elif submodel.submodel_id == "semiconductor_hardtech_v1":
        smoothed_ocf_profit = _smoothed_ocf_profit_proxy(snapshot)
        components = (
            _component_from_scores(
                "growth_refresh",
                0.3,
                (
                    ("revenue_growth", score_revenue_growth(snapshot.revenue_growth)),
                    ("net_profit_growth", score_net_profit_growth(snapshot.net_profit_growth)),
                ),
                note="半导体季报刷新先看收入与利润兑现，但需要结合周期位置阅读。",
            ),
            _component_from_scores(
                "cashflow_refresh",
                0.25,
                (("operating_cashflow_to_profit", score_operating_cashflow_to_profit(smoothed_ocf_profit)),),
                note="为降低中间报告期噪音，优先用经营现金流/利润历史均值确认利润改善是否兑现成现金流。",
            ),
            _component_from_scores(
                "operating_cycle_refresh",
                0.45,
                (
                    (
                        "accounts_receivable_growth",
                        score_relative_pressure(snapshot.accounts_receivable_growth, snapshot.revenue_growth),
                    ),
                    (
                        "inventory_growth",
                        score_relative_pressure(snapshot.inventory_growth, snapshot.revenue_growth),
                    ),
                ),
                note="库存与应收相对收入的压力，继续作为半导体周期位置与经营失真风险的 v1 代理。",
            ),
        )
    elif submodel.submodel_id == "auto_manufacturing_v1":
        smoothed_ocf_profit = _smoothed_ocf_profit_proxy(snapshot)
        components = (
            _component_from_scores(
                "growth_refresh",
                0.25,
                (
                    ("revenue_growth", score_revenue_growth(snapshot.revenue_growth)),
                    ("net_profit_growth", score_net_profit_growth(snapshot.net_profit_growth)),
                    ("overseas_revenue_share", score_overseas_revenue_share(snapshot.overseas_revenue_share)),
                ),
                note="汽车制造季报刷新先看收入、利润与海外收入结构是否继续兑现。",
            ),
            _component_from_scores(
                "cashflow_refresh",
                0.25,
                (("operating_cashflow_to_profit", score_operating_cashflow_to_profit(smoothed_ocf_profit)),),
                note="为降低中间报告期噪音，优先用经营现金流/利润历史均值确认汽车利润是否继续兑现成现金流。",
            ),
            _component_from_scores(
                "inventory_channel_refresh",
                0.5,
                (
                    (
                        "accounts_receivable_growth",
                        score_relative_pressure(snapshot.accounts_receivable_growth, snapshot.revenue_growth),
                    ),
                    (
                        "inventory_growth",
                        score_relative_pressure(snapshot.inventory_growth, snapshot.revenue_growth),
                    ),
                    ("asset_turnover", score_asset_turnover(snapshot.asset_turnover)),
                    ("price_war_pressure", score_price_war_pressure(snapshot.price_war_pressure)),
                ),
                note="库存、应收、周转率与价格战压力共同作为汽车渠道健康与经营质量的 v1 刷新代理。",
            ),
        )
    elif submodel.submodel_id == "insurance_v1":
        annualized_roe = _annualized_roe_proxy(snapshot)
        components = (
            _component_from_scores(
                "capital_refresh",
                0.4,
                (
                    ("solvency_adequacy_ratio", score_solvency_adequacy_ratio(snapshot.solvency_adequacy_ratio)),
                    ("combined_ratio", score_combined_ratio(snapshot.combined_ratio)),
                ),
                note="保险季报刷新优先看偿付能力与承保纪律；若 Q1 未披露综合成本率，则仅用已披露资本约束信号保守刷新。",
            ),
            _component_from_scores(
                "profitability_refresh",
                0.35,
                (
                    ("roe", score_roe(annualized_roe)),
                    ("investment_return", score_investment_return(snapshot.investment_return)),
                ),
                note="保险盈利刷新优先用年化 ROE，投资收益率仅在中间期公开可得时参与。",
            ),
            _component_from_scores(
                "business_growth_refresh",
                0.25,
                (
                    ("embedded_value_growth", score_net_profit_growth(snapshot.embedded_value_growth)),
                    ("new_business_value_growth", score_net_profit_growth(snapshot.new_business_value_growth)),
                    ("net_profit_growth", score_net_profit_growth(snapshot.net_profit_growth)),
                ),
                note="EV/NBV 在 Q1 常缺失时，先用净利增速做保守业务刷新代理，避免把未披露字段误当成恶化。",
            ),
        )
    elif submodel.submodel_id == "broker_v1":
        annualized_roe = _annualized_roe_proxy(snapshot)
        components = (
            _component_from_scores(
                "capital_refresh",
                0.35,
                (("net_capital_ratio", score_net_capital_ratio(snapshot.net_capital_ratio)),),
                note="券商季报刷新优先看监管资本缓冲；若中间期未披露净资本比率，则该项不主动补年报代理值。",
            ),
            _component_from_scores(
                "profitability_refresh",
                0.3,
                (("roe", score_roe(annualized_roe)),),
                note="券商盈利刷新先用年化 ROE 近似，降低中间报告期利润季节性扰动。",
            ),
            _component_from_scores(
                "business_growth_refresh",
                0.2,
                (
                    ("revenue_growth", score_revenue_growth(snapshot.revenue_growth)),
                    ("net_profit_growth", score_net_profit_growth(snapshot.net_profit_growth)),
                ),
                note="券商业务刷新仍以收入与利润兑现为主，但需要结合市场成交与投行业务周期阅读。",
            ),
            _component_from_scores(
                "shareholder_return_refresh",
                0.15,
                (
                    ("pb", score_pb_financial(snapshot.pb)),
                    ("dividend_yield", score_dividend_yield(snapshot.dividend_yield)),
                ),
                note="券商继续用 PB 与股息率刻画股东回报与估值安全边际。",
            ),
        )
    else:
        components = ()

    return tuple(component for component in components if component is not None)


def _build_interim_overlay(snapshot: FundamentalSnapshot, submodel: SubmodelConfig) -> Optional[InterimOverlayScore]:
    components = _build_interim_overlay_components(snapshot, submodel)
    if not components:
        return None

    overlay_score = round(sum(component.score * component.weight for component in components), 2)
    positive = tuple(component.component for component in components if component.score >= 75)
    negative = tuple(component.component for component in components if component.score <= 35)
    covered_metrics = tuple(metric for component in components for metric in component.covered_metrics)
    missing_metrics = tuple(metric for component in components for metric in component.missing_metrics)

    return InterimOverlayScore(
        snapshot=snapshot,
        components=components,
        overlay_score=overlay_score,
        rating_hint=_map_rating(overlay_score),
        covered_metrics=covered_metrics,
        missing_metrics=missing_metrics,
        drivers_positive=positive,
        drivers_negative=negative,
    )


def _resolve_interim_weights(
    snapshot: Optional[FundamentalSnapshot],
    profile: InterimWeightingProfile,
) -> tuple[float, float, str]:
    if snapshot is None:
        return profile.annual_after_annual, profile.interim_after_annual, "annual_only"

    month_day = (snapshot.report_period.month, snapshot.report_period.day)
    if month_day == (3, 31):
        return profile.annual_after_q1, profile.interim_after_q1, "q1_refresh"
    if month_day == (6, 30):
        return profile.annual_after_h1, profile.interim_after_h1, "h1_refresh"
    if month_day == (9, 30):
        return profile.annual_after_q3, profile.interim_after_q3, "q3_refresh"
    return profile.annual_after_h1, profile.interim_after_h1, "latest_interim_refresh"


def _compose_blended_comment(
    annual_anchor: AnnualAnchorScore,
    interim_overlay: Optional[InterimOverlayScore],
    annual_weight: float,
    interim_weight: float,
) -> str:
    if interim_overlay is None:
        return (
            f"当前仍仅使用 {annual_anchor.snapshot.report_period.isoformat()} 年报锚定分，"
            "尚未纳入更新的中间报告期刷新层。"
        )
    return (
        f"当前总分由年报锚定分与 {interim_overlay.snapshot.report_period.isoformat()} 中间报告刷新层共同构成，"
        f"当前权重为年报 {annual_weight:.0%} / 季报 {interim_weight:.0%}。"
    )


def fetch_and_analyze_cn_blended_fundamentals(
    symbol: str,
    name: Optional[str] = None,
    submodel: Optional[str] = None,
    manual_supplement: Optional[Mapping[str, Any]] = None,
    manual_supplement_path: Optional[str] = None,
    weighting_profile: InterimWeightingProfile = DEFAULT_INTERIM_WEIGHTING_PROFILE,
) -> BlendedCnFundamentalAnalysis:
    period_snapshots = fetch_cn_period_snapshots(symbol=symbol, name=name)
    annual_analysis = _analyze_cn_fetched_snapshot(
        period_snapshots.annual,
        submodel=submodel,
        manual_supplement=manual_supplement,
        manual_supplement_path=manual_supplement_path,
    )
    annual_anchor = AnnualAnchorScore(
        snapshot=annual_analysis.fetched.snapshot,
        scorecard=annual_analysis.scorecard,
        assumptions=annual_analysis.assumptions,
        warnings=tuple(annual_analysis.scorecard.warnings),
    )

    interim_overlay = None
    interim_warnings: tuple[str, ...] = ()
    interim_assumptions: tuple[str, ...] = ()
    if period_snapshots.interim is not None and annual_analysis.fetched.snapshot.period_type == "annual":
        submodel_config = resolve_submodel_for_symbol(annual_analysis.fetched.snapshot.symbol, submodel)
        supplemented_interim = apply_manual_supplement(
            period_snapshots.interim,
            submodel_config,
            resolve_manual_supplement(manual_supplement, manual_supplement_path),
        )
        interim_overlay = _build_interim_overlay(supplemented_interim.snapshot, submodel_config)
        interim_warnings = _derive_cn_source_warnings(supplemented_interim)
        interim_assumptions = supplemented_interim.assumptions

    annual_weight, interim_weight, freshness_label = _resolve_interim_weights(
        interim_overlay.snapshot if interim_overlay is not None else None,
        weighting_profile,
    )
    blended_total_score = round(
        annual_anchor.scorecard.total_score * annual_weight
        + ((interim_overlay.overlay_score if interim_overlay is not None else 0.0) * interim_weight),
        2,
    )
    blended_rating = annual_anchor.scorecard.rating if annual_anchor.scorecard.red_flag else _map_rating(blended_total_score)
    combined_assumptions = annual_anchor.assumptions + interim_assumptions
    combined_warnings = tuple(dict.fromkeys([*annual_anchor.warnings, *interim_warnings]))

    blended = BlendedFundamentalScoreCard(
        symbol=annual_anchor.snapshot.symbol,
        name=annual_anchor.snapshot.name,
        market=annual_anchor.snapshot.market,
        submodel_id=annual_anchor.scorecard.submodel_id,
        annual_anchor=annual_anchor,
        interim_overlay=interim_overlay,
        annual_weight=annual_weight,
        interim_weight=interim_weight,
        blended_total_score=blended_total_score,
        blended_rating=blended_rating,
        freshness_label=freshness_label,
        warnings=combined_warnings,
        assumptions=combined_assumptions,
        combined_comment=_compose_blended_comment(annual_anchor, interim_overlay, annual_weight, interim_weight),
    )

    return BlendedCnFundamentalAnalysis(
        blended=blended,
        annual_anchor=annual_anchor,
        interim_overlay=interim_overlay,
        assumptions=combined_assumptions,
        warnings=combined_warnings,
    )