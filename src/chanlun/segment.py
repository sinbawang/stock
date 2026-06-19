"""线段识别。"""

from typing import List, Optional, Tuple

from .models import Bi, BiDirection, Segment


def _confirmed_bis(bis: List[Bi]) -> List[Bi]:
    """线段只基于已确认笔计算，未确认尾笔不参与段识别。"""
    return [bi for bi in bis if bi.is_confirmed]


def _is_alternating(bis: List[Bi]) -> bool:
    return all(previous.direction != current.direction for previous, current in zip(bis, bis[1:]))


def _forms_initial_segment(window: List[Bi]) -> bool:
    if len(window) != 3 or not _is_alternating(window):
        return False

    lead_bi, _, same_dir_bi = window
    if lead_bi.direction == BiDirection.UP:
        return same_dir_bi.high > lead_bi.high
    return same_dir_bi.low < lead_bi.low


def _build_segment(segment_id: int, bis: List[Bi], start_idx: int, end_idx: int, is_confirmed: bool) -> Segment:
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
    )


def _extend_segment(bis: List[Bi], start_idx: int) -> Optional[Tuple[int, bool, Optional[int]]]:
    if start_idx + 2 >= len(bis):
        return None

    initial = bis[start_idx:start_idx + 3]
    if not _forms_initial_segment(initial):
        return None

    direction = initial[0].direction
    end_idx = start_idx + 2
    break_idx: Optional[int] = None
    is_confirmed = False

    if direction == BiDirection.UP:
        last_same_extreme = initial[2].high
        last_reverse_extreme = initial[1].low
    else:
        last_same_extreme = initial[2].low
        last_reverse_extreme = initial[1].high

    cursor = start_idx + 3
    while cursor < len(bis):
        reverse_bi = bis[cursor]
        if reverse_bi.direction == direction:
            break

        if direction == BiDirection.UP:
            if reverse_bi.low <= last_reverse_extreme:
                break_idx = cursor
                is_confirmed = True
                break
        else:
            if reverse_bi.high >= last_reverse_extreme:
                break_idx = cursor
                is_confirmed = True
                break

        if cursor + 1 >= len(bis):
            break

        same_dir_bi = bis[cursor + 1]
        if same_dir_bi.direction != direction:
            break

        if direction == BiDirection.UP:
            if same_dir_bi.high <= last_same_extreme:
                break
            last_reverse_extreme = reverse_bi.low
            last_same_extreme = same_dir_bi.high
        else:
            if same_dir_bi.low >= last_same_extreme:
                break
            last_reverse_extreme = reverse_bi.high
            last_same_extreme = same_dir_bi.low

        end_idx = cursor + 1
        cursor += 2

    return end_idx, is_confirmed, break_idx


def identify_segments(bis: List[Bi]) -> List[Segment]:
    """
    识别线段。

    第一阶段规则对应 docs/chanlun-rule-spec.md 6.1-6.5：
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

        end_idx, is_confirmed, break_idx = result
        segments.append(_build_segment(segment_id, bis, index, end_idx, is_confirmed))
        segment_id += 1

        if break_idx is not None:
            index = break_idx
        else:
            index = end_idx + 1

    return segments