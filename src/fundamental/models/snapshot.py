"""Standardized fundamental snapshot input model."""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from .common import DupontDriver, GuidanceAttainment, MarketCode


class FundamentalSnapshot(BaseModel):
    """A standardized fundamental snapshot for one symbol and one report period."""

    model_config = ConfigDict(extra="ignore")

    symbol: str
    name: str
    market: MarketCode
    report_period: date
    currency: str
    source: str
    updated_at: datetime

    market_cap: Optional[float] = None
    pe_ttm: Optional[float] = None
    pe_percentile_5y: Optional[float] = None
    pb: Optional[float] = None
    ps_ttm: Optional[float] = None
    peg: Optional[float] = None
    dividend_yield: Optional[float] = None

    roe: Optional[float] = None
    roe_3y_mean: Optional[float] = None
    roe_3y_cv: Optional[float] = None
    dupont_driver: Optional[DupontDriver] = None
    asset_turnover: Optional[float] = None
    equity_multiplier: Optional[float] = None

    gross_margin: Optional[float] = None
    gross_margin_trend: Optional[str] = None
    net_margin: Optional[float] = None
    revenue_growth: Optional[float] = None
    net_profit_growth: Optional[float] = None
    overseas_revenue_share: Optional[float] = None

    debt_to_asset: Optional[float] = None
    current_ratio: Optional[float] = None
    operating_cashflow_to_profit: Optional[float] = None
    operating_cashflow_to_profit_history: Optional[List[Optional[float]]] = None

    accounts_receivable_growth: Optional[float] = None
    inventory_growth: Optional[float] = None
    price_war_pressure: Optional[str] = None
    interest_bearing_debt_growth: Optional[float] = None
    operating_cashflow_growth: Optional[float] = None
    free_cashflow_yield: Optional[float] = None
    capex_to_operating_cashflow: Optional[float] = None
    unit_cost_position: Optional[float] = None
    reserve_life_index: Optional[float] = None
    commodity_price_sensitivity: Optional[float] = None

    capital_adequacy_ratio: Optional[float] = None
    core_tier1_ratio: Optional[float] = None
    npl_ratio: Optional[float] = None
    provision_coverage_ratio: Optional[float] = None
    loan_deposit_growth_gap: Optional[float] = None
    net_interest_margin: Optional[float] = None
    solvency_adequacy_ratio: Optional[float] = None
    combined_ratio: Optional[float] = None
    investment_return: Optional[float] = None
    embedded_value_growth: Optional[float] = None
    new_business_value_growth: Optional[float] = None
    net_capital_ratio: Optional[float] = None

    guidance_attainment: Optional[GuidanceAttainment] = None

    period_type: Optional[str] = None
    period_label: Optional[str] = None
    industry: Optional[str] = None
    notes: Optional[str] = None
    raw_payload_ref: Optional[str] = None
