"""Fetch one CN snapshot from public sources and analyze it with a configured submodel."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping, Optional

from fundamental.config.models import SubmodelConfig
from fundamental.data.cn_snapshot_fetcher import fetch_cn_fundamental_snapshot
from fundamental.data.hk_snapshot_fetcher import FundamentalSnapshotFetchResult
from fundamental.models.scorecard import FundamentalScoreCard

from .analyze_snapshot import analyze_snapshot, resolve_submodel_for_symbol
from .manual_supplement_helpers import apply_manual_supplement, resolve_manual_supplement
from .source_warning_helpers import (
    build_manual_supplement_warning,
    build_reporting_period_warning,
    get_manual_supplement_fields,
    normalize_warnings,
)


@dataclass(frozen=True)
class FetchedCnFundamentalAnalysis:
    fetched: FundamentalSnapshotFetchResult
    scorecard: FundamentalScoreCard
    assumptions: tuple[str, ...] = ()

def _derive_cn_source_warnings(fetched: FundamentalSnapshotFetchResult) -> tuple[str, ...]:
    field_sources = fetched.field_sources or {}
    warnings: list[str] = []

    reporting_period_warning = build_reporting_period_warning(
        fetched.snapshot.report_period,
        fetched.snapshot.period_type,
    )
    if reporting_period_warning:
        warnings.append(reporting_period_warning)

    manual_fields = get_manual_supplement_fields(field_sources)
    if manual_fields:
        manual_warning = build_manual_supplement_warning(field_sources)
        if manual_warning:
            warnings.append(manual_warning)
        energy_research_fields = {
            "unit_cost_position",
            "reserve_life_index",
            "commodity_price_sensitivity",
            "capex_to_operating_cashflow",
            "free_cashflow_yield",
        }
        if energy_research_fields.intersection(manual_fields):
            warnings.append("能源资源手工补充字段可能包含研究口径或公告摘要口径，应与公司原文披露口径区分阅读。")

    return normalize_warnings(warnings)


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


def _relax_missing_cn_dividend_yield(
    submodel: SubmodelConfig,
    missing_dividend_yield: bool,
) -> tuple[SubmodelConfig, tuple[str, ...]]:
    if not missing_dividend_yield or "dividend_yield" not in submodel.field_policy.required_core:
        return submodel, ()

    relaxed_policy = replace(
        submodel.field_policy,
        required_core=tuple(field for field in submodel.field_policy.required_core if field != "dividend_yield"),
        optional_manual=submodel.field_policy.optional_manual + ("dividend_yield",),
    )
    return (
        replace(submodel, field_policy=relaxed_policy),
        (
            "Runtime relaxation: dividend_yield is treated as optional because current public CN sources do not expose a stable point-in-time yield field for this submodel.",
        ),
    )


def fetch_and_analyze_cn_snapshot(
    symbol: str,
    name: Optional[str] = None,
    submodel: Optional[str] = None,
    manual_supplement: Optional[Mapping[str, Any]] = None,
    manual_supplement_path: Optional[str] = None,
) -> FetchedCnFundamentalAnalysis:
    fetched = fetch_cn_fundamental_snapshot(symbol=symbol, name=name)
    submodel_config = resolve_submodel_for_symbol(fetched.snapshot.symbol, submodel)
    fetched = apply_manual_supplement(
        fetched,
        submodel_config,
        resolve_manual_supplement(manual_supplement, manual_supplement_path),
    )
    analyzed_submodel, runtime_assumptions = _relax_missing_peg(
        submodel_config,
        missing_peg=fetched.snapshot.peg is None,
    )
    analyzed_submodel, cn_dividend_runtime_assumptions = _relax_missing_cn_dividend_yield(
        analyzed_submodel,
        missing_dividend_yield=fetched.snapshot.dividend_yield is None,
    )
    scorecard = analyze_snapshot(fetched.snapshot, analyzed_submodel)
    source_warnings = _derive_cn_source_warnings(fetched)
    if source_warnings:
        scorecard = scorecard.model_copy(
            update={
                "warnings": list(dict.fromkeys([*scorecard.warnings, *source_warnings])),
            }
        )
    return FetchedCnFundamentalAnalysis(
        fetched=fetched,
        scorecard=scorecard,
        assumptions=fetched.assumptions + runtime_assumptions + cn_dividend_runtime_assumptions,
    )