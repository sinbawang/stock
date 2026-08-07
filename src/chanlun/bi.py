"""笔识别。

基于已经过滤的分型列表识别笔，并支持三种尾部反向确认口径：
- any: 当前保守默认口径
- effective_only: 仅允许满足最小间隔的反向分型占位
- tail_mixed: 只对最后未确认尾笔链路启用 effective_only
"""

from typing import List, Literal, Optional
from .models import Fractal, Bi, FractalType, BiDirection, NormalizedBar


# 分型极值K线最小间隔：
# 顶分型最高K线与底分型最低K线之间（不含两端）至少保留 3 根K。
MIN_EXTREME_GAP = 4
MAX_INITIAL_START_SCAN = 8
PENDING_REVERSE_MODE_ANY = "any"
PENDING_REVERSE_MODE_EFFECTIVE_ONLY = "effective_only"
PENDING_REVERSE_MODE_TAIL_MIXED = "tail_mixed"
PendingReverseMode = Literal["any", "effective_only", "tail_mixed"]


def _is_more_extreme(base: Fractal, candidate: Fractal) -> bool:
    """同类分型极值比较。"""
    if base.fx_type == FractalType.TOP:
        return candidate.price > base.price
    return candidate.price < base.price


def _window_index_span(
    fractal: Fractal,
    normalized_bars: Optional[List[NormalizedBar]],
) -> Optional[tuple[int, int]]:
    """返回分型三K窗口覆盖范围(min_idx, max_idx)。"""
    if not normalized_bars:
        return None

    left = max(0, fractal.center_bar_idx - 1)
    right = min(len(normalized_bars), fractal.center_bar_idx + 2)
    window = normalized_bars[left:right]
    if not window:
        return None

    norm_indices = [bar.idx for bar in window]
    if not norm_indices:
        return None

    return min(norm_indices), max(norm_indices)


def _window_raw_index_span(
    fractal: Fractal,
    normalized_bars: Optional[List[NormalizedBar]],
) -> Optional[tuple[int, int]]:
    """返回分型三K窗口在原始K线上的覆盖范围(min_idx, max_idx)。"""
    if not normalized_bars:
        return None

    left = max(0, fractal.center_bar_idx - 1)
    right = min(len(normalized_bars), fractal.center_bar_idx + 2)
    window = normalized_bars[left:right]
    if not window:
        return None

    raw_indices = [idx for bar in window for idx in bar.src_indices]
    if not raw_indices:
        return None

    return min(raw_indices), max(raw_indices)


def _fractal_extreme_raw_idx(
    fractal: Fractal,
    normalized_bars: Optional[List[NormalizedBar]],
    is_start: bool,
) -> Optional[int]:
    """
    返回分型三K窗口中的“极值K线”索引（按原始K线 idx）。

    为保证间隔判定保守可靠：
    - 起点分型使用更靠右的极值K线（离终点更近）
    - 终点分型使用更靠左的极值K线（离起点更近）
    """
    if not normalized_bars:
        return fractal.center_bar_idx

    left = max(0, fractal.center_bar_idx - 1)
    right = min(len(normalized_bars), fractal.center_bar_idx + 2)
    window = normalized_bars[left:right]
    if not window:
        return None

    if fractal.fx_type == FractalType.TOP:
        extreme_value = max(bar.high for bar in window)
        candidate_bars = [bar for bar in window if bar.high == extreme_value]
    else:
        extreme_value = min(bar.low for bar in window)
        candidate_bars = [bar for bar in window if bar.low == extreme_value]

    candidate_raw_indices = [idx for bar in candidate_bars for idx in bar.src_indices]
    if not candidate_raw_indices:
        # 缺失映射时退回标准化索引近似。
        candidate_raw_indices = [bar.idx for bar in candidate_bars]

    if not candidate_raw_indices:
        return None

    return max(candidate_raw_indices) if is_start else min(candidate_raw_indices)


def _has_enough_pen_gap(
    start_fx: Fractal,
    end_fx: Fractal,
    normalized_bars: Optional[List[NormalizedBar]],
) -> bool:
    """
    成笔间隔判定。

    必须同时满足：
    1) 顶分型与底分型三K窗口不重叠（不能共用K线）。
    2) 顶分型最高K线与底分型最低K线之间（不含两端）在原始K线上至少 3 根K线。
    """
    center_gap = end_fx.center_bar_idx - start_fx.center_bar_idx
    if not normalized_bars:
        # 无标准化K明细时，按中心索引保守近似：center 差值 >= 4。
        return center_gap >= MIN_EXTREME_GAP

    start_span = _window_index_span(start_fx, normalized_bars)
    end_span = _window_index_span(end_fx, normalized_bars)
    if start_span is None or end_span is None:
        return False

    _, start_max = start_span
    end_min, _ = end_span
    # 条件1：分型窗口不能共用K线。
    if end_min <= start_max:
        return False

    start_extreme_idx = _fractal_extreme_raw_idx(start_fx, normalized_bars, is_start=True)
    end_extreme_idx = _fractal_extreme_raw_idx(end_fx, normalized_bars, is_start=False)
    if start_extreme_idx is None or end_extreme_idx is None:
        # 无法定位极值K时，退回原始窗口跨度近似。
        start_raw_span = _window_raw_index_span(start_fx, normalized_bars)
        end_raw_span = _window_raw_index_span(end_fx, normalized_bars)
        if start_raw_span is None or end_raw_span is None:
            return False
        _, start_raw_max = start_raw_span
        end_raw_min, _ = end_raw_span
        return end_raw_min - start_raw_max >= MIN_EXTREME_GAP

    # 条件2：极值K线之间（不含两端）在原始K线上至少 3 根。
    return end_extreme_idx - start_extreme_idx >= MIN_EXTREME_GAP


