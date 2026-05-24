"""Fetch and analyze A-share capital-flow snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

from capital_flow.data.cn_flow_fetcher import fetch_cn_capital_flow_snapshot
from capital_flow.models.scorecard import CapitalFlowScoreCard
from capital_flow.models.snapshot import CapitalFlowSnapshot

from .analyze_snapshot import analyze_capital_flow_snapshot


@dataclass(frozen=True)
class FetchedCnCapitalFlowAnalysis:
    snapshot: CapitalFlowSnapshot
    scorecard: CapitalFlowScoreCard


def fetch_and_analyze_cn_flow(
    symbol: str,
    name: str,
    trade_date: Optional[date] = None,
    source: str = "akshare.eastmoney",
    use_cache: bool = True,
    use_fallback: bool = True,
    cache_dir: Optional[Path | str] = None,
    max_cache_age_days: Optional[int] = 7,
) -> FetchedCnCapitalFlowAnalysis:
    """Fetch an A-share capital-flow snapshot and score it."""

    snapshot = fetch_cn_capital_flow_snapshot(
        symbol=symbol,
        name=name,
        trade_date=trade_date,
        source=source,
        use_cache=use_cache,
        use_fallback=use_fallback,
        **({"cache_dir": cache_dir} if cache_dir is not None else {}),
        max_cache_age_days=max_cache_age_days,
    )
    return FetchedCnCapitalFlowAnalysis(
        snapshot=snapshot,
        scorecard=analyze_capital_flow_snapshot(snapshot),
    )