from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import Bar, Bi, Segment, Zhongshu
from .zhongshu import is_zhongshu_expansion
from .zhongshu_contract import (
    CONSUMPTION_LEVEL_LABELS,
    CONSUMPTION_LEVEL_NOTES,
    TRANSITION_STATE_LABELS,
    TRANSITION_STATE_NOTES,
)
from .analysis_contract import (
    PRECISION_DYNAMIC_GRADE_LABELS,
    SIGNAL_BASIS_LABELS,
    SIGNAL_LIFECYCLE_STATE_LABELS,
    SIGNAL_POINT_LABELS,
    SMALL_TO_LARGE_STATUS_LABELS,
    SMALL_TO_LARGE_STATUS_NOTES,
    STRUCTURE_STATUS_LABELS,
    STRUCTURE_STATUS_NOTES,
    PrecisionDynamicGrade,
    SignalInvalidatedReason,
    SignalLifecycleState,
    SmallToLargeStatus,
    StructureStatus,
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


def format_small_to_large_status_label(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return SMALL_TO_LARGE_STATUS_LABELS.get(str(value), str(value))


def describe_small_to_large_status(value: Any) -> str:
    return SMALL_TO_LARGE_STATUS_NOTES.get(str(value or ""), "")


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
    """candidate 是否落在 anchor 之后「第一次确认性回抽 / 反抽」窗口内（spec §2.3）。

    二类点只能建立在一类点之后的第一次回试上：
    - 窗口：candidate 必须是 anchor 之后第一个同向回试笔（回抽 / 反抽）。
    - 失败 / 失效：若 anchor 之后、candidate 之前已出现更早的同向回试笔——无论它是否跌破 /
      升破 anchor 极值——首次回抽窗口都已被占用（更早那次已成或已破位失败），candidate 不再是
      「首次确认性回抽」，不得重复标二类点。这把原先仅「不破前低 / 前高」的判定扩到含破位失败态。
    candidate 自身不破 anchor 极值仍由调用方（`low > anchor.low` / `high < anchor.high`）校验。
    """
    for other in bis:
        if other.bi_id <= anchor.bi_id or other.bi_id >= candidate.bi_id:
            continue
        # anchor 向下 -> 首个向下回抽即占用窗口；anchor 向上 -> 首个向上反抽即占用窗口。
        if anchor.is_down() and other.is_down():
            return False
        if anchor.is_up() and other.is_up():
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


def _find_lb2_gap_divergence(
    segments: list[Segment],
    segment_strengths: dict[int, dict[str, float]],
) -> Segment | None:
    """类二买（LB2）隔段背驰：以最后一个已确认线段 A_{i+2}（当下回踩段，须向下）为锚，
    全链相邻取 A_i(下)-A_{i+1}(上)-A_{i+2}(下)；A_{i+2} 相对 A_i 段级力度衰减即成立，
    不要求破前低（贴合「不需要破前低/前高」）。返回 A_{i+2}（回踩段）。"""
    idx = next((i for i in range(len(segments) - 1, -1, -1) if segments[i].is_confirmed), None)
    if idx is None or idx < 2:
        return None
    ai, ai1, ai2 = segments[idx - 2], segments[idx - 1], segments[idx]
    if not (ai.is_down() and ai1.is_up() and ai2.is_down()):
        return None
    strength_ai = segment_strengths.get(ai.segment_id, {}).get("macd_sum_abs", 0.0)
    strength_ai2 = segment_strengths.get(ai2.segment_id, {}).get("macd_sum_abs", 0.0)
    if strength_ai > 0 and strength_ai2 < strength_ai:
        return ai2
    return None


def _find_ls2_gap_divergence(
    segments: list[Segment],
    segment_strengths: dict[int, dict[str, float]],
) -> Segment | None:
    """类二卖（LS2）隔段背驰：以最后一个已确认线段 A_{i+2}（当下反抽段，须向上）为锚，
    全链相邻取 A_i(上)-A_{i+1}(下)-A_{i+2}(上)；A_{i+2} 相对 A_i 段级力度衰减即成立，
    不要求破前高（贴合「不需要破前低/前高」）。返回 A_{i+2}（反抽段）。"""
    idx = next((i for i in range(len(segments) - 1, -1, -1) if segments[i].is_confirmed), None)
    if idx is None or idx < 2:
        return None
    ai, ai1, ai2 = segments[idx - 2], segments[idx - 1], segments[idx]
    if not (ai.is_up() and ai1.is_down() and ai2.is_up()):
        return None
    strength_ai = segment_strengths.get(ai.segment_id, {}).get("macd_sum_abs", 0.0)
    strength_ai2 = segment_strengths.get(ai2.segment_id, {}).get("macd_sum_abs", 0.0)
    if strength_ai > 0 and strength_ai2 < strength_ai:
        return ai2
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
    lifecycle_state: str | None = None,
    invalidated_reason: str | None = None,
) -> dict[str, object]:
    # 生命周期（spec §2.8 §3.3）：active 点未显式给状态时按 confirmed；forming/invalidated 由调用方显式传入。
    # 兜底 fail closed：§3.3 红线要求 confirmed 只能锚定 `is_confirmed=True` 的笔 / 线段，
    # 未确认笔只能承载 forming。若这里无条件盖 confirmed，未确认尾笔会被贴上确认态，
    # 并在后续帧因笔编号重排而「凭空消失」，直接撞上 repaint 红线。
    if lifecycle_state is None and active:
        anchor_confirmed = signal_bi is None or bool(getattr(signal_bi, "is_confirmed", False))
        lifecycle_state = (
            SignalLifecycleState.CONFIRMED.value
            if anchor_confirmed
            else SignalLifecycleState.FORMING.value
        )
    populated = active or lifecycle_state in (
        SignalLifecycleState.FORMING.value,
        SignalLifecycleState.INVALIDATED.value,
    )
    return {
        "point": _format_signal_point_name(point),
        "active": active,
        "lifecycle_state": lifecycle_state,
        "invalidated_reason": invalidated_reason,
        "signal_bi_id": signal_bi.bi_id if signal_bi else None,
        "time": _isoformat_ts(signal_bi.end_ts) if signal_bi else None,
        "price": round(float(price), 2) if price is not None else None,
        "basis": basis if populated else None,
        "related_zs_id": related_zs_id if populated else None,
        "related_bi_ids": list(related_bi_ids or []) if populated else [],
    }


def _relation_kind(previous: Zhongshu, current: Zhongshu) -> str:
    """同级别分解（第38/39课）+ 第20课中枢扩张：按中枢区间重叠判定走势类型。

    区间不重叠、且波动区间（GG/DD）回探重叠 → 中枢扩张，归入盘整（range）。
    区间不重叠、且波动不回探 → 趋势（up/down）。
    区间重叠 → 盘整/延伸（range）。

    扩张判定复用 `is_zhongshu_expansion`（第20课中枢中心定理二，GG/DD inclusive），
    保证走势类型改判与 `identify_expanded_zhongshus` 的更大级别中枢对象口径一致。
    """
    if current.zs_low > previous.zs_high:
        return "range" if is_zhongshu_expansion(previous, current) else "up"
    if current.zs_high < previous.zs_low:
        return "range" if is_zhongshu_expansion(previous, current) else "down"
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


def _decompose_walk_types(zhongshus: list[Zhongshu]) -> list[tuple[str, int, int]]:
    """同级别分解（第38/39课，spec §2/§5/§8）：把中枢链唯一分解为走势类型块。

    - 盘整(range)=恰好一个本级别中枢；相邻 range 关系（区间重叠或 GG/DD 回探扩张）
      各自独立成一个盘整（§8.2），不折叠成 zs_count>1 的大盘整。
    - 趋势(up/down)=>=2 个连续、同向、真不重叠（`_relation_kind` 判为 up/down）的中枢，
      合并为一个趋势块（§7）。

    返回 [(type, start_index, end_index), ...]，index 指向 zhongshus（含首尾）。
    """
    count = len(zhongshus)
    if count == 0:
        return []
    if count == 1:
        return [("range", 0, 0)]
    relations = [_relation_kind(zhongshus[i], zhongshus[i + 1]) for i in range(count - 1)]
    blocks: list[tuple[str, int, int]] = []
    index = 0
    while index < count:
        if index < count - 1 and relations[index] in {"up", "down"}:
            direction = relations[index]
            end_index = index + 1
            while end_index < count - 1 and relations[end_index] == direction:
                end_index += 1
            blocks.append((direction, index, end_index))
            index = end_index + 1
        else:
            blocks.append(("range", index, index))
            index += 1
    return blocks


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
    if not current_status and not confirmation_basis:
        # ZS5.2 三态契约原则第 5 条：字段缺失时一律按 unknown -> pending/auxiliary 降级，
        # 不允许补脑成 confirmed。此处是**共享**消费等级的唯一兜底，若默认 confirmed 会 fail open，
        # 直接击穿 T2 红线（高一级未确认时下游不得越级显示强确认）的多级别降级闸门。
        # 真实数据核查（21 个冻结窗口 + 4 个冻结 tech.json）两个字段均存在，本分支不可达，
        # 故该硬化在真实输出上行为中性，见 build/probe_consumption_default.py。
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
    # spec_id: SPEC.TREND_DIVERGENCE.SAME_LEVEL_DECOMPOSITION
    # 见 docs/chanlun/same-level-decomposition-spec.md；其上层走势类型/背驰总纲见
    # docs/chanlun/trend-divergence-spec.md。
    # 严格同级别分解：消费全部检出中枢（不做扩张重吸收裁剪），按 _decompose_walk_types 唯一切分
    # 为盘整(每盘整=1中枢) / 趋势(>=2 同向不重叠中枢) 走势类型块。
    latest_bar_ts = raw_bars[-1].ts if raw_bars else None
    chain = list(zhongshus)
    blocks = _decompose_walk_types(chain)

    if not blocks:
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

    def _block_confirmation_basis(kind: str, status: str) -> str:
        if status == "completed":
            return "confirmed_by_following_same_level_structure"
        if kind in {"up", "down"}:
            return "forming_next_same_level_zhongshu"
        return "single_active_zhongshu"

    groups: list[dict[str, object]] = []
    for block_index, (kind, start_index, end_index) in enumerate(blocks):
        is_last = block_index == len(blocks) - 1
        status = "ongoing" if is_last else "completed"
        groups.append(
            _build_group_state(
                chain,
                start_index,
                end_index,
                status=status,
                latest_ts=latest_bar_ts if is_last else chain[end_index].end_ts,
                confirmation_basis=_block_confirmation_basis(kind, status),
            )
        )

    current_ongoing = groups[-1]
    last_completed = groups[-2] if len(groups) >= 2 else None
    type_chain = [_group_type_chain_entry(group) for group in groups]

    if last_completed is None:
        relationship_kind = "undetermined"
        transition_state = "none"
        if current_ongoing.get("type") in {"up", "down"}:
            relationship_note = "已经出现同向不重叠中枢推进，当前按同级别分解视为趋势进行中。"
        else:
            relationship_note = "当前只有一个同级别中枢，按同级别分解视为盘整进行中。"
        current_structure_status = "ongoing_same_type"
    else:
        relationship_kind = "completed_then_new_type_ongoing"
        if current_ongoing.get("confirmation_basis") == "single_active_zhongshu":
            transition_state = "candidate_new_type"
            current_structure_status = "candidate_completed_waiting_stability"
            relationship_note = "上一段同级别走势已结束，当前新的同级别走势仍处候选待确认阶段。"
        else:
            transition_state = "ongoing_new_type"
            current_structure_status = "completed_then_new_type"
            relationship_note = "上一段同级别走势已结束，当前正在运行的是新的同级别走势类型。"

    consumption_level = _build_same_level_consumption_level(
        {
            "current_ongoing": current_ongoing,
            "current_structure_status": current_structure_status,
        }
    )

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
    ongoing_type = (structure_state.get("current_ongoing") or {}).get("type")

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
    # RS3 级别收敛：标准一/二类点是操作级别信号，须依附段级中枢；笔级中枢比线段级低半级，
    # 仅供执行级别/区间套次级别定位，不冒充操作级别点。故一/二类发点统一门控在 use_segment_divergence，
    # 段级中枢未成型（笔级中枢兜底）时操作级别只观察、不发一/二类点。
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
        and use_segment_divergence
        and ongoing_type == "down"
        and buy_signal_bi
        and buy_signal_bi.is_confirmed
        and buy_divergence
        and buy_signal_bi.low <= current_zs.zs_low
        and _has_reverse_turn_after(buy_signal_bi, direction="down", bis=bis)
    ):
        buy_points.append("buy_1")
    if (
        current_zs
        and use_segment_divergence
        and ongoing_type == "up"
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
        and use_segment_divergence
        and ongoing_type == "down"
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
    buy3_hold_bi: Bi | None = None
    if current_zs and latest_up:
        if use_segment_divergence and segments:
            _leave_seg, hold_seg = _find_buy3_segment_leave_hold(segments, current_zs, current_zs.zs_high)
            if hold_seg is not None:
                hold_bi = _bi_by_id(hold_seg.end_bi_id, bis) or _bi_by_id(hold_seg.start_bi_id, bis)
                if hold_bi is not None:
                    buy3_hold_bi = hold_bi
                    if latest_up.bi_id > hold_bi.bi_id:
                        buy3_signal_bi = hold_bi
                        buy_points.append("buy_3")
        else:
            _leave_bi, hold_bi = _find_buy3_bi_leave_hold(bis, current_zs.zs_high)
            if hold_bi is not None:
                buy3_hold_bi = hold_bi
                if latest_up.bi_id > hold_bi.bi_id:
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
        and use_segment_divergence
        and ongoing_type == "up"
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
    sell3_hold_bi: Bi | None = None
    if current_zs and latest_down:
        if use_segment_divergence and segments:
            _leave_seg, hold_seg = _find_sell3_segment_leave_hold(segments, current_zs, current_zs.zs_low)
            if hold_seg is not None:
                hold_bi = _bi_by_id(hold_seg.end_bi_id, bis) or _bi_by_id(hold_seg.start_bi_id, bis)
                if hold_bi is not None:
                    sell3_hold_bi = hold_bi
                    if latest_down.bi_id > hold_bi.bi_id:
                        sell3_signal_bi = hold_bi
                        sell_points.append("sell_3")
        else:
            _leave_bi, hold_bi = _find_sell3_bi_leave_hold(bis, current_zs.zs_low)
            if hold_bi is not None:
                sell3_hold_bi = hold_bi
                if latest_down.bi_id > hold_bi.bi_id:
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

    # 类二类买卖点（LB2/LS2）：同级别隔段背驰（A_i vs A_{i+2}）+ 回踩/反抽结束即生成，
    # 无前置一类点、不设破前低/前高，与标准二类点去重（标准点已成立时不重复标记）。
    # 仅在同级别分解已确认（最近中枢语义清晰）时给点；dual_interpretation_pending
    # （单/无确认中枢、候选待定）只作观察，不发机械点（spec §2.5/§2.6）。
    buy2like_signal_bi: Bi | None = None
    sell2like_signal_bi: Bi | None = None
    buy2like_anchor_bi: Bi | None = None
    sell2like_anchor_bi: Bi | None = None
    if (
        current_zs is not None
        and segments
        and _build_same_level_decomposition_mode(structure_state) == "single_confirmed"
    ):
        like_segment_strengths = compute_segment_strengths(segments, macd_points)
        if "buy_2" not in buy_points:
            lb2_seg = _find_lb2_gap_divergence(segments, like_segment_strengths)
            if lb2_seg is not None:
                anchor = _bi_by_id(lb2_seg.end_bi_id, bis)
                if anchor is not None:
                    buy2like_anchor_bi = anchor
                    if _has_reverse_turn_after(anchor, direction="down", bis=bis):
                        buy2like_signal_bi = anchor
                        buy_points.append("buy_2like")
        if "sell_2" not in sell_points:
            ls2_seg = _find_ls2_gap_divergence(segments, like_segment_strengths)
            if ls2_seg is not None:
                anchor = _bi_by_id(ls2_seg.end_bi_id, bis)
                if anchor is not None:
                    sell2like_anchor_bi = anchor
                    if _has_reverse_turn_after(anchor, direction="up", bis=bis):
                        sell2like_signal_bi = anchor
                        sell_points.append("sell_2like")

    # 类一类买卖点（LB1/LS1）：盘整背驰（离开段 vs 进入段，range 门控）+ 反向转折即生成，
    # 补标准一类点因趋势门控（ongoing_type==down/up）缺席的场景（spec §2.5，第27/65课）。
    # 复用一买/一卖同一背驰量与锚点，仅把趋势门控换成 range；与标准一类点、类二类点去重。
    # 门控为「单中枢中枢震荡」（ongoing_type==range 且 current_structure_status==ongoing_same_type，
    # 即最近中枢语义清晰的盘整），排除 candidate_completed_waiting_stability 过渡态（只观察）。
    buy1like_signal_bi: Bi | None = None
    sell1like_signal_bi: Bi | None = None
    if (
        current_zs is not None
        and ongoing_type == "range"
        and str(structure_state.get("current_structure_status") or "") == "ongoing_same_type"
    ):
        if (
            "buy_1" not in buy_points
            and buy_signal_bi is not None
            and buy_signal_bi.is_confirmed
            and buy_divergence
            and buy_signal_bi.low <= current_zs.zs_low
            and (buy2like_signal_bi is None or buy2like_signal_bi.bi_id != buy_signal_bi.bi_id)
            and _has_reverse_turn_after(buy_signal_bi, direction="down", bis=bis)
        ):
            buy1like_signal_bi = buy_signal_bi
            buy_points.append("buy_1like")
        if (
            "sell_1" not in sell_points
            and sell_signal_bi is not None
            and sell_signal_bi.is_confirmed
            and sell_divergence
            and sell_signal_bi.high >= current_zs.zs_high
            and (sell2like_signal_bi is None or sell2like_signal_bi.bi_id != sell_signal_bi.bi_id)
            and _has_reverse_turn_after(sell_signal_bi, direction="up", bis=bis)
        ):
            sell1like_signal_bi = sell_signal_bi
            sell_points.append("sell_1like")

    # RS1 实时预备态（spec §2.8）：背驰 / 离开条件已成立但反向转折尚未确认时，给 forming 观察态。
    # 覆盖一类 / 类一 / 二类 / 三类 / 类二（背驰 / 离开 / 隔段力度衰减已现、反向转折待确认）。
    # forming 只进入独立 `forming_points`，不写入 buy_points/sell_points/signal_points/signal_catalog，
    # 保持既有 confirmed 消费与 catalog 索引契约不变（spec §2.8 repaint 红线：forming 不得升 confirmed）。
    forming_points: list[dict[str, object]] = []
    forming_zs_id = current_zs.zs_id if current_zs else None
    forming_bi_ids = list(current_zs.bi_ids) if current_zs else []
    forming_same_type_range = (
        ongoing_type == "range"
        and str(structure_state.get("current_structure_status") or "") == "ongoing_same_type"
    )

    def _append_forming(point: str, signal_bi: Bi | None, price: float | None, basis: str) -> None:
        forming_points.append(
            _build_signal_point_detail(
                point,
                signal_bi,
                price,
                active=False,
                basis=basis,
                related_zs_id=forming_zs_id,
                related_bi_ids=forming_bi_ids,
                lifecycle_state=SignalLifecycleState.FORMING.value,
            )
        )

    if current_zs is not None:
        # forming（实时预备态）的锚点必须是**实时尾部**，而不是已完成的离开段末笔。
        # 离开段既已确认，其后必然还有后续笔（笔严格交替且已确认），于是
        # `_has_reverse_turn_after(离开段末笔)` 恒为 True —— forming 在真实链路上永不可达，
        # 只在「把离开笔截成链尾」的构造输入下成立（RS1 原单测正是这样截的）。
        # 尾部口径：最新同向笔仍停在离开极值一侧、且其后尚无已确认反向笔 = 待转折确认。
        # 这两个变量只服务 forming，不影响任何 confirmed 发点（confirmed 仍以离开段末笔为准）。
        buy_forming_bi = (
            latest_down if latest_down is not None and latest_down.low <= current_zs.zs_low else None
        )
        sell_forming_bi = (
            latest_up if latest_up is not None and latest_up.high >= current_zs.zs_high else None
        )
        buy_break = (
            buy_forming_bi is not None
            and buy_divergence
            and not _has_reverse_turn_after(buy_forming_bi, direction="down", bis=bis)
        )
        sell_break = (
            sell_forming_bi is not None
            and sell_divergence
            and not _has_reverse_turn_after(sell_forming_bi, direction="up", bis=bis)
        )
        if "buy_1" not in buy_points and ongoing_type == "down" and buy_break:
            _append_forming(
                "buy_1", buy_forming_bi, getattr(buy_forming_bi, "low", None), "bottom_divergence_near_zs_low"
            )
        if "sell_1" not in sell_points and ongoing_type == "up" and sell_break:
            _append_forming(
                "sell_1", sell_forming_bi, getattr(sell_forming_bi, "high", None), "top_divergence_near_zs_high"
            )
        if "buy_1like" not in buy_points and forming_same_type_range and buy_break:
            _append_forming(
                "buy_1like", buy_forming_bi, getattr(buy_forming_bi, "low", None), "consolidation_divergence_reverse_low"
            )
        if "sell_1like" not in sell_points and forming_same_type_range and sell_break:
            _append_forming(
                "sell_1like", sell_forming_bi, getattr(sell_forming_bi, "high", None), "consolidation_divergence_reverse_high"
            )

        # 二类预备：一类前置 + 首次回抽不破前低 / 前高已成立，待「再度走强 / 走弱创新高 / 新低」确认。
        if (
            "buy_2" not in buy_points
            and ongoing_type == "down"
            and buy2_precursor
            and latest_down is not None
            and buy2_anchor is not None
            and latest_down.bi_id != buy2_anchor.bi_id
            and latest_down.low > buy2_anchor.low
            and _is_first_reverse_hold(buy2_anchor, latest_down, bis)
        ):
            _append_forming("buy_2", latest_down, getattr(latest_down, "low", None), "buy1_pullback_confirmation")
        if (
            "sell_2" not in sell_points
            and ongoing_type == "up"
            and sell2_precursor
            and latest_up is not None
            and sell2_anchor is not None
            and latest_up.bi_id != sell2_anchor.bi_id
            and latest_up.high < sell2_anchor.high
            and _is_first_reverse_hold(sell2_anchor, latest_up, bis)
        ):
            _append_forming("sell_2", latest_up, getattr(latest_up, "high", None), "sell1_rebound_confirmation")

        # 三类预备：离开中枢后首次回踩 / 反抽守住边界已成立，待「再度走强 / 走弱」确认（尚未 renew）。
        if "buy_3" not in buy_points and "sell_3" not in sell_points and buy3_signal_bi is None and buy3_hold_bi is not None:
            _append_forming(
                "buy_3", buy3_hold_bi, getattr(buy3_hold_bi, "low", None), "leave_zs_then_pullback_holds_upper_edge"
            )
        if "sell_3" not in sell_points and "buy_3" not in buy_points and sell3_signal_bi is None and sell3_hold_bi is not None:
            _append_forming(
                "sell_3", sell3_hold_bi, getattr(sell3_hold_bi, "high", None), "leave_zs_then_rebound_fails_lower_edge"
            )

        # 类二预备：同级别隔段背驰已现，待反向转折确认（single_confirmed 门控下捕获的 anchor）。
        if "buy_2like" not in buy_points and buy2like_signal_bi is None and buy2like_anchor_bi is not None:
            _append_forming(
                "buy_2like", buy2like_anchor_bi, getattr(buy2like_anchor_bi, "low", None), "gap_segment_divergence_pullback_end"
            )
        if "sell_2like" not in sell_points and sell2like_signal_bi is None and sell2like_anchor_bi is not None:
            _append_forming(
                "sell_2like", sell2like_anchor_bi, getattr(sell2like_anchor_bi, "high", None), "gap_segment_divergence_rebound_end"
            )

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
        buy1_signal_bi=buy_signal_bi,
        buy2_signal_bi=buy2_anchor,
        buy3_signal_bi=buy3_signal_bi,
        sell1_signal_bi=sell_signal_bi,
        sell2_signal_bi=sell2_anchor,
        sell3_signal_bi=sell3_signal_bi,
        buy2like_signal_bi=buy2like_signal_bi,
        sell2like_signal_bi=sell2like_signal_bi,
        buy1like_signal_bi=buy1like_signal_bi,
        sell1like_signal_bi=sell1like_signal_bi,
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
        "forming_points": forming_points,
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
    buy1_signal_bi: Bi | None = None,
    buy2_signal_bi: Bi | None = None,
    buy3_signal_bi: Bi | None = None,
    sell1_signal_bi: Bi | None = None,
    sell2_signal_bi: Bi | None = None,
    sell3_signal_bi: Bi | None = None,
    buy2like_signal_bi: Bi | None = None,
    sell2like_signal_bi: Bi | None = None,
    buy1like_signal_bi: Bi | None = None,
    sell1like_signal_bi: Bi | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    signal_points: list[dict[str, object]] = []
    signal_catalog: list[dict[str, object]] = []
    related_zs_id = current_zs.zs_id if current_zs else None
    related_bi_ids = list(current_zs.bi_ids) if current_zs else []

    buy_basis_by_point = {
        "buy_1": "bottom_divergence_near_zs_low",
        "buy_2": "buy1_pullback_confirmation",
        "buy_3": "leave_zs_then_pullback_holds_upper_edge",
        "buy_2like": "gap_segment_divergence_pullback_end",
        "buy_1like": "consolidation_divergence_reverse_low",
    }
    sell_basis_by_point = {
        "sell_1": "top_divergence_near_zs_high",
        "sell_2": "sell1_rebound_confirmation",
        "sell_3": "leave_zs_then_rebound_fails_lower_edge",
        "sell_2like": "gap_segment_divergence_rebound_end",
        "sell_1like": "consolidation_divergence_reverse_high",
    }

    def buy_signal_bi_for(point: str) -> Bi | None:
        # 一/二类点在段级模式的锚点必须与发点门控用的是同一根笔（`buy_signal_bi` /
        # `buy2_anchor`，见 `analyze_chanlun_signals`），否则会出现「门控校验的是离开段末笔、
        # 载荷却锤在 latest_down」的不一致，latest_down 可能正是**未确认尾笔**，
        # 直接违反 spec §3.3「confirmed 仅锚定已确认笔/线段」红线。
        if point == "buy_1" and buy1_signal_bi is not None:
            return buy1_signal_bi
        if point == "buy_2" and buy2_signal_bi is not None:
            return buy2_signal_bi
        if point == "buy_3" and buy3_signal_bi is not None:
            return buy3_signal_bi
        if point == "buy_2like" and buy2like_signal_bi is not None:
            return buy2like_signal_bi
        if point == "buy_1like" and buy1like_signal_bi is not None:
            return buy1like_signal_bi
        return latest_down

    def sell_signal_bi_for(point: str) -> Bi | None:
        # 与买侧对称：一类点段级锚点是离开段末笔（而非「最新同向笔」）。
        if point == "sell_1" and sell1_signal_bi is not None:
            return sell1_signal_bi
        if point == "sell_2" and sell2_signal_bi is not None:
            return sell2_signal_bi
        if point == "sell_3" and sell3_signal_bi is not None:
            return sell3_signal_bi
        if point == "sell_2like" and sell2like_signal_bi is not None:
            return sell2like_signal_bi
        if point == "sell_1like" and sell1like_signal_bi is not None:
            return sell1like_signal_bi
        return latest_up if point == "sell_2" else latest_confirmed_up

    for point in buy_points:
        signal_bi = buy_signal_bi_for(point)
        signal_points.append(
            _build_signal_point_detail(
                point,
                signal_bi,
                getattr(signal_bi, "low", None),
                active=True,
                basis=buy_basis_by_point.get(point),
                related_zs_id=related_zs_id,
                related_bi_ids=related_bi_ids,
            )
        )
    for point in sell_points:
        signal_bi = sell_signal_bi_for(point)
        signal_points.append(
            _build_signal_point_detail(
                point,
                signal_bi,
                getattr(signal_bi, "high", None),
                active=True,
                basis=sell_basis_by_point.get(point),
                related_zs_id=related_zs_id,
                related_bi_ids=related_bi_ids,
            )
        )

    active_points = set(buy_points + sell_points)
    # 固定 6 槽（buy_1..sell_3）保持既有索引契约；类二类点（buy_2like/sell_2like）追加在其后。
    for point in ("buy_1", "buy_2", "buy_3"):
        signal_bi = buy_signal_bi_for(point)
        signal_catalog.append(
            _build_signal_point_detail(
                point,
                signal_bi,
                getattr(signal_bi, "low", None) if point in active_points else None,
                active=point in active_points,
                basis=buy_basis_by_point.get(point),
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
                basis=sell_basis_by_point.get(point),
                related_zs_id=related_zs_id,
                related_bi_ids=related_bi_ids,
            )
        )
    # 类二类点槽位追加在固定 6 槽之后（槽位 6=buy_2like、7=sell_2like）。
    signal_catalog.append(
        _build_signal_point_detail(
            "buy_2like",
            buy_signal_bi_for("buy_2like"),
            getattr(buy2like_signal_bi, "low", None) if "buy_2like" in active_points else None,
            active="buy_2like" in active_points,
            basis=buy_basis_by_point.get("buy_2like"),
            related_zs_id=related_zs_id,
            related_bi_ids=related_bi_ids,
        )
    )
    signal_catalog.append(
        _build_signal_point_detail(
            "sell_2like",
            sell_signal_bi_for("sell_2like"),
            getattr(sell2like_signal_bi, "high", None) if "sell_2like" in active_points else None,
            active="sell_2like" in active_points,
            basis=sell_basis_by_point.get("sell_2like"),
            related_zs_id=related_zs_id,
            related_bi_ids=related_bi_ids,
        )
    )
    # 类一类点槽位追加在类二类槽位之后（槽位 8=buy_1like、9=sell_1like）。
    signal_catalog.append(
        _build_signal_point_detail(
            "buy_1like",
            buy_signal_bi_for("buy_1like"),
            getattr(buy1like_signal_bi, "low", None) if "buy_1like" in active_points else None,
            active="buy_1like" in active_points,
            basis=buy_basis_by_point.get("buy_1like"),
            related_zs_id=related_zs_id,
            related_bi_ids=related_bi_ids,
        )
    )
    signal_catalog.append(
        _build_signal_point_detail(
            "sell_1like",
            sell_signal_bi_for("sell_1like"),
            getattr(sell1like_signal_bi, "high", None) if "sell_1like" in active_points else None,
            active="sell_1like" in active_points,
            basis=sell_basis_by_point.get("sell_1like"),
            related_zs_id=related_zs_id,
            related_bi_ids=related_bi_ids,
        )
    )
    return signal_points, signal_catalog


def build_signal_summary_fields(
    signals: dict[str, object],
    *,
    previous_frame: dict[str, object] | None = None,
    data_window: str | None = None,
) -> dict[str, object]:
    # spec_id: SPEC.BUY_SELL.CORE（见 docs/chanlun/buy-sell-multi-level-spec.md）
    same_level_consumption_level = signals.get("same_level_consumption_level")
    transitions = derive_signal_lifecycle_transitions(previous_frame, signals, data_window=data_window)
    return {
        "buy_points": [_format_signal_point_name(str(point)) for point in signals.get("buy_points", [])],
        "sell_points": [_format_signal_point_name(str(point)) for point in signals.get("sell_points", [])],
        "signal_points": list(signals.get("signal_points", [])),
        "signal_catalog": list(signals.get("signal_catalog", [])),
        "forming_points": list(signals.get("forming_points", [])),
        "invalidated_points": list(transitions.get("invalidated_points", [])),
        "signal_repaint_violations": list(transitions.get("repaint_violations", [])),
        "lifecycle_rebased_points": list(transitions.get("rebased_points", [])),
        "lifecycle_superseded_points": list(transitions.get("superseded_points", [])),
        "lifecycle_window_rebased": bool(transitions.get("window_rebased", False)),
        "lifecycle_frame": to_lifecycle_frame(signals, data_window=data_window),
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


# --- RS0 增量2：信号生命周期跨帧回放（invalidation 发射 + repaint 安全护栏，spec §2.8） ---
# invalidation 本质是跨帧概念：单帧快照恒按最新结构判定，前提被破坏时确认点自然不再发射，
# 故失效态由「按时间序的多帧 confirmed 集合」比较得出，同时作为「confirmed 不得凭空消失」的护栏。

_SIGNAL_INVALIDATION_REASON_BY_POINT = {
    "buy1": SignalInvalidatedReason.FIRST_CLASS_EXTREME_BROKEN.value,
    "sell1": SignalInvalidatedReason.FIRST_CLASS_EXTREME_BROKEN.value,
    "buy2": SignalInvalidatedReason.SECOND_CLASS_PULLBACK_FAILED.value,
    "sell2": SignalInvalidatedReason.SECOND_CLASS_PULLBACK_FAILED.value,
    "buy3": SignalInvalidatedReason.THIRD_CLASS_REENTERED_ZS.value,
    "sell3": SignalInvalidatedReason.THIRD_CLASS_REENTERED_ZS.value,
    "buy1like": SignalInvalidatedReason.CONSOLIDATION_DIVERGENCE_LOST.value,
    "sell1like": SignalInvalidatedReason.CONSOLIDATION_DIVERGENCE_LOST.value,
    "buy2like": SignalInvalidatedReason.GAP_DIVERGENCE_LOST.value,
    "sell2like": SignalInvalidatedReason.GAP_DIVERGENCE_LOST.value,
}


def _signal_point_side(point: str) -> str | None:
    if point.startswith("buy"):
        return "buy"
    if point.startswith("sell"):
        return "sell"
    return None


def _frame_latest_low(frame: dict[str, object]) -> float | None:
    if "latest_down_low" in frame:
        value = frame.get("latest_down_low")
        return float(value) if value is not None else None
    latest_down = frame.get("latest_down")
    return float(latest_down.low) if latest_down is not None else None


def _frame_latest_high(frame: dict[str, object]) -> float | None:
    if "latest_up_high" in frame:
        value = frame.get("latest_up_high")
        return float(value) if value is not None else None
    latest_up = frame.get("latest_confirmed_up")
    return float(latest_up.high) if latest_up is not None else None


def _frame_zs_high(frame: dict[str, object]) -> float | None:
    if "zs_high" in frame:
        value = frame.get("zs_high")
        return float(value) if value is not None else None
    current_zs = frame.get("current_zs")
    return float(current_zs.zs_high) if current_zs is not None else None


def _frame_zs_low(frame: dict[str, object]) -> float | None:
    if "zs_low" in frame:
        value = frame.get("zs_low")
        return float(value) if value is not None else None
    current_zs = frame.get("current_zs")
    return float(current_zs.zs_low) if current_zs is not None else None


# 旧版压缩帧缺少中枢标识时的哨兵：调用方必须按 **fail closed** 处理（不得据此豁免 repaint 违规）。
_LIFECYCLE_FIELD_MISSING = object()


def _frame_zs_id(frame: dict[str, object]) -> object:
    """取帧的**参考中枢编号**（`zs_id`）。

    `analyze_chanlun_signals` 输出携带对象 `current_zs`；`to_lifecycle_frame` 压缩帧携带标量 `zs_id`。
    两者皆无（改动前的旧压缩帧）→ 返回 `_LIFECYCLE_FIELD_MISSING`，调用方不得据此豁免。
    """
    current_zs = frame.get("current_zs")
    if current_zs is not None:
        return getattr(current_zs, "zs_id", None)
    if "zs_id" in frame:
        return frame.get("zs_id")
    return _LIFECYCLE_FIELD_MISSING


def _confirmed_anchor_map(frame: dict[str, object]) -> dict[str, set]:
    """按 `point` 归组帧内 confirmed 锚点（`signal_bi_id`）。"""
    anchors: dict[str, set] = {}
    for payload in frame.get("signal_points", []) or []:
        if payload.get("lifecycle_state") != SignalLifecycleState.CONFIRMED.value:
            continue
        anchors.setdefault(str(payload.get("point")), set()).add(payload.get("signal_bi_id"))
    return anchors


def classify_confirmed_disappearance(
    previous_frame: dict[str, object],
    frame: dict[str, object],
    *,
    point: str,
    signal_bi_id: object,
    current_anchors: dict[str, set] | None = None,
) -> str | None:
    """判定「confirmed 锚点消失」是否属于参考结构推进导致的**自然更替**（spec §2.8 / design §3）。

    返回**证据键**；返回 `None` 表示**无独立证据** → 调用方仍应判 repaint 违规（fail closed）。

    三条证据均为「结构已推进」的独立证据，且**不可能由本次消失自身推出**：

    - `reanchored`：同一 `point` 在本帧仍 confirmed，但锚点已换 —— 设计 §3 明文允许的
      「被更晚的点替换」。
    - `zs_superseded`：参考中枢被更替（`zs_id` 变化）—— 设计 §3 的「中枢换锚」。
    - `sibling_new_anchor`：**其他** `point` 在本帧新增了确认锚点（新结构产出新点）。

    **刻意排除**：本点自己的位置型门控变化（`hold_s3` / `ls2_anchor` 等）**不构成证据** ——
    它们就是本点自己的发点锚点，「门控变化」与「点消失」是同一件事，属**同义反复**；
    若把它们算作证据，则该判据恒真、闸门在真实数据上永不触发（空转闸门反模式）。

    旧帧缺少中枢标识（无 `zs_id` 且无 `current_zs`）时**不豁免**。
    """
    anchors = current_anchors if current_anchors is not None else _confirmed_anchor_map(frame)
    if set(anchors.get(point, set())) - {signal_bi_id}:
        return "reanchored"
    previous_zs_id = _frame_zs_id(previous_frame)
    current_zs_id = _frame_zs_id(frame)
    if (
        previous_zs_id is not _LIFECYCLE_FIELD_MISSING
        and current_zs_id is not _LIFECYCLE_FIELD_MISSING
        and previous_zs_id != current_zs_id
    ):
        return "zs_superseded"
    previous_anchors = _confirmed_anchor_map(previous_frame)
    for other, anchors_now in anchors.items():
        if other == point:
            continue
        if anchors_now - set(previous_anchors.get(other, set())):
            return "sibling_new_anchor"
    return None


def _signal_premise_broken(point: str, price: float, frame: dict[str, object]) -> bool:
    """判定某确认点在给定帧里成立前提是否已被破坏（spec §2.8 §3.2）。

    一 / 二 / 类一 / 类二：买点被后续新低跌破（`latest_down.low < price`）、卖点被新高升破；
    三类：回抽 / 反抽重新回到中枢（买三回落到 `zs_high` 之下、卖三反抽到 `zs_low` 之上）。
    帧可为 `analyze_chanlun_signals` 输出（对象）或 `to_lifecycle_frame` 压缩帧（标量，供持久化）。
    """
    side = _signal_point_side(point)
    if side is None:
        return False
    if point in ("buy3", "sell3"):
        if side == "buy":
            zs_high = _frame_zs_high(frame)
            low = _frame_latest_low(frame)
            return zs_high is not None and low is not None and low < zs_high
        zs_low = _frame_zs_low(frame)
        high = _frame_latest_high(frame)
        return zs_low is not None and high is not None and high > zs_low
    if side == "buy":
        low = _frame_latest_low(frame)
        return low is not None and low < float(price)
    high = _frame_latest_high(frame)
    return high is not None and high > float(price)


def replay_confirmed_signal_lifecycle(frames: list[dict[str, object]]) -> dict[str, object]:
    """按时间序回放多帧 `analyze_chanlun_signals` 输出，产出 confirmed 信号的生命周期时间线。

    - `invalidated`：某帧曾 confirmed 的信号锚点（`point` + `signal_bi_id`）在后续帧从 confirmed 集合
      消失，且该帧成立前提已被破坏（`_signal_premise_broken`）→ 记为失效，附 `invalidated_reason`。
    - `repaint_violations`：confirmed 信号消失但成立前提未破坏，**且无任何「参考结构已推进」的独立证据**
      → 违反 spec §2.8 repaint 红线（confirmed 不得凭空消失 / 翻转）。
    - `rebased`：相邻两帧的 `data_window` 不同（K 线窗口重基，如全量重抓 / 重算）时，笔编号会整体
      重排，`signal_bi_id` 不再是同一坐标系，此时锚点消失记为 `rebased` 而非 repaint 违规。
    - `superseded`：confirmed 锚点消失，但存在**独立证据**表明参考结构已推进
      （见 `classify_confirmed_disappearance`：`reanchored` / `zs_superseded` / `sibling_new_anchor`），
      即设计 §3 状态机明文允许的终态 `confirmed --> [*]：结构自然更替`。
      每条均附 `evidence`，供事后审计；**未命中证据时一律回退为 repaint 违规（fail closed）**。

    判定优先级：`invalidated` → `rebased` → `superseded` → `repaint_violations`。
    """
    timeline: list[dict[str, object]] = []
    invalidated: list[dict[str, object]] = []
    repaint_violations: list[dict[str, object]] = []
    rebased: list[dict[str, object]] = []
    superseded: list[dict[str, object]] = []
    history: dict[tuple[str, object], dict[str, object]] = {}
    window_rebased = False

    for idx, frame in enumerate(frames):
        current_window = frame.get("data_window")
        previous_window_known = idx > 0 and "data_window" in frames[idx - 1]
        previous_window = frames[idx - 1].get("data_window") if idx > 0 else None
        if idx == 0 or current_window is None:
            window_changed = False
        elif previous_window_known and current_window == previous_window:
            window_changed = False
        else:
            # 上一帧无窗口标识（改动前的旧帧）或窗口已变化 → 笔编号坐标系不可比。
            window_changed = True
        if window_changed:
            window_rebased = True
        current: dict[tuple[str, object], dict[str, object]] = {}
        for point_payload in frame.get("signal_points", []) or []:
            if point_payload.get("lifecycle_state") != SignalLifecycleState.CONFIRMED.value:
                continue
            key = (str(point_payload.get("point")), point_payload.get("signal_bi_id"))
            current[key] = point_payload

        current_anchors: dict[str, set] = {}
        for point_name, anchor in current:
            current_anchors.setdefault(point_name, set()).add(anchor)

        for key, payload in current.items():
            record = history.get(key)
            if record is None:
                history[key] = {
                    "point": key[0],
                    "signal_bi_id": key[1],
                    "price": payload.get("price"),
                    "status": "confirmed",
                }
                timeline.append({"frame": idx, "point": key[0], "signal_bi_id": key[1], "transition": "confirmed"})
            elif record["status"] == "invalidated":
                # 同锚点在失效后不应重新 confirmed；出现即视为 repaint 违规。
                repaint_violations.append({"frame": idx, "point": key[0], "signal_bi_id": key[1], "kind": "reconfirm_after_invalidated"})
            elif record["status"] == "superseded":
                # 同锚点在更替后不应回到 confirmed（更替是终态）；回来即视为 repaint 违规。
                repaint_violations.append({"frame": idx, "point": key[0], "signal_bi_id": key[1], "kind": "reconfirm_after_superseded"})

        for key, record in history.items():
            if record["status"] != "confirmed" or key in current:
                continue
            point = str(record["point"])
            price = record["price"]
            if price is not None and _signal_premise_broken(point, float(price), frame):
                reason = _SIGNAL_INVALIDATION_REASON_BY_POINT.get(point)
                record["status"] = "invalidated"
                invalidated.append(
                    {
                        "point": point,
                        "signal_bi_id": key[1],
                        "price": price,
                        "lifecycle_state": SignalLifecycleState.INVALIDATED.value,
                        "invalidated_reason": reason,
                        "invalidated_frame": idx,
                    }
                )
                timeline.append(
                    {"frame": idx, "point": point, "signal_bi_id": key[1], "transition": "invalidated", "invalidated_reason": reason}
                )
            elif window_changed:
                # K 线窗口重基（全量重抓 / 重算导致笔编号重排）：锚点消失不构成 repaint 违规。
                record["status"] = "rebased"
                rebased.append({"frame": idx, "point": point, "signal_bi_id": key[1], "kind": "vanished_on_rebase"})
                timeline.append({"frame": idx, "point": point, "signal_bi_id": key[1], "transition": "rebased"})
            else:
                evidence = classify_confirmed_disappearance(
                    frames[idx - 1],
                    frame,
                    point=point,
                    signal_bi_id=key[1],
                    current_anchors=current_anchors,
                )
                if evidence is not None:
                    record["status"] = "superseded"
                    superseded.append(
                        {
                            "frame": idx,
                            "point": point,
                            "signal_bi_id": key[1],
                            "kind": "vanished_on_structure_advance",
                            "evidence": evidence,
                        }
                    )
                    timeline.append(
                        {
                            "frame": idx,
                            "point": point,
                            "signal_bi_id": key[1],
                            "transition": "superseded",
                            "evidence": evidence,
                        }
                    )
                else:
                    # 无独立证据 → 仍按 repaint 红线报违规（fail closed，不得默认豁免）。
                    record["status"] = "repaint_violation"
                    repaint_violations.append({"frame": idx, "point": point, "signal_bi_id": key[1], "kind": "vanished_without_break"})
                    timeline.append({"frame": idx, "point": point, "signal_bi_id": key[1], "transition": "repaint_violation"})

    return {
        "timeline": timeline,
        "invalidated": invalidated,
        "repaint_violations": repaint_violations,
        "rebased": rebased,
        "superseded": superseded,
        "window_rebased": window_rebased,
    }


def to_lifecycle_frame(signals: dict[str, object], *, data_window: str | None = None) -> dict[str, object]:
    """从 `analyze_chanlun_signals` 输出提取可持久化的压缩生命周期帧（spec §2.8）。

    只保留跨帧回放所需字段（confirmed 锚点 + 前提比较标量），便于逐次运行 / 逐次刷新之间落盘对比。

    `data_window` 标识本次分析所用 K 线窗口（实现取窗口起始 bar 时间戳）：增量追加时保持稳定，
    全量重抓 / 重算会变化。跨帧比较据此区分「真 repaint」与「窗口重基导致锚点重编号」。

    另持久化参考中枢编号 `zs_id`：它是唯一能**独立于本次消失**说明「结构已推进」的标量，
    供 `classify_confirmed_disappearance` 判定自然更替（旧帧缺该键时按 fail closed 不豁免）。
    """
    latest_down = signals.get("latest_down")
    latest_confirmed_up = signals.get("latest_confirmed_up")
    current_zs = signals.get("current_zs")
    confirmed = [
        {
            "point": payload.get("point"),
            "signal_bi_id": payload.get("signal_bi_id"),
            "price": payload.get("price"),
            "time": payload.get("time"),
            "lifecycle_state": payload.get("lifecycle_state"),
        }
        for payload in signals.get("signal_points", []) or []
        if payload.get("lifecycle_state") == SignalLifecycleState.CONFIRMED.value
    ]
    return {
        "signal_points": confirmed,
        "latest_down_low": getattr(latest_down, "low", None),
        "latest_up_high": getattr(latest_confirmed_up, "high", None),
        "zs_high": getattr(current_zs, "zs_high", None),
        "zs_low": getattr(current_zs, "zs_low", None),
        "zs_id": getattr(current_zs, "zs_id", None),
        "data_window": data_window,
    }


def derive_signal_lifecycle_transitions(
    previous_frame: dict[str, object] | None,
    signals: dict[str, object],
    *,
    data_window: str | None = None,
) -> dict[str, object]:
    """跨相邻两帧（上一次运行 / 刷新 vs 当前）推导 invalidated 点与 repaint 违规（spec §2.8 RS0）。

    `previous_frame` 为 `to_lifecycle_frame` 压缩帧；缺失（首帧）时返回空结果。invalidated 点补成
    可被下游归一化的信号载荷（`lifecycle_state=invalidated` + `invalidated_reason`）。

    `data_window`（当前帧窗口标识）与 `previous_frame["data_window"]` 不同时，视为窗口重基：
    锚点消失记入 `rebased_points` 而不再计入 `repaint_violations`（笔编号已整体重排，跨窗口比较
    不成立）；前提被破坏的点仍正常计入 `invalidated_points`。

    锚点消失但存在「参考结构已推进」的独立证据时，记入 `superseded_points`（附
    `superseded_evidence`），即设计 §3 允许的自然更替终态；无证据仍计入 `repaint_violations`。
    """
    if not previous_frame:
        return {
            "invalidated_points": [],
            "repaint_violations": [],
            "rebased_points": [],
            "superseded_points": [],
            "window_rebased": False,
        }
    current_frame = to_lifecycle_frame(signals, data_window=data_window)
    lifecycle = replay_confirmed_signal_lifecycle([previous_frame, current_frame])
    invalidated_points = [
        {
            "point": entry.get("point"),
            "active": False,
            "lifecycle_state": SignalLifecycleState.INVALIDATED.value,
            "invalidated_reason": entry.get("invalidated_reason"),
            "signal_bi_id": entry.get("signal_bi_id"),
            "price": entry.get("price"),
            "time": None,
            "basis": None,
        }
        for entry in lifecycle.get("invalidated", [])
    ]
    rebased_points = [
        {
            "point": entry.get("point"),
            "signal_bi_id": entry.get("signal_bi_id"),
            "window_rebased": True,
        }
        for entry in lifecycle.get("rebased", [])
    ]
    superseded_points = [
        {
            "point": entry.get("point"),
            "signal_bi_id": entry.get("signal_bi_id"),
            "superseded_evidence": entry.get("evidence"),
        }
        for entry in lifecycle.get("superseded", [])
    ]
    return {
        "invalidated_points": invalidated_points,
        "repaint_violations": lifecycle.get("repaint_violations", []),
        "rebased_points": rebased_points,
        "superseded_points": superseded_points,
        "window_rebased": bool(lifecycle.get("window_rebased")),
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
    small_to_large_status = precision_entry.get("small_to_large_status")
    small_to_large_status_label = precision_entry.get("small_to_large_status_label")
    if not label and not description and not dynamic_grade_label and not small_to_large_status_label:
        return None
    lines = [line for line in [f"{operation_level}窗口：{label}" if label else None, description] if line]
    if dynamic_grade_label:
        lines.append(f"{operation_level}判级：{dynamic_grade_label}")
    if small_to_large_status_label:
        lines.append(f"小转大：{small_to_large_status_label}")
    return {
        "title": f"{operation_level}区间套窗口",
        "label": label,
        "description": description,
        "dynamic_grade": dynamic_grade,
        "dynamic_grade_label": dynamic_grade_label,
        "small_to_large_status": small_to_large_status,
        "small_to_large_status_label": small_to_large_status_label,
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


def _higher_level_structure_closed(higher_signals: dict[str, object], *, side: str) -> bool:
    """RS2：高级别结构是否已闭环（前段走势完成、切入同向新走势且同级别消费已确认）。

    红线（第35/43/44课）：低级别信号不得单独推翻高级别未完成结构，故只有高级别自身
    结构闭环时才允许把小转大候选升级为已确认转折。
    """
    structure_state = higher_signals.get("structure_state")
    if not isinstance(structure_state, dict):
        return False
    if str(structure_state.get("current_structure_status") or "").strip() != StructureStatus.COMPLETED_THEN_NEW_TYPE.value:
        return False
    consumption = str(higher_signals.get("same_level_consumption_level") or "").strip()
    if not consumption:
        consumption = _build_same_level_consumption_level(structure_state)
    if consumption != "confirmed":
        return False
    new_type = str((structure_state.get("current_ongoing") or {}).get("type") or "").strip()
    expected_type = "up" if side == "buy" else "down"
    return new_type == expected_type


def _build_small_to_large_status(
    higher_signals: dict[str, object],
    signal_points: list[dict[str, object]],
    *,
    side: str,
) -> str | None:
    """小转大 RS2 双向联立：候选 -> 必要条件已具备 -> 高级别结构闭环后升级为已确认转折。"""
    route = str(higher_signals.get("post_divergence_route") or "").strip()
    if route not in {"higher_level_reverse_trend", "higher_level_range"}:
        return None

    required_point = "buy3" if side == "buy" else "sell3"
    has_required_third_class = any(
        entry.get("active") and str(entry.get("point") or "").replace("_", "") == required_point
        for entry in signal_points
    )
    if not has_required_third_class:
        return SmallToLargeStatus.CANDIDATE.value
    if _higher_level_structure_closed(higher_signals, side=side):
        return SmallToLargeStatus.HIGHER_LEVEL_CONFIRMED.value
    return SmallToLargeStatus.THIRD_CLASS_CONFIRMED.value


def _build_small_to_large_reverse_confirm(
    status: str | None,
    *,
    side: str,
    higher_signals: dict[str, object],
) -> dict[str, object] | None:
    """区间套反向确认：仅当小转大升级为高级别已确认转折时，回填反向确认依据。"""
    if status != SmallToLargeStatus.HIGHER_LEVEL_CONFIRMED.value:
        return None
    structure_state = higher_signals.get("structure_state")
    higher_structure_status = (
        str(structure_state.get("current_structure_status") or "").strip()
        if isinstance(structure_state, dict)
        else None
    )
    direction_label = "向上" if side == "buy" else "向下"
    third_class_label = "三买" if side == "buy" else "三卖"
    return {
        "active": True,
        "basis": "lower_third_class_and_higher_structure_closed",
        "higher_structure_status": higher_structure_status or None,
        "note": (
            f"次级别最后一个中枢已出现{third_class_label}，且高级别结构已闭环切入{direction_label}新走势，"
            f"区间套反向确认小转大升级为高级别已确认转折。"
        ),
    }


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
    if not higher_consumption_level:
        higher_structure_state = higher_signals.get("structure_state")
        if isinstance(higher_structure_state, dict):
            higher_consumption_level = _build_same_level_consumption_level(higher_structure_state)
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
    small_to_large_status = _build_small_to_large_status(higher_signals, signal_points, side=side)
    small_to_large_status_label = format_small_to_large_status_label(small_to_large_status)
    small_to_large_status_note = describe_small_to_large_status(small_to_large_status)
    small_to_large_reverse_confirm = _build_small_to_large_reverse_confirm(
        small_to_large_status, side=side, higher_signals=higher_signals
    )
    if small_to_large_reverse_confirm is not None:
        note = f"{note} {small_to_large_reverse_confirm['note']}"

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
        "small_to_large_status": small_to_large_status,
        "small_to_large_status_label": small_to_large_status_label,
        "small_to_large_status_note": small_to_large_status_note or None,
        "small_to_large_reverse_confirm": small_to_large_reverse_confirm,
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