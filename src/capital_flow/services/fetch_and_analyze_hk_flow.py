"""Fetch and analyze HK capital-flow snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

from capital_flow.data.hk_flow_fetcher import fetch_hk_capital_flow_snapshot
from capital_flow.models.scorecard import CapitalFlowScoreCard
from capital_flow.models.snapshot import CapitalFlowSnapshot

from .analyze_snapshot import analyze_capital_flow_snapshot


@dataclass(frozen=True)
class FetchedHkCapitalFlowAnalysis:
    snapshot: CapitalFlowSnapshot
    scorecard: CapitalFlowScoreCard


def fetch_and_analyze_hk_flow(
    symbol: str,
    name: str,
    trade_date: Optional[date] = None,
    source: str = "eastmoney.hk_connect_components",
    use_cache: bool = True,
    cache_dir: Path | None = None,
    max_cache_age_days: int | None = 7,
) -> FetchedHkCapitalFlowAnalysis:
    """Fetch an HK capital-flow snapshot and score it."""

    snapshot = fetch_hk_capital_flow_snapshot(
        symbol=symbol,
        name=name,
        trade_date=trade_date,
        source=source,
        use_cache=use_cache,
        cache_dir=cache_dir,
        max_cache_age_days=max_cache_age_days,
    )
    return FetchedHkCapitalFlowAnalysis(
        snapshot=snapshot,
        scorecard=analyze_capital_flow_snapshot(snapshot),
    )