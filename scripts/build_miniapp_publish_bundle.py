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
    describe_consumption_level,
    describe_transition_state,
    describe_structure_status,
    format_signal_point_labels,
    format_consumption_level_label,
    format_structure_status_label,
    format_transition_state_label,
)
from chanlun.models import Bi, BiDirection
from chanlun.segment import (
    build_segment_tail_interpretations,
    classify_stop_reason,
    describe_stop_reason,
    identify_segments,
    is_fallback_confirmed_stop_reason,
    is_pending_stop_reason,
    is_theory_confirmed_stop_reason,
    summarize_stop_reason_outcome,
)
from storage_layout import REPORTS_DIR, REPORTS_META_DIR, holdings_file


DEFAULT_HOLDINGS_FILE = holdings_file()
DEFAULT_REPORTS_ROOT = REPORTS_DIR
DEFAULT_PUBLISH_ROOT = ROOT / "build" / "miniapp-publish"
PRIMARY_TECHNICAL_TIMEFRAME = "30m"
PRIMARY_TECHNICAL_LABEL = "30M"
DETAIL_TECHNICAL_TIMEFRAMES = ("day", "30m", "5m", "1m")
PRIMARY_TECHNICAL_CANDIDATES = ("30m", "day", "60m", "15m", "5m", "1m")
TIMEFRAME_LABELS = {
    "day": "DAY",
    "60m": "60M",
    "30m": "30M",
    "15m": "15M",
    "5m": "5M",
    "1m": "1M",
}

DEFAULT_SEGMENT_BOOTSTRAP_MODE = "prefer_earlier_start"
DEFAULT_STRICT_SEGMENT_RULES = True
ACTIVE_SEGMENT_BOOTSTRAP_MODE = DEFAULT_SEGMENT_BOOTSTRAP_MODE
ACTIVE_STRICT_SEGMENT_RULES = DEFAULT_STRICT_SEGMENT_RULES


@dataclass(frozen=True)
class Holding:
    symbol: str
    name: str
    market: str


