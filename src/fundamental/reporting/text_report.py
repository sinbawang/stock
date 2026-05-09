"""Render a FundamentalScoreCard into a readable text summary."""

from fundamental.models.scorecard import FundamentalScoreCard


DIMENSION_LABELS = {
    "profit_quality": "盈利质量",
    "growth_delivery": "成长兑现",
    "cashflow_and_operating_efficiency": "现金流与运营效率",
    "valuation_fit": "估值匹配",
    "growth_and_cycle": "成长与景气度",
    "operating_and_inventory_cycle": "营运与库存周期",
}


def _format_dimension_name(name: str) -> str:
    return DIMENSION_LABELS.get(name, name)


def _normalize_items(values: list[str]) -> list[str]:
    normalized = []
    for value in values:
        stripped = value.strip()
        if stripped and stripped not in normalized:
            normalized.append(stripped)
    return normalized


def _sort_missing_metrics(values: list[str]) -> list[str]:
    return sorted(_normalize_items(values))


def _render_lines(title: str, values: list[str]) -> list[str]:
    if not values:
        return []
    lines = [title]
    lines.extend(f"- {value}" for value in values)
    return lines


def _render_numbered_lines(title: str, values: list[str]) -> list[str]:
    if not values:
        return []
    lines = [title]
    lines.extend(f"{index}. {value}" for index, value in enumerate(values, start=1))
    return lines


def render_scorecard_text(scorecard: FundamentalScoreCard) -> str:
    header = (
        f"{scorecard.name} ({scorecard.symbol}) | "
        f"{scorecard.industry_bucket}/{scorecard.submodel_id} | {scorecard.report_period.isoformat()}"
    )
    summary = (
        f"总分: {scorecard.total_score:.2f} | "
        f"评级: {scorecard.rating} | "
        f"红线: {'是' if scorecard.red_flag else '否'}"
    )

    focus_questions = _normalize_items(scorecard.focus_questions)

    body: list[str] = [header, summary]
    focus_question_lines = _render_numbered_lines("关注问题", focus_questions)
    if focus_question_lines:
        body.extend(["", *focus_question_lines])

    dimension_lines = ["维度得分"]
    for dimension in scorecard.dimension_scores:
        dimension_lines.append(
            f"- {_format_dimension_name(dimension.dimension)}: "
            f"{dimension.score:.2f}/{dimension.weight:.2f}"
        )

    body.extend(["", *dimension_lines])

    strengths = _normalize_items(scorecard.strengths)
    risks = _normalize_items(scorecard.risks)
    warnings = _normalize_items(scorecard.warnings)
    missing_metrics = _sort_missing_metrics(scorecard.missing_metrics)

    for title, values in (
        ("优势", strengths),
        ("风险", risks),
        ("警告", warnings),
        ("缺失指标", missing_metrics),
    ):
        section_lines = _render_lines(title, values)
        if section_lines:
            body.extend(["", *section_lines])

    if scorecard.combined_comment:
        body.extend(["", "综合说明", f"- {scorecard.combined_comment}"])

    return "\n".join(line for line in body if line is not None).strip()
