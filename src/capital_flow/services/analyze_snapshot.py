"""Analyze an already-standardized capital-flow snapshot."""

from capital_flow.models.scorecard import CapitalFlowScoreCard
from capital_flow.models.snapshot import CapitalFlowSnapshot
from capital_flow.scoring import score_capital_flow_snapshot


def analyze_capital_flow_snapshot(snapshot: CapitalFlowSnapshot) -> CapitalFlowScoreCard:
    """Return a scorecard for a standardized capital-flow snapshot."""

    return score_capital_flow_snapshot(snapshot)