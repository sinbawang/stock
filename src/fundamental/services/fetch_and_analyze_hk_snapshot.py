"""Fetch one HK snapshot from public sources and analyze it with a configured submodel."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping, Optional

from fundamental.config.models import SubmodelConfig
from fundamental.data.hk_snapshot_fetcher import (
    FundamentalSnapshotFetchResult,
    fetch_hk_fundamental_snapshot,
)
from fundamental.models.scorecard import FundamentalScoreCard
from fundamental.models.snapshot import FundamentalSnapshot

from .analyze_snapshot import analyze_snapshot, resolve_submodel_for_symbol


@dataclass(frozen=True)
class FetchedFundamentalAnalysis:
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


def _apply_manual_supplement(
    fetched: FundamentalSnapshotFetchResult,
    submodel: SubmodelConfig,
    manual_supplement: Optional[Mapping[str, Any]],
) -> tuple[FundamentalSnapshotFetchResult, tuple[str, ...]]:
    if not manual_supplement:
        return fetched, ()

    updates = {field_name: value for field_name, value in manual_supplement.items() if value is not None}
    if not updates:
        return fetched, ()

    allowed_fields = set(submodel.field_policy.required_core)
    allowed_fields.update(submodel.field_policy.optional_manual)
    allowed_fields.update(submodel.field_policy.deferred_v2)
    allowed_fields.add("notes")

    unknown_fields = sorted(field_name for field_name in updates if field_name not in FundamentalSnapshot.model_fields)
    if unknown_fields:
        raise ValueError(f"Manual supplement contains unknown snapshot fields: {', '.join(unknown_fields)}")

    disallowed_fields = sorted(field_name for field_name in updates if field_name not in allowed_fields)
    if disallowed_fields:
        raise ValueError(
            "Manual supplement fields are not allowed for {}: {}".format(
                submodel.submodel_id,
                ", ".join(disallowed_fields),
            )
        )

    updated_snapshot = fetched.snapshot.model_copy(update=updates)
    field_sources = dict(fetched.field_sources or {})
    field_sources.update({field_name: "manual.supplement" for field_name in updates})
    updated_fetched = replace(
        fetched,
        snapshot=updated_snapshot,
        assumptions=fetched.assumptions
        + (
            "Manual supplement applied before analysis for fields: {}.".format(
                ", ".join(sorted(updates))
            ),
        ),
        raw_payload_refs=fetched.raw_payload_refs + (f"manual-supplement:{fetched.snapshot.symbol}",),
        field_sources=field_sources,
    )
    return updated_fetched, ()


def fetch_and_analyze_hk_snapshot(
    symbol: str,
    name: Optional[str] = None,
    submodel: Optional[str] = None,
    quote_overlay_source: Optional[str] = None,
    manual_supplement: Optional[Mapping[str, Any]] = None,
) -> FetchedFundamentalAnalysis:
    fetched = fetch_hk_fundamental_snapshot(
        symbol=symbol,
        name=name,
        quote_overlay_source=quote_overlay_source,
    )
    submodel_config = resolve_submodel_for_symbol(fetched.snapshot.symbol, submodel)
    fetched, supplement_assumptions = _apply_manual_supplement(
        fetched,
        submodel_config,
        manual_supplement,
    )
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