"""Fetch one CN snapshot from public sources and analyze it with a configured submodel."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional

from fundamental.config.models import SubmodelConfig
from fundamental.data.cn_snapshot_fetcher import fetch_cn_fundamental_snapshot
from fundamental.data.hk_snapshot_fetcher import FundamentalSnapshotFetchResult
from fundamental.models.scorecard import FundamentalScoreCard

from .analyze_snapshot import analyze_snapshot, resolve_submodel_for_symbol


@dataclass(frozen=True)
class FetchedCnFundamentalAnalysis:
    fetched: FundamentalSnapshotFetchResult
    scorecard: FundamentalScoreCard
    assumptions: tuple[str, ...] = ()
def _relax_missing_peg(submodel: SubmodelConfig, missing_peg: bool) -> tuple[SubmodelConfig, tuple[str, ...]]:
    if not missing_peg or "peg" not in submodel.field_policy.required_core:
        return submodel, ()

    relaxed_policy = replace(
        submodel.field_policy,
        required_core=tuple(field for field in submodel.field_policy.required_core if field != "peg"),
        optional_manual=submodel.field_policy.optional_manual + ("peg",),
    )
    return (
        replace(submodel, field_policy=relaxed_policy),
        ("Runtime relaxation: PEG is treated as optional because current TTM PE makes PEG unavailable.",),
    )


def fetch_and_analyze_cn_snapshot(
    symbol: str,
    name: Optional[str] = None,
    submodel: Optional[str] = None,
) -> FetchedCnFundamentalAnalysis:
    fetched = fetch_cn_fundamental_snapshot(symbol=symbol, name=name)
    submodel_config = resolve_submodel_for_symbol(fetched.snapshot.symbol, submodel)
    analyzed_submodel, runtime_assumptions = _relax_missing_peg(
        submodel_config,
        missing_peg=fetched.snapshot.peg is None,
    )
    scorecard = analyze_snapshot(fetched.snapshot, analyzed_submodel)
    return FetchedCnFundamentalAnalysis(
        fetched=fetched,
        scorecard=scorecard,
        assumptions=fetched.assumptions + runtime_assumptions,
    )