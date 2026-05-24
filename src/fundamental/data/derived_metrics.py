"""Derived fundamental metrics computed from already-fetched raw values."""

from __future__ import annotations

from typing import Optional

from fundamental.models.common import DupontDriver


def derive_peg(pe_ttm: Optional[float], net_profit_growth: Optional[float]) -> Optional[float]:
    if pe_ttm is None or net_profit_growth is None:
        return None
    if pe_ttm <= 0 or net_profit_growth <= 0:
        return None
    return round(pe_ttm / net_profit_growth, 4)


def derive_net_margin(net_profit: Optional[float], revenue: Optional[float]) -> Optional[float]:
    if net_profit is None or revenue in (None, 0):
        return None
    return round((net_profit / revenue) * 100.0, 4)


def derive_equity_multiplier(debt_to_asset: Optional[float]) -> Optional[float]:
    if debt_to_asset is None:
        return None
    debt_ratio = debt_to_asset / 100.0
    if debt_ratio >= 1.0:
        return None
    equity_ratio = 1.0 - debt_ratio
    if equity_ratio <= 0:
        return None
    return round(1.0 / equity_ratio, 4)


def derive_asset_turnover(roe: Optional[float], net_margin: Optional[float], equity_multiplier: Optional[float]) -> Optional[float]:
    if roe is None or net_margin is None or equity_multiplier in (None, 0):
        return None
    roe_ratio = roe / 100.0
    margin_ratio = net_margin / 100.0
    if margin_ratio <= 0:
        return None
    turnover = roe_ratio / (margin_ratio * equity_multiplier)
    if turnover <= 0:
        return None
    return round(turnover, 4)


def derive_dupont_driver(
    roe: Optional[float],
    net_margin: Optional[float],
    debt_to_asset: Optional[float],
) -> Optional[DupontDriver]:
    equity_multiplier = derive_equity_multiplier(debt_to_asset)
    asset_turnover = derive_asset_turnover(roe, net_margin, equity_multiplier)
    if net_margin is None or equity_multiplier is None or asset_turnover is None:
        return None

    if equity_multiplier >= 2.8 and (net_margin <= 10.0 or asset_turnover <= 0.8):
        return "leverage"
    if equity_multiplier <= 2.0 and (net_margin >= 8.0 or asset_turnover >= 0.8):
        return "margin_turnover"
    return "mixed"