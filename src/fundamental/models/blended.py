"""Cross-period blended fundamental scoring models."""

from dataclasses import dataclass, field
from typing import Optional

from .common import MarketCode, Rating
from .scorecard import FundamentalScoreCard
from .snapshot import FundamentalSnapshot


@dataclass(frozen=True)
class OverlayComponent:
    component: str
    score: float
    weight: float
    covered_metrics: tuple[str, ...] = ()
    missing_metrics: tuple[str, ...] = ()
    note: Optional[str] = None


@dataclass(frozen=True)
class InterimWeightingProfile:
    profile_id: str
    annual_after_annual: float = 1.0
    interim_after_annual: float = 0.0
    annual_after_q1: float = 0.8
    interim_after_q1: float = 0.2
    annual_after_h1: float = 0.65
    interim_after_h1: float = 0.35
    annual_after_q3: float = 0.5
    interim_after_q3: float = 0.5


@dataclass(frozen=True)
class AnnualAnchorScore:
    snapshot: FundamentalSnapshot
    scorecard: FundamentalScoreCard
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class InterimOverlayScore:
    snapshot: FundamentalSnapshot
    components: tuple[OverlayComponent, ...]
    overlay_score: float
    rating_hint: Optional[Rating] = None
    covered_metrics: tuple[str, ...] = ()
    missing_metrics: tuple[str, ...] = ()
    drivers_positive: tuple[str, ...] = ()
    drivers_negative: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class BlendedFundamentalScoreCard:
    symbol: str
    name: str
    market: MarketCode
    submodel_id: str
    annual_anchor: AnnualAnchorScore
    interim_overlay: Optional[InterimOverlayScore]
    annual_weight: float
    interim_weight: float
    blended_total_score: float
    blended_rating: Rating
    freshness_label: str
    warnings: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    combined_comment: Optional[str] = None