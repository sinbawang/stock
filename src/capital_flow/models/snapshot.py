"""Standardized capital-flow snapshot input model."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from .common import MarketCode


class CapitalFlowSnapshot(BaseModel):
    """A standardized capital-flow snapshot for one symbol and one trade date."""

    model_config = ConfigDict(extra="ignore")

    symbol: str
    name: str
    market: MarketCode
    trade_date: date
    source: str
    updated_at: datetime

    turnover: Optional[float] = None
    turnover_rate: Optional[float] = None
    volume_ratio: Optional[float] = None
    amount_ratio_5d: Optional[float] = None

    main_net_inflow: Optional[float] = None
    main_net_inflow_3d: Optional[float] = None
    main_net_inflow_5d: Optional[float] = None
    main_net_inflow_10d: Optional[float] = None
    super_large_net_inflow: Optional[float] = None
    large_order_net_inflow: Optional[float] = None
    medium_order_net_inflow: Optional[float] = None
    small_order_net_inflow: Optional[float] = None

    northbound_holding_change: Optional[float] = None
    margin_balance_change: Optional[float] = None

    southbound_net_buy: Optional[float] = None
    southbound_holding_change: Optional[float] = None
    short_sell_ratio: Optional[float] = None
    short_sell_turnover: Optional[float] = None

    dragon_tiger_flag: bool = False
    block_trade_flag: bool = False
    notes: Optional[str] = None
    raw_payload_ref: Optional[str] = None