def _is_valid_pen_endpoint(
    start_fx: Fractal,
    end_fx: Fractal,
    normalized_bars: Optional[List[NormalizedBar]],
) -> bool:
    del normalized_bars
    if end_fx.fx_type == start_fx.fx_type:
        return False

    if start_fx.fx_type == FractalType.BOTTOM:
        return end_fx.price > start_fx.price

    return end_fx.price < start_fx.price


def _is_leading_boundary_start(
    fractal: Fractal,
    normalized_bars: Optional[List[NormalizedBar]],
) -> bool:
    if not normalized_bars:
        return False

    return fractal.center_bar_idx < MIN_EXTREME_GAP


def _find_first_opposite(
    fractals: List[Fractal],
    start_idx: int,
    start_fx: Fractal,
    normalized_bars: Optional[List[NormalizedBar]],
) -> int:
    """从 start_idx 之后寻找第一个满足成笔约束的反向分型索引。"""
    j = start_idx + 1
    while j < len(fractals):
        fx = fractals[j]
        if (
            fx.fx_type != start_fx.fx_type
            and _has_enough_pen_gap(start_fx, fx, normalized_bars)
            and _is_valid_pen_endpoint(start_fx, fx, normalized_bars)
        ):
            return j
        j += 1
    return -1


def _extend_until_reversal(
    fractals: List[Fractal],
    end_idx: int,
    normalized_bars: Optional[List[NormalizedBar]],
    pending_reverse_mode: PendingReverseMode,
) -> tuple[int, bool]:
    """
    从候选终点 end_idx 开始，向后寻找：
    - 同类更极值分型则替换终点（笔延伸）
    - 遇到反向分型后，进入“确认候选”状态
    - 确认候选若不满足间隔，可被后续更强的同类反向分型替代
    - 只有确认候选本身满足间隔时，当前笔才确认
    返回: (最终终点索引, 是否已确认)
    """
    best_idx = end_idx
    best_fx = fractals[best_idx]
    pending_reverse: Optional[Fractal] = None

    k = end_idx + 1
    while k < len(fractals):
        fx = fractals[k]

        if fx.fx_type == best_fx.fx_type:
            if _is_more_extreme(best_fx, fx):
                best_idx = k
                best_fx = fx
                pending_reverse = None
            k += 1
            continue

        reverse_has_gap = _has_enough_pen_gap(best_fx, fx, normalized_bars)
        if (
            pending_reverse_mode == PENDING_REVERSE_MODE_EFFECTIVE_ONLY
            and not reverse_has_gap
        ):
            k += 1
            continue

        if pending_reverse is None or _is_more_extreme(pending_reverse, fx):
            pending_reverse = fx

        if (
            _has_enough_pen_gap(best_fx, pending_reverse, normalized_bars)
            and _is_valid_pen_endpoint(best_fx, pending_reverse, normalized_bars)
        ):
            return best_idx, True

        k += 1

    return best_idx, False


def _score_bi_sequence(bis: List[Bi]) -> tuple[int, int]:
    """返回可比较的笔序列评分：(确认笔数, 总笔数)。"""
    if not bis:
        return -1, -1

    confirmed_count = sum(1 for bi in bis if bi.is_confirmed)
    return confirmed_count, len(bis)


def _is_better_initial_bis(
    current: List[Bi],
    candidate: List[Bi],
    current_start_idx: int,
    candidate_start_idx: int,
) -> bool:
    """首笔候选比较：仅在质量明确提升时允许右移起点。"""
    if not candidate:
        return False
    if not current:
        return True

    current_score = _score_bi_sequence(current)
    candidate_score = _score_bi_sequence(candidate)
    if candidate_score != current_score:
        return candidate_score > current_score

    if candidate[0].is_confirmed and not current[0].is_confirmed:
        return True
    if current[0].is_confirmed and not candidate[0].is_confirmed:
        return False

    # 评分完全一致时保持更靠左的起点，减少无谓漂移。
    return candidate_start_idx < current_start_idx


