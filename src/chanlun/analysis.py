from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import Bar, Bi, Zhongshu


SIGNAL_POINT_LABELS = {
    "buy_1": "一买",
    "buy_2": "二买",
    "buy_3": "三买",
    "sell_1": "一卖",
    "sell_2": "二卖",
    "sell_3": "三卖",
}


SIGNAL_BASIS_LABELS = {
    "bottom_divergence_near_zs_low": "中枢下沿附近出现底背驰",
    "buy1_pullback_confirmation": "一买后回抽确认，低点未再跌破前低",
    "leave_zs_then_pullback_holds_upper_edge": "离开中枢后回踩上沿未失守",
    "top_divergence_near_zs_high": "中枢上沿附近出现顶背驰",
    "sell1_rebound_confirmation": "一卖后反抽确认，高点未再突破前高",
    "leave_zs_then_rebound_fails_lower_edge": "跌破中枢后反抽下沿失败",
}


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


def build_structure_state(raw_bars: list[Bar], zhongshus: list[Zhongshu]) -> dict[str, object]:
    latest_bar_ts = raw_bars[-1].ts if raw_bars else None
    if not zhongshus:
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
                "note": "当前尚未形成可用于同级别走势分解的中枢。",
            },
        }

    if len(zhongshus) == 1:
        only = zhongshus[0]
        return {
            "last_completed": None,
            "current_ongoing": {
                "type": "range",
                "status": "ongoing",
                "start_ts": _isoformat_ts(only.start_ts),
                "latest_ts": _isoformat_ts(latest_bar_ts or only.end_ts),
                "zs_count_so_far": 1,
                "confirmation_basis": "single_active_zhongshu",
                "start_zs_id": only.zs_id,
                "end_zs_id": only.zs_id,
            },
            "relationship": {
                "kind": "undetermined",
                "note": "当前只有一个同级别中枢，按工程口径先视为盘整进行中。",
            },
        }

    relations = [_relation_kind(previous, current) for previous, current in zip(zhongshus, zhongshus[1:])]
    current_kind = relations[-1]
    current_start_relation = len(relations) - 1
    while current_start_relation > 0 and relations[current_start_relation - 1] == current_kind:
        current_start_relation -= 1
    current_start_index = current_start_relation
    if current_kind == "range" and current_start_relation > 0:
        # When a new overlap suffix appears after a finished up/down run,
        # treat the latest zhongshu as the start of the new ongoing range
        # instead of folding the prior trend tail back into the new group.
        current_start_index = current_start_relation + 1
    current_group_count = len(zhongshus) - current_start_index
    current_ongoing = _build_group_state(
        zhongshus,
        current_start_index,
        len(zhongshus) - 1,
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
            zhongshus,
            previous_start_index,
            previous_end_index,
            status="completed",
            latest_ts=zhongshus[previous_end_index].end_ts,
            confirmation_basis="confirmed_by_following_same_level_structure",
        )

    relationship_kind = "undetermined"
    relationship_note = "当前同级别结构仍在演化，尚不能把新旧走势关系完全定型。"
    if last_completed is not None:
        if str(last_completed.get("type")) == str(current_ongoing.get("type")):
            relationship_kind = "same_type_extension"
            relationship_note = "当前结构更接近前一走势类型的同类延伸，暂未看到清晰的新类型完成边界。"
        else:
            relationship_kind = "completed_then_new_type_ongoing"
            relationship_note = "上一段同级别走势已结束，当前正在运行的是新的同级别走势类型。"
    elif current_kind in {"up", "down"}:
        relationship_note = "已经出现同向不重叠中枢推进，当前按工程口径视为趋势进行中。"
    else:
        relationship_note = "当前主要围绕最近同级别中枢展开，按工程口径视为盘整进行中。"

    return {
        "last_completed": last_completed,
        "current_ongoing": current_ongoing,
        "relationship": {
            "kind": relationship_kind,
            "note": relationship_note,
        },
    }


