"""Capital-flow scoring engine."""

from collections import OrderedDict
from typing import Iterable, Optional

from capital_flow.models.scorecard import (
    CapitalFlowDimensionScore,
    CapitalFlowScoreCard,
    TriggeredRule,
)
from capital_flow.models.snapshot import CapitalFlowSnapshot

from .rules import any_positive, missing_metric_names, present_metric_names


DIMENSION_WEIGHTS = OrderedDict(
    [
        ("flow_direction", 25),
        ("flow_persistence", 20),
        ("volume_confirmation", 20),
        ("institutional_hint", 20),
        ("overheat_risk", 15),
    ]
)

LOW_CONFIDENCE_SOURCE_DISCOUNT = 0.85


def _volume_thresholds(snapshot: CapitalFlowSnapshot) -> dict[str, float]:
    if snapshot.market == "HK":
        return {
            "volume_confirm_low": 1.0,
            "volume_confirm_high": 3.2,
            "amount_confirm_low": 1.0,
            "amount_confirm_high": 3.0,
            "volume_overheat": 6.0,
        }
    return {
        "volume_confirm_low": 1.0,
        "volume_confirm_high": 2.5,
        "amount_confirm_low": 1.0,
        "amount_confirm_high": 2.5,
        "volume_overheat": 5.0,
    }


def _rating(total_score: float, red_flag: bool) -> str:
    if red_flag or total_score < 50:
        return "D"
    if total_score >= 80:
        return "A"
    if total_score >= 65:
        return "B"
    return "C"


def _rule(rule_id: str, severity: str, message: str) -> TriggeredRule:
    return TriggeredRule(rule_id=rule_id, severity=severity, message=message)


def _is_low_confidence_source(snapshot: CapitalFlowSnapshot) -> bool:
    return (snapshot.source or "").endswith(".fallback")


def _apply_source_confidence_adjustment(
    snapshot: CapitalFlowSnapshot,
    raw_total_score: float,
) -> tuple[float, Optional[TriggeredRule]]:
    if not _is_low_confidence_source(snapshot):
        return raw_total_score, None
    adjusted_score = round(raw_total_score * LOW_CONFIDENCE_SOURCE_DISCOUNT, 2)
    return adjusted_score, _rule(
        "low_confidence_source_discount",
        "warning",
        f"低置信度资金流来源，评分按 {LOW_CONFIDENCE_SOURCE_DISCOUNT:.0%} 保守折减",
    )


def _build_dimension(
    dimension: str,
    score: float,
    basis: str,
    metrics: Iterable[tuple[str, Optional[float]]],
    passed_rules: Optional[list[TriggeredRule]] = None,
    failed_rules: Optional[list[TriggeredRule]] = None,
) -> CapitalFlowDimensionScore:
    weight = DIMENSION_WEIGHTS[dimension]
    return CapitalFlowDimensionScore(
        dimension=dimension,
        score=max(0.0, min(float(weight), score)),
        weight=weight,
        max_score=float(weight),
        score_basis=basis,
        used_metrics=present_metric_names(metrics),
        missing_metrics=missing_metric_names(metrics),
        passed_rules=passed_rules or [],
        failed_rules=failed_rules or [],
    )


def _score_flow_direction(snapshot: CapitalFlowSnapshot) -> CapitalFlowDimensionScore:
    metrics = (
        ("main_net_inflow", snapshot.main_net_inflow),
        ("super_large_net_inflow", snapshot.super_large_net_inflow),
        ("large_order_net_inflow", snapshot.large_order_net_inflow),
        ("southbound_net_buy", snapshot.southbound_net_buy),
    )
    positives = sum(1 for _, value in metrics if value is not None and value > 0)
    negatives = sum(1 for _, value in metrics if value is not None and value < 0)
    present = positives + negatives
    score = 12.0 if present else 8.0
    passed: list[TriggeredRule] = []
    failed: list[TriggeredRule] = []
    if positives:
        score += min(13.0, positives * 4.5)
        passed.append(_rule("flow_direction_positive", "pass", "关键资金指标出现净流入"))
    if negatives:
        score -= min(10.0, negatives * 3.5)
        failed.append(_rule("flow_direction_negative", "risk", "关键资金指标出现净流出"))
    return _build_dimension("flow_direction", score, "按关键资金流正负方向评分", metrics, passed, failed)


