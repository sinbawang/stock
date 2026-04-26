"""
分型识别（顶分型和底分型）。

基于标准化 K 线序列识别分型，包括去重规则。
"""

from typing import List
from .models import NormalizedBar, Fractal, FractalType


def _dominates_for_top(curr: NormalizedBar, side: NormalizedBar) -> bool:
    return curr.high >= side.high and curr.low >= side.low and (
        curr.high > side.high or curr.low > side.low
    )


def _dominates_for_bottom(curr: NormalizedBar, side: NormalizedBar) -> bool:
    return curr.high <= side.high and curr.low <= side.low and (
        curr.high < side.high or curr.low < side.low
    )


def identify_fractals(normalized_bars: List[NormalizedBar]) -> List[Fractal]:
    """
    识别分型。
    
    规格文档 4.1, 4.2:
    - 顶分型: 当前 K 线相对左右两侧都更高，允许一侧高点或低点相等，
             但至少一项严格更高
    - 底分型: 当前 K 线相对左右两侧都更低，允许一侧高点或低点相等，
             但至少一项严格更低
    
    Args:
        normalized_bars: 标准化 K 线序列
    
    Returns:
        识别到的分型列表
    """
    if len(normalized_bars) < 3:
        return []

    fractals = []
    fx_id = 0

    for i in range(1, len(normalized_bars) - 1):
        prev_bar = normalized_bars[i - 1]
        curr_bar = normalized_bars[i]
        next_bar = normalized_bars[i + 1]

        # 检查顶分型
        if _dominates_for_top(curr_bar, prev_bar) and _dominates_for_top(curr_bar, next_bar):
            fractals.append(
                Fractal(
                    fx_id=fx_id,
                    fx_type=FractalType.TOP,
                    ts=curr_bar.ts_high,
                    price=curr_bar.high,
                    center_bar_idx=i,
                    high=curr_bar.high,
                    low=curr_bar.low
                )
            )
            fx_id += 1

        # 检查底分型
        elif _dominates_for_bottom(curr_bar, prev_bar) and _dominates_for_bottom(curr_bar, next_bar):
            fractals.append(
                Fractal(
                    fx_id=fx_id,
                    fx_type=FractalType.BOTTOM,
                    ts=curr_bar.ts_low,
                    price=curr_bar.low,
                    center_bar_idx=i,
                    high=curr_bar.high,
                    low=curr_bar.low
                )
            )
            fx_id += 1

    return fractals


def filter_consecutive_fractals(fractals: List[Fractal]) -> List[Fractal]:
    """
    去重：连续同类型分型只保留极值的那个。
    
    规格文档 4.4:
    - 连续顶分型保留最高的
    - 连续底分型保留最低的
    
    Args:
        fractals: 原始分型列表
    
    Returns:
        去重后的分型列表
    """
    if len(fractals) < 2:
        return fractals

    filtered = [fractals[0]]

    for i in range(1, len(fractals)):
        curr = fractals[i]
        prev = filtered[-1]

        if curr.fx_type == prev.fx_type:
            # 同类型，比较极值
            if curr.fx_type == FractalType.TOP:
                # 比较 high，保留更高的
                if curr.price > prev.price:
                    filtered[-1] = curr
            else:  # BOTTOM
                # 比较 low，保留更低的
                if curr.price < prev.price:
                    filtered[-1] = curr
        else:
            # 不同类型，直接添加
            filtered.append(curr)

    return filtered
