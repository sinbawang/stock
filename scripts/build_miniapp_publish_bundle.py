from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from chanlun.analysis import (
    build_precision_window_display,
    build_signal_explanation_lines,
    describe_structure_status,
    format_signal_point_labels,
    format_structure_status_label,
)
from chanlun.models import Bi, BiDirection
from chanlun.segment import identify_segments
from storage_layout import REPORTS_DIR, REPORTS_META_DIR, holdings_file


DEFAULT_HOLDINGS_FILE = holdings_file()
DEFAULT_REPORTS_ROOT = REPORTS_DIR
DEFAULT_PUBLISH_ROOT = ROOT / "build" / "miniapp-publish"
PRIMARY_TECHNICAL_TIMEFRAME = "30m"
PRIMARY_TECHNICAL_LABEL = "30M"
DETAIL_TECHNICAL_TIMEFRAMES = ("day", "30m", "5m", "1m")
TIMEFRAME_LABELS = {
    "day": "DAY",
    "60m": "60M",
    "30m": "30M",
    "15m": "15M",
    "5m": "5M",
    "1m": "1M",
}


@dataclass(frozen=True)
class Holding:
    symbol: str
    name: str
    market: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a miniapp-native publish bundle from canonical reports.")
    parser.add_argument("--holdings-file", default=str(DEFAULT_HOLDINGS_FILE), help="Combined holdings JSON file")
    parser.add_argument("--reports-root", default=str(DEFAULT_REPORTS_ROOT), help="Canonical reports root")
    parser.add_argument("--publish-root", default=str(DEFAULT_PUBLISH_ROOT), help="Publish bundle root")
    parser.add_argument("--snapshot-stamp", default=None, help="Optional explicit snapshot stamp such as 20260530_210500")
    parser.add_argument("--latest-only", action="store_true", help="Only write the latest bundle and skip snapshots/<stamp>")
    parser.add_argument(
        "--publish-timeframes",
        nargs="+",
        choices=("day", "60m", "30m", "15m", "5m", "1m"),
        default=None,
        help="Optional chart timeframes to include in the publish bundle. Defaults to all available chart assets.",
    )
    return parser.parse_args()


def load_holdings(path: Path) -> list[Holding]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    markets = payload.get("markets") or {}
    holdings: list[Holding] = []
    for market in ("CN", "HK"):
        for item in markets.get(market, []):
            if not isinstance(item, dict):
                continue
            symbol = str(item.get("symbol") or "").strip()
            if not symbol:
                continue
            normalized = symbol.zfill(5) if market == "HK" else symbol.zfill(6)
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            holdings.append(Holding(symbol=normalized, name=name, market=market))
    return holdings


def latest_file(directory: Path, pattern: str) -> Path | None:
    matches = list(directory.glob(pattern))
    if not matches:
        return None
    return max(matches, key=lambda item: item.stat().st_mtime)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_section_lines(text: str, title: str) -> list[str]:
    pattern = rf"^{re.escape(title)}\s*\n(?P<body>.*?)(?=\n(?:[\u4e00-\u9fffA-Za-z0-9_ /]+[:：]|##\s)|\Z)"
    match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
    if not match:
        return []
    lines: list[str] = []
    for line in match.group("body").splitlines():
        line = line.strip()
        if line.startswith("- "):
            lines.append(line[2:])
    return lines


def safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def chart_publish_path(charts: list[dict[str, str]], timeframe: str) -> str | None:
    for chart in charts:
        if chart.get("timeframe") == timeframe:
            return chart.get("relative_path")
    return None


def maybe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def priority_rank(priority: str | None) -> int:
    mapping = {"P1": 1, "P2": 2, "P3": 3, "P4": 4, "P5": 5}
    return mapping.get((priority or "").strip(), 99)


def bias_rank(bias: str | None) -> int:
    mapping = {"偏多": 1, "偏强": 2, "震荡": 3, "偏弱": 4, "偏空": 5}
    return mapping.get((bias or "").strip(), 9)


def technical_sort_key(item: dict[str, Any]) -> tuple[int, int, int, str, str]:
    technical_payload = item.get("cards", {}).get("technical", {}) if item.get("cards") else item.get("technical", {})
    technical = technical_payload if isinstance(technical_payload, dict) else {}
    score = technical.get("score") if technical else item.get("technical_score")
    try:
        numeric_score = int(score)
    except (TypeError, ValueError):
        numeric_score = -1
    return (
        priority_rank(item.get("priority")),
        -numeric_score,
        bias_rank(technical.get("bias") if technical else item.get("technical_bias")),
        safe_text(item.get("updated_at")),
        safe_text(item.get("symbol")),
    )