def _score_flow_persistence(snapshot: CapitalFlowSnapshot) -> CapitalFlowDimensionScore:
    metrics = (
        ("main_net_inflow_3d", snapshot.main_net_inflow_3d),
        ("main_net_inflow_5d", snapshot.main_net_inflow_5d),
        ("main_net_inflow_10d", snapshot.main_net_inflow_10d),
    )
    score = 8.0
    passed: list[TriggeredRule] = []
    failed: list[TriggeredRule] = []
    if any_positive(snapshot.main_net_inflow_3d, snapshot.main_net_inflow_5d, snapshot.main_net_inflow_10d):
        score += 8.0
        passed.append(_rule("flow_persistence_positive", "pass", "多日窗口资金净流入"))
    if snapshot.main_net_inflow_5d is not None and snapshot.main_net_inflow_10d is not None:
        if snapshot.main_net_inflow_5d > 0 and snapshot.main_net_inflow_10d > 0:
            score += 4.0
            passed.append(_rule("flow_persistence_confirmed", "pass", "5日与10日资金方向一致为正"))
        elif snapshot.main_net_inflow_5d < 0 and snapshot.main_net_inflow_10d < 0:
            score -= 5.0
            failed.append(_rule("flow_persistence_negative", "risk", "5日与10日资金持续净流出"))
    return _build_dimension("flow_persistence", score, "按3/5/10日资金窗口持续性评分", metrics, passed, failed)


def _score_volume_confirmation(snapshot: CapitalFlowSnapshot) -> CapitalFlowDimensionScore:
    thresholds = _volume_thresholds(snapshot)
    metrics = (
        ("turnover_rate", snapshot.turnover_rate),
        ("volume_ratio", snapshot.volume_ratio),
        ("amount_ratio_5d", snapshot.amount_ratio_5d),
    )
    score = 10.0
    passed: list[TriggeredRule] = []
    failed: list[TriggeredRule] = []
    if snapshot.volume_ratio is not None:
        if thresholds["volume_confirm_low"] <= snapshot.volume_ratio <= thresholds["volume_confirm_high"]:
            score += 6.0
            passed.append(_rule("volume_ratio_confirmed", "pass", "量比温和放大"))
        elif snapshot.volume_ratio > thresholds["volume_overheat"] - 1:
            score -= 5.0
            failed.append(_rule("volume_ratio_overheated", "risk", "量比异常放大"))
    if (
        snapshot.amount_ratio_5d is not None
        and thresholds["amount_confirm_low"] <= snapshot.amount_ratio_5d <= thresholds["amount_confirm_high"]
    ):
        score += 4.0
        passed.append(_rule("amount_ratio_confirmed", "pass", "成交额相对5日均值温和放大"))
    return _build_dimension("volume_confirmation", score, "按量比、换手和成交额放大情况评分", metrics, passed, failed)


def _score_institutional_hint(snapshot: CapitalFlowSnapshot) -> CapitalFlowDimensionScore:
    metrics = (
        ("northbound_holding_change", snapshot.northbound_holding_change),
        ("southbound_holding_change", snapshot.southbound_holding_change),
        ("margin_balance_change", snapshot.margin_balance_change),
        ("short_sell_ratio", snapshot.short_sell_ratio),
    )
    score = 8.0
    passed: list[TriggeredRule] = []
    failed: list[TriggeredRule] = []
    if any_positive(snapshot.northbound_holding_change, snapshot.southbound_holding_change, snapshot.margin_balance_change):
        score += 8.0
        passed.append(_rule("institutional_channel_positive", "pass", "通道或杠杆资金出现正向变化"))
    if snapshot.short_sell_ratio is not None:
        if snapshot.short_sell_ratio >= 20:
            score -= 6.0
            failed.append(_rule("short_sell_ratio_high", "risk", "港股沽空比例偏高"))
        elif snapshot.short_sell_ratio <= 8:
            score += 4.0
            passed.append(_rule("short_sell_ratio_low", "pass", "港股沽空比例较低"))
    return _build_dimension("institutional_hint", score, "按北向/南向/融资/沽空等通道线索评分", metrics, passed, failed)