def _resolve_segment_bootstrap_mode_for_timeframe(timeframe: str) -> str:
    normalized = safe_text(timeframe)
    # Keep 1m publish JSON aligned with report-generation anchor policy unless
    # caller explicitly overrides segment bootstrap mode via CLI.
    if normalized == "1m" and ACTIVE_SEGMENT_BOOTSTRAP_MODE == DEFAULT_SEGMENT_BOOTSTRAP_MODE:
        return "first_valid_seed"
    return ACTIVE_SEGMENT_BOOTSTRAP_MODE


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
    parser.add_argument(
        "--publish-json-only",
        action="store_true",
        help="Publish chart JSON payloads only and skip copying image assets (svg/jpg/png).",
    )
    parser.add_argument(
        "--expected-tech-timeframes",
        nargs="+",
        choices=("day", "60m", "30m", "15m", "5m", "1m"),
        default=None,
        help="Optional expected technical timeframes used for missing-file alerts.",
    )
    parser.add_argument(
        "--skip-regenerate-context",
        action="store_true",
        help="Mark missing files as potentially caused by skip-regenerate reuse.",
    )
    parser.add_argument(
        "--skip-gen-fund-context",
        action="store_true",
        help="Mark missing fund.json as potentially caused by skip-gen-fund reuse.",
    )
    parser.add_argument(
        "--failed-symbols",
        nargs="+",
        default=None,
        help="Optional failed symbols from regeneration stage used for missing-file diagnosis.",
    )
    parser.add_argument(
        "--segment-bootstrap-mode",
        default=DEFAULT_SEGMENT_BOOTSTRAP_MODE,
        choices=("auto", "prefer_earlier_start", "first_valid_seed", "skip_left_edge"),
        help="Segment bootstrap mode used when deriving publish chart segments from bis records.",
    )
    parser.add_argument(
        "--strict-segment-rules",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_STRICT_SEGMENT_RULES,
        help="Enable strict segment rules when deriving publish chart segments.",
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


def read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return read_json(path)


def load_previous_publish_stock_payloads(latest_dir: Path) -> dict[str, dict[str, Any]]:
    stocks_dir = latest_dir / "stocks"
    if not stocks_dir.exists():
        return {}

    payloads: dict[str, dict[str, Any]] = {}
    for stock_dir in sorted(item for item in stocks_dir.iterdir() if item.is_dir()):
        symbol = stock_dir.name
        summary = read_json_if_exists(stock_dir / "summary.json")
        detail = read_json_if_exists(stock_dir / "detail.json")
        if not summary and not detail:
            continue
        payloads[symbol] = {"summary": summary, "detail": detail}
    return payloads


def _section_timeframe_key(section: dict[str, Any]) -> str:
    timeframe = safe_text(section.get("timeframe")).lower()
    if timeframe:
        return timeframe
    key = safe_text(section.get("key")).lower()
    if key.startswith("technical_"):
        return key.removeprefix("technical_")
    return ""


def merge_technical_sections_with_fallback(
    sections: list[dict[str, Any]],
    fallback_detail_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not fallback_detail_payload:
        return sections

    fallback_sections = fallback_detail_payload.get("sections") or []
    if not isinstance(fallback_sections, list):
        return sections

    existing_timeframes = {
        _section_timeframe_key(section)
        for section in sections
        if isinstance(section, dict) and str(section.get("key") or "").startswith("technical")
    }

    merged = list(sections)
    for section in fallback_sections:
        if not isinstance(section, dict):
            continue
        key = str(section.get("key") or "")
        if not key.startswith("technical"):
            continue
        timeframe = _section_timeframe_key(section)
        if timeframe not in {"day", "30m"}:
            continue
        if timeframe in existing_timeframes:
            continue
        merged.append(section)
        existing_timeframes.add(timeframe)

    order_map = {value: index for index, value in enumerate(DETAIL_TECHNICAL_TIMEFRAMES)}

    def _sort_key(section: dict[str, Any]) -> tuple[int, str]:
        key = str(section.get("key") or "")
        if key == "fundamental":
            return (-2, "")
        if key == "capital_flow":
            return (99, "")
        timeframe = _section_timeframe_key(section)
        return (order_map.get(timeframe, 50), timeframe)

    return sorted(merged, key=_sort_key)


def resolve_primary_technical_payload(stock_dir: Path) -> tuple[str, dict[str, Any]]:
    for timeframe in PRIMARY_TECHNICAL_CANDIDATES:
        tech_path = stock_dir / timeframe / "tech.json"
        if tech_path.exists():
            return timeframe, read_json(tech_path)
    return PRIMARY_TECHNICAL_TIMEFRAME, {}


def latest_generated_technical_at(stock_dir: Path) -> str:
    timestamps: list[str] = []
    seen: set[str] = set()
    for timeframe in (*DETAIL_TECHNICAL_TIMEFRAMES, *PRIMARY_TECHNICAL_CANDIDATES):
        normalized = safe_text(timeframe).lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        tech_payload = read_json_if_exists(stock_dir / normalized / "tech.json")
        generated_at = safe_text(tech_payload.get("generated_at"))
        if generated_at:
            timestamps.append(generated_at)
    return max(timestamps) if timestamps else ""


def _missing_reason(
    *,
    symbol: str,
    failed_symbols: set[str],
    skip_regenerate_context: bool,
    skip_gen_fund_context: bool,
    kind: str,
) -> str:
    if symbol in failed_symbols:
        return "holding_generation_failed"
    if kind == "fund_json" and skip_gen_fund_context:
        return "fund_generation_skipped"
    if skip_regenerate_context:
        return "skip_regenerate_reused_stale_reports"
    return "requested_but_not_generated"


def collect_missing_artifact_alerts(
    *,
    holding: Holding,
    stock_dir: Path,
    expected_tech_timeframes: tuple[str, ...] | None,
    skip_regenerate_context: bool,
    skip_gen_fund_context: bool,
    failed_symbols: set[str],
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    symbol = holding.symbol
    expected = expected_tech_timeframes or (PRIMARY_TECHNICAL_TIMEFRAME,)

    base_path = stock_dir / "base.json"
    if not base_path.exists():
        alerts.append(
            {
                "symbol": symbol,
                "name": holding.name,
                "market": holding.market,
                "kind": "base_json",
                "path": str(base_path),
                "reason": _missing_reason(
                    symbol=symbol,
                    failed_symbols=failed_symbols,
                    skip_regenerate_context=skip_regenerate_context,
                    skip_gen_fund_context=skip_gen_fund_context,
                    kind="base_json",
                ),
            }
        )

    fund_path = stock_dir / "fund.json"
    if not fund_path.exists():
        alerts.append(
            {
                "symbol": symbol,
                "name": holding.name,
                "market": holding.market,
                "kind": "fund_json",
                "path": str(fund_path),
                "reason": _missing_reason(
                    symbol=symbol,
                    failed_symbols=failed_symbols,
                    skip_regenerate_context=skip_regenerate_context,
                    skip_gen_fund_context=skip_gen_fund_context,
                    kind="fund_json",
                ),
            }
        )

    for timeframe in expected:
        tech_path = stock_dir / timeframe / "tech.json"
        if tech_path.exists():
            continue
        alerts.append(
            {
                "symbol": symbol,
                "name": holding.name,
                "market": holding.market,
                "kind": "tech_json",
                "timeframe": timeframe,
                "path": str(tech_path),
                "reason": _missing_reason(
                    symbol=symbol,
                    failed_symbols=failed_symbols,
                    skip_regenerate_context=skip_regenerate_context,
                    skip_gen_fund_context=skip_gen_fund_context,
                    kind="tech_json",
                ),
            }
        )

    return alerts


def build_missing_artifacts_payload(
    *,
    alerts: list[dict[str, Any]],
    expected_tech_timeframes: tuple[str, ...] | None,
    skip_regenerate_context: bool,
    skip_gen_fund_context: bool,
    failed_symbols: set[str],
) -> dict[str, Any]:
    by_reason: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    for item in alerts:
        reason = safe_text(item.get("reason"), "unknown")
        kind = safe_text(item.get("kind"), "unknown")
        by_reason[reason] = by_reason.get(reason, 0) + 1
        by_kind[kind] = by_kind.get(kind, 0) + 1
    return {
        "schema_version": "missing-artifacts-v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "counts": {
            "total": len(alerts),
            "by_reason": by_reason,
            "by_kind": by_kind,
            "affected_symbols": len({safe_text(item.get("symbol")) for item in alerts if safe_text(item.get("symbol"))}),
        },
        "context": {
            "expected_tech_timeframes": list(expected_tech_timeframes) if expected_tech_timeframes else [PRIMARY_TECHNICAL_TIMEFRAME],
            "skip_regenerate": skip_regenerate_context,
            "skip_gen_fund": skip_gen_fund_context,
            "failed_symbols": sorted(failed_symbols),
        },
        "alerts": alerts,
    }


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


def safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return safe_text(value).lower() in {"1", "true", "yes", "y"}


def safe_int_list(value: Any) -> list[int]:
    if isinstance(value, list):
        result: list[int] = []
        for item in value:
            try:
                result.append(int(item))
            except (TypeError, ValueError):
                continue
        return result

    text = safe_text(value)
    if not text:
        return []

    result: list[int] = []
    for part in text.split(","):
        token = part.strip()
        if not token:
            continue
        try:
            result.append(int(token))
        except (TypeError, ValueError):
            continue
    return result


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
    transition_fields = build_transition_summary_fields(technical)
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
        **transition_fields,
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


def infer_transition_state(structure_state: dict[str, Any], current: dict[str, Any], relationship: dict[str, Any]) -> str:
    explicit = safe_text(relationship.get("transition_state"))
    if explicit:
        return explicit

    relationship_kind = safe_text(relationship.get("kind"))
    if relationship_kind == "same_type_extension":
        return "same_type_extension"
    if relationship_kind == "completed_then_new_type_ongoing":
        current_structure_status = safe_text(structure_state.get("current_structure_status"))
        if current_structure_status == "candidate_completed_waiting_stability":
            return "candidate_new_type"
        if safe_text(current.get("type")):
            return "ongoing_new_type"
    return "none"


def infer_consumption_level(
    summary: dict[str, Any],
    structure_state: dict[str, Any],
    current: dict[str, Any],
    relationship: dict[str, Any],
) -> str:
    explicit = safe_text(summary.get("same_level_consumption_level")) or safe_text(structure_state.get("consumption_level"))
    if explicit:
        return explicit

    current_structure_status = infer_structure_status(structure_state, current, relationship)
    confirmation_basis = safe_text((structure_state.get("current_ongoing") or {}).get("confirmation_basis"))
    if confirmation_basis == "no_same_level_zhongshu":
        return "auxiliary"
    if current_structure_status == "candidate_completed_waiting_stability":
        return "pending"
    if confirmation_basis == "single_active_zhongshu":
        return "pending"
    return "confirmed"


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
    transition_state = infer_transition_state(structure_state, current, relationship)
    transition_state_note = describe_transition_state(transition_state)
    consumption_level = infer_consumption_level(summary, structure_state, current, relationship)
    consumption_level_note = safe_text(summary.get("same_level_consumption_level_note")) or describe_consumption_level(consumption_level)
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
    if transition_state_note:
        transition_state_label = format_transition_state_label(transition_state)
        if transition_state_label and transition_state_label != transition_state:
            lines.append(f"转场状态：{transition_state_label}，{transition_state_note}")
        else:
            lines.append(f"转场状态：{transition_state_note}")
    if current_structure_status_note:
        lines.append(f"切分状态：{current_structure_status_note}")
    if consumption_level_note:
        consumption_level_label = safe_text(summary.get("same_level_consumption_level_label")) or format_consumption_level_label(consumption_level)
        if consumption_level_label and consumption_level_label != consumption_level:
            lines.append(f"消费等级：{consumption_level_label}，{consumption_level_note}")
        else:
            lines.append(f"消费等级：{consumption_level_note}")
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
        "same_level_consumption_level": consumption_level,
        "same_level_consumption_level_label": safe_text(summary.get("same_level_consumption_level_label")) or format_consumption_level_label(consumption_level),
        "same_level_consumption_level_note": consumption_level_note,
        "transition_state": transition_state,
        "transition_state_label": format_transition_state_label(transition_state),
        "transition_state_note": transition_state_note,
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

    zs_monitor_alert = safe_text(summary.get("zs_monitor_alert")).lower()
    if zs_monitor_alert in {"pre_breakout", "pre_breakdown"}:
        direction = "向上预警" if zs_monitor_alert == "pre_breakout" else "向下预警"
        pending_text = "当前不构成确认三买" if zs_monitor_alert == "pre_breakout" else "当前不构成确认三卖"
        bias_text = {
            "strong": "偏强",
            "weak": "偏弱",
            "neutral": "中性",
        }.get(safe_text(summary.get("zs_monitor_bias")).lower(), "")
        midline = summary.get("zs_monitor_midline")
        basis_parts = []
        if midline is not None:
            basis_parts.append(f"中线 {midline}")
        if bias_text:
            basis_parts.append(f"节奏{bias_text}")
        basis_suffix = f"（{'，'.join(basis_parts)}）" if basis_parts else ""
        lines.append(f"中枢预警：{direction}，{pending_text}{basis_suffix}")

    post_divergence_route = safe_text(summary.get("post_divergence_route")).lower()
    if post_divergence_route:
        route_label = {
            "higher_level_range": "更大级别盘整",
            "higher_level_reverse_trend": "更大级别反趋势",
            "last_zs_extension": "最后中枢延伸",
        }.get(post_divergence_route, post_divergence_route)
        route_from = safe_text(summary.get("route_level_from"))
        route_to = safe_text(summary.get("route_level_to"))
        route_suffix = f"（{route_from} -> {route_to}）" if route_from and route_to else ""
        lines.append(f"去向候选：{route_label}{route_suffix}，当前只按观察态处理")

    rhythm_state = safe_text(summary.get("oscillation_rhythm_state")).lower()
    rhythm_label = {
        "up_bias": "节奏偏强",
        "down_bias": "节奏偏弱",
        "balanced": "节奏平衡",
        "pending": "节奏待判定",
    }.get(rhythm_state)
    if rhythm_label:
        lines.append(f"节奏监视：{rhythm_label}，当前只作辅助观察")

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


def build_transition_overview_bullet(technical: dict[str, Any]) -> str:
    decomposition = technical.get("same_level_decomposition") or {}
    transition_state = safe_text(decomposition.get("transition_state")).lower()
    if not transition_state or transition_state == "none":
        return ""
    transition_label = safe_text(decomposition.get("transition_state_label")) or transition_state
    structure_status_label = safe_text(decomposition.get("current_structure_status_label"))
    consumption_level_label = safe_text(decomposition.get("same_level_consumption_level_label"))
    if structure_status_label:
        if consumption_level_label:
            return f"结构转场 {transition_label}，切分 {structure_status_label}，消费 {consumption_level_label}"
        return f"结构转场 {transition_label}，切分 {structure_status_label}"
    if consumption_level_label:
        return f"结构转场 {transition_label}，消费 {consumption_level_label}"
    return f"结构转场 {transition_label}"


def build_transition_summary_fields(technical: dict[str, Any]) -> dict[str, Any]:
    decomposition = technical.get("same_level_decomposition") or {}
    transition_state = safe_text(decomposition.get("transition_state")).lower()
    consumption_level = safe_text(decomposition.get("same_level_consumption_level")).lower()
    consumption_level_label = safe_text(decomposition.get("same_level_consumption_level_label")) or consumption_level
    if not transition_state or transition_state == "none":
        return {
            "technical_transition_state": None,
            "technical_transition_label": None,
            "technical_transition_summary": None,
            "technical_consumption_level": consumption_level or None,
            "technical_consumption_label": consumption_level_label or None,
        }
    transition_label = safe_text(decomposition.get("transition_state_label")) or transition_state
    structure_status_label = safe_text(decomposition.get("current_structure_status_label"))
    summary = f"结构转场 {transition_label}"
    if structure_status_label:
        summary = f"{summary}，切分 {structure_status_label}"
    if consumption_level_label:
        summary = f"{summary}，消费 {consumption_level_label}"
    return {
        "technical_transition_state": transition_state,
        "technical_transition_label": transition_label,
        "technical_transition_summary": summary,
        "technical_consumption_level": consumption_level or None,
        "technical_consumption_label": consumption_level_label or None,
    }


def build_zhongshu_level_note(tech_payload: dict[str, Any]) -> str:
    structure = tech_payload.get("structure") or {}
    primary_level = safe_text(structure.get("primary_zhongshu_level")) or safe_text(tech_payload.get("zhongshu_level"))
    if primary_level == "segment":
        return "中枢口径：主中枢=线段中枢；类中枢仅作辅助参考。"
    if primary_level == "bi":
        return "中枢口径：主中枢=类中枢（笔级），用于兼容旧口径。"
    return ""


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
    structure_payload = tech_payload.get("structure") or {}
    analysis_text = safe_text(tech_payload.get("analysis_text"))
    precision_entry = summary.get("precision_entry") or tech_payload.get("precision_entry") or {}
    precision_window_display = build_precision_window_display(precision_entry)
    same_level_decomposition = build_same_level_decomposition(tech_payload)
    latest_signal_summary = build_latest_signal_summary(tech_payload)
    zhongshu_level_note = build_zhongshu_level_note(tech_payload)
    technical_focus_lines = build_technical_focus_lines(same_level_decomposition, latest_signal_summary)
    if zhongshu_level_note:
        technical_focus_lines.append(zhongshu_level_note)
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
        "oscillation_rhythm_state": summary.get("oscillation_rhythm_state") or tech_payload.get("oscillation_rhythm_state"),
        "post_divergence_route": summary.get("post_divergence_route") or tech_payload.get("post_divergence_route"),
        "route_level_from": summary.get("route_level_from") or tech_payload.get("route_level_from"),
        "route_level_to": summary.get("route_level_to") or tech_payload.get("route_level_to"),
        "latest_signal_summary": latest_signal_summary,
        "technical_focus_lines": technical_focus_lines,
        "zhongshu_level": tech_payload.get("zhongshu_level"),
        "primary_zhongshu_level": structure_payload.get("primary_zhongshu_level"),
        "latest_zhongshu": structure_payload.get("latest_zhongshu"),
        "latest_lei_zhongshu": structure_payload.get("latest_lei_zhongshu"),
        "zhongshu_level_note": zhongshu_level_note,
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


def build_timeframe_technical_sections(
    stock_dir: Path,
    timeframes: tuple[str, ...],
    primary_timeframe: str = PRIMARY_TECHNICAL_TIMEFRAME,
) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for timeframe in timeframes:
        tech_path = stock_dir / timeframe / "tech.json"
        if not tech_path.exists():
            continue
        section = build_technical_section(read_json(tech_path))
        label = TIMEFRAME_LABELS.get(timeframe, timeframe.upper())
        section["key"] = "technical" if timeframe == primary_timeframe else f"technical_{timeframe}"
        section["title"] = f"{label} 技术面"
        section["timeframe"] = timeframe
        section["operation_level"] = section.get("operation_level") or label
        sections.append(section)
    return sections


def build_chart_specs(
    stock_dir: Path,
    publish_timeframes: tuple[str, ...] | None = None,
    *,
    include_chart_images: bool = True,
) -> list[dict[str, str]]:
    charts: list[dict[str, str]] = []
    timeframe_order = publish_timeframes or ("30m", "5m", "1m", "day")
    for timeframe in timeframe_order:
        chart_spec: dict[str, str] = {
            "timeframe": timeframe,
            "label": f"{timeframe.upper()} 结构图",
        }

        data_source_path = find_latest_chart_bars_csv(stock_dir / timeframe, timeframe)
        if data_source_path:
            chart_spec["data_source_path"] = str(data_source_path)
            chart_spec["data_relative_path"] = f"charts/{timeframe}.json"

        if include_chart_images:
            for extension in ("svg", "jpg", "png"):
                chart_path = stock_dir / timeframe / f"structure.{extension}"
                if not chart_path.exists():
                    continue
                chart_spec["source_path"] = str(chart_path)
                chart_spec["relative_path"] = f"charts/{timeframe}.{extension}"
                break

        if chart_spec.get("relative_path") or chart_spec.get("data_relative_path"):
            charts.append(chart_spec)
    return charts


def _parse_chart_bars_date_range(path: Path) -> tuple[int, int] | None:
    match = re.search(r"_(\d{8})_to_(\d{8})(?:\.csv|_|$)", path.name)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _chart_bars_sort_key(path: Path) -> tuple[int, int, int, float]:
    parsed_range = _parse_chart_bars_date_range(path)
    if parsed_range is None:
        return (0, 0, 0, path.stat().st_mtime)
    start_date, end_date = parsed_range
    # Prefer the latest end date first; for the same end date choose the
    # earliest start date so publish JSON keeps the widest available history.
    return (1, end_date, -start_date, path.stat().st_mtime)


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
    return max(candidates, key=_chart_bars_sort_key)


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


_ZHONGSHU_BI_KEYS = {
    "start_bi_id",
    "end_bi_id",
    "entering_bi_id",
    "core_bi_ids",
    "exit_bi_id",
    "bi_ids",
    "render_start_bi_id",
    "render_end_bi_id",
}

_ZHONGSHU_SEGMENT_KEYS = {
    "start_segment_id",
    "end_segment_id",
    "entering_segment_id",
    "core_segment_ids",
    "exit_segment_id",
    "segment_ids",
    "render_start_segment_id",
    "render_end_segment_id",
}


def normalize_chart_zhongshu_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return zhongshu records with a single id namespace based on structure_level."""
    normalized: list[dict[str, Any]] = []
    for record in records:
        item = dict(record)
        level = safe_text(item.get("structure_level"))
        if level == "segment":
            for key in _ZHONGSHU_BI_KEYS:
                item.pop(key, None)
        elif level == "bi":
            for key in _ZHONGSHU_SEGMENT_KEYS:
                item.pop(key, None)
        normalized.append(item)
    return normalized


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
    stop_reason = segment.stop_reason
    outcome_summary = summarize_stop_reason_outcome(stop_reason)
    return {
        "segment_id": segment.segment_id,
        "direction": segment.direction.value,
        "start_bi_id": segment.start_bi_id,
        "end_bi_id": segment.end_bi_id,
        "theory_candidate_end_bi_id": segment.theory_candidate_end_bi_id,
        "start_ts": segment.start_ts.strftime("%Y-%m-%d %H:%M"),
        "end_ts": segment.end_ts.strftime("%Y-%m-%d %H:%M"),
        "theory_candidate_end_ts": segment.theory_candidate_end_ts.strftime("%Y-%m-%d %H:%M") if segment.theory_candidate_end_ts else None,
        "start_price": segment.start_price,
        "end_price": segment.end_price,
        "theory_candidate_end_price": segment.theory_candidate_end_price,
        "high": segment.high,
        "low": segment.low,
        "start_norm_idx": segment.norm_bar_range[0],
        "end_norm_idx": segment.norm_bar_range[1],
        "bi_ids": ",".join(str(bi_id) for bi_id in segment.bi_ids),
        "last_same_extreme": segment.last_same_extreme,
        "last_reverse_extreme": segment.last_reverse_extreme,
        "break_bi_id": segment.break_bi_id,
        "stop_reason": stop_reason,
        "is_reclaimed": segment.is_reclaimed,
        "absorbed_segment_ids": ",".join(str(segment_id) for segment_id in segment.absorbed_segment_ids),
        "stop_reason_label": describe_stop_reason(stop_reason),
        "stop_category": classify_stop_reason(stop_reason).value,
        "stop_outcome_bucket": outcome_summary["bucket"],
        "stop_outcome_label": outcome_summary["label"],
        "is_theory_confirmed_stop": is_theory_confirmed_stop_reason(stop_reason),
        "is_fallback_confirmed_stop": is_fallback_confirmed_stop_reason(stop_reason),
        "is_pending_stop": is_pending_stop_reason(stop_reason),
        "is_confirmed": segment.is_confirmed,
        "status": "confirmed" if segment.is_confirmed else "preprocessing",
        "note": "auto_generated",
    }


def _normalize_segment_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(record)
    if normalized.get("theory_candidate_end_bi_id") is None:
        normalized["theory_candidate_end_bi_id"] = normalized.get("end_bi_id")
    if normalized.get("theory_candidate_end_ts") is None:
        normalized["theory_candidate_end_ts"] = normalized.get("end_ts")
    if normalized.get("theory_candidate_end_price") is None:
        normalized["theory_candidate_end_price"] = normalized.get("end_price")
    stop_reason = safe_text(normalized.get("stop_reason"))
    if not safe_text(normalized.get("stop_reason_label")):
        normalized["stop_reason_label"] = describe_stop_reason(stop_reason)
    stop_category = safe_text(normalized.get("stop_category"))
    if not stop_category:
        stop_category = classify_stop_reason(stop_reason).value
        normalized["stop_category"] = stop_category

    if "stop_outcome_bucket" not in normalized:
        outcome_summary = summarize_stop_reason_outcome(stop_reason)
        normalized["stop_outcome_bucket"] = outcome_summary["bucket"]
    if "stop_outcome_label" not in normalized:
        outcome_summary = summarize_stop_reason_outcome(stop_reason)
        normalized["stop_outcome_label"] = outcome_summary["label"]

    if "is_theory_confirmed_stop" not in normalized:
        normalized["is_theory_confirmed_stop"] = is_theory_confirmed_stop_reason(stop_reason)
    if "is_fallback_confirmed_stop" not in normalized:
        normalized["is_fallback_confirmed_stop"] = is_fallback_confirmed_stop_reason(stop_reason)
    if "is_pending_stop" not in normalized:
        normalized["is_pending_stop"] = is_pending_stop_reason(stop_reason)
    normalized["is_reclaimed"] = safe_bool(normalized.get("is_reclaimed"))
    normalized["absorbed_segment_ids"] = safe_int_list(normalized.get("absorbed_segment_ids"))
    return normalized


def build_segment_records(
    bis_records: list[dict[str, Any]],
    segment_records: list[dict[str, Any]],
    timeframe: str = PRIMARY_TECHNICAL_TIMEFRAME,
) -> list[dict[str, Any]]:
    bootstrap_mode = _resolve_segment_bootstrap_mode_for_timeframe(timeframe)
    should_recompute = ACTIVE_SEGMENT_BOOTSTRAP_MODE != DEFAULT_SEGMENT_BOOTSTRAP_MODE or ACTIVE_STRICT_SEGMENT_RULES

    if segment_records and (not should_recompute or not bis_records):
        return [_normalize_segment_record(record) for record in segment_records]
    bis = build_bis_from_records(bis_records)
    if not bis:
        return []
    return [
        serialize_segment_record(segment)
        for segment in identify_segments(
            bis,
            bootstrap_mode=bootstrap_mode,
            bootstrap_skip_confirmed_bis=0,
            strict_segment_rules=ACTIVE_STRICT_SEGMENT_RULES,
        )
    ]


def build_segment_stop_reason_annotations(segment_records: list[dict[str, Any]], timeframe: str) -> dict[str, Any]:
    annotations: list[dict[str, Any]] = []
    timeframe_label = TIMEFRAME_LABELS.get(timeframe, timeframe.upper())
    for record in segment_records:
        stop_reason = safe_text(record.get("stop_reason"))
        stop_reason_label = safe_text(record.get("stop_reason_label")) or describe_stop_reason(stop_reason)
        if not stop_reason_label:
            continue
        segment_id = record.get("segment_id")
        segment_hint = f"S{segment_id}" if segment_id is not None else "最新线段"
        annotations.append(
            {
                "segment_id": segment_id,
                "stop_reason": stop_reason,
                "stop_reason_label": stop_reason_label,
                "stop_category": classify_stop_reason(stop_reason).value,
                "stop_outcome_bucket": summarize_stop_reason_outcome(stop_reason)["bucket"],
                "stop_outcome_label": summarize_stop_reason_outcome(stop_reason)["label"],
                "is_theory_confirmed_stop": is_theory_confirmed_stop_reason(stop_reason),
                "is_fallback_confirmed_stop": is_fallback_confirmed_stop_reason(stop_reason),
                "is_pending_stop": is_pending_stop_reason(stop_reason),
                "text": f"{timeframe_label} {segment_hint} 停驻原因：{stop_reason_label}",
            }
        )

    return {
        "latest": annotations[-1] if annotations else None,
        "items": annotations,
    }


def build_latest_segment_stop_reason_line(
    stock_dir: Path,
    timeframe: str = PRIMARY_TECHNICAL_TIMEFRAME,
    tech_payload: dict[str, Any] | None = None,
) -> str:
    timeframe_dir = stock_dir / timeframe
    bars_csv = find_latest_chart_bars_csv(timeframe_dir, timeframe)
    if bars_csv is None:
        if not tech_payload:
            return ""
        summary = (tech_payload.get("summary") or {})
        structure_state = (summary.get("structure_state") or {})
        current_structure_status = safe_text(structure_state.get("current_structure_status"))
        fallback_label = "候选完成待确认" if current_structure_status == "candidate_completed_waiting_stability" else "尾段待确认"
        timeframe_label = TIMEFRAME_LABELS.get(timeframe, timeframe.upper())
        return f"{timeframe_label} 最新线段 停驻原因：{fallback_label}"

    bis_records = read_csv_records(sibling_analysis_csv(bars_csv, "_normalized_bis"))
    segment_records = build_segment_records(
        bis_records,
        read_csv_records(sibling_analysis_csv(bars_csv, "_normalized_segments")),
        timeframe,
    )
    if not segment_records:
        if not tech_payload:
            return ""
        summary = (tech_payload.get("summary") or {})
        structure_state = (summary.get("structure_state") or {})
        current_structure_status = safe_text(structure_state.get("current_structure_status"))
        fallback_label = "候选完成待确认" if current_structure_status == "candidate_completed_waiting_stability" else "尾段待确认"
        timeframe_label = TIMEFRAME_LABELS.get(timeframe, timeframe.upper())
        return f"{timeframe_label} 最新线段 停驻原因：{fallback_label}"

    latest = segment_records[-1]
    stop_reason_label = safe_text(latest.get("stop_reason_label"))
    if not stop_reason_label:
        stop_reason_label = describe_stop_reason(safe_text(latest.get("stop_reason")))
    if not stop_reason_label:
        return ""

    segment_id = latest.get("segment_id")
    segment_hint = f"S{segment_id}" if segment_id is not None else "最新线段"
    timeframe_label = TIMEFRAME_LABELS.get(timeframe, timeframe.upper())
    return f"{timeframe_label} {segment_hint} 停驻原因：{stop_reason_label}"


def sibling_analysis_csv(bars_csv: Path, suffix: str) -> Path:
    return bars_csv.with_name(f"{bars_csv.stem}{suffix}.csv")


def serialize_segment_tail_interpretation(interpretation: Any) -> dict[str, Any]:
    return {
        "segment_id": interpretation.segment_id,
        "kind": interpretation.kind,
        "confidence": interpretation.confidence,
        "uncertainty": interpretation.uncertainty,
        "evidence": interpretation.evidence,
        "suggested_catalyst": interpretation.suggested_catalyst,
        "is_reclaimed": getattr(interpretation, "is_reclaimed", False),
        "absorbed_segment_ids": list(getattr(interpretation, "absorbed_segment_ids", [])),
    }


def build_segment_tail_interpretations_fallback(tech_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not tech_payload:
        return []

    summary = (tech_payload.get("summary") or {})
    structure_state = (summary.get("structure_state") or {})
    current_structure_status = safe_text(structure_state.get("current_structure_status")) or "unknown"
    ongoing = structure_state.get("current_ongoing") or {}
    ongoing_type = safe_text(ongoing.get("type")) or "unknown"

    return [
        {
            "segment_id": 0,
            "kind": "pending_confirmation",
            "confidence": "medium",
            "uncertainty": "当前尾段缺少足够的后续笔推进或反向突破证据，暂时以待确认结构呈现。",
            "evidence": f"current_structure_status={current_structure_status}; current_ongoing_type={ongoing_type}",
            "suggested_catalyst": "继续观察后续笔推进和反向突破是否形成正式终结条件。",
            "is_reclaimed": False,
            "absorbed_segment_ids": [],
        }
    ]


def build_latest_segment_reclaim_line(
    segment_tail_interpretations: list[dict[str, Any]],
    timeframe: str,
) -> str:
    if not segment_tail_interpretations:
        return ""

    latest = segment_tail_interpretations[-1]
    if not safe_bool(latest.get("is_reclaimed")):
        return ""

    absorbed_segment_ids = safe_int_list(latest.get("absorbed_segment_ids"))
    if not absorbed_segment_ids:
        return ""

    timeframe_label = TIMEFRAME_LABELS.get(timeframe, timeframe.upper())
    segment_id = latest.get("segment_id")
    segment_hint = f"S{segment_id}" if segment_id is not None else "最新线段"
    absorbed_segments = "、".join(f"S{segment_id}" for segment_id in absorbed_segment_ids)
    return f"{timeframe_label} {segment_hint} 线段重写吸收：已吸收旧段 {absorbed_segments}，当前尾段继续按待确认结构观察。"


def build_segment_tail_interpretations_payload(
    stock_dir: Path,
    timeframe: str,
    tech_payload: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    timeframe_dir = stock_dir / timeframe
    bars_csv = find_latest_chart_bars_csv(timeframe_dir, timeframe)
    if bars_csv is None:
        return build_segment_tail_interpretations_fallback(tech_payload)

    bis_records = read_csv_records(sibling_analysis_csv(bars_csv, "_normalized_bis"))
    bis = build_bis_from_records(bis_records)
    if not bis:
        return build_segment_tail_interpretations_fallback(tech_payload)

    segments = identify_segments(
        bis,
        bootstrap_mode=_resolve_segment_bootstrap_mode_for_timeframe(timeframe),
        bootstrap_skip_confirmed_bis=0,
        strict_segment_rules=ACTIVE_STRICT_SEGMENT_RULES,
    )
    interpretations = build_segment_tail_interpretations(bis, segments)
    rendered = [serialize_segment_tail_interpretation(interpretation) for interpretation in interpretations]
    if rendered:
        return rendered
    return build_segment_tail_interpretations_fallback(tech_payload)


def _enrich_bi_records_with_fractals(
    bis_records: list[dict[str, Any]],
    fractal_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not bis_records:
        return []

    fractal_by_id: dict[int, dict[str, Any]] = {}
    for record in fractal_records:
        try:
            fractal_id = int(record.get("fx_id") or 0)
        except (TypeError, ValueError):
            continue
        fractal_by_id[fractal_id] = record

    enriched: list[dict[str, Any]] = []
    for record in bis_records:
        normalized = dict(record)
        try:
            start_fx_id = int(record.get("start_fx_id") or 0)
            end_fx_id = int(record.get("end_fx_id") or 0)
        except (TypeError, ValueError):
            enriched.append(normalized)
            continue

        start_fx = fractal_by_id.get(start_fx_id)
        end_fx = fractal_by_id.get(end_fx_id)
        if start_fx is not None:
            normalized["start_price"] = start_fx.get("price")
            normalized["start_fx_type"] = start_fx.get("fx_type")
        if end_fx is not None:
            normalized["end_price"] = end_fx.get("price")
            normalized["end_fx_type"] = end_fx.get("fx_type")
        enriched.append(normalized)

    return enriched


def _trend_type_boundary_bar_indices(
    type_chain: list[dict[str, Any]],
    bars_records: list[dict[str, Any]],
) -> list[int]:
    """把 type_chain 各段 start_ts 映射到 bars CSV 的 bar index。

    chart-data-v1 的 `trend_type_boundaries` 供小程序 canvas 模式画走势类型
    分界虚竖线（前端 `drawPanelDividers` / `getTrendDividerBarIndices`）。
    跳过映射到左边缘（index <= 0）的分界，并对重复 index 去重。
    """
    if not type_chain or not bars_records:
        return []

    indices: list[int] = []
    for entry in type_chain:
        start_ts = safe_text(entry.get("start_ts"))
        if not start_ts:
            continue
        normalized = start_ts.replace("T", " ")[:16]
        bar_index = len(bars_records) - 1
        for index, record in enumerate(bars_records):
            if safe_text(record.get("ts"))[:16] >= normalized:
                bar_index = index
                break
        if bar_index > 0:
            indices.append(bar_index)

    unique: list[int] = []
    for index in indices:
        if index not in unique:
            unique.append(index)
    return unique


def build_chart_data_payload(chart_spec: dict[str, str]) -> dict[str, Any] | None:
    source_value = chart_spec.get("data_source_path")
    if not source_value:
        return None

    bars_csv = Path(source_value)
    if not bars_csv.exists():
        return None

    timeframe = safe_text(chart_spec.get("timeframe"))
    timeframe_dir = bars_csv.parent.parent
    tech_payload = read_json_if_exists(timeframe_dir / "tech.json")
    precision_entry = ((tech_payload.get("summary") or {}).get("precision_entry") or tech_payload.get("precision_entry") or {})
    pending_reverse_mode = safe_text(precision_entry.get("pending_reverse_mode")) or safe_text(tech_payload.get("pending_reverse_mode")) or "effective_only"
    fractal_records = read_csv_records(sibling_analysis_csv(bars_csv, "_normalized_fractals"))
    bis_records = _enrich_bi_records_with_fractals(
        read_csv_records(sibling_analysis_csv(bars_csv, "_normalized_bis")),
        fractal_records,
    )
    segment_records = build_segment_records(
        bis_records,
        read_csv_records(sibling_analysis_csv(bars_csv, "_normalized_segments")),
        timeframe,
    )
    stock_dir = bars_csv.parent.parent
    structure_payload = tech_payload.get("structure") if isinstance(tech_payload, dict) else {}
    lei_zhongshus = normalize_chart_zhongshu_records(
        read_csv_records(sibling_analysis_csv(bars_csv, "_normalized_zhongshu_lei"))
    )
    zhongshus = normalize_chart_zhongshu_records(
        read_csv_records(sibling_analysis_csv(bars_csv, "_normalized_zhongshu"))
    )

    bars_records = read_csv_records(bars_csv)
    structure_state = (tech_payload.get("structure_state") or {}) if isinstance(tech_payload, dict) else {}
    trend_type_boundaries = _trend_type_boundary_bar_indices(
        (structure_state or {}).get("type_chain") or [],
        bars_records,
    )

    return {
        "schema_version": "chart-data-v1",
        "timeframe": timeframe,
        "pending_reverse_mode": pending_reverse_mode,
        "zhongshu_level": safe_text(tech_payload.get("zhongshu_level")) if isinstance(tech_payload, dict) else "",
        "primary_zhongshu_level": safe_text((structure_payload or {}).get("primary_zhongshu_level")) if isinstance(structure_payload, dict) else "",
        "label": chart_spec.get("label"),
        "source_csv": bars_csv.name,
        "bars": bars_records,
        "trend_type_boundaries": trend_type_boundaries,
        "normalized_bars": read_csv_records(sibling_analysis_csv(bars_csv, "_normalized")),
        "macd": read_csv_records(sibling_analysis_csv(bars_csv, "_normalized_macd")),
        "fractals": fractal_records,
        "confirmed_fractals": read_csv_records(sibling_analysis_csv(bars_csv, "_normalized_confirmed_fractals")),
        "bis": bis_records,
        "segments": segment_records,
        "segment_stop_reason_annotations": build_segment_stop_reason_annotations(segment_records, timeframe),
        "segment_tail_interpretations": build_segment_tail_interpretations_payload(stock_dir, timeframe, None),
        "zhongshus": zhongshus,
        "lei_zhongshus": lei_zhongshus,
    }


def build_summary_payload(
    holding: Holding,
    stock_dir: Path,
    group_item: dict[str, Any] | None,
    publish_timeframes: tuple[str, ...] | None = None,
    include_chart_images: bool = True,
    fallback_summary_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base_payload = read_json_if_exists(stock_dir / "base.json")
    fund_payload = read_json_if_exists(stock_dir / "fund.json")
    primary_technical_timeframe, tech_payload = resolve_primary_technical_payload(stock_dir)
    base_summary = base_payload.get("summary") or {}
    fund_summary = fund_payload.get("summary") or {}
    tech_summary = tech_payload.get("summary") or {}
    structure_payload = tech_payload.get("structure") or {}
    precision_entry = tech_summary.get("precision_entry") or tech_payload.get("precision_entry") or {}
    precision_window_display = build_precision_window_display(precision_entry)
    same_level_decomposition = build_same_level_decomposition(tech_payload)
    latest_signal_summary = build_latest_signal_summary(tech_payload)
    zhongshu_level_note = build_zhongshu_level_note(tech_payload)
    technical_focus_lines = build_technical_focus_lines(same_level_decomposition, latest_signal_summary)
    if zhongshu_level_note:
        technical_focus_lines.append(zhongshu_level_note)
    segment_stop_line = (
        build_latest_segment_stop_reason_line(stock_dir, primary_technical_timeframe, tech_payload)
        if tech_payload
        else ""
    )
    segment_tail_interpretations = (
        build_segment_tail_interpretations_payload(stock_dir, primary_technical_timeframe, tech_payload)
        if tech_payload
        else []
    )
    segment_reclaim_line = build_latest_segment_reclaim_line(segment_tail_interpretations, primary_technical_timeframe)
    charts = build_chart_specs(stock_dir, publish_timeframes=publish_timeframes, include_chart_images=include_chart_images)
    cover_chart_path = chart_publish_path(charts, primary_technical_timeframe) or chart_publish_path(charts, PRIMARY_TECHNICAL_TIMEFRAME)
    primary_technical_label = TIMEFRAME_LABELS.get(primary_technical_timeframe, primary_technical_timeframe.upper())

    has_day_or_30m_local = any((stock_dir / timeframe / "tech.json").exists() for timeframe in ("day", "30m"))
    fallback_technical = (((fallback_summary_payload or {}).get("cards") or {}).get("technical") or {})
    fallback_timeframe = safe_text(fallback_technical.get("timeframe")).lower()
    if not has_day_or_30m_local and fallback_timeframe in {"day", "30m"}:
        tech_card_payload = fallback_technical
        primary_technical_timeframe = fallback_timeframe
        primary_technical_label = TIMEFRAME_LABELS.get(primary_technical_timeframe, primary_technical_timeframe.upper())
    else:
        tech_card_payload = {
            "timeframe": tech_payload.get("timeframe") or primary_technical_timeframe,
            "timeframe_label": primary_technical_label,
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
            "oscillation_rhythm_state": tech_summary.get("oscillation_rhythm_state") or tech_payload.get("oscillation_rhythm_state"),
            "post_divergence_route": tech_summary.get("post_divergence_route") or tech_payload.get("post_divergence_route"),
            "route_level_from": tech_summary.get("route_level_from") or tech_payload.get("route_level_from"),
            "route_level_to": tech_summary.get("route_level_to") or tech_payload.get("route_level_to"),
            "latest_signal_summary": latest_signal_summary,
            "technical_focus_lines": technical_focus_lines + ([segment_reclaim_line] if segment_reclaim_line else []),
            "zhongshu_level": tech_payload.get("zhongshu_level"),
            "primary_zhongshu_level": structure_payload.get("primary_zhongshu_level"),
            "latest_zhongshu": structure_payload.get("latest_zhongshu"),
            "latest_lei_zhongshu": structure_payload.get("latest_lei_zhongshu"),
            "zhongshu_level_note": zhongshu_level_note,
            "segment_tail_interpretations": segment_tail_interpretations,
            "precision_entry": precision_entry,
            "precision_note": precision_entry.get("note"),
            "precision_window_basis_label": precision_entry.get("window_basis_label") or (precision_entry.get("nested_from") or {}).get("window_basis_label"),
            "precision_window_basis_description": precision_entry.get("window_basis_description") or (precision_entry.get("nested_from") or {}).get("window_basis_description"),
            "precision_window_display": precision_window_display,
        }
    updated_at = max(
        safe_text(base_payload.get("generated_at")),
        safe_text(fund_payload.get("generated_at")),
        latest_generated_technical_at(stock_dir),
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
                **tech_card_payload,
                "timeframe_label": tech_card_payload.get("timeframe_label") or primary_technical_label,
            },
            "capital_flow": {
                "score": fund_summary.get("score"),
                "rating": fund_summary.get("rating"),
                "source": fund_summary.get("source"),
                "summary": first_non_empty(fund_summary.get("comment"), (fund_payload.get("scorecard") or {}).get("combined_comment")),
            },
        },
        "cover_chart": {"timeframe": primary_technical_timeframe, "path": f"stocks/{holding.symbol}/{cover_chart_path}"} if cover_chart_path else None,
        "jump": {"detail": f"stocks/{holding.symbol}/detail.json"},
        "tags": [value for value in [group_item.get("bucket") if group_item else None, group_item.get("priority") if group_item else None, group_item.get("action") if group_item else None] if value],
    }


def build_detail_payload(
    holding: Holding,
    stock_dir: Path,
    group_item: dict[str, Any] | None,
    publish_timeframes: tuple[str, ...] | None = None,
    include_chart_images: bool = True,
    fallback_detail_payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    base_payload = read_json_if_exists(stock_dir / "base.json")
    fund_payload = read_json_if_exists(stock_dir / "fund.json")
    primary_technical_timeframe, tech_payload = resolve_primary_technical_payload(stock_dir)
    charts = build_chart_specs(stock_dir, publish_timeframes=publish_timeframes, include_chart_images=include_chart_images)
    fundamental = build_fundamental_section(base_payload)
    technical_sections = build_timeframe_technical_sections(
        stock_dir,
        DETAIL_TECHNICAL_TIMEFRAMES,
        primary_timeframe=primary_technical_timeframe,
    )
    technical_sections = merge_technical_sections_with_fallback(technical_sections, fallback_detail_payload)
    technical = next((section for section in technical_sections if section.get("key") == "technical"), None) or build_technical_section(tech_payload)
    segment_stop_line = (
        build_latest_segment_stop_reason_line(stock_dir, primary_technical_timeframe, tech_payload)
        if tech_payload
        else ""
    )
    segment_tail_interpretations = (
        build_segment_tail_interpretations_payload(stock_dir, primary_technical_timeframe, tech_payload)
        if tech_payload
        else []
    )
    segment_reclaim_line = build_latest_segment_reclaim_line(segment_tail_interpretations, primary_technical_timeframe)
    if segment_stop_line:
        technical_focus_lines = list(technical.get("technical_focus_lines") or [])
        technical_focus_lines.append(segment_stop_line)
        technical["technical_focus_lines"] = technical_focus_lines
    if segment_reclaim_line:
        technical_focus_lines = list(technical.get("technical_focus_lines") or [])
        technical_focus_lines.append(segment_reclaim_line)
        technical["technical_focus_lines"] = technical_focus_lines
    technical["segment_tail_interpretations"] = segment_tail_interpretations
    capital_flow = build_capital_flow_section(fund_payload)
    technical_timeframe = safe_text(technical.get("timeframe")) or primary_technical_timeframe
    technical_label = TIMEFRAME_LABELS.get(technical_timeframe, technical_timeframe.upper())
    overview_bullets = [
        f"基本面 {safe_text(fundamental.get('score'), 'missing')}/{safe_text(fundamental.get('rating'), 'missing')}",
        f"{technical_label} 技术面 {safe_text(technical.get('conclusion'), 'missing')}",
    ]
    transition_overview_bullet = build_transition_overview_bullet(technical)
    if transition_overview_bullet:
        overview_bullets.append(transition_overview_bullet)
    overview_bullets.append(f"资金面 {safe_text(capital_flow.get('score'), 'missing')}/{safe_text(capital_flow.get('rating'), 'missing')}")
    updated_at = max(
        safe_text(base_payload.get("generated_at")),
        safe_text(fund_payload.get("generated_at")),
        latest_generated_technical_at(stock_dir),
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
                "path": (f"stocks/{holding.symbol}/{chart['relative_path']}" if chart.get("relative_path") else None),
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
        if chart.get("source_path") and chart.get("relative_path"):
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
                **build_transition_summary_fields(((item.get("cards") or {}).get("technical") or {})),
                "tags": item.get("tags", []),
            }
            for item in ordered
        ],
    }


def ensure_clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def prepare_staging_dir(path: Path) -> Path:
    if path.exists():
        shutil.rmtree(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


def finalize_staging_dir(staging_path: Path, target_path: Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        shutil.rmtree(target_path)
    shutil.move(str(staging_path), str(target_path))


def collect_bundle_integrity(bundle_dir: Path) -> dict[str, Any]:
    stocks_dir = bundle_dir / "stocks"
    stock_dirs = sorted(item for item in stocks_dir.iterdir() if item.is_dir()) if stocks_dir.exists() else []
    return {
        "bundle_dir": str(bundle_dir),
        "index_present": (bundle_dir / "index.json").exists(),
        "portfolio_group_present": (bundle_dir / "groups" / "portfolio.json").exists(),
        "a_share_group_present": (bundle_dir / "groups" / "a_share.json").exists(),
        "h_share_group_present": (bundle_dir / "groups" / "h_share.json").exists(),
        "alerts_present": (bundle_dir / "alerts" / "missing_artifacts.json").exists(),
        "stock_dir_count": len(stock_dirs),
        "summary_json_count": sum(1 for stock_dir in stock_dirs if (stock_dir / "summary.json").exists()),
        "detail_json_count": sum(1 for stock_dir in stock_dirs if (stock_dir / "detail.json").exists()),
        "base_json_count": sum(1 for stock_dir in stock_dirs if (stock_dir / "base.json").exists()),
    }


def generate_bundle(
    holdings_path: Path,
    reports_root: Path,
    publish_root: Path,
    snapshot_stamp: str | None,
    latest_only: bool,
    publish_timeframes: tuple[str, ...] | None = None,
    include_chart_images: bool = True,
    expected_tech_timeframes: tuple[str, ...] | None = None,
    skip_regenerate_context: bool = False,
    skip_gen_fund_context: bool = False,
    failed_symbols: set[str] | None = None,
) -> dict[str, Any]:
    stamp = snapshot_stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    latest_dir = publish_root / "latest"
    snapshot_dir = publish_root / "snapshots" / stamp
    staging_root = publish_root / ".staging"
    meta_dir = reports_root / "_meta"
    holdings = load_holdings(holdings_path)
    previous_stock_payloads = load_previous_publish_stock_payloads(latest_dir)
    group_payloads = load_group_payloads(meta_dir)
    group_item_map = collect_group_item_map(group_payloads)

    target_pairs: list[tuple[Path, Path]] = []
    latest_staging_dir = prepare_staging_dir(staging_root / f"latest_{stamp}")
    target_pairs.append((latest_staging_dir, latest_dir))
    if not latest_only:
        snapshot_staging_dir = prepare_staging_dir(staging_root / f"snapshot_{stamp}")
        target_pairs.append((snapshot_staging_dir, snapshot_dir))

    staging_targets = [staging for staging, _ in target_pairs]

    summary_payloads: list[dict[str, Any]] = []
    missing_alerts: list[dict[str, Any]] = []
    failed_symbol_set = failed_symbols or set()
    try:
        for holding in holdings:
            stock_dir = reports_root / holding.symbol
            if not stock_dir.exists():
                continue
            missing_alerts.extend(
                collect_missing_artifact_alerts(
                    holding=holding,
                    stock_dir=stock_dir,
                    expected_tech_timeframes=expected_tech_timeframes,
                    skip_regenerate_context=skip_regenerate_context,
                    skip_gen_fund_context=skip_gen_fund_context,
                    failed_symbols=failed_symbol_set,
                )
            )
            base_source_path = stock_dir / "base.json"
            summary_payload = build_summary_payload(
                holding,
                stock_dir,
                group_item_map.get(holding.symbol),
                publish_timeframes=publish_timeframes,
                include_chart_images=include_chart_images,
                fallback_summary_payload=(previous_stock_payloads.get(holding.symbol) or {}).get("summary"),
            )
            detail_payload, chart_specs = build_detail_payload(
                holding,
                stock_dir,
                group_item_map.get(holding.symbol),
                publish_timeframes=publish_timeframes,
                include_chart_images=include_chart_images,
                fallback_detail_payload=(previous_stock_payloads.get(holding.symbol) or {}).get("detail"),
            )
            summary_payloads.append(summary_payload)
            for target in staging_targets:
                stock_target_dir = target / "stocks" / holding.symbol
                copy_optional_json_asset(base_source_path, stock_target_dir / "base.json")
                write_json(stock_target_dir / "summary.json", summary_payload)
                write_json(stock_target_dir / "detail.json", detail_payload)
                copy_chart_assets(chart_specs, stock_target_dir)

        portfolio_payload = build_portfolio_group(summary_payloads, group_item_map)
        generated_at = datetime.now().isoformat(timespec="seconds")
        index_payload = build_index_payload(summary_payloads, generated_at)
        missing_payload = build_missing_artifacts_payload(
            alerts=missing_alerts,
            expected_tech_timeframes=expected_tech_timeframes,
            skip_regenerate_context=skip_regenerate_context,
            skip_gen_fund_context=skip_gen_fund_context,
            failed_symbols=failed_symbol_set,
        )
        for target in staging_targets:
            write_json(target / "index.json", index_payload)
            if "a_share" in group_payloads:
                write_json(target / "groups" / "a_share.json", group_payloads["a_share"])
            if "h_share" in group_payloads:
                write_json(target / "groups" / "h_share.json", group_payloads["h_share"])
            write_json(target / "groups" / "portfolio.json", portfolio_payload)
            write_json(target / "alerts" / "missing_artifacts.json", missing_payload)

        for staging_path, target_path in target_pairs:
            finalize_staging_dir(staging_path, target_path)
    except Exception:
        for staging_path, _ in target_pairs:
            if staging_path.exists():
                shutil.rmtree(staging_path, ignore_errors=True)
        raise

    if missing_alerts:
        print(f"WARN missing_artifacts={len(missing_alerts)} affected_symbols={missing_payload['counts']['affected_symbols']}")
        for item in missing_alerts[:30]:
            timeframe = f"/{item['timeframe']}" if item.get("timeframe") else ""
            print(f"WARN {item['symbol']}{timeframe} {item['kind']} reason={item['reason']}")

    latest_integrity = collect_bundle_integrity(latest_dir)
    snapshot_integrity = collect_bundle_integrity(snapshot_dir) if not latest_only else None

    return {
        "latest": latest_dir,
        "snapshot": snapshot_dir,
        "missing_artifact_alert_count": len(missing_alerts),
        "missing_artifact_alert_path": latest_dir / "alerts" / "missing_artifacts.json",
        "bundle_integrity": latest_integrity,
        "snapshot_bundle_integrity": snapshot_integrity,
    }


def main() -> None:
    global ACTIVE_SEGMENT_BOOTSTRAP_MODE
    global ACTIVE_STRICT_SEGMENT_RULES

    args = parse_args()
    ACTIVE_SEGMENT_BOOTSTRAP_MODE = str(args.segment_bootstrap_mode)
    ACTIVE_STRICT_SEGMENT_RULES = bool(args.strict_segment_rules)
    outputs = generate_bundle(
        holdings_path=Path(args.holdings_file),
        reports_root=Path(args.reports_root),
        publish_root=Path(args.publish_root),
        snapshot_stamp=args.snapshot_stamp,
        latest_only=args.latest_only,
        publish_timeframes=tuple(args.publish_timeframes) if args.publish_timeframes else None,
        include_chart_images=not bool(args.publish_json_only),
        expected_tech_timeframes=tuple(args.expected_tech_timeframes) if args.expected_tech_timeframes else None,
        skip_regenerate_context=args.skip_regenerate_context,
        skip_gen_fund_context=args.skip_gen_fund_context,
        failed_symbols=set(args.failed_symbols or []),
    )
    print(f"latest= {outputs['latest']}")
    print(f"missing_artifact_alert_count= {outputs['missing_artifact_alert_count']}")
    print(f"missing_artifact_alert_path= {outputs['missing_artifact_alert_path']}")
    if not args.latest_only:
        print(f"snapshot= {outputs['snapshot']}")


if __name__ == "__main__":
    main()