def build_portfolio_item(summary_payload: dict[str, Any], group_item: dict[str, Any] | None = None) -> dict[str, Any]:
    technical = ((summary_payload.get("cards") or {}).get("technical") or {})
    fundamental = ((summary_payload.get("cards") or {}).get("fundamental") or {})
    capital_flow = ((summary_payload.get("cards") or {}).get("capital_flow") or {})
    return {
        "priority": (group_item or {}).get("priority") or summary_payload.get("priority"),
        "action": (group_item or {}).get("action") or summary_payload.get("action"),
        "symbol": summary_payload.get("symbol"),
        "name": summary_payload.get("name"),
        "market": summary_payload.get("market"),
        "bucket": (group_item or {}).get("bucket") or summary_payload.get("bucket"),
        "fundamental": f"{safe_text(fundamental.get('score'), 'missing')}/{safe_text(fundamental.get('rating'), 'missing')}",
        "technical": safe_text(technical.get("conclusion"), "missing"),
        "capital_flow": f"{safe_text(capital_flow.get('score'), 'missing')}/{safe_text(capital_flow.get('rating'), 'missing')}/{safe_text(capital_flow.get('source'), 'missing')}",
        "comment": (group_item or {}).get("comment") or summary_payload.get("comment"),
        "updated_at": summary_payload.get("updated_at"),
        "summary": f"stocks/{summary_payload['symbol']}/summary.json",
        "detail": f"stocks/{summary_payload['symbol']}/detail.json",
        "cover_chart": (summary_payload.get("cover_chart") or {}).get("path"),
        "technical_score": technical.get("score"),
        "technical_rating": technical.get("rating"),
        "technical_bias": technical.get("bias"),
        "technical_score_breakdown": technical.get("score_breakdown") or {},
        "tags": summary_payload.get("tags") or [],
    }


def parse_markdown_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_combined_group_file(path: Path, group_key: str) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    generated_at = ""
    counts: dict[str, int] = {"today_action": 0, "watch_pool": 0, "risk_pool": 0}
    notes: list[str] = []
    sections: list[dict[str, Any]] = []
    current_section: dict[str, Any] | None = None
    in_notes = False

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("Generated at:"):
            generated_at = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("清单分布:"):
            payload = stripped.split(":", 1)[1].strip()
            for part in payload.split(","):
                key, _, value = part.strip().partition("=")
                normalized = {
                    "今日动作": "today_action",
                    "观察池": "watch_pool",
                    "风险池": "risk_pool",
                }.get(key.strip())
                if normalized:
                    try:
                        counts[normalized] = int(value.strip())
                    except ValueError:
                        counts[normalized] = 0
        elif stripped.startswith("### "):
            mapping = {
                "今日动作": "today_action",
                "观察池": "watch_pool",
                "风险池": "risk_pool",
            }
            title = stripped[4:].strip()
            current_section = {"key": mapping.get(title, title), "title": title, "items": []}
            sections.append(current_section)
            in_notes = False
        elif stripped == "## 口径说明":
            in_notes = True
            current_section = None
        elif in_notes and stripped.startswith("- "):
            notes.append(stripped[2:])
        elif current_section and stripped.startswith("| P"):
            cells = parse_markdown_table_row(stripped)
            if len(cells) >= 9:
                current_section["items"].append(
                    {
                        "priority": cells[0],
                        "action": cells[1],
                        "symbol": cells[2].zfill(5) if len(cells[2]) == 5 else cells[2].zfill(6),
                        "name": cells[3],
                        "bucket": cells[4],
                        "fundamental": cells[5],
                        "technical": cells[6],
                        "capital_flow": cells[7],
                        "comment": cells[8],
                    }
                )

    return {
        "schema_version": "v1",
        "group": group_key,
        "generated_at": generated_at,
        "counts": counts,
        "sections": sections,
        "notes": notes,
        "source_file": path.name,
    }


