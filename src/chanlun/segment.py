"""线段识别。"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .models import Bi, BiDirection, Segment


@dataclass
class _FeatureSequenceElement:
    high: float
    low: float
    source_indices: List[int] = field(default_factory=list)


def _confirmed_bis(bis: List[Bi]) -> List[Bi]:
    """线段只基于已确认笔计算，未确认尾笔不参与段识别。"""
    return [bi for bi in bis if bi.is_confirmed]


def _is_alternating(bis: List[Bi]) -> bool:
    return all(previous.direction != current.direction for previous, current in zip(bis, bis[1:]))


def _has_common_overlap(window: List[Bi]) -> bool:
    overlap_low = max(bi.low for bi in window)
    overlap_high = min(bi.high for bi in window)
    return overlap_low <= overlap_high


def _forms_initial_segment(window: List[Bi]) -> bool:
    return len(window) == 3 and _is_alternating(window) and _has_common_overlap(window)


def _feature_sequence_has_gap(left_bi: Bi, right_bi: Bi) -> bool:
    return max(left_bi.low, right_bi.low) > min(left_bi.high, right_bi.high)


def _contains(left: _FeatureSequenceElement, right: _FeatureSequenceElement) -> bool:
    return (
        (left.high >= right.high and left.low <= right.low)
        or (right.high >= left.high and right.low <= left.low)
    )


def _resolve_feature_sequence_trend(
    previous_element: _FeatureSequenceElement,
    current_element: _FeatureSequenceElement,
    current_trend_up: Optional[bool],
) -> bool:
    if current_trend_up is not None:
        return current_trend_up
    if current_element.high > previous_element.high:
        return True
    if current_element.low < previous_element.low:
        return False
    return current_element.low >= previous_element.low


def _merge_feature_sequence_element(
    left: _FeatureSequenceElement,
    right: _FeatureSequenceElement,
    *,
    trend_up: bool,
) -> _FeatureSequenceElement:
    if trend_up:
        high = max(left.high, right.high)
        low = max(left.low, right.low)
    else:
        high = min(left.high, right.high)
        low = min(left.low, right.low)
    return _FeatureSequenceElement(
        high=high,
        low=low,
        source_indices=[*left.source_indices, *right.source_indices],
    )


def _build_standard_feature_sequence(
    bis: List[Bi],
    reverse_indices: List[int],
) -> List[_FeatureSequenceElement]:
    if not reverse_indices:
        return []

    elements: List[_FeatureSequenceElement] = []
    trend_up: Optional[bool] = None

    for reverse_idx in reverse_indices:
        reverse_bi = bis[reverse_idx]
        current = _FeatureSequenceElement(
            high=reverse_bi.high,
            low=reverse_bi.low,
            source_indices=[reverse_idx],
        )

        if not elements:
            elements.append(current)
            continue

        if _contains(elements[-1], current):
            merge_trend_up = _resolve_feature_sequence_trend(elements[-1], current, trend_up)
            elements[-1] = _merge_feature_sequence_element(
                elements[-1],
                current,
                trend_up=merge_trend_up,
            )
            trend_up = merge_trend_up
            continue

        previous = elements[-1]
        if current.high >= previous.high and current.low >= previous.low:
            trend_up = True
        elif current.high <= previous.high and current.low <= previous.low:
            trend_up = False
        elements.append(current)

    return elements


def _feature_element_has_gap(
    left: _FeatureSequenceElement,
    right: _FeatureSequenceElement,
) -> bool:
    return max(left.low, right.low) > min(left.high, right.high)


def _feature_element_pivot_index(
    bis: List[Bi],
    element: _FeatureSequenceElement,
    direction: BiDirection,
) -> int:
    if direction == BiDirection.UP:
        return max(element.source_indices, key=lambda idx: (bis[idx].high, bis[idx].low, -idx))
    return min(element.source_indices, key=lambda idx: (bis[idx].low, bis[idx].high, idx))


def _feature_sequence_break(
    bis: List[Bi],
    reverse_indices: List[int],
    direction: BiDirection,
) -> Optional[Tuple[int, int, str]]:
    standard_sequence = _build_standard_feature_sequence(bis, reverse_indices)
    if len(standard_sequence) < 3:
        return None

    left_element, middle_element, right_element = standard_sequence[-3:]

    if _feature_element_has_gap(left_element, middle_element):
        return None

    if direction == BiDirection.UP:
        is_top_fractal = (
            middle_element.high > left_element.high
            and middle_element.high > right_element.high
            and middle_element.low > left_element.low
            and middle_element.low > right_element.low
        )
        if is_top_fractal:
            pivot_idx = _feature_element_pivot_index(bis, middle_element, direction)
            return pivot_idx - 1, pivot_idx, "feature_sequence_fractal"
        return None

    is_bottom_fractal = (
        middle_element.high < left_element.high
        and middle_element.high < right_element.high
        and middle_element.low < left_element.low
        and middle_element.low < right_element.low
    )
    if is_bottom_fractal:
        pivot_idx = _feature_element_pivot_index(bis, middle_element, direction)
        return pivot_idx - 1, pivot_idx, "feature_sequence_fractal"
    return None


def _gap_feature_sequence_candidate(
    bis: List[Bi],
    reverse_indices: List[int],
    direction: BiDirection,
) -> Optional[int]:
    standard_sequence = _build_standard_feature_sequence(bis, reverse_indices)
    if len(standard_sequence) < 3:
        return None

    left_element, middle_element, right_element = standard_sequence[-3:]
    if not _feature_element_has_gap(left_element, middle_element):
        return None

    if direction == BiDirection.UP:
        is_gap_top_fractal = (
            middle_element.high > left_element.high
            and middle_element.high > right_element.high
            and middle_element.low > left_element.low
            and middle_element.low > right_element.low
        )
        if is_gap_top_fractal:
            return _feature_element_pivot_index(bis, middle_element, direction)
        return None

    is_gap_bottom_fractal = (
        middle_element.high < left_element.high
        and middle_element.high < right_element.high
        and middle_element.low < left_element.low
        and middle_element.low < right_element.low
    )
    if is_gap_bottom_fractal:
        return _feature_element_pivot_index(bis, middle_element, direction)
    return None


def _breaks_first_bi_start(direction: BiDirection, candidate_bi: Bi, first_bi: Bi) -> bool:
    if direction == BiDirection.UP:
        return candidate_bi.low < first_bi.low
    return candidate_bi.high > first_bi.high


def _reclaims_transition_back_to_prior_segment(
    bis: List[Bi],
    transition_idx: int,
    prior_direction: BiDirection,
) -> Optional[int]:
    if transition_idx + 3 >= len(bis):
        return None

    transition_bi = bis[transition_idx]
    candidate_direction = transition_bi.direction
    if candidate_direction == prior_direction:
        return None

    for idx in range(transition_idx + 1, len(bis)):
        candidate_bi = bis[idx]
        if candidate_bi.direction == candidate_direction:
            if _same_direction_extends(candidate_direction, candidate_bi, transition_bi.high if candidate_direction == BiDirection.UP else transition_bi.low):
                return None
            continue

        if _breaks_first_bi_start(candidate_direction, candidate_bi, transition_bi):
            return idx

    return None


def _rediscriminate_gap_break(
    bis: List[Bi],
    start_idx: int,
) -> Optional[bool]:
    if start_idx + 2 >= len(bis):
        return None

    first_bi = bis[start_idx]
    direction = first_bi.direction
    first_end_extreme = first_bi.high if direction == BiDirection.UP else first_bi.low
    cursor = start_idx + 1

    while cursor < len(bis):
        reverse_bi = bis[cursor]
        if reverse_bi.direction == direction:
            return None

        if _breaks_first_bi_start(direction, reverse_bi, first_bi):
            return False

        if cursor + 1 >= len(bis):
            return None

        same_dir_bi = bis[cursor + 1]
        if same_dir_bi.direction != direction:
            return None

        if _same_direction_extends(direction, same_dir_bi, first_end_extreme):
            return True

        cursor += 2

    return None


def _segment_extremes(
    bis: List[Bi],
    start_idx: int,
    end_idx: int,
) -> Tuple[float, float]:
    direction = bis[start_idx].direction
    window = bis[start_idx:end_idx + 1]
    same_direction_bis = [bi for bi in window if bi.direction == direction]
    reverse_direction_bis = [bi for bi in window if bi.direction != direction]

    if direction == BiDirection.UP:
        last_same_extreme = same_direction_bis[-1].high
        last_reverse_extreme = reverse_direction_bis[-1].low
    else:
        last_same_extreme = same_direction_bis[-1].low
        last_reverse_extreme = reverse_direction_bis[-1].high

    return last_same_extreme, last_reverse_extreme


def _same_direction_extends(
    direction: BiDirection,
    candidate_bi: Bi,
    reference_extreme: float,
) -> bool:
    if direction == BiDirection.UP:
        return candidate_bi.high > reference_extreme
    return candidate_bi.low < reference_extreme


def _reverse_breaks_last_reverse_extreme(
    direction: BiDirection,
    reverse_bi: Bi,
    last_reverse_extreme: float,
) -> bool:
    if direction == BiDirection.UP:
        return reverse_bi.low < last_reverse_extreme
    return reverse_bi.high > last_reverse_extreme


def _reverse_confirms_gap_break(
    direction: BiDirection,
    reverse_bi: Bi,
    next_reverse_bi: Bi,
) -> bool:
    if direction == BiDirection.UP:
        return next_reverse_bi.low < reverse_bi.low
    return next_reverse_bi.high > reverse_bi.high


def _build_segment(
    segment_id: int,
    bis: List[Bi],
    start_idx: int,
    end_idx: int,
    is_confirmed: bool,
    *,
    last_same_extreme: float,
    last_reverse_extreme: float,
    break_bi_id: Optional[int],
    stop_reason: str,
) -> Segment:
    window = bis[start_idx:end_idx + 1]
    start_bi = window[0]
    end_bi = window[-1]
    start_price = start_bi.low if start_bi.direction == BiDirection.UP else start_bi.high
    end_price = end_bi.high if end_bi.direction == BiDirection.UP else end_bi.low
    return Segment(
        segment_id=segment_id,
        direction=start_bi.direction,
        start_bi_id=start_bi.bi_id,
        end_bi_id=end_bi.bi_id,
        start_ts=start_bi.start_ts,
        end_ts=end_bi.end_ts,
        start_price=start_price,
        end_price=end_price,
        high=max(bi.high for bi in window),
        low=min(bi.low for bi in window),
        norm_bar_range=(start_bi.norm_bar_range[0], end_bi.norm_bar_range[1]),
        bi_ids=[bi.bi_id for bi in window],
        is_confirmed=is_confirmed,
        last_same_extreme=last_same_extreme,
        last_reverse_extreme=last_reverse_extreme,
        break_bi_id=break_bi_id,
        stop_reason=stop_reason,
    )


def _extend_segment(
    bis: List[Bi],
    start_idx: int,
) -> Optional[Tuple[int, bool, Optional[int], str, Optional[int]]]:
    if start_idx + 2 >= len(bis):
        return None

    initial = bis[start_idx:start_idx + 3]
    direction = initial[0].direction
    break_idx: Optional[int] = None
    is_confirmed = False

    if _forms_initial_segment(initial):
        end_idx = start_idx + 2
        reverse_indices = [start_idx + 1]
        cursor = start_idx + 3
    else:
        return None

    last_same_extreme, last_reverse_extreme = _segment_extremes(bis, start_idx, end_idx)
    pending_gap_break_idx: Optional[int] = None

    while cursor < len(bis):
        reverse_bi = bis[cursor]
        if reverse_bi.direction == direction:
            break_bi_id = reverse_bi.bi_id
            stop_reason = "unexpected_same_direction"
            break

        reclaimed_idx = _reclaims_transition_back_to_prior_segment(bis, cursor, direction)
        if reclaimed_idx is not None:
            end_idx = reclaimed_idx
            last_same_extreme, last_reverse_extreme = _segment_extremes(bis, start_idx, end_idx)
            reverse_indices = [
                idx
                for idx in range(start_idx, end_idx + 1)
                if bis[idx].direction != direction
            ]
            cursor = reclaimed_idx + 1
            continue

        reverse_indices.append(cursor)
        gap_candidate_idx = _gap_feature_sequence_candidate(bis, reverse_indices, direction)
        if gap_candidate_idx is not None:
            pending_gap_break_idx = gap_candidate_idx

        if pending_gap_break_idx is not None:
            pending_gap_outcome = _rediscriminate_gap_break(bis, pending_gap_break_idx)
            if pending_gap_outcome is True:
                end_idx = pending_gap_break_idx - 1
                break_idx = pending_gap_break_idx
                is_confirmed = True
                break_bi_id = bis[break_idx].bi_id
                stop_reason = "feature_sequence_gap_fractal"
                break
            if pending_gap_outcome is False:
                pending_gap_break_idx = None

        feature_break = _feature_sequence_break(bis, reverse_indices, direction)
        if feature_break is not None:
            end_idx, break_idx, stop_reason = feature_break
            is_confirmed = True
            break_bi_id = bis[break_idx].bi_id
            break

        if _reverse_breaks_last_reverse_extreme(direction, reverse_bi, last_reverse_extreme):
            break_idx = cursor
            is_confirmed = True
            break_bi_id = reverse_bi.bi_id
            stop_reason = "reverse_break"
            break

        if cursor + 1 >= len(bis):
            break_bi_id = reverse_bi.bi_id
            stop_reason = "no_followup_same_direction"
            break

        same_dir_bi = bis[cursor + 1]
        if same_dir_bi.direction != direction:
            break_bi_id = same_dir_bi.bi_id
            stop_reason = "same_direction_slot_not_filled"
            break

        if direction == BiDirection.UP:
            if same_dir_bi.high <= last_same_extreme:
                if cursor + 2 < len(bis):
                    next_reverse_bi = bis[cursor + 2]
                    candidate_feature_break = _feature_sequence_break(
                        bis,
                        reverse_indices + [cursor + 2],
                        direction,
                    )
                    if candidate_feature_break is not None:
                        end_idx, break_idx, stop_reason = candidate_feature_break
                        is_confirmed = True
                        break_bi_id = bis[break_idx].bi_id
                        break
                    gap_candidate_idx = _gap_feature_sequence_candidate(
                        bis,
                        reverse_indices + [cursor + 2],
                        direction,
                    )
                    if gap_candidate_idx is not None:
                        pending_gap_break_idx = gap_candidate_idx
                    if pending_gap_break_idx is not None:
                        pending_gap_outcome = _rediscriminate_gap_break(bis, pending_gap_break_idx)
                        if pending_gap_outcome is True:
                            end_idx = pending_gap_break_idx - 1
                            break_idx = pending_gap_break_idx
                            is_confirmed = True
                            break_bi_id = bis[break_idx].bi_id
                            stop_reason = "feature_sequence_gap_fractal"
                            break
                        if pending_gap_outcome is False:
                            pending_gap_break_idx = None
                            cursor += 2
                            continue
                        else:
                            cursor += 2
                            continue
                    if (
                        next_reverse_bi.direction != direction
                        and _reverse_breaks_last_reverse_extreme(direction, next_reverse_bi, last_reverse_extreme)
                    ):
                        break_idx = cursor
                        is_confirmed = True
                        break_bi_id = next_reverse_bi.bi_id
                        stop_reason = "reverse_break_after_gap"
                        break
                break_bi_id = same_dir_bi.bi_id
                stop_reason = "same_direction_not_extending"
                break
            last_reverse_extreme = reverse_bi.low
            last_same_extreme = same_dir_bi.high
        else:
            if same_dir_bi.low >= last_same_extreme:
                if cursor + 2 < len(bis):
                    next_reverse_bi = bis[cursor + 2]
                    candidate_feature_break = _feature_sequence_break(
                        bis,
                        reverse_indices + [cursor + 2],
                        direction,
                    )
                    if candidate_feature_break is not None:
                        end_idx, break_idx, stop_reason = candidate_feature_break
                        is_confirmed = True
                        break_bi_id = bis[break_idx].bi_id
                        break
                    gap_candidate_idx = _gap_feature_sequence_candidate(
                        bis,
                        reverse_indices + [cursor + 2],
                        direction,
                    )
                    if gap_candidate_idx is not None:
                        pending_gap_break_idx = gap_candidate_idx
                    if pending_gap_break_idx is not None:
                        pending_gap_outcome = _rediscriminate_gap_break(bis, pending_gap_break_idx)
                        if pending_gap_outcome is True:
                            end_idx = pending_gap_break_idx - 1
                            break_idx = pending_gap_break_idx
                            is_confirmed = True
                            break_bi_id = bis[break_idx].bi_id
                            stop_reason = "feature_sequence_gap_fractal"
                            break
                        if pending_gap_outcome is False:
                            pending_gap_break_idx = None
                            cursor += 2
                            continue
                        else:
                            cursor += 2
                            continue
                    if (
                        next_reverse_bi.direction != direction
                        and _reverse_breaks_last_reverse_extreme(direction, next_reverse_bi, last_reverse_extreme)
                    ):
                        break_idx = cursor
                        is_confirmed = True
                        break_bi_id = next_reverse_bi.bi_id
                        stop_reason = "reverse_break_after_gap"
                        break
                break_bi_id = same_dir_bi.bi_id
                stop_reason = "same_direction_not_extending"
                break
            last_reverse_extreme = reverse_bi.high
            last_same_extreme = same_dir_bi.low

        end_idx = cursor + 1
        cursor += 2

    else:
        break_bi_id = None
        stop_reason = "exhausted_confirmed_bis"

    return end_idx, is_confirmed, break_idx, stop_reason, break_bi_id


def identify_segments(bis: List[Bi]) -> List[Segment]:
    """
    识别线段。

    第一阶段规则对应 docs/chanlun/chanlun-rule-spec.md 6.1-6.5：
    - 输入可传入全量笔序列，但实现内部只使用已确认笔
    - 至少 3 笔，方向交替，首尾笔同向
    - 同向笔必须持续推进，反向笔不得破坏最近关键低/高点
    - 被反向笔有效破坏时，线段终结并确认为已完成线段
    - 若尾部尚未被有效反向笔破坏，则保留一个未确认尾段
    """
    bis = _confirmed_bis(bis)

    if len(bis) < 3:
        return []

    segments: List[Segment] = []
    segment_id = 0
    index = 0

    while index <= len(bis) - 3:
        result = _extend_segment(bis, index)
        if result is None:
            index += 1
            continue

        end_idx, is_confirmed, break_idx, stop_reason, break_bi_id = result
        last_same_extreme, last_reverse_extreme = _segment_extremes(bis, index, end_idx)
        segments.append(
            _build_segment(
                segment_id,
                bis,
                index,
                end_idx,
                is_confirmed,
                last_same_extreme=last_same_extreme,
                last_reverse_extreme=last_reverse_extreme,
                break_bi_id=break_bi_id,
                stop_reason=stop_reason,
            )
        )
        segment_id += 1

        if break_idx is not None:
            index = break_idx
        else:
            index = end_idx + 1

    return segments