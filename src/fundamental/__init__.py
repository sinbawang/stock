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
from .reporting import (
    render_blended_fundamental_brief,
    render_blended_scorecard_text,
    render_fundamental_brief,
    render_scorecard_text,
    save_blended_fundamental_brief,
    save_blended_scorecard_text,
    save_fundamental_brief,
)
from .services import (
    BlendedCnFundamentalAnalysis,
    FetchedCnFundamentalAnalysis,
    FetchedFundamentalAnalysis,
    analyze_snapshot,
    fetch_and_analyze_cn_blended_fundamentals,
    fetch_and_analyze_cn_snapshot,
    fetch_and_analyze_hk_snapshot,
)

__all__ = [
    "FundamentalSnapshot",
    "FundamentalDimensionScore",
    "FundamentalScoreCard",
    "TriggeredRule",
    "FundamentalSnapshotFetchResult",
    "BlendedCnFundamentalAnalysis",
    "FetchedFundamentalAnalysis",
    "FetchedCnFundamentalAnalysis",
    "fetch_and_analyze_cn_blended_fundamentals",
    "fetch_cn_fundamental_snapshot",
    "fetch_hk_fundamental_snapshot",
    "fetch_and_analyze_cn_snapshot",
    "fetch_and_analyze_hk_snapshot",
    "render_blended_fundamental_brief",
    "render_blended_scorecard_text",
    "render_fundamental_brief",
    "render_scorecard_text",
    "save_blended_fundamental_brief",
    "save_blended_scorecard_text",
    "save_fundamental_brief",
    "analyze_snapshot",
]
