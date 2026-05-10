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
from fundamental.models.snapshot import FundamentalSnapshot

from .analyze_snapshot import analyze_snapshot, resolve_submodel_for_symbol


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


def _format_field_labels(field_names: list[str]) -> str:
    labels = {
        "dividend_yield": "股息率",
        "solvency_adequacy_ratio": "综合偿付能力充足率",
        "combined_ratio": "综合成本率",
        "investment_return": "投资收益率",
        "embedded_value_growth": "内含价值增长率",
        "new_business_value_growth": "新业务价值增长率",
        "net_capital_ratio": "净资本比率",
        "revenue_growth": "营收增速",
        "net_profit_growth": "净利增速",
    }
    return "、".join(labels.get(field_name, field_name) for field_name in field_names)


def _derive_hk_source_warnings(fetched: FundamentalSnapshotFetchResult) -> tuple[str, ...]:
    field_sources = fetched.field_sources or {}
    warnings: list[str] = []

    manual_fields = sorted(
        field_name
        for field_name, source in field_sources.items()
        if source == "manual.supplement" and field_name != "notes"
    )
    if manual_fields:
        warnings.append(f"以下字段当前使用手工补充口径: {_format_field_labels(manual_fields)}。")
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

    normalized: list[str] = []
    for item in warnings:
        stripped = item.strip()
        if stripped and stripped not in normalized:
            normalized.append(stripped)
    return tuple(normalized)


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