from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import Bar, Bi, Zhongshu
from .zhongshu_contract import (
    CONSUMPTION_LEVEL_LABELS,
    CONSUMPTION_LEVEL_NOTES,
    TRANSITION_STATE_LABELS,
    TRANSITION_STATE_NOTES,
)
from .analysis_contract import (
    SIGNAL_BASIS_LABELS,
    SIGNAL_POINT_LABELS,
    STRUCTURE_STATUS_LABELS,
    STRUCTURE_STATUS_NOTES,
)


# 注：transition_state / consumption_level 的 label/note 字典已迁移到
# `zhongshu_contract.py`；signal_point / signal_basis / structure_status 的
# label/note 字典已迁移到 `analysis_contract.py`。两者都是 SDD 唯一事实源，
# 本模块从契约模块导入，不再维护第二份拷贝。见 tests/test_zhongshu_contract.py
# 与 tests/test_analysis_contract.py。


def compute_bi_strengths(bis: list[Bi], macd_points: list[Any]) -> dict[int, dict[str, float]]:
    strengths: dict[int, dict[str, float]] = {}
    for bi in bis:
        segment = [point for point in macd_points if bi.start_ts <= point.ts <= bi.end_ts]
        if not segment:
            continue
        strengths[bi.bi_id] = {
            "macd_sum_abs": sum(abs(point.macd) for point in segment),
            "dif_max": max(point.dif for point in segment),
            "dif_min": min(point.dif for point in segment),
        }
    return strengths


def _isoformat_ts(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).isoformat(timespec="seconds")
        except ValueError:
            return value
    return value.isoformat(timespec="seconds")


def _format_signal_point_name(point: str) -> str:
    return point.replace("_", "")


def format_signal_point_label(point: str) -> str:
    normalized = point if point in SIGNAL_POINT_LABELS else point.replace("buy", "buy_").replace("sell", "sell_")
    return SIGNAL_POINT_LABELS.get(normalized, point)


def format_signal_point_labels(points: list[str]) -> list[str]:
    return [format_signal_point_label(point) for point in points]


