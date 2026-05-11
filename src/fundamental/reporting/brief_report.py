"""Render and save user-facing fundamental brief text files."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from typing import Any, Mapping, Optional, Sequence

from fundamental.models.scorecard import FundamentalScoreCard
from fundamental.models.snapshot import FundamentalSnapshot

from .text_report import DIMENSION_LABELS


def _format_dimension_name(name: str) -> str:
    return DIMENSION_LABELS.get(name, name.replace("_", " ").title())


def _normalize_items(values: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        stripped = value.strip()
        if stripped and stripped not in normalized:
            normalized.append(stripped)
    return normalized


def _format_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return format(value, ".12g")
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if any(char in text for char in [",", "，", "=", '"']):
        return '"' + text.replace('"', '\\"') + '"'
    return text


def _manual_supplement_lines(snapshot: FundamentalSnapshot, field_sources: Optional[Mapping[str, str]]) -> list[str]:
    if not field_sources:
        return []

    lines: list[str] = []
    for field_name in sorted(field_name for field_name, source in field_sources.items() if source == "manual.supplement"):
        value = getattr(snapshot, field_name, None)
        lines.append(f"- {field_name}={_format_scalar(value)}")
    return lines


def _dupont_summary_line(snapshot: FundamentalSnapshot) -> Optional[str]:
    items: list[str] = []
    for label, field_name in (
        ("净利率", "net_margin"),
        ("总资产周转率", "asset_turnover"),
        ("权益乘数", "equity_multiplier"),
        ("杜邦驱动", "dupont_driver"),
    ):
        value = getattr(snapshot, field_name, None)
        if value is not None:
            items.append(f"{label}={_format_scalar(value)}")
    if not items:
        return None
    return "- 杜邦拆解: " + ", ".join(items)


def _format_score_basis_summary(score_basis: Optional[str]) -> Optional[str]:
    if not score_basis:
        return None

    normalized_parts: list[str] = []
    for part in (item.strip() for item in score_basis.split(";")):
        if not part:
            continue
        scored_match = re.fullmatch(r"已计分(\d+/\d+)项\[(.*)\]", part)
        if scored_match:
            normalized_parts.append(f"{scored_match.group(1)}项 {scored_match.group(2)}")
            continue
        if part.startswith("已计分") and part.endswith("项"):
            normalized_parts.append(part.replace("已计分", ""))
            continue
        if part.startswith("平均="):
            normalized_parts.append("平均" + part[len("平均=") :])
            continue
        if part.startswith("缺失[") and part.endswith("]"):
            missing_text = part[3:-1].replace(" NA", "")
            normalized_parts.append("缺失 " + missing_text)
            continue
        weighted_match = re.fullmatch(r"×\d+/100=(.*)", part)
        if weighted_match:
            normalized_parts.append(f"折算{weighted_match.group(1)}")
            continue
        if part.startswith("维度分="):
            normalized_parts.append("维度分" + part[len("维度分=") :])
            continue
        normalized_parts.append(part)

    if not normalized_parts:
        return None
    return "; ".join(normalized_parts)


def render_fundamental_brief(
    scorecard: FundamentalScoreCard,
    snapshot: FundamentalSnapshot,
    field_sources: Optional[Mapping[str, str]] = None,
    generated_at: Optional[datetime] = None,
) -> str:
    generated = generated_at or datetime.now()
    strengths = _normalize_items(scorecard.strengths)
    risks = _normalize_items(scorecard.risks)
    warnings = _normalize_items(scorecard.warnings)
    missing_metrics = _normalize_items(scorecard.missing_metrics)
    supplement_lines = _manual_supplement_lines(snapshot, field_sources)

    lines = [
        f"{scorecard.name}基本面简报",
        f"时间: {generated.strftime('%Y-%m-%d %H:%M')}",
        f"标的: {scorecard.name}({scorecard.symbol})  报告期: {scorecard.report_period.isoformat()}",
        f"评级: {scorecard.rating}  总分: {scorecard.total_score:.2f}  红线: {'有' if scorecard.red_flag else '无'}",
        f"子模型: {scorecard.submodel_id}",
        "",
        "核心结论:",
    ]
    lines.extend(
        f"- {_format_dimension_name(dimension.dimension)} {dimension.score:.2f}/{dimension.weight:.2f}。"
        for dimension in scorecard.dimension_scores
    )
    calculation_lines = [
        f"- {_format_dimension_name(dimension.dimension)}: {summary}"
        for dimension in scorecard.dimension_scores
        for summary in [_format_score_basis_summary(dimension.score_basis)]
        if summary
    ]
    if calculation_lines:
        lines.extend(["", "计算说明:", *calculation_lines])

    if strengths:
        lines.extend(["", "亮点:"])
        lines.extend(f"- {item}" for item in strengths)
    if risks:
        lines.extend(["", "风险:"])
        lines.extend(f"- {item}" for item in risks)
    if warnings:
        lines.extend(["", "警告:"])
        lines.extend(f"- {item}" for item in warnings)
    if missing_metrics:
        lines.extend(["", "当前缺失字段:"])
        lines.extend(f"- {item}" for item in missing_metrics)

    lines.extend(["", "补充说明:"])
    summary_parts: list[str] = []
    for field_name in ("pe_ttm", "pb", "ps_ttm"):
        value = getattr(snapshot, field_name, None)
        if value is not None:
            summary_parts.append(f"{field_name}={_format_scalar(value)}")
    if summary_parts:
        lines.append("- " + ", ".join(summary_parts))
    dupont_summary = _dupont_summary_line(snapshot)
    if dupont_summary:
        lines.append(dupont_summary)
    if field_sources and field_sources.get("market_cap"):
        lines.append(f"- market_cap 来源: {field_sources['market_cap']}")
    if scorecard.combined_comment:
        lines.append(f"- 综合说明: {scorecard.combined_comment}")

    if supplement_lines:
        lines.extend(["", "手工补充字段:", *supplement_lines])

    return "\n".join(lines).strip() + "\n"


def save_fundamental_brief(
    scorecard: FundamentalScoreCard,
    snapshot: FundamentalSnapshot,
    field_sources: Optional[Mapping[str, str]] = None,
    output_dir: str | Path = "data/_meta",
    generated_at: Optional[datetime] = None,
) -> Path:
    generated = generated_at or datetime.now()
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"{scorecard.symbol}_{scorecard.name}_fundamental_brief_{generated.strftime('%Y%m%d_%H%M%S')}.txt"
    output_path = target_dir / file_name
    output_path.write_text(
        render_fundamental_brief(
            scorecard=scorecard,
            snapshot=snapshot,
            field_sources=field_sources,
            generated_at=generated,
        ),
        encoding="utf-8",
    )
    return output_path