"""Reusable metric scoring helpers for first-version fundamental models."""

from typing import Optional


def _linear_score(value: float, low: float, high: float, low_score: float, high_score: float) -> float:
    if value <= low:
        return low_score
    if value >= high:
        return high_score
    ratio = (value - low) / (high - low)
    return low_score + ratio * (high_score - low_score)


def score_roe(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value <= 8:
        return 0.0
    if value < 12:
        return _linear_score(value, 8.0, 12.0, 0.0, 58.33)
    if value < 20:
        return _linear_score(value, 12.0, 20.0, 58.33, 100.0)
    return 100.0


def score_roe_stability(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value >= 0.5:
        return 0.0
    if value <= 0.2:
        return 100.0
    return _linear_score(value, 0.5, 0.2, 0.0, 100.0)


def score_dupont_driver(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    if value == "margin_turnover":
        return 100.0
    if value == "mixed":
        return 60.0
    if value == "leverage":
        return 0.0
    return None


def score_operating_cashflow_to_profit(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value <= 0.6:
        return 0.0
    if value < 1.0:
        return _linear_score(value, 0.6, 1.0, 0.0, 80.0)
    if value < 1.5:
        return _linear_score(value, 1.0, 1.5, 80.0, 100.0)
    return 100.0


def score_revenue_growth(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value <= 0:
        return 0.0
    if value >= 20:
        return 100.0
    return _linear_score(value, 0.0, 20.0, 0.0, 100.0)


def score_net_profit_growth(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value <= 0:
        return 0.0
    if value >= 30:
        return 100.0
    return _linear_score(value, 0.0, 30.0, 0.0, 100.0)


def score_guidance_attainment(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    if value == "beat":
        return 100.0
    if value == "meet":
        return 50.0
    if value == "miss":
        return 0.0
    return None


def score_debt_to_asset(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value >= 70:
        return 0.0
    if value <= 40:
        return 100.0
    return _linear_score(value, 70.0, 40.0, 0.0, 100.0)


def score_relative_pressure(metric_growth: Optional[float], revenue_growth: Optional[float]) -> Optional[float]:
    if metric_growth is None or revenue_growth is None:
        return None
    delta = metric_growth - revenue_growth
    if delta <= 0:
        return 100.0
    if delta >= 15:
        return 0.0
    return _linear_score(delta, 0.0, 15.0, 100.0, 0.0)


def score_pe_percentile(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value <= 25:
        return 100.0
    if value < 75:
        return _linear_score(value, 25.0, 75.0, 100.0, 40.0)
    if value >= 100:
        return 0.0
    return _linear_score(value, 75.0, 100.0, 20.0, 0.0)


def score_peg(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value <= 0.8:
        return 100.0
    if value < 1.5:
        return _linear_score(value, 0.8, 1.5, 100.0, 60.0)
    if value < 2.0:
        return _linear_score(value, 1.5, 2.0, 60.0, 20.0)
    return 0.0
