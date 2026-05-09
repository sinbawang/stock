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


RULE_HANDLERS: Dict[str, Callable[[FundamentalSnapshot], Optional[TriggeredRule]]] = {
    "ocf_profit_history_low": _ocf_profit_history_low,
    "inventory_pressure_single_period": _inventory_pressure_single_period,
    "receivable_pressure_single_period": _receivable_pressure_single_period,
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