def _score_overheat_risk(snapshot: CapitalFlowSnapshot) -> CapitalFlowDimensionScore:
    thresholds = _volume_thresholds(snapshot)
    metrics = (
        ("turnover_rate", snapshot.turnover_rate),
        ("volume_ratio", snapshot.volume_ratio),
        ("amount_ratio_5d", snapshot.amount_ratio_5d),
    )
    score = 12.0
    passed: list[TriggeredRule] = []
    failed: list[TriggeredRule] = []
    if snapshot.turnover_rate is not None and snapshot.turnover_rate >= 15:
        score -= 5.0
        failed.append(_rule("turnover_rate_overheated", "risk", "换手率偏高，短线拥挤风险上升"))
    if snapshot.volume_ratio is not None and snapshot.volume_ratio >= thresholds["volume_overheat"]:
        score -= 5.0
        failed.append(_rule("volume_ratio_extreme", "risk", "量比极端放大"))
    if snapshot.dragon_tiger_flag or snapshot.block_trade_flag:
        score -= 3.0
        failed.append(_rule("event_disturbance", "warning", "存在龙虎榜或大宗交易等事件扰动"))
    if not failed:
        score += 3.0
        passed.append(_rule("no_obvious_overheat", "pass", "未见明显过热信号"))
    return _build_dimension("overheat_risk", score, "按换手、量比和事件扰动扣分", metrics, passed, failed)


def score_capital_flow_snapshot(snapshot: CapitalFlowSnapshot) -> CapitalFlowScoreCard:
    """Score a standardized capital-flow snapshot."""

    dimensions = [
        _score_flow_direction(snapshot),
        _score_flow_persistence(snapshot),
        _score_volume_confirmation(snapshot),
        _score_institutional_hint(snapshot),
        _score_overheat_risk(snapshot),
    ]
    raw_total_score = round(sum(item.score for item in dimensions), 2)
    total_score, confidence_rule = _apply_source_confidence_adjustment(snapshot, raw_total_score)
    triggered_rules = [rule for item in dimensions for rule in item.passed_rules + item.failed_rules]
    if confidence_rule:
        triggered_rules.append(confidence_rule)
    red_flag = any(rule.severity == "red_flag" for rule in triggered_rules)
    missing_metrics = sorted({metric for item in dimensions for metric in item.missing_metrics})

    strengths = [rule.message for rule in triggered_rules if rule.severity == "pass"]
    risks = [rule.message for rule in triggered_rules if rule.severity in {"risk", "red_flag"}]
    warnings = [rule.message for rule in triggered_rules if rule.severity == "warning"]
    if missing_metrics:
        warnings.append("资金面部分指标缺失，评分只反映已取得字段")

    if total_score >= 75 and not risks:
        comment = "资金面呈正向确认，适合用于提高技术面信号置信度。"
    elif risks:
        comment = "资金面存在风险信号，技术面结论需要降低确认度。"
    else:
        comment = "资金面信号中性，暂不构成强确认。"

    return CapitalFlowScoreCard(
        symbol=snapshot.symbol,
        name=snapshot.name,
        market=snapshot.market,
        trade_date=snapshot.trade_date,
        total_score=total_score,
        rating=_rating(total_score, red_flag),
        red_flag=red_flag,
        dimension_scores=dimensions,
        strengths=strengths,
        risks=risks,
        warnings=warnings,
        missing_metrics=missing_metrics,
        triggered_rules=triggered_rules,
        combined_comment=comment,
    )