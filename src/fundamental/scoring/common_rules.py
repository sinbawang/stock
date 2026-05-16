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
    return _linear_score(value, 40.0, 70.0, 100.0, 0.0)


def score_pb_financial(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value <= 0.7:
        return 100.0
    if value < 1.0:
        return _linear_score(value, 0.7, 1.0, 100.0, 80.0)
    if value < 1.5:
        return _linear_score(value, 1.0, 1.5, 80.0, 40.0)
    if value >= 2.0:
        return 0.0
    return _linear_score(value, 1.5, 2.0, 40.0, 0.0)


def score_dividend_yield(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value <= 1.0:
        return 20.0
    if value < 3.0:
        return _linear_score(value, 1.0, 3.0, 20.0, 70.0)
    if value < 6.0:
        return _linear_score(value, 3.0, 6.0, 70.0, 100.0)
    return 100.0


def score_capex_to_operating_cashflow(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value >= 1.0:
        return 0.0
    if value > 0.8:
        return _linear_score(value, 1.0, 0.8, 0.0, 30.0)
    if value > 0.5:
        return _linear_score(value, 0.8, 0.5, 30.0, 75.0)
    if value <= 0.25:
        return 100.0
    return _linear_score(value, 0.5, 0.25, 75.0, 100.0)


def score_unit_cost_position(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value <= 20.0:
        return 20.0
    if value < 50.0:
        return _linear_score(value, 20.0, 50.0, 20.0, 70.0)
    if value < 80.0:
        return _linear_score(value, 50.0, 80.0, 70.0, 100.0)
    return 100.0


def score_reserve_life_index(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value <= 5.0:
        return 0.0
    if value < 10.0:
        return _linear_score(value, 5.0, 10.0, 0.0, 60.0)
    if value < 15.0:
        return _linear_score(value, 10.0, 15.0, 60.0, 100.0)
    return 100.0


def score_commodity_price_sensitivity(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value >= 1.8:
        return 0.0
    if value > 1.2:
        return _linear_score(value, 1.8, 1.2, 0.0, 50.0)
    if value > 0.8:
        return _linear_score(value, 1.2, 0.8, 50.0, 100.0)
    return 100.0


def score_core_tier1_ratio(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value <= 7.0:
        return 0.0
    if value < 9.0:
        return _linear_score(value, 7.0, 9.0, 0.0, 60.0)
    if value < 11.0:
        return _linear_score(value, 9.0, 11.0, 60.0, 100.0)
    return 100.0


def score_npl_ratio(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value <= 1.0:
        return 100.0
    if value < 1.5:
        return _linear_score(value, 1.0, 1.5, 100.0, 70.0)
    if value < 3.0:
        return _linear_score(value, 1.5, 3.0, 70.0, 0.0)
    return 0.0


def score_provision_coverage_ratio(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value <= 120.0:
        return 0.0
    if value < 180.0:
        return _linear_score(value, 120.0, 180.0, 0.0, 60.0)
    if value < 250.0:
        return _linear_score(value, 180.0, 250.0, 60.0, 100.0)
    return 100.0


def score_loan_deposit_growth_gap(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    gap = abs(value)
    if gap <= 2.0:
        return 100.0
    if gap < 5.0:
        return _linear_score(gap, 2.0, 5.0, 100.0, 70.0)
    if gap < 10.0:
        return _linear_score(gap, 5.0, 10.0, 70.0, 0.0)
    return 0.0


def score_net_interest_margin(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value <= 1.2:
        return 0.0
    if value < 1.8:
        return _linear_score(value, 1.2, 1.8, 0.0, 70.0)
    if value < 2.3:
        return _linear_score(value, 1.8, 2.3, 70.0, 100.0)
    return 100.0


def score_solvency_adequacy_ratio(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value <= 130.0:
        return 0.0
    if value < 170.0:
        return _linear_score(value, 130.0, 170.0, 0.0, 60.0)
    if value < 220.0:
        return _linear_score(value, 170.0, 220.0, 60.0, 100.0)
    return 100.0


def score_combined_ratio(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value <= 96.0:
        return 100.0
    if value < 100.0:
        return _linear_score(value, 96.0, 100.0, 100.0, 80.0)
    if value < 103.0:
        return _linear_score(value, 100.0, 103.0, 80.0, 20.0)
    return 0.0


def score_investment_return(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value <= 2.0:
        return 0.0
    if value < 4.0:
        return _linear_score(value, 2.0, 4.0, 0.0, 70.0)
    if value < 5.5:
        return _linear_score(value, 4.0, 5.5, 70.0, 100.0)
    return 100.0


def score_net_capital_ratio(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value <= 120.0:
        return 0.0
    if value < 160.0:
        return _linear_score(value, 120.0, 160.0, 0.0, 60.0)
    if value < 220.0:
        return _linear_score(value, 160.0, 220.0, 60.0, 100.0)
    return 100.0


def score_relative_pressure(metric_growth: Optional[float], revenue_growth: Optional[float]) -> Optional[float]:
    if metric_growth is None or revenue_growth is None:
        return None
    delta = metric_growth - revenue_growth
    if delta <= 0:
        return 100.0
    if delta >= 15:
        return 0.0
    return _linear_score(delta, 0.0, 15.0, 100.0, 0.0)


def score_asset_turnover(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value <= 0.4:
        return 0.0
    if value < 0.8:
        return _linear_score(value, 0.4, 0.8, 0.0, 70.0)
    if value < 1.2:
        return _linear_score(value, 0.8, 1.2, 70.0, 100.0)
    return 100.0


def score_gross_margin_trend(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"improving", "up", "stronger", "改善", "提升", "向上"}:
        return 100.0
    if normalized in {"stable", "flat", "steady", "稳定", "持平", "平稳"}:
        return 60.0
    if normalized in {"weakening", "down", "compressed", "承压", "下滑", "走弱"}:
        return 0.0
    return None


def score_price_war_pressure(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"low", "mild", "可控", "低", "较低"}:
        return 100.0
    if normalized in {"medium", "moderate", "中", "中等"}:
        return 60.0
    if normalized in {"high", "severe", "激烈", "高", "较高"}:
        return 0.0
    return None


def score_overseas_revenue_share(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if value <= 5.0:
        return 20.0
    if value < 20.0:
        return _linear_score(value, 5.0, 20.0, 20.0, 70.0)
    if value < 35.0:
        return _linear_score(value, 20.0, 35.0, 70.0, 100.0)
    return 100.0


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
