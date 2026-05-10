"""Automated first-version risk and red-flag rules."""

from typing import Callable, Dict, List, Optional

from fundamental.config.models import SubmodelConfig
from fundamental.models.scorecard import TriggeredRule
from fundamental.models.snapshot import FundamentalSnapshot


def _ocf_profit_history_low(snapshot: FundamentalSnapshot) -> Optional[TriggeredRule]:
    history = snapshot.operating_cashflow_to_profit_history or []
    recent = [value for value in history if value is not None][:2]
    if len(recent) >= 2 and all(value < 0.8 for value in recent):
        return TriggeredRule(
            rule_id="ocf_profit_history_low",
            severity="red_flag",
            message="经营现金流/净利润最近两期均低于 0.8。",
            automated=True,
        )
    return None


def _inventory_pressure_single_period(snapshot: FundamentalSnapshot) -> Optional[TriggeredRule]:
    if (
        snapshot.inventory_growth is not None
        and snapshot.revenue_growth is not None
        and snapshot.inventory_growth > snapshot.revenue_growth + 15
    ):
        return TriggeredRule(
            rule_id="inventory_pressure_single_period",
            severity="risk",
            message="存货增速显著高于营收增速。",
            automated=True,
        )
    return None


def _receivable_pressure_single_period(snapshot: FundamentalSnapshot) -> Optional[TriggeredRule]:
    if (
        snapshot.accounts_receivable_growth is not None
        and snapshot.revenue_growth is not None
        and snapshot.accounts_receivable_growth > snapshot.revenue_growth + 15
    ):
        return TriggeredRule(
            rule_id="receivable_pressure_single_period",
            severity="risk",
            message="应收增速显著高于营收增速。",
            automated=True,
        )
    return None


def _core_tier1_ratio_low(snapshot: FundamentalSnapshot) -> Optional[TriggeredRule]:
    if snapshot.core_tier1_ratio is not None and snapshot.core_tier1_ratio < 8.5:
        return TriggeredRule(
            rule_id="core_tier1_ratio_low",
            severity="red_flag",
            message="核心一级资本充足率低于舒适区。",
            automated=True,
        )
    return None


def _npl_ratio_high(snapshot: FundamentalSnapshot) -> Optional[TriggeredRule]:
    if snapshot.npl_ratio is not None and snapshot.npl_ratio > 2.0:
        return TriggeredRule(
            rule_id="npl_ratio_high",
            severity="risk",
            message="不良率已升至需要重点跟踪的区间。",
            automated=True,
        )
    return None


def _provision_coverage_low(snapshot: FundamentalSnapshot) -> Optional[TriggeredRule]:
    if snapshot.provision_coverage_ratio is not None and snapshot.provision_coverage_ratio < 150.0:
        return TriggeredRule(
            rule_id="provision_coverage_low",
            severity="risk",
            message="拨备覆盖率偏低，资产质量缓冲转弱。",
            automated=True,
        )
    return None


def _solvency_adequacy_ratio_low(snapshot: FundamentalSnapshot) -> Optional[TriggeredRule]:
    if snapshot.solvency_adequacy_ratio is not None and snapshot.solvency_adequacy_ratio < 150.0:
        return TriggeredRule(
            rule_id="solvency_adequacy_ratio_low",
            severity="red_flag",
            message="偿付能力充足率低于舒适区。",
            automated=True,
        )
    return None


def _combined_ratio_high(snapshot: FundamentalSnapshot) -> Optional[TriggeredRule]:
    if snapshot.combined_ratio is not None and snapshot.combined_ratio > 103.0:
        return TriggeredRule(
            rule_id="combined_ratio_high",
            severity="risk",
            message="综合成本率偏高，承保纪律需要重点跟踪。",
            automated=True,
        )
    return None


def _net_capital_ratio_low(snapshot: FundamentalSnapshot) -> Optional[TriggeredRule]:
    if snapshot.net_capital_ratio is not None and snapshot.net_capital_ratio < 150.0:
        return TriggeredRule(
            rule_id="net_capital_ratio_low",
            severity="red_flag",
            message="净资本比例低于舒适区。",
            automated=True,
        )
    return None


RULE_HANDLERS: Dict[str, Callable[[FundamentalSnapshot], Optional[TriggeredRule]]] = {
    "ocf_profit_history_low": _ocf_profit_history_low,
    "inventory_pressure_single_period": _inventory_pressure_single_period,
    "receivable_pressure_single_period": _receivable_pressure_single_period,
    "core_tier1_ratio_low": _core_tier1_ratio_low,
    "npl_ratio_high": _npl_ratio_high,
    "provision_coverage_low": _provision_coverage_low,
    "solvency_adequacy_ratio_low": _solvency_adequacy_ratio_low,
    "combined_ratio_high": _combined_ratio_high,
    "net_capital_ratio_low": _net_capital_ratio_low,
}


def evaluate_automated_risk_rules(
    snapshot: FundamentalSnapshot, submodel: SubmodelConfig
) -> List[TriggeredRule]:
    triggered: List[TriggeredRule] = []
    for rule in submodel.risk_rules:
        if not rule.enabled or not rule.automated:
            continue
        handler = RULE_HANDLERS.get(rule.rule_id)
        if handler is None:
            continue
        result = handler(snapshot)
        if result is not None:
            triggered.append(result)
    return triggered