def format_structure_status_label(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return STRUCTURE_STATUS_LABELS.get(str(value), str(value))


def describe_structure_status(value: Any) -> str:
    return STRUCTURE_STATUS_NOTES.get(str(value or ""), "")


def format_transition_state_label(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return TRANSITION_STATE_LABELS.get(str(value), str(value))


def describe_transition_state(value: Any) -> str:
    return TRANSITION_STATE_NOTES.get(str(value or ""), "")


def format_consumption_level_label(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return CONSUMPTION_LEVEL_LABELS.get(str(value), str(value))


def describe_consumption_level(value: Any) -> str:
    return CONSUMPTION_LEVEL_NOTES.get(str(value or ""), "")


def describe_reabsorbed_zhongshu_debug(zhongshus: list[Any], current_zs: Any | None) -> str:
    if current_zs is None:
        return ""
    latest_zs_id = getattr(current_zs, "zs_id", None)
    if latest_zs_id is None:
        return ""

    predecessor = next(
        (
            item
            for item in reversed(zhongshus[:-1])
            if getattr(item, "superseded_by_zs_id", None) == latest_zs_id
            and bool(getattr(item, "is_reabsorbed_by_larger_expansion", False))
        ),
        None,
    )
    if predecessor is None:
        return ""

    previous_zs_id = getattr(predecessor, "zs_id", None)
    previous_exit_bi_id = getattr(predecessor, "exit_bi_id", None)
    current_entering_bi_id = getattr(current_zs, "entering_bi_id", None)
    return (
        f"重写说明：前一中枢 ZS{previous_zs_id} 虽已走出，"
        f"但其走出笔 {previous_exit_bi_id} 被当前中枢 ZS{latest_zs_id} 复用为进入笔 {current_entering_bi_id}，"
        "当前按更大级别扩展吸收处理。"
    )


def describe_signal_entry(entry: dict[str, object]) -> str:
    point = format_signal_point_label(str(entry.get("point") or ""))
    basis = SIGNAL_BASIS_LABELS.get(str(entry.get("basis") or ""))
    price = entry.get("price")
    related_zs_id = entry.get("related_zs_id")

    fragments = [point]
    if basis:
        fragments.append(basis)
    if price is not None:
        fragments.append(f"参考价 {float(price):.2f}")
    if related_zs_id is not None:
        fragments.append(f"关联中枢 ZS{related_zs_id}")
    return "，".join(fragments)


def build_signal_explanation_lines(signals: dict[str, object]) -> list[str]:
    explanations: list[str] = []
    for entry in signals.get("signal_points", []):
        if entry.get("active"):
            explanations.append(describe_signal_entry(entry))
    return explanations


def _find_recent_confirmed_bis_by_direction(
    confirmed_bis: list[Bi],
    *,
    direction: str,
    limit: int,
) -> list[Bi]:
    matches: list[Bi] = []
    for bi in reversed(confirmed_bis):
        if direction == "up" and bi.is_up():
            matches.append(bi)
        elif direction == "down" and bi.is_down():
            matches.append(bi)
        if len(matches) == limit:
            break
    return matches


def _has_top_divergence(candidate: Bi | None, previous: Bi | None, strengths: dict[int, dict[str, float]]) -> bool:
    if candidate is None or previous is None:
        return False
    candidate_strength = strengths.get(candidate.bi_id, {})
    previous_strength = strengths.get(previous.bi_id, {})
    return candidate.high > previous.high and candidate_strength.get("macd_sum_abs", 0.0) < previous_strength.get(
        "macd_sum_abs", 0.0
    )


def _has_bottom_divergence(candidate: Bi | None, previous: Bi | None, strengths: dict[int, dict[str, float]]) -> bool:
    if candidate is None or previous is None:
        return False
    candidate_strength = strengths.get(candidate.bi_id, {})
    previous_strength = strengths.get(previous.bi_id, {})
    return candidate.low < previous.low and candidate_strength.get("macd_sum_abs", 0.0) < previous_strength.get(
        "macd_sum_abs", 0.0
    )


def _has_reverse_turn_after(signal_bi: Bi | None, *, direction: str, bis: list[Bi]) -> bool:
    if signal_bi is None:
        return False
    signal_id = signal_bi.bi_id
    for candidate in bis:
        if candidate.bi_id <= signal_id or not candidate.is_confirmed:
            continue
        if direction == "down" and candidate.is_up() and candidate.low >= signal_bi.low:
            return True
        if direction == "up" and candidate.is_down() and candidate.high <= signal_bi.high:
            return True
    return False


def _is_first_reverse_hold(anchor: Bi, candidate: Bi, bis: list[Bi]) -> bool:
    """candidate 是否是 anchor 之后第一个「不破 anchor 极值」的反向 bi。

    用于二类点「首次回抽锁定」：二类点只能建立在第一类点之后的第一次确认性回抽上，
    后续再次回抽即使同样不破前低 / 前高，也不得重复标记为二类点。
    """
    for other in bis:
        if other.bi_id <= anchor.bi_id or other.bi_id >= candidate.bi_id:
            continue
        if anchor.is_down():
            # 一买锚点是向下的笔；反向 bi 是向下回抽，须不破前低
            if other.is_down() and other.low > anchor.low:
                return False
        else:
            # 一卖锚点是向上的笔；反向 bi 是向上反抽，须不破前高
            if other.is_up() and other.high < anchor.high:
                return False
    return True


def _build_signal_point_detail(
    point: str,
    signal_bi: Bi | None,
    price: float | None,
    *,
    active: bool,
    basis: str | None,
    related_zs_id: int | None,
    related_bi_ids: list[int] | None,
) -> dict[str, object]:
    return {
        "point": _format_signal_point_name(point),
        "active": active,
        "signal_bi_id": signal_bi.bi_id if signal_bi else None,
        "time": _isoformat_ts(signal_bi.end_ts) if signal_bi else None,
        "price": round(float(price), 2) if price is not None else None,
        "basis": basis if active else None,
        "related_zs_id": related_zs_id if active else None,
        "related_bi_ids": list(related_bi_ids or []) if active else [],
    }


def _relation_kind(previous: Zhongshu, current: Zhongshu) -> str:
    if current.zs_low > previous.zs_high:
        return "up"
    if current.zs_high < previous.zs_low:
        return "down"
    return "range"


def _build_group_state(
    zhongshus: list[Zhongshu],
    start_index: int,
    end_index: int,
    *,
    status: str,
    latest_ts: datetime | None,
    confirmation_basis: str,
) -> dict[str, object]:
    group = zhongshus[start_index : end_index + 1]
    group_type = "range"
    if len(group) >= 2:
        group_type = _relation_kind(group[0], group[1])
    return {
        "type": group_type,
        "status": status,
        "start_ts": _isoformat_ts(group[0].start_ts),
        "end_ts": _isoformat_ts(group[-1].end_ts) if status != "ongoing" else None,
        "latest_ts": _isoformat_ts(latest_ts or group[-1].end_ts),
        "zs_count": len(group),
        "zs_count_so_far": len(group),
        "confirmation_basis": confirmation_basis,
        "start_zs_id": group[0].zs_id,
        "end_zs_id": group[-1].zs_id,
    }


def _is_reabsorbed_tail(zhongshu: Zhongshu) -> bool:
    return bool(
        getattr(zhongshu, "is_reabsorbed_by_larger_expansion", False)
        or getattr(zhongshu, "superseded_by_zs_id", None) is not None
    )


def _is_live_zhongshu(zhongshu: Zhongshu) -> bool:
    return getattr(zhongshu, "superseded_by_zs_id", None) is None and not getattr(
        zhongshu, "is_reabsorbed_by_larger_expansion", False
    )


def _split_live_zhongshu_runs(zhongshus: list[Zhongshu]) -> list[list[Zhongshu]]:
    runs: list[list[Zhongshu]] = []
    current_run: list[Zhongshu] = []
    for zhongshu in zhongshus:
        if _is_live_zhongshu(zhongshu):
            current_run.append(zhongshu)
            continue
        if current_run:
            runs.append(current_run)
            current_run = []
    if current_run:
        runs.append(current_run)
    return runs


def _build_completed_run_state(zhongshus: list[Zhongshu]) -> dict[str, object]:
    return _build_group_state(
        zhongshus,
        0,
        len(zhongshus) - 1,
        status="completed",
        latest_ts=zhongshus[-1].end_ts,
        confirmation_basis="confirmed_by_following_same_level_structure",
    )


def _completed_run_type_entries(live_runs: list[list[Zhongshu]]) -> list[dict[str, object]]:
    """把当前 run 之前的所有 run 折叠成 completed 类型链条目（run 粒度）。"""
    entries: list[dict[str, object]] = []
    for run in live_runs[:-1]:
        group_type = "range" if len(run) < 2 else _relation_kind(run[0], run[1])
        entries.append(
            {
                "type": group_type,
                "status": "completed",
                "zs_count": len(run),
                "start_zs_id": run[0].zs_id,
                "end_zs_id": run[-1].zs_id,
            }
        )
    return entries


def _group_type_chain_entry(group: dict[str, object]) -> dict[str, object]:
    """把 `_build_group_state(...)` 产出的 group 快照转成类型链条目。"""
    return {
        "type": group.get("type"),
        "status": group.get("status"),
        "zs_count": group.get("zs_count") if group.get("zs_count") is not None else group.get("zs_count_so_far"),
        "start_zs_id": group.get("start_zs_id"),
        "end_zs_id": group.get("end_zs_id"),
    }


def _find_reabsorbed_tail_before_current(zhongshus: list[Zhongshu], current: Zhongshu | None) -> Zhongshu | None:
    if current is None:
        return None
    target_id = getattr(current, "zs_id", None)
    if target_id is None:
        return None
    for item in reversed(zhongshus):
        if item is current:
            continue
        if getattr(item, "superseded_by_zs_id", None) != target_id:
            continue
        if getattr(item, "is_reabsorbed_by_larger_expansion", False):
            return item
    return None


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _recent_local_zs_band(raw_bars: list[Bar], *, lookback: int = 20) -> tuple[float, float] | None:
    if not raw_bars:
        return None
    window = raw_bars[-lookback:]
    lows: list[float] = []
    highs: list[float] = []
    for bar in window:
        close_value = _safe_float(getattr(bar, "close", None))
        low_value = _safe_float(getattr(bar, "low", None))
        high_value = _safe_float(getattr(bar, "high", None))
        if close_value is not None:
            lows.append(close_value)
            highs.append(close_value)
        if low_value is not None:
            lows.append(low_value)
        if high_value is not None:
            highs.append(high_value)
    if not lows or not highs:
        return None
    return min(lows), max(highs)


def _build_zs_monitor_state(
    raw_bars: list[Bar],
    current_zs: Zhongshu | None,
    *,
    buy_points: list[str],
    sell_points: list[str],
) -> dict[str, object]:
    if not raw_bars:
        return {
            "zs_monitor_midline": None,
            "zs_monitor_bias": None,
            "zs_monitor_alert": "none",
        }

    alert = "none"
    latest_close = _safe_float(getattr(raw_bars[-1], "close", None))
    if latest_close is None:
        return {
            "zs_monitor_midline": None,
            "zs_monitor_bias": None,
            "zs_monitor_alert": "none",
        }

    if current_zs is not None:
        zs_low = _safe_float(getattr(current_zs, "zs_low", None))
        zs_high = _safe_float(getattr(current_zs, "zs_high", None))
        if zs_low is None or zs_high is None:
            return {
                "zs_monitor_midline": None,
                "zs_monitor_bias": None,
                "zs_monitor_alert": "none",
            }
    else:
        fallback_band = _recent_local_zs_band(raw_bars)
        if fallback_band is None:
            return {
                "zs_monitor_midline": None,
                "zs_monitor_bias": None,
                "zs_monitor_alert": "none",
            }
        zs_low, zs_high = fallback_band

    width = zs_high - zs_low
    if width <= 0:
        return {
            "zs_monitor_midline": None,
            "zs_monitor_bias": None,
            "zs_monitor_alert": "none",
        }

    midline = round((zs_low + zs_high) / 2.0, 2)
    bias_threshold = max(width * 0.1, 1e-9)
    if latest_close >= ((zs_low + zs_high) / 2.0) + bias_threshold:
        bias = "strong"
    elif latest_close <= ((zs_low + zs_high) / 2.0) - bias_threshold:
        bias = "weak"
    else:
        bias = "neutral"

    if latest_close > zs_high:
        return {
            "zs_monitor_midline": midline,
            "zs_monitor_bias": bias,
            "zs_monitor_alert": "pre_breakout",
        }
    if latest_close < zs_low:
        return {
            "zs_monitor_midline": midline,
            "zs_monitor_bias": bias,
            "zs_monitor_alert": "pre_breakdown",
        }

    trigger_band = max(width * 0.2, 1e-9)
    if latest_close >= zs_high - trigger_band:
        alert = "pre_breakout"
    elif latest_close <= zs_low + trigger_band:
        alert = "pre_breakdown"

    return {
        "zs_monitor_midline": midline,
        "zs_monitor_bias": bias,
        "zs_monitor_alert": alert,
    }


def _build_same_level_decomposition_mode(structure_state: dict[str, object]) -> str:
    current_status = str(structure_state.get("current_structure_status") or "").strip()
    current_ongoing = structure_state.get("current_ongoing") or {}
    confirmation_basis = str(current_ongoing.get("confirmation_basis") or "").strip()

    if current_status == "candidate_completed_waiting_stability":
        return "dual_interpretation_pending"
    if confirmation_basis in {"no_same_level_zhongshu", "single_active_zhongshu"}:
        return "dual_interpretation_pending"
    return "single_confirmed"


def _build_same_level_consumption_level(structure_state: dict[str, object]) -> str:
    current_status = str(structure_state.get("current_structure_status") or "").strip()
    current_ongoing = structure_state.get("current_ongoing") or {}
    confirmation_basis = str(current_ongoing.get("confirmation_basis") or "").strip()

    if confirmation_basis == "no_same_level_zhongshu":
        return "auxiliary"
    if current_status == "candidate_completed_waiting_stability":
        return "pending"
    if confirmation_basis == "single_active_zhongshu":
        return "pending"
    return "confirmed"


def _build_post_divergence_route(
    structure_state: dict[str, object],
    divergence: dict[str, object],
    *,
    top_divergence: bool,
    bottom_divergence: bool,
) -> str | None:
    # spec_id: SPEC.TREND_DIVERGENCE.CORE（见 docs/chanlun/trend-divergence-spec.md）
    ongoing = structure_state.get("current_ongoing") or {}
    confirmation_basis = str(ongoing.get("confirmation_basis") or "").strip()
    trend = divergence.get("trend") or {}
    range_divergence = divergence.get("range") or {}

    if trend.get("strict"):
        return "higher_level_reverse_trend"
    if range_divergence.get("strict"):
        return "higher_level_range"
    if top_divergence or bottom_divergence or confirmation_basis == "still_inside_last_zs_extension":
        return "last_zs_extension"
    return None


def _build_oscillation_rhythm_state(
    current_zs: Zhongshu | None,
    confirmed_bis: list[Bi],
    strengths: dict[int, dict[str, float]],
) -> str:
    if current_zs is None:
        return "pending"
    latest_confirmed = confirmed_bis[-1] if confirmed_bis else None
    if latest_confirmed is None:
        return "pending"

    direction = "up" if latest_confirmed.is_up() else "down"
    recent_same_direction = _find_recent_confirmed_bis_by_direction(confirmed_bis, direction=direction, limit=2)
    if len(recent_same_direction) < 2:
        return "pending"

    latest_same_direction = recent_same_direction[0]
    previous_same_direction = recent_same_direction[1]
    latest_strength = _safe_float((strengths.get(latest_same_direction.bi_id) or {}).get("macd_sum_abs"))
    previous_strength = _safe_float((strengths.get(previous_same_direction.bi_id) or {}).get("macd_sum_abs"))
    if latest_strength is None or previous_strength is None or previous_strength <= 0:
        return "pending"

    ratio = latest_strength / previous_strength
    if ratio >= 1.1:
        return "up_bias" if direction == "up" else "down_bias"
    if ratio <= 0.9:
        return "down_bias" if direction == "up" else "up_bias"
    return "balanced"


def build_structure_state(raw_bars: list[Bar], zhongshus: list[Zhongshu]) -> dict[str, object]:
    # spec_id: SPEC.TREND_DIVERGENCE.CORE（见 docs/chanlun/trend-divergence-spec.md）
    latest_bar_ts = raw_bars[-1].ts if raw_bars else None
    live_runs = _split_live_zhongshu_runs(zhongshus)

    if not live_runs:
        return {
            "last_completed": None,
            "current_ongoing": {
                "type": "unknown",
                "status": "ongoing",
                "start_ts": _isoformat_ts(raw_bars[0].ts) if raw_bars else None,
                "latest_ts": _isoformat_ts(latest_bar_ts),
                "zs_count_so_far": 0,
                "confirmation_basis": "no_same_level_zhongshu",
            },
            "relationship": {
                "kind": "undetermined",
                "transition_state": "none",
                "note": "当前尚未形成可用于同级别走势分解的中枢。",
            },
            "current_structure_status": "ongoing_same_type",
            "consumption_level": "auxiliary",
            "type_chain": [],
        }

    current_run = live_runs[-1]
    previous_run = live_runs[-2] if len(live_runs) > 1 else None

    if len(current_run) == 1:
        only = current_run[0]
        reabsorbed_tail = _find_reabsorbed_tail_before_current(zhongshus, only)
        last_completed = None
        current_group_type = "range"
        if previous_run and not (reabsorbed_tail is not None and max(reabsorbed_tail.zs_low, only.zs_low) < min(reabsorbed_tail.zs_high, only.zs_high)):
            last_completed = _build_completed_run_state(previous_run)
        if reabsorbed_tail is not None and max(reabsorbed_tail.zs_low, only.zs_low) < min(reabsorbed_tail.zs_high, only.zs_high):
            current_group_type = _relation_kind(previous_run[-1], only) if previous_run else "range"
        relationship_kind = "undetermined"
        transition_state = "none"
        relationship_note = "当前只有一个同级别中枢，按工程口径先视为盘整进行中。"
        current_structure_status = "ongoing_same_type"
        if last_completed is not None:
            relationship_kind = "completed_then_new_type_ongoing"
            transition_state = "candidate_new_type"
            relationship_note = "上一段同级别走势已结束，当前新的同级别走势仍处候选待确认阶段。"
            current_structure_status = "candidate_completed_waiting_stability"
        return {
            "last_completed": last_completed,
            "current_ongoing": {
                "type": current_group_type,
                "status": "ongoing",
                "start_ts": _isoformat_ts(only.start_ts),
                "latest_ts": _isoformat_ts(latest_bar_ts or only.end_ts),
                "zs_count_so_far": 1,
                "confirmation_basis": "single_active_zhongshu",
                "start_zs_id": only.zs_id,
                "end_zs_id": only.zs_id,
            },
            "relationship": {
                "kind": relationship_kind,
                "transition_state": transition_state,
                "note": relationship_note,
            },
            "current_structure_status": current_structure_status,
            "consumption_level": "pending",
            "type_chain": _completed_run_type_entries(live_runs)
            + [
                {
                    "type": current_group_type,
                    "status": "ongoing",
                    "zs_count": 1,
                    "start_zs_id": only.zs_id,
                    "end_zs_id": only.zs_id,
                }
            ],
        }

    relations = [_relation_kind(previous, current) for previous, current in zip(current_run, current_run[1:])]
    current_kind = relations[-1]
    current_start_relation = len(relations) - 1
    while current_start_relation > 0 and relations[current_start_relation - 1] == current_kind:
        current_start_relation -= 1
    current_start_index = current_start_relation
    if current_kind == "range" and current_start_relation > 0:
        previous_run_kind = relations[current_start_relation - 1]
        previous_tail = current_run[-2]
        previous_tail_is_same_type_extension = not bool(getattr(previous_tail, "is_terminated", False)) or _is_reabsorbed_tail(previous_tail)
        if previous_run_kind in {"up", "down"} and previous_tail_is_same_type_extension:
            while current_start_relation > 1 and relations[current_start_relation - 2] == previous_run_kind:
                current_start_relation -= 1
            current_start_index = current_start_relation - 1
            current_kind = previous_run_kind
        else:
            # When a new overlap suffix appears after a finished up/down run,
            # treat the latest zhongshu as the start of the new ongoing range.
            current_start_index = current_start_relation + 1
    current_group_count = len(current_run) - current_start_index
    current_ongoing = _build_group_state(
        current_run,
        current_start_index,
        len(current_run) - 1,
        status="ongoing",
        latest_ts=latest_bar_ts,
        confirmation_basis=(
            "forming_next_same_level_zhongshu"
            if current_kind in {"up", "down"}
            else ("single_active_zhongshu" if current_group_count == 1 else "still_inside_last_zs_extension")
        ),
    )

    last_completed = None
    if current_start_index > 0:
        previous_end_index = current_start_index - 1
        previous_start_index = previous_end_index
        if previous_end_index > 0:
            previous_kind = relations[previous_end_index - 1]
            while previous_start_index > 0 and relations[previous_start_index - 1] == previous_kind:
                previous_start_index -= 1
        last_completed = _build_group_state(
            current_run,
            previous_start_index,
            previous_end_index,
            status="completed",
            latest_ts=current_run[previous_end_index].end_ts,
            confirmation_basis="confirmed_by_following_same_level_structure",
        )
    elif previous_run is not None:
        last_completed = _build_completed_run_state(previous_run)

    relationship_kind = "undetermined"
    transition_state = "none"
    relationship_note = "当前同级别结构仍在演化，尚不能把新旧走势关系完全定型。"
    current_structure_status = "ongoing_same_type"
    if last_completed is not None:
        if str(last_completed.get("type")) == str(current_ongoing.get("type")):
            relationship_kind = "same_type_extension"
            transition_state = "same_type_extension"
            relationship_note = "当前结构更接近前一走势类型的同类延伸，暂未看到清晰的新类型完成边界。"
            current_structure_status = "ongoing_same_type"
        else:
            relationship_kind = "completed_then_new_type_ongoing"
            transition_state = (
                "candidate_new_type"
                if current_ongoing.get("confirmation_basis") == "single_active_zhongshu"
                else "ongoing_new_type"
            )
            relationship_note = "上一段同级别走势已结束，当前正在运行的是新的同级别走势类型。"
            current_structure_status = (
                "candidate_completed_waiting_stability"
                if current_ongoing.get("confirmation_basis") == "single_active_zhongshu"
                else "completed_then_new_type"
            )
    elif current_kind in {"up", "down"}:
        relationship_note = "已经出现同向不重叠中枢推进，当前按工程口径视为趋势进行中。"
        current_structure_status = "ongoing_same_type"
    else:
        relationship_note = "当前主要围绕最近同级别中枢展开，按工程口径视为盘整进行中。"
        current_structure_status = "ongoing_same_type"

    consumption_level = _build_same_level_consumption_level(
        {
            "current_ongoing": current_ongoing,
            "current_structure_status": current_structure_status,
        }
    )

    type_chain = _completed_run_type_entries(live_runs)
    if last_completed is not None:
        type_chain.append(_group_type_chain_entry(last_completed))
    type_chain.append(_group_type_chain_entry(current_ongoing))

    return {
        "last_completed": last_completed,
        "current_ongoing": current_ongoing,
        "relationship": {
            "kind": relationship_kind,
            "transition_state": transition_state,
            "note": relationship_note,
        },
        "current_structure_status": current_structure_status,
        "consumption_level": consumption_level,
        "type_chain": type_chain,
    }


def _build_strength_comparison(
    candidate: Bi | None,
    reference: Bi | None,
    strengths: dict[int, dict[str, float]],
) -> dict[str, object] | None:
    if candidate is None or reference is None:
        return None
    candidate_strength = strengths.get(candidate.bi_id, {}).get("macd_sum_abs", 0.0)
    reference_strength = strengths.get(reference.bi_id, {}).get("macd_sum_abs", 0.0)
    return {
        "candidate_bi_id": candidate.bi_id,
        "candidate_strength": round(float(candidate_strength), 4),
        "reference_bi_id": reference.bi_id,
        "reference_strength": round(float(reference_strength), 4),
        "decayed": candidate_strength < reference_strength,
    }


def build_divergence_state(
    structure_state: dict[str, object],
    *,
    top_divergence: bool,
    bottom_divergence: bool,
    latest_confirmed_up: Bi | None,
    latest_down: Bi | None,
    previous_confirmed_up: Bi | None = None,
    previous_confirmed_down: Bi | None = None,
    strengths: dict[int, dict[str, float]] | None = None,
    current_zs: Zhongshu | None = None,
) -> dict[str, object]:
    strengths = strengths or {}
    ongoing = structure_state.get("current_ongoing") or {}
    ongoing_type = ongoing.get("type")

    trend_active = False
    trend_direction = None
    trend_signal_bi = None
    trend_reference_bi = None
    if ongoing_type == "up" and top_divergence:
        trend_active = True
        trend_direction = "up"
        trend_signal_bi = latest_confirmed_up
        trend_reference_bi = previous_confirmed_up
    elif ongoing_type == "down" and bottom_divergence:
        trend_active = True
        trend_direction = "down"
        trend_signal_bi = latest_down
        trend_reference_bi = previous_confirmed_down

    range_active = False
    range_direction = None
    range_signal_bi = None
    range_reference_bi = None
    if ongoing_type == "range":
        if top_divergence:
            range_active = True
            range_direction = "up"
            range_signal_bi = latest_confirmed_up
            range_reference_bi = previous_confirmed_up
        elif bottom_divergence:
            range_active = True
            range_direction = "down"
            range_signal_bi = latest_down
            range_reference_bi = previous_confirmed_down

    reference_zs_id = current_zs.zs_id if current_zs is not None else None

    def _departure_confirmed(signal_bi: Bi | None, direction: str | None) -> bool:
        if current_zs is None or signal_bi is None:
            return False
        if direction == "up":
            return signal_bi.high > current_zs.zs_high
        if direction == "down":
            return signal_bi.low < current_zs.zs_low
        return False

    def _touches_boundary(signal_bi: Bi | None, direction: str | None) -> bool:
        if current_zs is None or signal_bi is None:
            return False
        if direction == "up":
            return signal_bi.high >= current_zs.zs_high
        if direction == "down":
            return signal_bi.low <= current_zs.zs_low
        return False

    trend_strength = _build_strength_comparison(trend_signal_bi, trend_reference_bi, strengths)
    range_strength = _build_strength_comparison(range_signal_bi, range_reference_bi, strengths)

    trend_departure_confirmed = _departure_confirmed(trend_signal_bi, trend_direction)
    trend_strict = bool(
        trend_active
        and reference_zs_id is not None
        and trend_departure_confirmed
        and trend_strength is not None
        and trend_strength.get("decayed")
    )

    range_touches_boundary = _touches_boundary(range_signal_bi, range_direction)
    range_strict = bool(
        range_active
        and reference_zs_id is not None
        and range_touches_boundary
        and range_strength is not None
        and range_strength.get("decayed")
    )

    return {
        "top": {
            "active": top_divergence,
            "signal_bi_id": latest_confirmed_up.bi_id if latest_confirmed_up else None,
            "time": _isoformat_ts(latest_confirmed_up.end_ts) if latest_confirmed_up else None,
            "price": round(float(latest_confirmed_up.high), 2) if latest_confirmed_up else None,
        },
        "bottom": {
            "active": bottom_divergence,
            "signal_bi_id": latest_down.bi_id if latest_down else None,
            "time": _isoformat_ts(latest_down.end_ts) if latest_down else None,
            "price": round(float(latest_down.low), 2) if latest_down else None,
        },
        "trend": {
            "active": trend_active,
            "direction": trend_direction,
            "signal_bi_id": trend_signal_bi.bi_id if trend_signal_bi else None,
            "time": _isoformat_ts(trend_signal_bi.end_ts) if trend_signal_bi else None,
            "price": round(float(trend_signal_bi.high if trend_direction == "up" else trend_signal_bi.low), 2)
            if trend_signal_bi
            else None,
            "basis": "same_level_trend_macd_strength" if trend_active else None,
            "strict": trend_strict,
            "reference_zs_id": reference_zs_id if trend_active else None,
            "departure_confirmed": trend_departure_confirmed if trend_active else None,
            "strength_comparison": trend_strength if trend_active else None,
        },
        "range": {
            "active": range_active,
            "direction": range_direction,
            "signal_bi_id": range_signal_bi.bi_id if range_signal_bi else None,
            "time": _isoformat_ts(range_signal_bi.end_ts) if range_signal_bi else None,
            "price": round(float(range_signal_bi.high if range_direction == "up" else range_signal_bi.low), 2)
            if range_signal_bi
            else None,
            "basis": "first_same_level_zhongshu_failed_departure" if range_active else None,
            "strict": range_strict,
            "reference_zs_id": reference_zs_id if range_active else None,
            "touches_boundary": range_touches_boundary if range_active else None,
            "strength_comparison": range_strength if range_active else None,
        },
    }


def analyze_chanlun_signals(
    raw_bars: list[Bar],
    bis: list[Bi],
    zhongshus: list[Zhongshu],
    macd_points: list[Any],
) -> dict[str, object]:
    confirmed_bis = [bi for bi in bis if bi.is_confirmed]
    strengths = compute_bi_strengths(bis, macd_points)
    recent_confirmed_ups = _find_recent_confirmed_bis_by_direction(confirmed_bis, direction="up", limit=3)
    latest_confirmed_up = recent_confirmed_ups[0] if len(recent_confirmed_ups) >= 1 else None
    previous_confirmed_up = recent_confirmed_ups[1] if len(recent_confirmed_ups) >= 2 else None
    earlier_confirmed_up = recent_confirmed_ups[2] if len(recent_confirmed_ups) >= 3 else None

    recent_confirmed_downs = _find_recent_confirmed_bis_by_direction(confirmed_bis, direction="down", limit=3)
    latest_confirmed_down = recent_confirmed_downs[0] if len(recent_confirmed_downs) >= 1 else None
    previous_confirmed_down = recent_confirmed_downs[1] if len(recent_confirmed_downs) >= 2 else None
    earlier_confirmed_down = recent_confirmed_downs[2] if len(recent_confirmed_downs) >= 3 else None

    latest_up = next((bi for bi in reversed(bis) if bi.is_up()), None)
    latest_down = next((bi for bi in reversed(bis) if bi.is_down()), None)

    top_reference_bi = previous_confirmed_up if previous_confirmed_up is not None else latest_confirmed_up
    bottom_reference_bi = previous_confirmed_down if previous_confirmed_down is not None else latest_confirmed_down

    current_zs = zhongshus[-1] if zhongshus else None
    structure_state = build_structure_state(raw_bars, zhongshus)

    top_divergence = False
    if (
        current_zs
        and latest_confirmed_up
        and top_reference_bi
        and latest_confirmed_up.bi_id != top_reference_bi.bi_id
    ):
        top_divergence = _has_top_divergence(latest_confirmed_up, top_reference_bi, strengths)

    bottom_divergence = False
    if latest_down and bottom_reference_bi and latest_down.bi_id != bottom_reference_bi.bi_id:
        bottom_divergence = _has_bottom_divergence(latest_down, bottom_reference_bi, strengths)
    elif latest_confirmed_down and bottom_reference_bi and latest_confirmed_down.bi_id != bottom_reference_bi.bi_id:
        bottom_divergence = _has_bottom_divergence(latest_confirmed_down, bottom_reference_bi, strengths)
    current_zs_exit_bi = None
    if current_zs and current_zs.exit_bi_id is not None:
        current_zs_exit_bi = next((bi for bi in bis if bi.bi_id == current_zs.exit_bi_id), None)
    buy_points: list[str] = []
    sell_points: list[str] = []
    if (
        current_zs
        and latest_down
        and latest_down.is_confirmed
        and bottom_divergence
        and latest_down.low <= current_zs.zs_low
        and _has_reverse_turn_after(latest_down, direction="down", bis=bis)
    ):
        buy_points.append("buy_1")
    if (
        current_zs
        and latest_confirmed_up
        and latest_confirmed_up.is_confirmed
        and top_divergence
        and latest_confirmed_up.high >= current_zs.zs_high
        and _has_reverse_turn_after(latest_confirmed_up, direction="up", bis=bis)
    ):
        sell_points.append("sell_1")
    previous_buy1_active = (
        current_zs is not None
        and latest_confirmed_down is not None
        and previous_confirmed_down is not None
        and latest_confirmed_down.bi_id != previous_confirmed_down.bi_id
        and _has_bottom_divergence(latest_confirmed_down, previous_confirmed_down, strengths)
        and latest_confirmed_down.low <= current_zs.zs_low
    )
    if (
        current_zs
        and previous_buy1_active
        and latest_confirmed_up
        and latest_down
        and latest_confirmed_down is not None
        and latest_down.bi_id != latest_confirmed_down.bi_id
        and latest_confirmed_up.high > latest_confirmed_down.high
        and latest_down.low > latest_confirmed_down.low
        and _is_first_reverse_hold(latest_confirmed_down, latest_down, bis)
    ):
        buy_points.append("buy_2")
    if current_zs and latest_confirmed_up and latest_confirmed_up.high > current_zs.zs_high and latest_down and latest_down.low >= current_zs.zs_high:
        buy_points.append("buy_3")
    previous_sell1_active = (
        current_zs is not None
        and latest_confirmed_up is not None
        and previous_confirmed_up is not None
        and _has_top_divergence(latest_confirmed_up, previous_confirmed_up, strengths)
        and latest_confirmed_up.high >= current_zs.zs_high
    )
    if (
        current_zs
        and previous_sell1_active
        and latest_up
        and latest_down
        and latest_confirmed_up
        and latest_up.bi_id != latest_confirmed_up.bi_id
        and latest_up.high < latest_confirmed_up.high
        and latest_down.low < latest_confirmed_up.low
        and _is_first_reverse_hold(latest_confirmed_up, latest_up, bis)
    ):
        sell_points.append("sell_2")
    if current_zs and latest_down and latest_down.low < current_zs.zs_low and latest_confirmed_up and latest_confirmed_up.high <= current_zs.zs_low:
        sell_points.append("sell_3")

    same_level_decomposition_mode = _build_same_level_decomposition_mode(structure_state)
    same_level_consumption_level = _build_same_level_consumption_level(structure_state)
    divergence = build_divergence_state(
        structure_state,
        top_divergence=top_divergence,
        bottom_divergence=bottom_divergence,
        latest_confirmed_up=latest_confirmed_up,
        latest_down=latest_down,
        previous_confirmed_up=previous_confirmed_up,
        previous_confirmed_down=previous_confirmed_down,
        strengths=strengths,
        current_zs=current_zs,
    )
    post_divergence_route = _build_post_divergence_route(
        structure_state,
        divergence,
        top_divergence=top_divergence,
        bottom_divergence=bottom_divergence,
    )
    oscillation_rhythm_state = _build_oscillation_rhythm_state(current_zs, confirmed_bis, strengths)
    signal_points, signal_catalog = build_signal_point_payloads(
        buy_points=buy_points,
        sell_points=sell_points,
        latest_confirmed_up=latest_confirmed_up,
        latest_up=latest_up,
        latest_down=latest_down,
        current_zs=current_zs,
    )
    zs_monitor_state = _build_zs_monitor_state(
        raw_bars,
        current_zs,
        buy_points=buy_points,
        sell_points=sell_points,
    )

    return {
        "current_zs": current_zs,
        "current_zs_exit_bi": current_zs_exit_bi,
        "current_zs_exit_time": _isoformat_ts(current_zs_exit_bi.end_ts) if current_zs_exit_bi else None,
        "latest_confirmed_up": latest_confirmed_up,
        "latest_down": latest_down,
        "top_divergence": top_divergence,
        "bottom_divergence": bottom_divergence,
        "buy_points": buy_points,
        "sell_points": sell_points,
        "signal_points": signal_points,
        "signal_catalog": signal_catalog,
        "structure_state": structure_state,
        "same_level_decomposition_mode": same_level_decomposition_mode,
        "same_level_consumption_level": same_level_consumption_level,
        "post_divergence_route": post_divergence_route,
        "oscillation_rhythm_state": oscillation_rhythm_state,
        "divergence": divergence,
        **zs_monitor_state,
    }


def build_signal_point_payloads(
    *,
    buy_points: list[str],
    sell_points: list[str],
    latest_confirmed_up: Bi | None,
    latest_up: Bi | None,
    latest_down: Bi | None,
    current_zs: Zhongshu | None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    signal_points: list[dict[str, object]] = []
    signal_catalog: list[dict[str, object]] = []
    related_zs_id = current_zs.zs_id if current_zs else None
    related_bi_ids = list(current_zs.bi_ids) if current_zs else []

    for point in buy_points:
        basis = {
            "buy_1": "bottom_divergence_near_zs_low",
            "buy_2": "buy1_pullback_confirmation",
            "buy_3": "leave_zs_then_pullback_holds_upper_edge",
        }.get(point)
        signal_points.append(
            _build_signal_point_detail(
                point,
                latest_down,
                getattr(latest_down, "low", None),
                active=True,
                basis=basis,
                related_zs_id=related_zs_id,
                related_bi_ids=related_bi_ids,
            )
        )
    for point in sell_points:
        basis = {
            "sell_1": "top_divergence_near_zs_high",
            "sell_2": "sell1_rebound_confirmation",
            "sell_3": "leave_zs_then_rebound_fails_lower_edge",
        }.get(point)
        signal_bi = latest_up if point == "sell_2" else latest_confirmed_up
        signal_points.append(
            _build_signal_point_detail(
                point,
                signal_bi,
                getattr(signal_bi, "high", None),
                active=True,
                basis=basis,
                related_zs_id=related_zs_id,
                related_bi_ids=related_bi_ids,
            )
        )

    active_points = set(buy_points + sell_points)
    for point in ("buy_1", "buy_2", "buy_3"):
        signal_catalog.append(
            _build_signal_point_detail(
                point,
                latest_down,
                getattr(latest_down, "low", None) if point in active_points else None,
                active=point in active_points,
                basis={
                    "buy_1": "bottom_divergence_near_zs_low",
                    "buy_2": "buy1_pullback_confirmation",
                    "buy_3": "leave_zs_then_pullback_holds_upper_edge",
                }.get(point),
                related_zs_id=related_zs_id,
                related_bi_ids=related_bi_ids,
            )
        )
    for point in ("sell_1", "sell_2", "sell_3"):
        signal_bi = latest_up if point == "sell_2" else latest_confirmed_up
        signal_catalog.append(
            _build_signal_point_detail(
                point,
                signal_bi,
                getattr(signal_bi, "high", None) if point in active_points else None,
                active=point in active_points,
                basis={
                    "sell_1": "top_divergence_near_zs_high",
                    "sell_2": "sell1_rebound_confirmation",
                    "sell_3": "leave_zs_then_rebound_fails_lower_edge",
                }.get(point),
                related_zs_id=related_zs_id,
                related_bi_ids=related_bi_ids,
            )
        )
    return signal_points, signal_catalog


def build_signal_summary_fields(signals: dict[str, object]) -> dict[str, object]:
    # spec_id: SPEC.BUY_SELL.CORE（见 docs/chanlun/buy-sell-multi-level-spec.md）
    same_level_consumption_level = signals.get("same_level_consumption_level")
    return {
        "buy_points": [_format_signal_point_name(str(point)) for point in signals.get("buy_points", [])],
        "sell_points": [_format_signal_point_name(str(point)) for point in signals.get("sell_points", [])],
        "signal_points": list(signals.get("signal_points", [])),
        "signal_catalog": list(signals.get("signal_catalog", [])),
        "structure_state": signals.get("structure_state"),
        "same_level_decomposition_mode": signals.get("same_level_decomposition_mode"),
        "same_level_consumption_level": same_level_consumption_level,
        "same_level_consumption_level_label": format_consumption_level_label(same_level_consumption_level) or None,
        "same_level_consumption_level_note": describe_consumption_level(same_level_consumption_level) or None,
        "post_divergence_route": signals.get("post_divergence_route"),
        "oscillation_rhythm_state": signals.get("oscillation_rhythm_state"),
        "divergence": signals.get("divergence"),
        "zs_monitor_alert": signals.get("zs_monitor_alert", "none"),
        "zs_monitor_midline": signals.get("zs_monitor_midline"),
        "zs_monitor_bias": signals.get("zs_monitor_bias"),
    }


def _parse_signal_time(value: object) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _infer_execution_side_from_direction(direction: object) -> str | None:
    if direction == "down":
        return "buy"
    if direction == "up":
        return "sell"
    return None


def _describe_precision_window_basis(window_basis: object) -> str:
    if window_basis == "current_zs_exit_bi":
        return "窗口依据：上级别已确认离开笔，当前按中枢结束至离开笔完成时间收缩区间套窗口。"
    if window_basis == "current_zs_anchor_cap":
        return "窗口依据：上级别离开笔尚未单独解析，当前先按中枢结束至触发锚点限制区间套窗口。"
    return "窗口依据：上级别尚无可用中枢边界，当前先按触发锚点向后跟踪区间套窗口。"


def _precision_window_basis_label(window_basis: object) -> str:
    if window_basis == "current_zs_exit_bi":
        return "离开笔窗口"
    if window_basis == "current_zs_anchor_cap":
        return "中枢到锚点窗口"
    return "锚点跟踪窗口"


def build_precision_window_display(precision_entry: dict[str, object] | None) -> dict[str, object] | None:
    if not precision_entry:
        return None
    operation_level = precision_entry.get("operation_level") or precision_entry.get("timeframe") or "5M"
    nested_from = precision_entry.get("nested_from") or {}
    label = precision_entry.get("window_basis_label") or nested_from.get("window_basis_label")
    description = precision_entry.get("window_basis_description") or nested_from.get("window_basis_description")
    if not label and not description:
        return None
    lines = [line for line in [f"{operation_level}窗口：{label}" if label else None, description] if line]
    return {
        "title": f"{operation_level}区间套窗口",
        "label": label,
        "description": description,
        "lines": lines,
    }


def _active_higher_level_precision_context(higher_signals: dict[str, object]) -> dict[str, object] | None:
    signal_points = list(higher_signals.get("signal_points") or [])
    current_zs = higher_signals.get("current_zs")
    current_zs_end = getattr(current_zs, "end_ts", None)
    current_zs_exit_time = _parse_signal_time(higher_signals.get("current_zs_exit_time"))
    related_zs_id = getattr(current_zs, "zs_id", None)
    exit_bi_id = getattr(current_zs, "exit_bi_id", None)
    zs_is_terminated = bool(getattr(current_zs, "is_terminated", False)) if current_zs is not None else False
    buy_entries = [entry for entry in signal_points if str(entry.get("point") or "").startswith("buy") and entry.get("active")]
    sell_entries = [entry for entry in signal_points if str(entry.get("point") or "").startswith("sell") and entry.get("active")]

    def _window_basis(anchor_time: datetime | None) -> str:
        if current_zs_exit_time is not None:
            return "current_zs_exit_bi"
        if current_zs_end is not None and anchor_time is not None and anchor_time >= current_zs_end:
            return "current_zs_anchor_cap"
        return "higher_signal_anchor"

    def _window_end(anchor_time: datetime | None) -> datetime | None:
        if current_zs_exit_time is not None:
            return current_zs_exit_time
        if current_zs_end is None or anchor_time is None:
            return None
        if anchor_time < current_zs_end:
            return None
        return anchor_time

    if buy_entries:
        anchor = buy_entries[-1]
        anchor_time = _parse_signal_time(anchor.get("time"))
        return {
            "side": "buy",
            "anchor_time": anchor_time,
            "window_start_time": current_zs_end or anchor_time,
            "window_end_time": _window_end(anchor_time),
            "window_basis": _window_basis(anchor_time),
            "related_zs_id": related_zs_id,
            "exit_bi_id": exit_bi_id,
            "zs_is_terminated": zs_is_terminated,
            "trigger": str(anchor.get("point") or "buy"),
        }
    if sell_entries:
        anchor = sell_entries[-1]
        anchor_time = _parse_signal_time(anchor.get("time"))
        return {
            "side": "sell",
            "anchor_time": anchor_time,
            "window_start_time": current_zs_end or anchor_time,
            "window_end_time": _window_end(anchor_time),
            "window_basis": _window_basis(anchor_time),
            "related_zs_id": related_zs_id,
            "exit_bi_id": exit_bi_id,
            "zs_is_terminated": zs_is_terminated,
            "trigger": str(anchor.get("point") or "sell"),
        }

    divergence = higher_signals.get("divergence") or {}
    for key in ("trend", "range"):
        item = divergence.get(key) or {}
        if not item.get("active"):
            continue
        side = _infer_execution_side_from_direction(item.get("direction"))
        if side is None:
            continue
        anchor_time = _parse_signal_time(item.get("time"))
        return {
            "side": side,
            "anchor_time": anchor_time,
            "window_start_time": current_zs_end or anchor_time,
            "window_end_time": _window_end(anchor_time),
            "window_basis": _window_basis(anchor_time),
            "related_zs_id": related_zs_id,
            "exit_bi_id": exit_bi_id,
            "zs_is_terminated": zs_is_terminated,
            "trigger": f"higher_{key}_divergence",
        }

    if higher_signals.get("bottom_divergence"):
        anchor_time = _parse_signal_time((divergence.get("bottom") or {}).get("time"))
        return {
            "side": "buy",
            "anchor_time": anchor_time,
            "window_start_time": current_zs_end or anchor_time,
            "window_end_time": _window_end(anchor_time),
            "window_basis": _window_basis(anchor_time),
            "related_zs_id": related_zs_id,
            "exit_bi_id": exit_bi_id,
            "zs_is_terminated": zs_is_terminated,
            "trigger": "higher_bottom_divergence",
        }
    if higher_signals.get("top_divergence"):
        anchor_time = _parse_signal_time((divergence.get("top") or {}).get("time"))
        return {
            "side": "sell",
            "anchor_time": anchor_time,
            "window_start_time": current_zs_end or anchor_time,
            "window_end_time": _window_end(anchor_time),
            "window_basis": _window_basis(anchor_time),
            "related_zs_id": related_zs_id,
            "exit_bi_id": exit_bi_id,
            "zs_is_terminated": zs_is_terminated,
            "trigger": "higher_top_divergence",
        }
    return None


def build_lower_timeframe_precision_entry(
    higher_signals: dict[str, object],
    lower_signals: dict[str, object],
    *,
    lower_timeframe: str,
    lower_timeframe_label: str,
    pending_reverse_mode: str,
    source: str | None = None,
    source_actual: str | None = None,
) -> dict[str, object]:
    higher_context = _active_higher_level_precision_context(higher_signals)
    lower_signal_points = list(lower_signals.get("signal_points") or [])
    lower_signal_catalog = list(lower_signals.get("signal_catalog") or [])
    structure_state = lower_signals.get("structure_state")
    divergence = lower_signals.get("divergence") or {}

    if higher_context is None:
        return {
            "timeframe": lower_timeframe,
            "operation_level": lower_timeframe_label,
            "pending_reverse_mode": pending_reverse_mode,
            "status": "standby",
            "source": source,
            "source_actual": source_actual,
            "buy_points": [],
            "sell_points": [],
            "signal_points": [],
            "signal_catalog": [],
            "signal_descriptions": [],
            "structure_state": structure_state,
            "divergence": divergence,
            "nested_from": None,
            "note": f"{lower_timeframe_label} 仅在上级别买卖点或背驰段激活后才进入区间套执行；当前上级别尚未给出可绑定的离开段/背驰段窗口。",
        }

    side = str(higher_context.get("side"))
    anchor_time = higher_context.get("anchor_time")
    window_start_time = higher_context.get("window_start_time")
    window_end_time = higher_context.get("window_end_time")
    window_basis = higher_context.get("window_basis")
    window_basis_note = _describe_precision_window_basis(higher_context.get("window_basis"))
    window_basis_label = _precision_window_basis_label(window_basis)

    def _matches_window(point_time: datetime | None) -> bool:
        if point_time is None:
            return False
        if window_start_time is not None and point_time < window_start_time:
            return False
        if window_end_time is not None and point_time > window_end_time:
            return False
        return True

    def _matches_point(entry: dict[str, object]) -> bool:
        point = str(entry.get("point") or "")
        if not entry.get("active"):
            return False
        if not point.startswith(side):
            return False
        point_time = _parse_signal_time(entry.get("time"))
        return _matches_window(point_time)

    signal_points = [entry for entry in lower_signal_points if _matches_point(entry)]
    signal_catalog: list[dict[str, object]] = []
    for entry in lower_signal_catalog:
        point = str(entry.get("point") or "")
        if not point.startswith(side):
            continue
        filtered_entry = dict(entry)
        if not _matches_point(filtered_entry):
            filtered_entry["active"] = False
            filtered_entry["basis"] = None
            filtered_entry["time"] = None
            filtered_entry["price"] = None
            filtered_entry["related_zs_id"] = None
            filtered_entry["related_bi_ids"] = []
        signal_catalog.append(filtered_entry)

    signal_descriptions = build_signal_explanation_lines({"signal_points": signal_points, "signal_catalog": signal_catalog})
    buy_points = [_format_signal_point_name(str(entry.get("point") or "")) for entry in signal_points if str(entry.get("point") or "").startswith("buy")]
    sell_points = [_format_signal_point_name(str(entry.get("point") or "")) for entry in signal_points if str(entry.get("point") or "").startswith("sell")]

    status = "watch"
    note = f"{lower_timeframe_label} 已绑定上级别{side}侧离开段/背驰段窗口，但次级别尚未出现同向且落在该窗口内的精确买卖点。{window_basis_note}"
    trend_divergence = divergence.get("trend") or {}
    range_divergence = divergence.get("range") or {}
    trend_divergence_active = (
        trend_divergence.get("active")
        and _infer_execution_side_from_direction(trend_divergence.get("direction")) == side
        and _matches_window(_parse_signal_time(trend_divergence.get("time")))
    )
    range_divergence_active = (
        range_divergence.get("active")
        and _infer_execution_side_from_direction(range_divergence.get("direction")) == side
        and _matches_window(_parse_signal_time(range_divergence.get("time")))
    )

    if signal_descriptions:
        status = "actionable"
        note = (
            f"{lower_timeframe_label} 已出现{'；'.join(signal_descriptions)}，"
            f"可按 {pending_reverse_mode} 口径用于区间套精确定位。{window_basis_note}"
        )
    elif trend_divergence_active:
        note = (
            f"{lower_timeframe_label} 已出现{'底' if side == 'buy' else '顶'}部趋势背驰，"
            f"等待次级别买卖点确认后再精确执行。{window_basis_note}"
        )
    elif range_divergence_active:
        note = f"{lower_timeframe_label} 已出现盘整背驰，等待回抽确认后再作为区间套精确点。{window_basis_note}"

    return {
        "timeframe": lower_timeframe,
        "operation_level": lower_timeframe_label,
        "pending_reverse_mode": pending_reverse_mode,
        "status": status,
        "source": source,
        "source_actual": source_actual,
        "buy_points": buy_points,
        "sell_points": sell_points,
        "signal_points": signal_points,
        "signal_catalog": signal_catalog,
        "signal_descriptions": signal_descriptions,
        "structure_state": structure_state,
        "divergence": divergence,
        "window_basis_label": window_basis_label,
        "window_basis_description": window_basis_note,
        "nested_from": {
            "side": side,
            "window_start_time": _isoformat_ts(window_start_time),
            "window_end_time": _isoformat_ts(window_end_time),
            "window_basis": window_basis,
            "window_basis_label": window_basis_label,
            "window_basis_description": window_basis_note,
            "anchor_time": _isoformat_ts(anchor_time),
            "related_zs_id": higher_context.get("related_zs_id"),
            "exit_bi_id": higher_context.get("exit_bi_id"),
            "zs_is_terminated": higher_context.get("zs_is_terminated"),
            "trigger": higher_context.get("trigger"),
        },
        "note": note,
    }