def _identify_bis_from_start(
    fractals: List[Fractal],
    normalized_bars: Optional[List[NormalizedBar]],
    pending_reverse_mode: Literal["any", "effective_only"],
    start_idx: int,
) -> List[Bi]:
    """从指定分型索引开始识别笔。"""
    if start_idx >= len(fractals) - 1:
        return []

    bis: List[Bi] = []
    bi_id = 0
    i = start_idx

    while i < len(fractals) - 1:
        start_fx = fractals[i]

        if bi_id == 0 and i > 0 and _is_leading_boundary_start(start_fx, normalized_bars):
            i += 1
            continue

        end_idx = _find_first_opposite(fractals, i, start_fx, normalized_bars)
        if end_idx < 0:
            i += 1
            continue

        end_idx, is_confirmed = _extend_until_reversal(
            fractals,
            end_idx,
            normalized_bars,
            pending_reverse_mode,
        )
        end_fx = fractals[end_idx]

        if bi_id == 0 and not is_confirmed and end_idx < len(fractals) - 1:
            i += 1
            continue

        direction = BiDirection.UP if start_fx.fx_type == FractalType.BOTTOM else BiDirection.DOWN

        bi = Bi(
            bi_id=bi_id,
            direction=direction,
            start_fx_id=start_fx.fx_id,
            end_fx_id=end_fx.fx_id,
            start_ts=start_fx.ts,
            end_ts=end_fx.ts,
            high=max(start_fx.high, end_fx.high),
            low=min(start_fx.low, end_fx.low),
            norm_bar_range=(start_fx.center_bar_idx, end_fx.center_bar_idx),
            is_confirmed=is_confirmed,
        )

        bis.append(bi)
        bi_id += 1

        if not is_confirmed:
            break

        i = end_idx

    return bis


def _identify_bis_core(
    fractals: List[Fractal],
    normalized_bars: Optional[List[NormalizedBar]],
    pending_reverse_mode: Literal["any", "effective_only"],
    bootstrap_initial_start: bool = True,
) -> List[Bi]:
    if len(fractals) < 2:
        return []

    best_bis = _identify_bis_from_start(
        fractals,
        normalized_bars,
        pending_reverse_mode,
        start_idx=0,
    )

    if not bootstrap_initial_start or len(fractals) <= 3:
        return best_bis

    best_start_idx = 0
    scan_end = min(len(fractals) - 1, MAX_INITIAL_START_SCAN)
    for candidate_start_idx in range(1, scan_end):
        candidate_bis = _identify_bis_from_start(
            fractals,
            normalized_bars,
            pending_reverse_mode,
            start_idx=candidate_start_idx,
        )
        if _is_better_initial_bis(
            best_bis,
            candidate_bis,
            best_start_idx,
            candidate_start_idx,
        ):
            best_bis = candidate_bis
            best_start_idx = candidate_start_idx

    return best_bis


def _tail_mixed_bis(
    fractals: List[Fractal],
    normalized_bars: Optional[List[NormalizedBar]],
) -> List[Bi]:
    base_bis = _identify_bis_core(
        fractals,
        normalized_bars,
        PENDING_REVERSE_MODE_ANY,
    )
    if not base_bis or base_bis[-1].is_confirmed:
        return base_bis

    tail_start_fx_id = base_bis[-1].start_fx_id
    tail_start_idx = next(
        (idx for idx, fractal in enumerate(fractals) if fractal.fx_id == tail_start_fx_id),
        None,
    )
    if tail_start_idx is None:
        return base_bis

    suffix_bis = _identify_bis_core(
        fractals[tail_start_idx:],
        normalized_bars,
        PENDING_REVERSE_MODE_EFFECTIVE_ONLY,
        bootstrap_initial_start=False,
    )
    if not suffix_bis:
        return base_bis

    prefix_bis = base_bis[:-1]
    for offset, bi in enumerate(suffix_bis, start=len(prefix_bis)):
        bi.bi_id = offset
    return prefix_bis + suffix_bis


def identify_bis(
    fractals: List[Fractal],
    normalized_bars: Optional[List[NormalizedBar]] = None,
    pending_reverse_mode: PendingReverseMode = PENDING_REVERSE_MODE_EFFECTIVE_ONLY,
) -> List[Bi]:
    """
    识别笔。
    
    规格文档 5.1-5.6:
    - 笔由类型相反的两个相邻分型构成
    - 成笔条件：分型三K窗口不得重叠，且两端分型极值K线在原始K线上之间至少 3 根K线
    - 笔末端可能被更强同类分型替代，直到反向分型出现后确认
    - 反向确认支持 any / effective_only / tail_mixed 三种模式（默认 effective_only）
    
    Args:
        fractals: 已去重的分型列表
        normalized_bars: 标准化K线序列，用于成笔间隔判定
        pending_reverse_mode: 尾部反向确认模式
    
    Returns:
        识别到的笔列表
    """
    if pending_reverse_mode not in {
        PENDING_REVERSE_MODE_ANY,
        PENDING_REVERSE_MODE_EFFECTIVE_ONLY,
        PENDING_REVERSE_MODE_TAIL_MIXED,
    }:
        raise ValueError(f"Unsupported pending_reverse_mode: {pending_reverse_mode}")

    if pending_reverse_mode == PENDING_REVERSE_MODE_TAIL_MIXED:
        return _tail_mixed_bis(fractals, normalized_bars)

    return _identify_bis_core(
        fractals,
        normalized_bars,
        pending_reverse_mode,
    )
