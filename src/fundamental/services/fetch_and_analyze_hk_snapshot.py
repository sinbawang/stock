"""Fetch one HK snapshot from public sources and analyze it with a configured submodel."""

from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Any, Mapping, Optional

from fundamental.config.models import SubmodelConfig
from fundamental.data.hk_snapshot_fetcher import (
    FundamentalSnapshotFetchResult,
    fetch_hk_fundamental_snapshot,
)
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
class FetchedFundamentalAnalysis:
    fetched: FundamentalSnapshotFetchResult
    scorecard: FundamentalScoreCard
    assumptions: tuple[str, ...] = ()


def _extract_latest_disclosure_date(assumptions: tuple[str, ...]) -> Optional[str]:
    for item in assumptions:
        match = re.search(r"Latest PICC solvency report disclosure date used for fallback: (\d{4}-\d{2}-\d{2})", item)
        if match is not None:
            return match.group(1)
    return None


def _derive_hk_source_warnings(fetched: FundamentalSnapshotFetchResult) -> tuple[str, ...]:
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
        if "investment_return" in manual_fields:
            warnings.append("投资收益率当前为手工补充/代理值时，应与公司原文直接披露口径区分阅读。")
        insurance_cross_scope_fields = {
            "solvency_adequacy_ratio",
            "combined_ratio",
            "embedded_value_growth",
            "new_business_value_growth",
        }
        if insurance_cross_scope_fields.intersection(manual_fields):
            warnings.append("保险手工补充字段可能存在跨主体口径: 偿付能力偏集团监管口径，综合成本率偏财险口径，EV/NBV 偏寿险口径。")

    if field_sources.get("solvency_adequacy_ratio") == "official.solvency_report":
        disclosure_date = _extract_latest_disclosure_date(fetched.assumptions)
        if disclosure_date is not None:
            warnings.append(
                f"偿付能力充足率当前来自官网偿付能力报告摘要（披露日 {disclosure_date}），不是 {fetched.snapshot.report_period.isoformat()} 年报口径。"
            )
        else:
            warnings.append(
                f"偿付能力充足率当前来自官网偿付能力报告摘要，不是 {fetched.snapshot.report_period.isoformat()} 年报口径。"
            )

    if field_sources.get("net_capital_ratio") == "official.annual_report_proxy":
        warnings.append("净资本比率当前由官方年报中的风险覆盖率代理映射，不是公司直接披露的净资本比率字段。")

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


def fetch_and_analyze_hk_snapshot(
    symbol: str,
    name: Optional[str] = None,
    submodel: Optional[str] = None,
    quote_overlay_source: Optional[str] = None,
    manual_supplement: Optional[Mapping[str, Any]] = None,
    manual_supplement_path: Optional[str] = None,
) -> FetchedFundamentalAnalysis:
    fetched = fetch_hk_fundamental_snapshot(
        symbol=symbol,
        name=name,
        quote_overlay_source=quote_overlay_source,
    )
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
    scorecard = analyze_snapshot(fetched.snapshot, analyzed_submodel)
    source_warnings = _derive_hk_source_warnings(fetched)
    if source_warnings:
        scorecard = scorecard.model_copy(
            update={
                "warnings": list(dict.fromkeys([*scorecard.warnings, *source_warnings])),
            }
        )
    return FetchedFundamentalAnalysis(
        fetched=fetched,
        scorecard=scorecard,
        assumptions=fetched.assumptions + runtime_assumptions,
    )