def load_group_payloads(meta_dir: Path) -> dict[str, dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    file_map = {
        "a_share": latest_file(meta_dir, "group_a_share_combined_overview_*.txt"),
        "h_share": latest_file(meta_dir, "group_h_share_combined_overview_*.txt"),
    }
    for group_key, path in file_map.items():
        if path is not None:
            payloads[group_key] = parse_combined_group_file(path, group_key)
    return payloads


def collect_group_item_map(group_payloads: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    item_map: dict[str, dict[str, Any]] = {}
    for payload in group_payloads.values():
        for section in payload.get("sections", []):
            for item in section.get("items", []):
                item_map[item["symbol"]] = item
    return item_map


def first_non_empty(*values: Any) -> str:
    for value in values:
        text = safe_text(value)
        if text:
            return text
    return ""


def trend_type_label(value: Any) -> str:
    mapping = {
        "up": "上涨",
        "down": "下跌",
        "range": "盘整",
        "consolidation": "盘整",
    }
    return mapping.get(safe_text(value).lower(), safe_text(value))


def signal_point_label(value: Any) -> str:
    labels = format_signal_point_labels([value] if value else [])
    return labels[0] if labels else safe_text(value)


def infer_structure_status(structure_state: dict[str, Any], current: dict[str, Any], relationship: dict[str, Any]) -> str:
    explicit = safe_text(structure_state.get("current_structure_status"))
    if explicit:
        return explicit

    relationship_kind = safe_text(relationship.get("kind"))
    if relationship_kind == "same_type_extension":
        return "ongoing_same_type"
    if relationship_kind == "completed_then_new_type_ongoing":
        return "completed_then_new_type"
    if safe_text(current.get("type")) == "range":
        return "ongoing_same_type"
    return "ongoing_same_type"


def normalize_signal_point(signal: dict[str, Any] | None) -> dict[str, Any] | None:
    if not signal:
        return None
    point = safe_text(signal.get("point"))
    return {
        "point": point,
        "label": signal_point_label(point),
        "time": signal.get("time"),
        "price": maybe_float(signal.get("price")),
        "active": bool(signal.get("active", True)),
        "basis": signal.get("basis"),
    }


def build_same_level_debug_context(tech_payload: dict[str, Any]) -> dict[str, Any]:
    structure = tech_payload.get("structure") or {}
    latest_raw = structure.get("latest_zhongshu") or {}
    zhongshus = structure.get("zhongshus") or []
    latest_zs_id = latest_raw.get("zs_id")

    reabsorbed_predecessor = None
    if latest_zs_id is not None:
        reabsorbed_predecessor = next(
            (
                item
                for item in reversed(zhongshus)
                if item.get("superseded_by_zs_id") == latest_zs_id and item.get("is_reabsorbed_by_larger_expansion") is True
            ),
            None,
        )

    latest_debug = None
    if latest_raw:
        latest_debug = {
            "zs_id": latest_raw.get("zs_id"),
            "entering_bi_id": latest_raw.get("entering_bi_id"),
            "exit_bi_id": latest_raw.get("exit_bi_id"),
            "is_terminated": latest_raw.get("is_terminated"),
            "superseded_by_zs_id": latest_raw.get("superseded_by_zs_id"),
            "is_reabsorbed_by_larger_expansion": latest_raw.get("is_reabsorbed_by_larger_expansion"),
        }

    predecessor_debug = None
    if reabsorbed_predecessor:
        predecessor_debug = {
            "zs_id": reabsorbed_predecessor.get("zs_id"),
            "entering_bi_id": reabsorbed_predecessor.get("entering_bi_id"),
            "exit_bi_id": reabsorbed_predecessor.get("exit_bi_id"),
            "is_terminated": reabsorbed_predecessor.get("is_terminated"),
            "superseded_by_zs_id": reabsorbed_predecessor.get("superseded_by_zs_id"),
            "is_reabsorbed_by_larger_expansion": reabsorbed_predecessor.get("is_reabsorbed_by_larger_expansion"),
        }

    return {
        "auto_reabsorption_detected": predecessor_debug is not None,
        "latest_zhongshu": latest_debug,
        "reabsorbed_predecessor": predecessor_debug,
    }


def build_reabsorption_focus_line(debug_context: dict[str, Any]) -> str:
    if not debug_context.get("auto_reabsorption_detected"):
        return ""
    latest = debug_context.get("latest_zhongshu") or {}
    predecessor = debug_context.get("reabsorbed_predecessor") or {}
    if not latest or not predecessor:
        return ""
    return (
        f"重写说明：前一中枢 ZS{predecessor.get('zs_id')} 的走出笔 {predecessor.get('exit_bi_id')} "
        f"被当前中枢 ZS{latest.get('zs_id')} 复用为进入笔 {latest.get('entering_bi_id')}，"
        "当前按更大级别扩展吸收处理。"
    )


def build_same_level_decomposition(tech_payload: dict[str, Any]) -> dict[str, Any]:
    summary = tech_payload.get("summary") or {}
    structure_state = summary.get("structure_state") or tech_payload.get("structure_state") or {}
    previous_raw = structure_state.get("last_completed") or {}
    current_raw = structure_state.get("current_ongoing") or {}
    relationship = structure_state.get("relationship") or {}

    previous = {
        "type": previous_raw.get("type"),
        "type_label": trend_type_label(previous_raw.get("type")),
        "start_ts": previous_raw.get("start_ts"),
        "end_ts": previous_raw.get("end_ts"),
        "zs_count": previous_raw.get("zs_count"),
        "status": previous_raw.get("status"),
    }
    current = {
        "type": current_raw.get("type"),
        "type_label": trend_type_label(current_raw.get("type")),
        "start_ts": current_raw.get("start_ts"),
        "latest_ts": current_raw.get("latest_ts"),
        "zs_count": current_raw.get("zs_count") or current_raw.get("zs_count_so_far"),
        "status": current_raw.get("status"),
    }
    current_structure_status = infer_structure_status(structure_state, current, relationship)
    current_structure_status_note = describe_structure_status(current_structure_status)
    debug_context = build_same_level_debug_context(tech_payload)
    summary_note = "当前同级别走势输出为工程结构摘要，非严格递归分解后的最终理论标签。"
    same_type_extension = (
        relationship.get("kind") == "same_type_extension"
        and previous.get("type")
        and previous.get("type") == current.get("type")
    )

    lines: list[str] = []
    if previous.get("type"):
        lines.append(
            (
                f"前段已确认同型片段：{previous['type_label']} {safe_text(previous.get('start_ts'))} -> {safe_text(previous.get('end_ts'))}"
                if same_type_extension
                else f"上个已完成走势：{previous['type_label']} {safe_text(previous.get('start_ts'))} -> {safe_text(previous.get('end_ts'))}"
            )
        )
    if current.get("type"):
        lines.append(
            f"当前进行走势：{current['type_label']} 自 {safe_text(current.get('start_ts'))} 起，最新 {safe_text(current.get('latest_ts'))}"
        )
    note = safe_text(relationship.get("note"))
    if note:
        lines.append(f"走势连接：{note}")
    if current_structure_status_note:
        lines.append(f"切分状态：{current_structure_status_note}")
    reabsorption_line = build_reabsorption_focus_line(debug_context)
    if reabsorption_line:
        lines.append(reabsorption_line)
    lines.append(f"口径说明：{summary_note}")

    return {
        "mode": "engineering_summary",
        "is_strict_theory_equivalent": False,
        "summary_note": summary_note,
        "current_structure_status": current_structure_status,
        "current_structure_status_label": format_structure_status_label(current_structure_status),
        "current_structure_status_note": current_structure_status_note,
        "debug_context": debug_context,
        "previous": previous,
        "current": current,
        "relationship": relationship,
        "lines": lines,
    }


def build_latest_signal_summary(tech_payload: dict[str, Any]) -> dict[str, Any]:
    summary = tech_payload.get("summary") or {}
    active_signals = [normalize_signal_point(item) for item in (summary.get("signal_points") or [])]
    catalog_signals = [normalize_signal_point(item) for item in (summary.get("signal_catalog") or []) if item.get("active")]
    merged = [item for item in active_signals + catalog_signals if item and item.get("point")]

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in merged:
        key = (safe_text(item.get("point")), safe_text(item.get("time")), safe_text(item.get("price")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    deduped.sort(key=lambda item: safe_text(item.get("time")), reverse=True)
    latest_buy = next((item for item in deduped if safe_text(item.get("point")).startswith("buy")), None)
    latest_sell = next((item for item in deduped if safe_text(item.get("point")).startswith("sell")), None)
    latest_overall = deduped[0] if deduped else None

    lines: list[str] = []
    if latest_buy:
        buy_price = f"，价格 {latest_buy['price']:.2f}" if latest_buy.get("price") is not None else ""
        lines.append(f"最近买点：{latest_buy['label']} {safe_text(latest_buy.get('time'))}{buy_price}")
    if latest_sell:
        sell_price = f"，价格 {latest_sell['price']:.2f}" if latest_sell.get("price") is not None else ""
        lines.append(f"最近卖点：{latest_sell['label']} {safe_text(latest_sell.get('time'))}{sell_price}")

    return {
        "latest_buy": latest_buy,
        "latest_sell": latest_sell,
        "latest_overall": latest_overall,
        "recent_active": deduped[:3],
        "lines": lines,
    }


def build_technical_focus_lines(decomposition: dict[str, Any], signal_summary: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    lines.extend(decomposition.get("lines") or [])
    lines.extend(signal_summary.get("lines") or [])
    return lines


def build_fundamental_section(base_payload: dict[str, Any]) -> dict[str, Any]:
    summary = base_payload.get("summary") or {}
    blended = base_payload.get("blended") or {}
    annual_anchor = blended.get("annual_anchor") or {}
    scorecard = annual_anchor.get("scorecard") or {}
    snapshot = annual_anchor.get("snapshot") or {}
    return {
        "key": "fundamental",
        "title": "基本面",
        "rating": summary.get("rating"),
        "score": summary.get("score"),
        "submodel": summary.get("submodel"),
        "report_period": snapshot.get("report_period"),
        "summary": first_non_empty(scorecard.get("combined_comment"), summary.get("comment")),
        "highlights": (scorecard.get("strengths") or [])[:3],
        "risks": (scorecard.get("risks") or [])[:3],
        "follow_ups": (scorecard.get("focus_questions") or [])[:3],
        "warnings": (scorecard.get("warnings") or [])[:3],
    }


def build_capital_flow_section(fund_payload: dict[str, Any]) -> dict[str, Any]:
    summary = fund_payload.get("summary") or {}
    scorecard = fund_payload.get("scorecard") or {}
    snapshot = fund_payload.get("snapshot") or {}
    metrics: list[dict[str, str]] = []
    label_map = [
        ("main_net_inflow", "主力净流入"),
        ("main_net_inflow_5d", "5日主力净流入"),
        ("southbound_net_buy", "南向净买入"),
        ("southbound_holding_change", "南向持股变化"),
        ("short_sell_ratio", "沽空比例"),
    ]
    for key, label in label_map:
        value = snapshot.get(key)
        if value is not None:
            metrics.append({"label": label, "value": str(value)})
    return {
        "key": "capital_flow",
        "title": "资金面",
        "rating": summary.get("rating"),
        "score": summary.get("score"),
        "source": summary.get("source"),
        "trade_date": scorecard.get("trade_date"),
        "summary": first_non_empty(summary.get("comment"), scorecard.get("combined_comment")),
        "strengths": (scorecard.get("strengths") or [])[:3],
        "risks": (scorecard.get("risks") or [])[:3],
        "warnings": (scorecard.get("warnings") or [])[:3],
        "metrics": metrics[:5],
    }
def build_technical_section(tech_payload: dict[str, Any]) -> dict[str, Any]:
    summary = tech_payload.get("summary") or {}
    analysis_text = safe_text(tech_payload.get("analysis_text"))
    precision_entry = summary.get("precision_entry") or tech_payload.get("precision_entry") or {}
    precision_window_display = build_precision_window_display(precision_entry)
    same_level_decomposition = build_same_level_decomposition(tech_payload)
    latest_signal_summary = build_latest_signal_summary(tech_payload)
    signal_context = {
        "signal_points": summary.get("signal_points") or [],
        "signal_catalog": summary.get("signal_catalog") or [],
    }
    return {
        "key": "technical",
        "title": "技术面",
        "timeframe": tech_payload.get("timeframe") or PRIMARY_TECHNICAL_TIMEFRAME,
        "source": tech_payload.get("source"),
        "operation_level": summary.get("operation_level"),
        "score": summary.get("score"),
        "rating": summary.get("rating"),
        "bias": summary.get("bias"),
        "score_breakdown": summary.get("score_breakdown") or {},
        "conclusion": summary.get("conclusion"),
        "suggestion": summary.get("suggestion"),
        "buy_points": summary.get("buy_points") or [],
        "buy_point_labels": format_signal_point_labels(summary.get("buy_points") or []),
        "sell_points": summary.get("sell_points") or [],
        "sell_point_labels": format_signal_point_labels(summary.get("sell_points") or []),
        "signal_points": summary.get("signal_points") or [],
        "signal_catalog": summary.get("signal_catalog") or [],
        "signal_descriptions": build_signal_explanation_lines(signal_context),
        "same_level_decomposition": same_level_decomposition,
        "latest_signal_summary": latest_signal_summary,
        "technical_focus_lines": build_technical_focus_lines(same_level_decomposition, latest_signal_summary),
        "precision_entry": precision_entry,
        "precision_note": precision_entry.get("note"),
        "precision_window_basis_label": precision_entry.get("window_basis_label") or (precision_entry.get("nested_from") or {}).get("window_basis_label"),
        "precision_window_basis_description": precision_entry.get("window_basis_description") or (precision_entry.get("nested_from") or {}).get("window_basis_description"),
        "precision_window_display": precision_window_display,
        "precision_signal_descriptions": precision_entry.get("signal_descriptions") or [],
        "overview": extract_section_lines(analysis_text, "概览：")[:4],
        "structure": extract_section_lines(analysis_text, "结构：")[:4],
        "signals": extract_section_lines(analysis_text, "信号：")[:4],
        "focus": extract_section_lines(analysis_text, "观察重点：")[:2],
    }


def build_timeframe_technical_sections(stock_dir: Path, timeframes: tuple[str, ...]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for timeframe in timeframes:
        tech_path = stock_dir / timeframe / "tech.json"
        if not tech_path.exists():
            continue
        section = build_technical_section(read_json(tech_path))
        label = TIMEFRAME_LABELS.get(timeframe, timeframe.upper())
        section["key"] = "technical" if timeframe == PRIMARY_TECHNICAL_TIMEFRAME else f"technical_{timeframe}"
        section["title"] = f"{label} 技术面"
        section["timeframe"] = timeframe
        section["operation_level"] = section.get("operation_level") or label
        sections.append(section)
    return sections


def build_chart_specs(stock_dir: Path, publish_timeframes: tuple[str, ...] | None = None) -> list[dict[str, str]]:
    charts: list[dict[str, str]] = []
    timeframe_order = publish_timeframes or ("30m", "5m", "1m", "day")
    for timeframe in timeframe_order:
        for extension in ("svg", "jpg", "png"):
            chart_path = stock_dir / timeframe / f"structure.{extension}"
            if not chart_path.exists():
                continue
            chart_spec = {
                "timeframe": timeframe,
                "source_path": str(chart_path),
                "relative_path": f"charts/{timeframe}.{extension}",
                "label": f"{timeframe.upper()} 结构图",
            }
            data_source_path = find_latest_chart_bars_csv(stock_dir / timeframe, timeframe)
            if data_source_path:
                chart_spec["data_source_path"] = str(data_source_path)
                chart_spec["data_relative_path"] = f"charts/{timeframe}.json"
            charts.append(chart_spec)
            break
    return charts


def find_latest_chart_bars_csv(timeframe_dir: Path, timeframe: str) -> Path | None:
    analyze_dir = timeframe_dir / "analyze"
    if not analyze_dir.exists():
        return None

    candidates = [
        path
        for path in analyze_dir.glob(f"*_{timeframe}_*.csv")
        if "_normalized" not in path.stem
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def parse_csv_value(value: Any) -> Any:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    if text in ("True", "true"):
        return True
    if text in ("False", "false"):
        return False
    if re.fullmatch(r"[-+]?\d+", text):
        try:
            return int(text)
        except ValueError:
            return text
    if re.fullmatch(r"[-+]?(?:\d+\.\d*|\d*\.\d+)(?:[eE][-+]?\d+)?", text) or re.fullmatch(r"[-+]?\d+[eE][-+]?\d+", text):
        try:
            return float(text)
        except ValueError:
            return text
    return text


def read_csv_records(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [
            {key: parse_csv_value(value) for key, value in row.items()}
            for row in reader
        ]


def parse_report_datetime(value: Any) -> datetime:
    text = safe_text(value)
    if not text:
        raise ValueError("empty datetime value")
    return datetime.fromisoformat(text)


def build_bis_from_records(records: list[dict[str, Any]]) -> list[Bi]:
    bis: list[Bi] = []
    for record in records:
        direction = safe_text(record.get("direction"))
        if not direction:
            continue
        bis.append(
            Bi(
                bi_id=int(record.get("bi_id") or 0),
                direction=BiDirection(direction),
                start_fx_id=int(record.get("start_fx_id") or 0),
                end_fx_id=int(record.get("end_fx_id") or 0),
                start_ts=parse_report_datetime(record.get("start_ts")),
                end_ts=parse_report_datetime(record.get("end_ts")),
                high=float(record.get("high") or 0.0),
                low=float(record.get("low") or 0.0),
                norm_bar_range=(int(record.get("start_norm_idx") or 0), int(record.get("end_norm_idx") or 0)),
                is_confirmed=bool(record.get("is_confirmed")),
            )
        )
    return bis


def serialize_segment_record(segment: Any) -> dict[str, Any]:
    return {
        "segment_id": segment.segment_id,
        "direction": segment.direction.value,
        "start_bi_id": segment.start_bi_id,
        "end_bi_id": segment.end_bi_id,
        "start_ts": segment.start_ts.strftime("%Y-%m-%d %H:%M"),
        "end_ts": segment.end_ts.strftime("%Y-%m-%d %H:%M"),
        "start_price": segment.start_price,
        "end_price": segment.end_price,
        "high": segment.high,
        "low": segment.low,
        "start_norm_idx": segment.norm_bar_range[0],
        "end_norm_idx": segment.norm_bar_range[1],
        "bi_ids": ",".join(str(bi_id) for bi_id in segment.bi_ids),
        "last_same_extreme": segment.last_same_extreme,
        "last_reverse_extreme": segment.last_reverse_extreme,
        "break_bi_id": segment.break_bi_id,
        "stop_reason": segment.stop_reason,
        "is_confirmed": segment.is_confirmed,
        "status": "confirmed" if segment.is_confirmed else "preprocessing",
        "note": "auto_generated",
    }


def build_segment_records(bis_records: list[dict[str, Any]], segment_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if segment_records:
        return segment_records
    bis = build_bis_from_records(bis_records)
    if not bis:
        return []
    return [serialize_segment_record(segment) for segment in identify_segments(bis)]


def sibling_analysis_csv(bars_csv: Path, suffix: str) -> Path:
    return bars_csv.with_name(f"{bars_csv.stem}{suffix}.csv")


def build_chart_data_payload(chart_spec: dict[str, str]) -> dict[str, Any] | None:
    source_value = chart_spec.get("data_source_path")
    if not source_value:
        return None

    bars_csv = Path(source_value)
    if not bars_csv.exists():
        return None

    return {
        "schema_version": "chart-data-v1",
        "timeframe": chart_spec.get("timeframe"),
        "label": chart_spec.get("label"),
        "source_csv": bars_csv.name,
        "bars": read_csv_records(bars_csv),
        "normalized_bars": read_csv_records(sibling_analysis_csv(bars_csv, "_normalized")),
        "macd": read_csv_records(sibling_analysis_csv(bars_csv, "_normalized_macd")),
        "fractals": read_csv_records(sibling_analysis_csv(bars_csv, "_normalized_fractals")),
        "confirmed_fractals": read_csv_records(sibling_analysis_csv(bars_csv, "_normalized_confirmed_fractals")),
        "bis": read_csv_records(sibling_analysis_csv(bars_csv, "_normalized_bis")),
        "segments": build_segment_records(
            read_csv_records(sibling_analysis_csv(bars_csv, "_normalized_bis")),
            read_csv_records(sibling_analysis_csv(bars_csv, "_normalized_segments")),
        ),
        "zhongshus": read_csv_records(sibling_analysis_csv(bars_csv, "_normalized_zhongshu")),
    }


def build_summary_payload(
    holding: Holding,
    stock_dir: Path,
    group_item: dict[str, Any] | None,
    publish_timeframes: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    base_payload = read_json(stock_dir / "base.json")
    fund_payload = read_json(stock_dir / "fund.json")
    tech_payload = read_json(stock_dir / PRIMARY_TECHNICAL_TIMEFRAME / "tech.json")
    base_summary = base_payload.get("summary") or {}
    fund_summary = fund_payload.get("summary") or {}
    tech_summary = tech_payload.get("summary") or {}
    precision_entry = tech_summary.get("precision_entry") or tech_payload.get("precision_entry") or {}
    precision_window_display = build_precision_window_display(precision_entry)
    same_level_decomposition = build_same_level_decomposition(tech_payload)
    latest_signal_summary = build_latest_signal_summary(tech_payload)
    charts = build_chart_specs(stock_dir, publish_timeframes=publish_timeframes)
    cover_chart_path = chart_publish_path(charts, PRIMARY_TECHNICAL_TIMEFRAME)
    updated_at = max(
        safe_text(base_payload.get("generated_at")),
        safe_text(fund_payload.get("generated_at")),
        safe_text(tech_payload.get("generated_at")),
    )
    return {
        "schema_version": "v1",
        "symbol": holding.symbol,
        "name": holding.name,
        "market": holding.market,
        "updated_at": updated_at,
        "priority": group_item.get("priority") if group_item else None,
        "action": group_item.get("action") if group_item else None,
        "bucket": group_item.get("bucket") if group_item else None,
        "comment": group_item.get("comment") if group_item else first_non_empty(fund_summary.get("comment"), fund_summary.get("summary")),
        "cards": {
            "fundamental": {
                "score": base_summary.get("score"),
                "rating": base_summary.get("rating"),
                "summary": first_non_empty(base_summary.get("comment"), (base_payload.get("blended") or {}).get("annual_anchor", {}).get("scorecard", {}).get("combined_comment")),
            },
            "technical": {
                "timeframe": tech_payload.get("timeframe") or PRIMARY_TECHNICAL_TIMEFRAME,
                "timeframe_label": PRIMARY_TECHNICAL_LABEL,
                "operation_level": tech_summary.get("operation_level"),
                "score": tech_summary.get("score"),
                "rating": tech_summary.get("rating"),
                "bias": tech_summary.get("bias"),
                "score_breakdown": tech_summary.get("score_breakdown") or {},
                "conclusion": tech_summary.get("conclusion"),
                "suggestion": tech_summary.get("suggestion"),
                "buy_points": tech_summary.get("buy_points") or [],
                "buy_point_labels": format_signal_point_labels(tech_summary.get("buy_points") or []),
                "sell_points": tech_summary.get("sell_points") or [],
                "sell_point_labels": format_signal_point_labels(tech_summary.get("sell_points") or []),
                "signal_points": tech_summary.get("signal_points") or [],
                "signal_catalog": tech_summary.get("signal_catalog") or [],
                "signal_descriptions": build_signal_explanation_lines(
                    {
                        "signal_points": tech_summary.get("signal_points") or [],
                        "signal_catalog": tech_summary.get("signal_catalog") or [],
                    }
                ),
                "same_level_decomposition": same_level_decomposition,
                "latest_signal_summary": latest_signal_summary,
                "technical_focus_lines": build_technical_focus_lines(same_level_decomposition, latest_signal_summary),
                "precision_entry": precision_entry,
                "precision_note": precision_entry.get("note"),
                "precision_window_basis_label": precision_entry.get("window_basis_label") or (precision_entry.get("nested_from") or {}).get("window_basis_label"),
                "precision_window_basis_description": precision_entry.get("window_basis_description") or (precision_entry.get("nested_from") or {}).get("window_basis_description"),
                "precision_window_display": precision_window_display,
            },
            "capital_flow": {
                "score": fund_summary.get("score"),
                "rating": fund_summary.get("rating"),
                "source": fund_summary.get("source"),
                "summary": first_non_empty(fund_summary.get("comment"), (fund_payload.get("scorecard") or {}).get("combined_comment")),
            },
        },
        "cover_chart": {"timeframe": PRIMARY_TECHNICAL_TIMEFRAME, "path": f"stocks/{holding.symbol}/{cover_chart_path}"} if cover_chart_path else None,
        "jump": {"detail": f"stocks/{holding.symbol}/detail.json"},
        "tags": [value for value in [group_item.get("bucket") if group_item else None, group_item.get("priority") if group_item else None, group_item.get("action") if group_item else None] if value],
    }


def build_detail_payload(
    holding: Holding,
    stock_dir: Path,
    group_item: dict[str, Any] | None,
    publish_timeframes: tuple[str, ...] | None = None,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    base_payload = read_json(stock_dir / "base.json")
    fund_payload = read_json(stock_dir / "fund.json")
    tech_payload = read_json(stock_dir / PRIMARY_TECHNICAL_TIMEFRAME / "tech.json")
    charts = build_chart_specs(stock_dir, publish_timeframes=publish_timeframes)
    fundamental = build_fundamental_section(base_payload)
    technical_sections = build_timeframe_technical_sections(stock_dir, DETAIL_TECHNICAL_TIMEFRAMES)
    technical = next((section for section in technical_sections if section.get("key") == "technical"), None) or build_technical_section(tech_payload)
    capital_flow = build_capital_flow_section(fund_payload)
    overview_bullets = [
        f"基本面 {safe_text(fundamental.get('score'), 'missing')}/{safe_text(fundamental.get('rating'), 'missing')}",
        f"{PRIMARY_TECHNICAL_LABEL} 技术面 {safe_text(technical.get('conclusion'), 'missing')}",
        f"资金面 {safe_text(capital_flow.get('score'), 'missing')}/{safe_text(capital_flow.get('rating'), 'missing')}",
    ]
    updated_at = max(
        safe_text(base_payload.get("generated_at")),
        safe_text(fund_payload.get("generated_at")),
        safe_text(tech_payload.get("generated_at")),
    )
    payload = {
        "schema_version": "v1",
        "symbol": holding.symbol,
        "name": holding.name,
        "market": holding.market,
        "updated_at": updated_at,
        "headline": {
            "title": f"{holding.name} {holding.symbol}",
            "subtitle": "三轴综合观察",
            "priority": group_item.get("priority") if group_item else None,
            "action": group_item.get("action") if group_item else None,
            "bucket": group_item.get("bucket") if group_item else None,
        },
        "overview": {
            "summary": group_item.get("comment") if group_item else first_non_empty(technical.get("conclusion"), fundamental.get("summary")),
            "bullets": overview_bullets,
        },
        "sections": [fundamental, *technical_sections, capital_flow],
        "charts": [
            {
                "timeframe": chart["timeframe"],
                "path": f"stocks/{holding.symbol}/{chart['relative_path']}",
                "data_path": f"stocks/{holding.symbol}/{chart['data_relative_path']}" if chart.get("data_relative_path") else None,
                "label": chart["label"],
            }
            for chart in charts
        ],
        "disclaimer": "本页面仅用于持仓跟踪与研究，不构成投资建议。",
    }
    return payload, charts


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def copy_optional_json_asset(source_path: Path, target_path: Path) -> None:
    if not source_path.exists():
        return
    payload = read_json(source_path)
    write_json(target_path, payload)


def copy_chart_assets(chart_specs: list[dict[str, str]], stock_target_dir: Path) -> None:
    for chart in chart_specs:
        source_path = Path(chart["source_path"])
        target_path = stock_target_dir / chart["relative_path"]
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        chart_data_payload = build_chart_data_payload(chart)
        if chart_data_payload and chart.get("data_relative_path"):
            write_json(stock_target_dir / chart["data_relative_path"], chart_data_payload)


def build_portfolio_group(summary_payloads: list[dict[str, Any]], group_item_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    items = [build_portfolio_item(summary_payload, group_item_map.get(str(summary_payload.get("symbol")))) for summary_payload in summary_payloads]
    items.sort(key=technical_sort_key)
    return {
        "schema_version": "v1",
        "group": "portfolio",
        "generated_at": max((payload.get("updated_at") or "") for payload in summary_payloads) if summary_payloads else "",
        "counts": {"items": len(items)},
        "sections": [{"key": "portfolio", "title": "全部持仓", "items": items}],
        "notes": ["由 A 股与港股组合概览合并生成，仅用于原生小程序展示。"],
    }


def build_index_payload(summary_payloads: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
    ordered = sorted(summary_payloads, key=technical_sort_key)
    return {
        "schema_version": "v1",
        "generated_at": generated_at,
        "source_root": "data/reports",
        "markets": ["CN", "HK"],
        "counts": {
            "stocks": len(summary_payloads),
            "cn": sum(1 for item in summary_payloads if item.get("market") == "CN"),
            "hk": sum(1 for item in summary_payloads if item.get("market") == "HK"),
        },
        "groups": {
            "portfolio": "groups/portfolio.json",
            "a_share": "groups/a_share.json",
            "h_share": "groups/h_share.json",
        },
        "stocks": [
            {
                "symbol": item["symbol"],
                "name": item["name"],
                "market": item["market"],
                "updated_at": item["updated_at"],
                "summary": f"stocks/{item['symbol']}/summary.json",
                "detail": f"stocks/{item['symbol']}/detail.json",
                "cover_chart": item.get("cover_chart", {}).get("path") if item.get("cover_chart") else None,
                "technical_score": ((item.get("cards") or {}).get("technical") or {}).get("score"),
                "technical_rating": ((item.get("cards") or {}).get("technical") or {}).get("rating"),
                "technical_bias": ((item.get("cards") or {}).get("technical") or {}).get("bias"),
                "tags": item.get("tags", []),
            }
            for item in ordered
        ],
    }


def ensure_clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def generate_bundle(
    holdings_path: Path,
    reports_root: Path,
    publish_root: Path,
    snapshot_stamp: str | None,
    latest_only: bool,
    publish_timeframes: tuple[str, ...] | None = None,
) -> dict[str, Path]:
    stamp = snapshot_stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    latest_dir = publish_root / "latest"
    snapshot_dir = publish_root / "snapshots" / stamp
    meta_dir = reports_root / "_meta"
    holdings = load_holdings(holdings_path)
    group_payloads = load_group_payloads(meta_dir)
    group_item_map = collect_group_item_map(group_payloads)

    targets = [latest_dir] if latest_only else [latest_dir, snapshot_dir]
    for target in targets:
        ensure_clean_dir(target)

    summary_payloads: list[dict[str, Any]] = []
    for holding in holdings:
        stock_dir = reports_root / holding.symbol
        if not stock_dir.exists():
            continue
        base_source_path = stock_dir / "base.json"
        summary_payload = build_summary_payload(holding, stock_dir, group_item_map.get(holding.symbol), publish_timeframes=publish_timeframes)
        detail_payload, chart_specs = build_detail_payload(holding, stock_dir, group_item_map.get(holding.symbol), publish_timeframes=publish_timeframes)
        summary_payloads.append(summary_payload)
        for target in targets:
            stock_target_dir = target / "stocks" / holding.symbol
            copy_optional_json_asset(base_source_path, stock_target_dir / "base.json")
            write_json(stock_target_dir / "summary.json", summary_payload)
            write_json(stock_target_dir / "detail.json", detail_payload)
            copy_chart_assets(chart_specs, stock_target_dir)

    portfolio_payload = build_portfolio_group(summary_payloads, group_item_map)
    generated_at = datetime.now().isoformat(timespec="seconds")
    index_payload = build_index_payload(summary_payloads, generated_at)
    for target in targets:
        write_json(target / "index.json", index_payload)
        if "a_share" in group_payloads:
            write_json(target / "groups" / "a_share.json", group_payloads["a_share"])
        if "h_share" in group_payloads:
            write_json(target / "groups" / "h_share.json", group_payloads["h_share"])
        write_json(target / "groups" / "portfolio.json", portfolio_payload)
    return {"latest": latest_dir, "snapshot": snapshot_dir}


def main() -> None:
    args = parse_args()
    outputs = generate_bundle(
        holdings_path=Path(args.holdings_file),
        reports_root=Path(args.reports_root),
        publish_root=Path(args.publish_root),
        snapshot_stamp=args.snapshot_stamp,
        latest_only=args.latest_only,
        publish_timeframes=tuple(args.publish_timeframes) if args.publish_timeframes else None,
    )
    print(f"latest= {outputs['latest']}")
    if not args.latest_only:
        print(f"snapshot= {outputs['snapshot']}")


if __name__ == "__main__":
    main()