def build_divergence_state(
    structure_state: dict[str, object],
    *,
    top_divergence: bool,
    bottom_divergence: bool,
    latest_confirmed_up: Bi | None,
    latest_down: Bi | None,
) -> dict[str, object]:
    ongoing = structure_state.get("current_ongoing") or {}
    ongoing_type = ongoing.get("type")

    trend_active = False
    trend_direction = None
    trend_signal_bi = None
    if ongoing_type == "up" and top_divergence:
        trend_active = True
        trend_direction = "up"
        trend_signal_bi = latest_confirmed_up
    elif ongoing_type == "down" and bottom_divergence:
        trend_active = True
        trend_direction = "down"
        trend_signal_bi = latest_down

    range_active = False
    range_direction = None
    range_signal_bi = None
    if ongoing_type == "range":
        if top_divergence:
            range_active = True
            range_direction = "up"
            range_signal_bi = latest_confirmed_up
        elif bottom_divergence:
            range_active = True
            range_direction = "down"
            range_signal_bi = latest_down

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
    previous_confirmed_down = recent_confirmed_downs[0] if len(recent_confirmed_downs) >= 1 else None
    earlier_confirmed_down = recent_confirmed_downs[1] if len(recent_confirmed_downs) >= 2 else None

    latest_up = next((bi for bi in reversed(bis) if bi.is_up()), None)
    latest_down = next((bi for bi in reversed(bis) if bi.is_down()), None)
    top_divergence = _has_top_divergence(latest_confirmed_up, previous_confirmed_up, strengths)

    bottom_divergence = False
    if latest_down and previous_confirmed_down and latest_down.bi_id != previous_confirmed_down.bi_id:
        bottom_divergence = _has_bottom_divergence(latest_down, previous_confirmed_down, strengths)

    current_zs = zhongshus[-1] if zhongshus else None
    current_zs_exit_bi = None
    if current_zs and current_zs.exit_bi_id is not None:
        current_zs_exit_bi = next((bi for bi in bis if bi.bi_id == current_zs.exit_bi_id), None)
    buy_points: list[str] = []
    sell_points: list[str] = []
    if current_zs and latest_down and bottom_divergence and latest_down.low <= current_zs.zs_low:
        buy_points.append("buy_1")
    if current_zs and latest_confirmed_up and top_divergence and latest_confirmed_up.high >= current_zs.zs_high:
        sell_points.append("sell_1")
    previous_buy1_active = (
        current_zs is not None
        and previous_confirmed_down is not None
        and earlier_confirmed_down is not None
        and _has_bottom_divergence(previous_confirmed_down, earlier_confirmed_down, strengths)
        and previous_confirmed_down.low <= current_zs.zs_low
    )
    if (
        current_zs
        and previous_buy1_active
        and latest_confirmed_up
        and latest_down
        and latest_down.bi_id != previous_confirmed_down.bi_id
        and latest_confirmed_up.high > previous_confirmed_down.high
        and latest_down.low > previous_confirmed_down.low
        and latest_down.low >= current_zs.zs_low
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
        and latest_down.low < latest_confirmed_up.low
        and latest_up.high < latest_confirmed_up.high
        and latest_up.high <= current_zs.zs_high
    ):
        sell_points.append("sell_2")
    if current_zs and latest_down and latest_down.low < current_zs.zs_low and latest_confirmed_up and latest_confirmed_up.high <= current_zs.zs_low:
        sell_points.append("sell_3")

    structure_state = build_structure_state(raw_bars, zhongshus)
    divergence = build_divergence_state(
        structure_state,
        top_divergence=top_divergence,
        bottom_divergence=bottom_divergence,
        latest_confirmed_up=latest_confirmed_up,
        latest_down=latest_down,
    )
    signal_points, signal_catalog = build_signal_point_payloads(
        buy_points=buy_points,
        sell_points=sell_points,
        latest_confirmed_up=latest_confirmed_up,
        latest_up=latest_up,
        latest_down=latest_down,
        current_zs=current_zs,
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
        "divergence": divergence,
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
    return {
        "buy_points": [_format_signal_point_name(str(point)) for point in signals.get("buy_points", [])],
        "sell_points": [_format_signal_point_name(str(point)) for point in signals.get("sell_points", [])],
        "signal_points": list(signals.get("signal_points", [])),
        "signal_catalog": list(signals.get("signal_catalog", [])),
        "structure_state": signals.get("structure_state"),
        "divergence": signals.get("divergence"),
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