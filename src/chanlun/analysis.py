from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import Bar, Bi, Segment, Zhongshu
from .zhongshu_contract import (
    CONSUMPTION_LEVEL_LABELS,
    CONSUMPTION_LEVEL_NOTES,
    TRANSITION_STATE_LABELS,
    TRANSITION_STATE_NOTES,
)
from .analysis_contract import (
    PRECISION_DYNAMIC_GRADE_LABELS,
    SIGNAL_BASIS_LABELS,
    SIGNAL_POINT_LABELS,
    STRUCTURE_STATUS_LABELS,
    STRUCTURE_STATUS_NOTES,
    PrecisionDynamicGrade,
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


def compute_segment_strengths(
    segments: list[Segment],
    macd_points: list[Any],
) -> dict[int, dict[str, float]]:
    """按线段时间窗聚合 MACD 面积，得到线段级力度表（key=segment_id）。

    与 `compute_bi_strengths` 同构：线段力度 = 其 `start_ts..end_ts` 窗内
    `abs(macd)` 之和，作为一类点「离开段 vs 进入段」比较的力度口径。
    """
    strengths: dict[int, dict[str, float]] = {}
    for segment in segments:
        window = [point for point in macd_points if segment.start_ts <= point.ts <= segment.end_ts]
        if not window:
            continue
        strengths[segment.segment_id] = {
            "macd_sum_abs": sum(abs(point.macd) for point in window),
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


def _segment_by_id(segment_id: int | None, segments: list[Segment]) -> Segment | None:
    if segment_id is None:
        return None
    return next((segment for segment in segments if segment.segment_id == segment_id), None)


def _bi_by_id(bi_id: int | None, bis: list[Bi]) -> Bi | None:
    if bi_id is None:
        return None
    return next((bi for bi in bis if bi.bi_id == bi_id), None)


def _has_segment_bottom_divergence(
    exit_segment: Segment | None,
    entering_segment: Segment | None,
    segment_strengths: dict[int, dict[str, float]],
) -> bool:
    """线段级底背驰：离开段与进入段同向下行，离开段创新低且力度衰减。"""
    if exit_segment is None or entering_segment is None:
        return False
    if not (exit_segment.is_down() and entering_segment.is_down()):
        return False
    exit_strength = segment_strengths.get(exit_segment.segment_id, {}).get("macd_sum_abs", 0.0)
    entering_strength = segment_strengths.get(entering_segment.segment_id, {}).get("macd_sum_abs", 0.0)
    return exit_segment.low < entering_segment.low and exit_strength < entering_strength


def _has_segment_top_divergence(
    exit_segment: Segment | None,
    entering_segment: Segment | None,
    segment_strengths: dict[int, dict[str, float]],
) -> bool:
    """线段级顶背驰：离开段与进入段同向上行，离开段创新高且力度衰减。"""
    if exit_segment is None or entering_segment is None:
        return False
    if not (exit_segment.is_up() and entering_segment.is_up()):
        return False
    exit_strength = segment_strengths.get(exit_segment.segment_id, {}).get("macd_sum_abs", 0.0)
    entering_strength = segment_strengths.get(entering_segment.segment_id, {}).get("macd_sum_abs", 0.0)
    return exit_segment.high > entering_segment.high and exit_strength < entering_strength


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


def _latest_bi_before(anchor_id: int, direction: str, bis: list[Bi]) -> Bi | None:
    """返回 anchor_id 之前（bi_id < anchor_id）最近的 direction 方向 bi。"""
    for bi in reversed(bis):
        if bi.bi_id >= anchor_id:
            continue
        if direction == "up" and bi.is_up():
            return bi
        if direction == "down" and bi.is_down():
            return bi
    return None


def _renewed_beyond_previous(latest_bi: Bi, pullback_bi: Bi, bis: list[Bi]) -> bool:
    """「再度走强 / 走弱」的力度口径：renewed bi 必须创新高 / 新低。

    - 向上 renewed：latest_bi.high > 回抽前最近向上 bi 的 high（创新高）
    - 向下 renewed：latest_bi.low < 反抽前最近向下 bi 的 low（创新低）
    """
    direction = "up" if latest_bi.is_up() else "down"
    prior = _latest_bi_before(pullback_bi.bi_id, direction, bis)
    if prior is None:
        return False
    if latest_bi.is_up():
        return latest_bi.high > prior.high
    return latest_bi.low < prior.low


def _find_buy3_bi_leave_hold(bis: list[Bi], level: float) -> tuple[Bi | None, Bi | None]:
    """笔级：向上离开（high > level）后紧随的向下回试不破 level。"""
    for i, bi in enumerate(bis):
        if not bi.is_up() or bi.high <= level:
            continue
        next_bi = bis[i + 1] if i + 1 < len(bis) else None
        if next_bi is not None and next_bi.is_down() and next_bi.low >= level:
            return bi, next_bi
    return None, None


def _find_sell3_bi_leave_hold(bis: list[Bi], level: float) -> tuple[Bi | None, Bi | None]:
    """笔级：向下离开（low < level）后紧随的向上反抽不破 level。"""
    for i, bi in enumerate(bis):
        if not bi.is_down() or bi.low >= level:
            continue
        next_bi = bis[i + 1] if i + 1 < len(bis) else None
        if next_bi is not None and next_bi.is_up() and next_bi.high <= level:
            return bi, next_bi
    return None, None


def _find_buy3_segment_leave_hold(
    segments: list[Segment], zhongshu: Zhongshu, level: float
) -> tuple[Segment | None, Segment | None]:
    """段级：核心起，向上离开后紧随的向下回试不破 level。"""
    for i, seg in enumerate(segments):
        if seg.segment_id < zhongshu.start_bi_id:
            continue
        if not seg.is_up() or seg.high <= level:
            continue
        next_seg = segments[i + 1] if i + 1 < len(segments) else None
        if next_seg is not None and next_seg.is_down() and next_seg.low >= level:
            return seg, next_seg
    return None, None


def _find_sell3_segment_leave_hold(
    segments: list[Segment], zhongshu: Zhongshu, level: float
) -> tuple[Segment | None, Segment | None]:
    """段级：核心起，向下离开后紧随的向上反抽不破 level。"""
    for i, seg in enumerate(segments):
        if seg.segment_id < zhongshu.start_bi_id:
            continue
        if not seg.is_down() or seg.low >= level:
            continue
        next_seg = segments[i + 1] if i + 1 < len(segments) else None
        if next_seg is not None and next_seg.is_up() and next_seg.high <= level:
            return seg, next_seg
    return None, None


def _immediate_next_bi(bis: list[Bi], anchor_bi: Bi | None) -> Bi | None:
    """anchor_bi 在 bis 列表中的紧随下一根笔。"""
    if anchor_bi is None:
        return None
    for i, bi in enumerate(bis):
        if bi.bi_id == anchor_bi.bi_id and i + 1 < len(bis):
            return bis[i + 1]
    return None


def _immediate_down_bi_holding_above(bis: list[Bi], anchor_bi: Bi | None, level: float) -> Bi | None:
    """anchor_bi 紧随的向下笔且 low >= level（回试尚未成段时回退到笔级）。"""
    next_bi = _immediate_next_bi(bis, anchor_bi)
    if next_bi is not None and next_bi.is_down() and next_bi.low >= level:
        return next_bi
    return None


def _immediate_up_bi_holding_below(bis: list[Bi], anchor_bi: Bi | None, level: float) -> Bi | None:
    """anchor_bi 紧随的向上笔且 high <= level（反抽尚未成段时回退到笔级）。"""
    next_bi = _immediate_next_bi(bis, anchor_bi)
    if next_bi is not None and next_bi.is_up() and next_bi.high <= level:
        return next_bi
    return None


def _last_up_segment_breaking_above(segments: list[Segment], zhongshu: Zhongshu, level: float) -> Segment | None:
    """段级：核心起，最后一个 high > level 的向上段（回试尚未成段时的离开段）。"""
    for seg in reversed(segments):
        if seg.segment_id < zhongshu.start_bi_id:
            continue
        if seg.is_up() and seg.high > level:
            return seg
    return None


def _last_down_segment_breaking_below(segments: list[Segment], zhongshu: Zhongshu, level: float) -> Segment | None:
    """段级：核心起，最后一个 low < level 的向下段（反抽尚未成段时的离开段）。"""
    for seg in reversed(segments):
        if seg.segment_id < zhongshu.start_bi_id:
            continue
        if seg.is_down() and seg.low < level:
            return seg
    return None


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
    """同级别分解（第38/39课）：只按中枢区间重叠与否判定，不处理中枢扩张。

    区间不重叠 → 趋势（up/down）；区间重叠 → 盘整/延伸（range）。
    中枢扩张/更高级别中枢属于「纯粹按中枢」的非同级别分解视角，不在此判定。
    """
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
                "start_ts": _isoformat_ts(run[0].start_ts),
                "end_ts": _isoformat_ts(run[-1].end_ts),
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
        "start_ts": group.get("start_ts"),
        "end_ts": group.get("end_ts"),
    }


def _current_run_completed_type_entries(
    current_run: list[Zhongshu],
    relations: list[str],
    current_start_index: int,
) -> list[dict[str, object]]:
    """枚举 current_run 内 current_start_index 之前的所有已完成类型块（早→晚）。

    块边界按 relations 的相邻异同切分，与 `last_completed` 的回退口径一致；
    相邻块共享一个边界中枢（后一块的 start_index 即前一块的 end_index），
    从而把 `up → range → up` 这类段内多段切换完整展开进 type_chain 前缀。
    """
    entries: list[dict[str, object]] = []
    end_index = current_start_index - 1
    while end_index >= 0:
        start_index = end_index
        if end_index > 0:
            block_kind = relations[end_index - 1]
            while start_index > 0 and relations[start_index - 1] == block_kind:
                start_index -= 1
        entries.insert(
            0,
            _group_type_chain_entry(
                _build_group_state(
                    current_run,
                    start_index,
                    end_index,
                    status="completed",
                    latest_ts=current_run[end_index].end_ts,
                    confirmation_basis="confirmed_by_following_same_level_structure",
                )
            ),
        )
        if start_index == 0:
            break
        end_index = start_index
    return entries


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


def _build_decomposition_selector(
    structure_state: dict[str, object],
    zhongshus: list[Zhongshu],
) -> dict[str, object]:
    """同级别分解的多义性契约锚点（第38/39课）。

    同级别分解具有唯一性（「同级别分解具有唯一性，不存在任何含糊乱分解的可能」），
    只按中枢区间重叠与否判定（重叠=延伸，不重叠=趋势），不处理中枢扩张/更高级别中枢。
    因此 `dual_interpretation_pending` 表达的是「确认待定」（单中枢/候选新类型尚未确认），
    而非「存在多个合法分解」——同级别分解下没有可枚举的几何多解，无需选择。
    本字段保留为 machine-readable 契约锚点：未来若引入扩张/更高级别分解，选择器从
    此挂接。
    """
    mode = _build_same_level_decomposition_mode(structure_state)
    if mode != "dual_interpretation_pending":
        return {
            "mode": mode,
            "alternatives": [],
            "selected": None,
            "selection_reason": "同级别分解唯一分解已收敛，无需选择。",
        }

    relationship = structure_state.get("relationship") or {}
    transition_state = str(relationship.get("transition_state") or "").strip()
    if transition_state == "candidate_new_type":
        reason = "前段已完成、当前为新类型候选（单中枢未确认）；同级别分解具唯一性，无几何多解，待确认即可。"
    else:
        reason = "当前为单中枢/无中枢的确认待定；同级别分解具唯一性，无几何多解，待确认即可。"
    return {
        "mode": mode,
        "alternatives": [],
        "selected": None,
        "selection_reason": reason,
    }


def _finalize_structure_state(
    structure_state: dict[str, object],
    zhongshus: list[Zhongshu],
) -> dict[str, object]:
    structure_state["decomposition_selector"] = _build_decomposition_selector(structure_state, zhongshus)
    return structure_state


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
        return _finalize_structure_state({
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
        }, zhongshus)

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
        return _finalize_structure_state({
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
                    "start_ts": _isoformat_ts(only.start_ts),
                    "end_ts": None,
                }
            ],
        }, zhongshus)

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
    if current_start_index > 0:
        type_chain.extend(
            _current_run_completed_type_entries(current_run, relations, current_start_index)
        )
    type_chain.append(_group_type_chain_entry(current_ongoing))

    return _finalize_structure_state({
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
    }, zhongshus)


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
    segments: list[Segment] | None = None,
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

    # 线段级中枢：一类点背驰用「离开段 vs 进入段」严格力度口径；笔级中枢保持笔级口径。
    segment_bottom_divergence = False
    segment_top_divergence = False
    entering_segment: Segment | None = None
    exit_segment: Segment | None = None
    if current_zs is not None and current_zs.structure_level == "segment" and segments:
        entering_segment = _segment_by_id(current_zs.entering_bi_id, segments)
        exit_segment = _segment_by_id(current_zs.exit_bi_id, segments)
        if entering_segment is not None and exit_segment is not None:
            segment_strengths = compute_segment_strengths(segments, macd_points)
            segment_bottom_divergence = _has_segment_bottom_divergence(
                exit_segment, entering_segment, segment_strengths
            )
            segment_top_divergence = _has_segment_top_divergence(
                exit_segment, entering_segment, segment_strengths
            )

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
        if current_zs.structure_level == "segment" and segments:
            current_zs_exit_bi = _segment_by_id(current_zs.exit_bi_id, segments)
        else:
            current_zs_exit_bi = next((bi for bi in bis if bi.bi_id == current_zs.exit_bi_id), None)
    buy_points: list[str] = []
    sell_points: list[str] = []
    use_segment_divergence = current_zs is not None and current_zs.structure_level == "segment" and bool(segments)
    buy_divergence = segment_bottom_divergence if use_segment_divergence else bottom_divergence
    sell_divergence = segment_top_divergence if use_segment_divergence else top_divergence

    # 一类点信号锚点：段级模式取离开段末笔（而非最新同向笔），边界/转折均以离开段末笔为基准。
    buy_signal_bi = latest_down
    sell_signal_bi = latest_confirmed_up
    exit_end_bi: Bi | None = None
    if use_segment_divergence and exit_segment is not None:
        exit_end_bi = _bi_by_id(exit_segment.end_bi_id, bis)
        if exit_end_bi is not None:
            if exit_segment.is_down():
                buy_signal_bi = exit_end_bi
            else:
                sell_signal_bi = exit_end_bi
    if (
        current_zs
        and buy_signal_bi
        and buy_signal_bi.is_confirmed
        and buy_divergence
        and buy_signal_bi.low <= current_zs.zs_low
        and _has_reverse_turn_after(buy_signal_bi, direction="down", bis=bis)
    ):
        buy_points.append("buy_1")
    if (
        current_zs
        and sell_signal_bi
        and sell_signal_bi.is_confirmed
        and sell_divergence
        and sell_signal_bi.high >= current_zs.zs_high
        and _has_reverse_turn_after(sell_signal_bi, direction="up", bis=bis)
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
    buy2_precursor = segment_bottom_divergence if use_segment_divergence else previous_buy1_active
    buy2_anchor = buy_signal_bi if use_segment_divergence else latest_confirmed_down
    if (
        current_zs
        and buy2_precursor
        and latest_up
        and latest_down
        and buy2_anchor is not None
        and latest_down.bi_id != buy2_anchor.bi_id
        and latest_down.low > buy2_anchor.low
        and _is_first_reverse_hold(buy2_anchor, latest_down, bis)
        and latest_up.bi_id > latest_down.bi_id
        and _renewed_beyond_previous(latest_up, latest_down, bis)
    ):
        buy_points.append("buy_2")
    buy3_signal_bi: Bi | None = None
    if current_zs and latest_up:
        if use_segment_divergence and segments:
            leave_seg, hold_seg = _find_buy3_segment_leave_hold(segments, current_zs, current_zs.zs_high)
            if hold_seg is not None:
                hold_bi = _bi_by_id(hold_seg.end_bi_id, bis) or _bi_by_id(hold_seg.start_bi_id, bis)
            else:
                anchor_seg = (
                    exit_segment
                    if exit_segment is not None and exit_segment.is_up()
                    else _last_up_segment_breaking_above(segments, current_zs, current_zs.zs_high)
                )
                anchor_bi = _bi_by_id(anchor_seg.end_bi_id, bis) if anchor_seg is not None else None
                hold_bi = _immediate_down_bi_holding_above(bis, anchor_bi, current_zs.zs_high)
            if hold_bi is not None and latest_up.bi_id > hold_bi.bi_id:
                buy3_signal_bi = hold_bi
                buy_points.append("buy_3")
        else:
            _leave_bi, hold_bi = _find_buy3_bi_leave_hold(bis, current_zs.zs_high)
            if hold_bi is not None and latest_up.bi_id > hold_bi.bi_id:
                buy3_signal_bi = hold_bi
                buy_points.append("buy_3")
    previous_sell1_active = (
        current_zs is not None
        and latest_confirmed_up is not None
        and previous_confirmed_up is not None
        and _has_top_divergence(latest_confirmed_up, previous_confirmed_up, strengths)
        and latest_confirmed_up.high >= current_zs.zs_high
    )
    sell2_precursor = segment_top_divergence if use_segment_divergence else previous_sell1_active
    sell2_anchor = sell_signal_bi if use_segment_divergence else latest_confirmed_up
    if (
        current_zs
        and sell2_precursor
        and latest_up
        and latest_down
        and sell2_anchor is not None
        and latest_up.bi_id != sell2_anchor.bi_id
        and latest_up.high < sell2_anchor.high
        and _is_first_reverse_hold(sell2_anchor, latest_up, bis)
        and latest_down.bi_id > latest_up.bi_id
        and _renewed_beyond_previous(latest_down, latest_up, bis)
    ):
        sell_points.append("sell_2")
    sell3_signal_bi: Bi | None = None
    if current_zs and latest_down:
        if use_segment_divergence and segments:
            leave_seg, hold_seg = _find_sell3_segment_leave_hold(segments, current_zs, current_zs.zs_low)
            if hold_seg is not None:
                hold_bi = _bi_by_id(hold_seg.end_bi_id, bis) or _bi_by_id(hold_seg.start_bi_id, bis)
            else:
                anchor_seg = (
                    exit_segment
                    if exit_segment is not None and exit_segment.is_down()
                    else _last_down_segment_breaking_below(segments, current_zs, current_zs.zs_low)
                )
                anchor_bi = _bi_by_id(anchor_seg.end_bi_id, bis) if anchor_seg is not None else None
                hold_bi = _immediate_up_bi_holding_below(bis, anchor_bi, current_zs.zs_low)
            if hold_bi is not None and latest_down.bi_id > hold_bi.bi_id:
                sell3_signal_bi = hold_bi
                sell_points.append("sell_3")
        else:
            _leave_bi, hold_bi = _find_sell3_bi_leave_hold(bis, current_zs.zs_low)
            if hold_bi is not None and latest_down.bi_id > hold_bi.bi_id:
                sell3_signal_bi = hold_bi
                sell_points.append("sell_3")

    # 三买与三卖针对同一中枢互斥：若两者同时触发，仅保留更晚的「离开-回试」，
    # 较新的信号覆盖较早的信号（例如先向上离开成三买、随后反转向下跌破成三卖）。
    if buy3_signal_bi is not None and sell3_signal_bi is not None:
        if sell3_signal_bi.bi_id > buy3_signal_bi.bi_id:
            buy3_signal_bi = None
            if "buy_3" in buy_points:
                buy_points.remove("buy_3")
        else:
            sell3_signal_bi = None
            if "sell_3" in sell_points:
                sell_points.remove("sell_3")

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
        buy3_signal_bi=buy3_signal_bi,
        sell3_signal_bi=sell3_signal_bi,
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
    buy3_signal_bi: Bi | None = None,
    sell3_signal_bi: Bi | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    signal_points: list[dict[str, object]] = []
    signal_catalog: list[dict[str, object]] = []
    related_zs_id = current_zs.zs_id if current_zs else None
    related_bi_ids = list(current_zs.bi_ids) if current_zs else []

    def buy_signal_bi_for(point: str) -> Bi | None:
        if point == "buy_3" and buy3_signal_bi is not None:
            return buy3_signal_bi
        return latest_down

    def sell_signal_bi_for(point: str) -> Bi | None:
        if point == "sell_3" and sell3_signal_bi is not None:
            return sell3_signal_bi
        return latest_up if point == "sell_2" else latest_confirmed_up

    for point in buy_points:
        basis = {
            "buy_1": "bottom_divergence_near_zs_low",
            "buy_2": "buy1_pullback_confirmation",
            "buy_3": "leave_zs_then_pullback_holds_upper_edge",
        }.get(point)
        signal_bi = buy_signal_bi_for(point)
        signal_points.append(
            _build_signal_point_detail(
                point,
                signal_bi,
                getattr(signal_bi, "low", None),
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
        signal_bi = sell_signal_bi_for(point)
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
        signal_bi = buy_signal_bi_for(point)
        signal_catalog.append(
            _build_signal_point_detail(
                point,
                signal_bi,
                getattr(signal_bi, "low", None) if point in active_points else None,
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
        signal_bi = sell_signal_bi_for(point)
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
    dynamic_grade = precision_entry.get("dynamic_grade")
    dynamic_grade_label = precision_entry.get("dynamic_grade_label")
    if not label and not description and not dynamic_grade_label:
        return None
    lines = [line for line in [f"{operation_level}窗口：{label}" if label else None, description] if line]
    if dynamic_grade_label:
        lines.append(f"{operation_level}判级：{dynamic_grade_label}")
    return {
        "title": f"{operation_level}区间套窗口",
        "label": label,
        "description": description,
        "dynamic_grade": dynamic_grade,
        "dynamic_grade_label": dynamic_grade_label,
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


def _higher_level_drift(higher_signals: dict[str, object]) -> str | None:
    """上级别中枢漂移方向（86课动态判级输入）：up / down / range / None。"""
    structure_state = higher_signals.get("structure_state") or {}
    current_ongoing = structure_state.get("current_ongoing") or {}
    drift = str(current_ongoing.get("type") or "").strip()
    return drift if drift in {"up", "down", "range"} else None


def _grade_by_higher_drift(drift: str | None, side: str) -> str | None:
    """86课：次级别买卖点随大级别中枢漂移方向的操作意义分级。

    - 震荡（range）：买卖点都只是震荡机会。
    - 上移（up）：卖点逆势=警戒，买点顺势但滞后=无操作价值。
    - 下移（down）：卖点顺势但滞后=无操作价值，买点逆势=警戒。
    """
    if drift == "range":
        return PrecisionDynamicGrade.OSCILLATION_OPPORTUNITY.value
    if drift == "up":
        return PrecisionDynamicGrade.WARNING.value if side == "sell" else PrecisionDynamicGrade.NO_OPERATIONAL_VALUE.value
    if drift == "down":
        return PrecisionDynamicGrade.NO_OPERATIONAL_VALUE.value if side == "sell" else PrecisionDynamicGrade.WARNING.value
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

    higher_consumption_level = str(higher_signals.get("same_level_consumption_level") or "").strip()
    higher_consumption_level_label = format_consumption_level_label(higher_consumption_level)
    if higher_consumption_level in {"auxiliary", "pending"} and status == "actionable":
        status = "watch"
        note = (
            f"{note} 上级别同级别结构尚未确认为稳定标准中枢"
            f"（{higher_consumption_level_label or higher_consumption_level}），"
            f"次级别买卖点仅作观察提示，不按严格区间套执行。"
        )

    higher_drift = _higher_level_drift(higher_signals)
    dynamic_grade = _grade_by_higher_drift(higher_drift, side)
    dynamic_grade_label = PRECISION_DYNAMIC_GRADE_LABELS.get(dynamic_grade) if dynamic_grade else None

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
        "higher_consumption_level": higher_consumption_level or None,
        "higher_consumption_level_label": higher_consumption_level_label,
        "dynamic_grade": dynamic_grade,
        "dynamic_grade_label": dynamic_grade_label,
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