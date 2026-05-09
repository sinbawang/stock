"""Fetch one HK snapshot from public sources and analyze it with a configured submodel."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional

from fundamental.config.models import SubmodelConfig
from fundamental.config.registry import get_submodel, get_submodel_for_symbol
from fundamental.data.hk_snapshot_fetcher import (
    FundamentalSnapshotFetchResult,
    fetch_hk_fundamental_snapshot,
)
from fundamental.models.scorecard import FundamentalScoreCard

from .analyze_snapshot import analyze_snapshot


@dataclass(frozen=True)
class FetchedFundamentalAnalysis:
    fetched: FundamentalSnapshotFetchResult
    scorecard: FundamentalScoreCard
    assumptions: tuple[str, ...] = ()


def _resolve_submodel(symbol: str, submodel: Optional[str]) -> SubmodelConfig:
    if submodel is not None:
        return get_submodel(submodel)

    resolved = get_submodel_for_symbol(symbol)
    if resolved is None:
        raise ValueError(f"未能根据代码 {symbol} 自动匹配基本面子模型")
    return resolved


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


def fetch_and_analyze_hk_snapshot(
    symbol: str,
    name: Optional[str] = None,
    submodel: Optional[str] = None,
    quote_overlay_source: Optional[str] = None,
) -> FetchedFundamentalAnalysis:
    fetched = fetch_hk_fundamental_snapshot(
        symbol=symbol,
        name=name,
        quote_overlay_source=quote_overlay_source,
    )
    submodel_config = _resolve_submodel(fetched.snapshot.symbol, submodel)
    analyzed_submodel, runtime_assumptions = _relax_missing_peg(
        submodel_config,
        missing_peg=fetched.snapshot.peg is None,
    )
    scorecard = analyze_snapshot(fetched.snapshot, analyzed_submodel)
    return FetchedFundamentalAnalysis(
        fetched=fetched,
        scorecard=scorecard,
        assumptions=fetched.assumptions + runtime_assumptions,
    )