"""Fundamental analysis package.

This package is intentionally a sibling of ``chanlun``:
- ``chanlun`` contains technical-analysis logic
- ``fundamental`` contains fundamental-analysis logic
"""

from .models.snapshot import FundamentalSnapshot
from .models.scorecard import (
    FundamentalDimensionScore,
    FundamentalScoreCard,
    TriggeredRule,
)
from .data import FundamentalSnapshotFetchResult, fetch_cn_fundamental_snapshot, fetch_hk_fundamental_snapshot
from .reporting import render_scorecard_text
from .services import (
    FetchedCnFundamentalAnalysis,
    FetchedFundamentalAnalysis,
    analyze_snapshot,
    fetch_and_analyze_cn_snapshot,
    fetch_and_analyze_hk_snapshot,
)

__all__ = [
    "FundamentalSnapshot",
    "FundamentalDimensionScore",
    "FundamentalScoreCard",
    "TriggeredRule",
    "FundamentalSnapshotFetchResult",
    "FetchedFundamentalAnalysis",
    "FetchedCnFundamentalAnalysis",
    "fetch_cn_fundamental_snapshot",
    "fetch_hk_fundamental_snapshot",
    "fetch_and_analyze_cn_snapshot",
    "fetch_and_analyze_hk_snapshot",
    "render_scorecard_text",
    "analyze_snapshot",
]
