"""
笔识别（从一个分型到下一个反向分型）。

基于已经过滤的分型列表识别笔。
"""

from typing import List, Optional
from .models import Fractal, Bi, FractalType, BiDirection, NormalizedBar


# 分型中心索引最小间隔：
# - 未提供 normalized_bars 时，按历史约定允许 >=3（三K窗口不重叠）
# - 提供 normalized_bars 时，默认 >=4，或在原始K线映射上满足独立K补偿
MIN_CENTER_GAP = 4


def _is_more_extreme(base: Fractal, candidate: Fractal) -> bool:
    """同类分型极值比较。"""
    if base.fx_type == FractalType.TOP:
        return candidate.price > base.price
    return candidate.price < base.price


def _fractal_window_extremes(
    fractal: Fractal,
    normalized_bars: Optional[List[NormalizedBar]],
) -> tuple[float, float]:
    if not normalized_bars:
        return fractal.high, fractal.low

    left = max(0, fractal.center_bar_idx - 1)
    right = min(len(normalized_bars), fractal.center_bar_idx + 2)
    window = normalized_bars[left:right]
    if not window:
        return fractal.high, fractal.low

    return max(bar.high for bar in window), min(bar.low for bar in window)


def _window_raw_index_span(
    fractal: Fractal,
    normalized_bars: Optional[List[NormalizedBar]],
) -> Optional[tuple[int, int]]:
    """返回分型三K窗口在原始K线索引上的覆盖范围(min_idx, max_idx)。"""
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


def _has_enough_pen_gap(
    start_fx: Fractal,
    end_fx: Fractal,
    normalized_bars: Optional[List[NormalizedBar]],
) -> bool:
    """
    成笔间隔判定。

    默认要求 center 差值 >= MIN_CENTER_GAP(=4)，确保两个三K窗口之间有至少1根独立标准化K。
    放宽特例：若差值==3（标准化后中间0根），但在原始K线映射上两个三K窗口之间仍有至少1根独立K，
    则允许成笔（用于处理包含关系压缩导致的“视觉无间隔”）。
    """
    center_gap = end_fx.center_bar_idx - start_fx.center_bar_idx

    # 未提供标准化映射时，按基础规则仅要求两分型三K窗口不重叠。
    if not normalized_bars:
        return center_gap >= MIN_CENTER_GAP - 1

    if center_gap >= MIN_CENTER_GAP:
        return True

    if center_gap != MIN_CENTER_GAP - 1:
        return False

    start_span = _window_raw_index_span(start_fx, normalized_bars)
    end_span = _window_raw_index_span(end_fx, normalized_bars)
    if start_span is None or end_span is None:
        return False

    _, start_max = start_span
    end_min, _ = end_span
    # 原始K线至少留出1根独立K: end_min - start_max >= 2
    return end_min - start_max >= 2


def _is_valid_pen_endpoint(
    start_fx: Fractal,
    end_fx: Fractal,
    normalized_bars: Optional[List[NormalizedBar]],
) -> bool:
    if end_fx.fx_type == start_fx.fx_type:
        return False

    start_window_high, start_window_low = _fractal_window_extremes(start_fx, normalized_bars)
    if start_fx.fx_type == FractalType.BOTTOM:
        return end_fx.price > start_window_high

    return end_fx.price < start_window_low


def _find_first_opposite(
    fractals: List[Fractal],
    start_idx: int,
    start_fx: Fractal,
    normalized_bars: Optional[List[NormalizedBar]],
) -> int:
    """从 start_idx 之后寻找第一个满足间隔条件的反向分型索引。"""
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

        if pending_reverse is None or _is_more_extreme(pending_reverse, fx):
            pending_reverse = fx

        if (
            _has_enough_pen_gap(best_fx, pending_reverse, normalized_bars)
            and _is_valid_pen_endpoint(best_fx, pending_reverse, normalized_bars)
        ):
            return best_idx, True

        k += 1

    return best_idx, False


def identify_bis(
    fractals: List[Fractal],
    normalized_bars: Optional[List[NormalizedBar]] = None,
) -> List[Bi]:
    """
    识别笔。
    
    规格文档 5.1-5.4:
    - 笔由类型相反的两个相邻分型构成
    - 成笔条件：至少间隔 1 根标准化 K 线
    - 笔末端可能被更强同类分型替代，直到反向分型出现后确认
    
    Args:
        fractals: 已去重的分型列表
    
    Returns:
        识别到的笔列表
    """
    if len(fractals) < 2:
        return []

    bis: List[Bi] = []
    bi_id = 0

    i = 0

    while i < len(fractals) - 1:
        start_fx = fractals[i]
        end_idx = _find_first_opposite(fractals, i, start_fx, normalized_bars)
        if end_idx < 0:
            i += 1
            continue

        end_idx, is_confirmed = _extend_until_reversal(fractals, end_idx, normalized_bars)
        end_fx = fractals[end_idx]

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

        # 未确认笔处理：
        # - 有 normalized 映射时，继续后移扫描，避免提前截断后续笔
        # - 无映射时，保持历史行为（预处理后终止）以兼容既有规则与测试
        if not is_confirmed:
            if normalized_bars:
                i += 1
                continue
            break

        # 进入下一笔
        i = end_idx

    return bis
