"""Fetch HK annual and interim snapshots, then build a blended score view."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from fundamental.data.hk_snapshot_fetcher import fetch_hk_period_snapshots
from fundamental.models.blended import AnnualAnchorScore, BlendedFundamentalScoreCard, InterimOverlayScore, InterimWeightingProfile

from .analyze_snapshot import analyze_snapshot, resolve_submodel_for_symbol
from .fetch_and_analyze_cn_blended import (
    DEFAULT_INTERIM_WEIGHTING_PROFILE,
    _build_interim_overlay,
    _compose_blended_comment,
    _map_rating,
    _resolve_interim_weights,
)
from .fetch_and_analyze_hk_snapshot import _derive_hk_source_warnings, _relax_missing_peg, resolve_hk_quote_overlay_source
from .manual_supplement_helpers import apply_manual_supplement, resolve_manual_supplement


SUPPORTED_HK_BLENDED_SUBMODELS = {
    "platform_internet_v1",
    "digital_infra_v1",
    "semiconductor_hardtech_v1",
    "auto_manufacturing_v1",
    "insurance_v1",
    "broker_v1",
}


@dataclass(frozen=True)
class BlendedHkFundamentalAnalysis:
    blended: BlendedFundamentalScoreCard
    annual_anchor: AnnualAnchorScore
    interim_overlay: Optional[InterimOverlayScore]
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def _analyze_hk_fetched_snapshot(
    fetched,
    *,
    submodel: Optional[str],
    manual_supplement: Optional[Mapping[str, Any]],
    manual_supplement_path: Optional[str],
):
    submodel_config = resolve_submodel_for_symbol(fetched.snapshot.symbol, submodel)
    if submodel_config.submodel_id not in SUPPORTED_HK_BLENDED_SUBMODELS:
        raise RuntimeError(
            "HK blended POC currently supports platform_internet_v1, digital_infra_v1, semiconductor_hardtech_v1, auto_manufacturing_v1, insurance_v1, and broker_v1 only; other HK submodels should be added incrementally."
        )

    supplemented = apply_manual_supplement(
        fetched,
        submodel_config,
        resolve_manual_supplement(manual_supplement, manual_supplement_path),
    )
    analyzed_submodel, runtime_assumptions = _relax_missing_peg(
        submodel_config,
        missing_peg=supplemented.snapshot.peg is None,
    )
    scorecard = analyze_snapshot(supplemented.snapshot, analyzed_submodel)
    source_warnings = _derive_hk_source_warnings(supplemented)
    if source_warnings:
        scorecard = scorecard.model_copy(
            update={
                "warnings": list(dict.fromkeys([*scorecard.warnings, *source_warnings])),
            }
        )
    return supplemented, analyzed_submodel, scorecard, runtime_assumptions


def fetch_and_analyze_hk_blended_fundamentals(
    symbol: str,
    name: Optional[str] = None,
    submodel: Optional[str] = None,
    quote_overlay_source: Optional[str] = None,
    manual_supplement: Optional[Mapping[str, Any]] = None,
    manual_supplement_path: Optional[str] = None,
    weighting_profile: InterimWeightingProfile = DEFAULT_INTERIM_WEIGHTING_PROFILE,
) -> BlendedHkFundamentalAnalysis:
    requested_submodel = resolve_submodel_for_symbol(symbol, submodel)
    period_snapshots = fetch_hk_period_snapshots(
        symbol=symbol,
        name=name,
        quote_overlay_source=resolve_hk_quote_overlay_source(requested_submodel, quote_overlay_source),
    )
    annual_fetched, analyzed_submodel, annual_scorecard, annual_runtime_assumptions = _analyze_hk_fetched_snapshot(
        period_snapshots.annual,
        submodel=submodel,
        manual_supplement=manual_supplement,
        manual_supplement_path=manual_supplement_path,
    )
    annual_anchor = AnnualAnchorScore(
        snapshot=annual_fetched.snapshot,
        scorecard=annual_scorecard,
        assumptions=annual_fetched.assumptions + annual_runtime_assumptions,
        warnings=tuple(annual_scorecard.warnings),
    )

    interim_overlay = None
    interim_warnings: tuple[str, ...] = ()
    interim_assumptions: tuple[str, ...] = ()
    if period_snapshots.interim is not None and annual_fetched.snapshot.period_type == "annual":
        supplemented_interim = period_snapshots.interim
        interim_overlay = _build_interim_overlay(supplemented_interim.snapshot, analyzed_submodel)
        interim_warnings = _derive_hk_source_warnings(supplemented_interim)
        interim_runtime_assumptions: tuple[str, ...] = ()
        if supplemented_interim.snapshot.peg is None:
            _relaxed_submodel, interim_runtime_assumptions = _relax_missing_peg(
                analyzed_submodel,
                missing_peg=True,
            )
        interim_assumptions = supplemented_interim.assumptions + interim_runtime_assumptions

    annual_weight, interim_weight, freshness_label = _resolve_interim_weights(
        interim_overlay.snapshot if interim_overlay is not None else None,
        weighting_profile,
    )
    blended_total_score = round(
        annual_anchor.scorecard.total_score * annual_weight
        + ((interim_overlay.overlay_score if interim_overlay is not None else 0.0) * interim_weight),
        2,
    )
    blended_rating = annual_anchor.scorecard.rating if annual_anchor.scorecard.red_flag else _map_rating(blended_total_score)
    combined_assumptions = annual_anchor.assumptions + interim_assumptions
    combined_warnings = tuple(dict.fromkeys([*annual_anchor.warnings, *interim_warnings]))

    blended = BlendedFundamentalScoreCard(
        symbol=annual_anchor.snapshot.symbol,
        name=annual_anchor.snapshot.name,
        market=annual_anchor.snapshot.market,
        submodel_id=annual_anchor.scorecard.submodel_id,
        annual_anchor=annual_anchor,
        interim_overlay=interim_overlay,
        annual_weight=annual_weight,
        interim_weight=interim_weight,
        blended_total_score=blended_total_score,
        blended_rating=blended_rating,
        freshness_label=freshness_label,
        warnings=combined_warnings,
        assumptions=combined_assumptions,
        combined_comment=_compose_blended_comment(annual_anchor, interim_overlay, annual_weight, interim_weight),
    )

    return BlendedHkFundamentalAnalysis(
        blended=blended,
        annual_anchor=annual_anchor,
        interim_overlay=interim_overlay,
        assumptions=combined_assumptions,
        warnings=combined_warnings,
    )