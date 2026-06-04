from __future__ import annotations

from pathlib import Path

from .brief_report import render_blended_fundamental_brief, _format_component_name, _format_dimension_name, _format_metric_name
from .text_report import _format_score_basis_for_display


def _metric_detail(snapshot, metric_name: str) -> dict[str, object]:
    return {
        "name": metric_name,
        "label": _format_metric_name(metric_name),
        "value": getattr(snapshot, metric_name, None),
    }


def _annual_dimension_presentation(blended) -> list[dict[str, object]]:
    snapshot = blended.annual_anchor.snapshot
    scorecard = blended.annual_anchor.scorecard
    payloads: list[dict[str, object]] = []
    for dimension in scorecard.dimension_scores:
        payloads.append(
            {
                "dimension": dimension.dimension,
                "title": _format_dimension_name(dimension.dimension),
                "score": dimension.score,
                "weight": dimension.weight,
                "max_score": dimension.max_score,
                "red_flag": scorecard.red_flag,
                "formula": _format_score_basis_for_display(dimension.score_basis, snapshot),
                "covered_metrics": [_metric_detail(snapshot, metric_name) for metric_name in dimension.used_metrics if metric_name],
                "missing_metrics": [_metric_detail(snapshot, metric_name) for metric_name in dimension.missing_metrics if metric_name],
                "passed_rules": list(dimension.passed_rules),
                "failed_rules": list(dimension.failed_rules),
                "notes": list(dimension.notes),
            }
        )
    return payloads


def _interim_component_presentation(blended) -> list[dict[str, object]]:
    overlay = blended.interim_overlay
    if overlay is None:
        return []
    snapshot = overlay.snapshot
    payloads: list[dict[str, object]] = []
    for component in overlay.components:
        payloads.append(
            {
                "component": component.component,
                "title": _format_component_name(component.component),
                "score": component.score,
                "weight": component.weight,
                "weighted_score": round(component.score * component.weight, 4),
                "formula": "单指标刷新" if len(component.covered_metrics) <= 1 else "覆盖指标均值刷新",
                "covered_metrics": [_metric_detail(snapshot, metric_name) for metric_name in component.covered_metrics if metric_name],
                "missing_metrics": [_metric_detail(snapshot, metric_name) for metric_name in component.missing_metrics if metric_name],
                "note": component.note,
            }
        )
    return payloads


def build_fundamental_presentation(blended, base_text_path: Path) -> dict[str, object]:
    annual_scorecard = blended.annual_anchor.scorecard
    interim_overlay = blended.interim_overlay
    return {
        "periods": {
            "annual": blended.annual_anchor.snapshot.report_period.isoformat(),
            "annual_label": blended.annual_anchor.snapshot.period_label or "年报",
            "interim": interim_overlay.snapshot.report_period.isoformat() if interim_overlay is not None else None,
            "interim_label": (interim_overlay.snapshot.period_label or "中间报告期") if interim_overlay is not None else None,
        },
        "summary": {
            "score": blended.blended_total_score,
            "rating": blended.blended_rating,
            "red_flag": annual_scorecard.red_flag,
            "annual_anchor_score": annual_scorecard.total_score,
            "annual_anchor_rating": annual_scorecard.rating,
            "annual_anchor_label": blended.annual_anchor.snapshot.period_label or "年报",
            "interim_overlay_score": interim_overlay.overlay_score if interim_overlay is not None else None,
            "interim_overlay_rating": interim_overlay.rating_hint if interim_overlay is not None else None,
            "interim_overlay_label": (interim_overlay.snapshot.period_label or "中间报告期") if interim_overlay is not None else None,
            "annual_weight": blended.annual_weight,
            "interim_weight": blended.interim_weight,
            "freshness_label": blended.freshness_label,
            "comment": blended.combined_comment,
        },
        "red_flag": {
            "triggered": annual_scorecard.red_flag,
            "rules": list(annual_scorecard.triggered_rules),
        },
        "current_missing_fields": list(annual_scorecard.missing_metrics),
        "annual_dimensions": _annual_dimension_presentation(blended),
        "interim_components": _interim_component_presentation(blended),
        "warnings": list(blended.warnings),
        "assumptions": list(blended.assumptions),
        "base_text_path": str(base_text_path),
    }


def write_base_text(blended, output_dir: Path) -> Path:
    output_path = output_dir / "base.txt"
    output_path.write_text(render_blended_fundamental_brief(blended=blended), encoding="utf-8")
    return output_path