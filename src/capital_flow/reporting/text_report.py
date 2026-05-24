"""Render capital-flow scorecards into readable text."""

from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from capital_flow.models.scorecard import CapitalFlowScoreCard
from capital_flow.models.snapshot import CapitalFlowSnapshot


DIMENSION_LABELS = {
    "flow_direction": "资金方向",
    "flow_persistence": "资金持续性",
    "volume_confirmation": "量能确认",
    "institutional_hint": "通道与机构线索",
    "overheat_risk": "过热风险",
}


METRIC_DISPLAY_NAMES = {
    "turnover": "成交额",
    "turnover_rate": "换手率",
    "volume_ratio": "量比",
    "amount_ratio_5d": "成交额/5日均值",
    "main_net_inflow": "主力净流入",
    "main_net_inflow_3d": "3日主力净流入",
    "main_net_inflow_5d": "5日主力净流入",
    "main_net_inflow_10d": "10日主力净流入",
    "southbound_net_buy": "南向净买入",
    "southbound_holding_change": "南向持股变化",
    "northbound_holding_change": "北向持股变化",
    "margin_balance_change": "融资余额变化",
    "short_sell_ratio": "沽空比例",
    "short_sell_turnover": "沽空成交额",
}


def _dimension_label(name: str) -> str:
    return DIMENSION_LABELS.get(name, name)


def _metric_label(name: str) -> str:
    return METRIC_DISPLAY_NAMES.get(name, name)


def _format_value(value: Optional[float]) -> str:
    if value is None:
        return "缺失"
    return format(value, ".12g")


def _render_snapshot_lines(snapshot: Optional[CapitalFlowSnapshot]) -> list[str]:
    if snapshot is None:
        return []
    fields = (
        "turnover",
        "turnover_rate",
        "volume_ratio",
        "amount_ratio_5d",
        "main_net_inflow",
        "main_net_inflow_5d",
        "southbound_net_buy",
        "southbound_holding_change",
        "northbound_holding_change",
        "margin_balance_change",
        "short_sell_ratio",
        "short_sell_turnover",
    )
    lines = ["关键资金指标:"]
    for field_name in fields:
        value = getattr(snapshot, field_name, None)
        if value is not None:
            lines.append(f"- {_metric_label(field_name)}: {_format_value(value)}")
    if len(lines) == 1:
        return []
    return lines


def _render_snapshot_source_lines(snapshot: Optional[CapitalFlowSnapshot]) -> list[str]:
    if snapshot is None:
        return []
    lines = [f"- 数据源: {snapshot.source}"]
    if snapshot.raw_payload_ref:
        lines.append(f"- 原始引用: {snapshot.raw_payload_ref}")
    if snapshot.notes:
        lines.append(f"- 口径说明: {snapshot.notes}")
    return lines

def render_capital_flow_text(
    scorecard: CapitalFlowScoreCard,
    snapshot: Optional[CapitalFlowSnapshot] = None,
) -> str:
    """Render a capital-flow scorecard as plain text."""

    lines = [
        f"# 资金面评分卡: {scorecard.symbol} {scorecard.name}",
        "",
        f"- 市场: {scorecard.market}",
        f"- 交易日: {scorecard.trade_date.isoformat()}",
        f"- 总分: {scorecard.total_score:.1f}/100",
        f"- 评级: {scorecard.rating}",
        f"- 红线: {'是' if scorecard.red_flag else '否'}",
    ]
    lines.extend(_render_snapshot_source_lines(snapshot))
    lines.append("")

    snapshot_lines = _render_snapshot_lines(snapshot)
    if snapshot_lines:
        lines.extend(snapshot_lines)
        lines.append("")

    lines.append("维度得分:")
    for item in scorecard.dimension_scores:
        lines.append(
            f"- {_dimension_label(item.dimension)}: {item.score:.1f}/{item.max_score:.0f}"
            + (f" ({item.score_basis})" if item.score_basis else "")
        )
    lines.append("")

    if scorecard.strengths:
        lines.append("正向线索:")
        lines.extend(f"- {value}" for value in scorecard.strengths)
        lines.append("")
    if scorecard.risks:
        lines.append("风险线索:")
        lines.extend(f"- {value}" for value in scorecard.risks)
        lines.append("")
    if scorecard.warnings:
        lines.append("口径提示:")
        lines.extend(f"- {value}" for value in scorecard.warnings)
        lines.append("")
    if scorecard.missing_metrics:
        lines.append("缺失指标:")
        lines.extend(f"- {_metric_label(value)}" for value in scorecard.missing_metrics)
        lines.append("")
    if scorecard.combined_comment:
        lines.append("综合判断:")
        lines.append(scorecard.combined_comment)
        lines.append("")
    lines.append(f"Generated at: {datetime.now().isoformat(timespec='seconds')}")
    return "\n".join(lines)


def save_capital_flow_text(
    scorecard: CapitalFlowScoreCard,
    snapshot: Optional[CapitalFlowSnapshot] = None,
    output_dir: Union[str, Path] = Path("data") / "_meta",
) -> Path:
    """Save a capital-flow text report and return its path."""

    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = (
        f"{scorecard.symbol}_{scorecard.name}_capital_flow_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    )
    path = target_dir / filename
    path.write_text(render_capital_flow_text(scorecard, snapshot), encoding="utf-8")
    return path