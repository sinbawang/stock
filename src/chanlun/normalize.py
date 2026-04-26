"""
包含关系处理（去包含）。

按规格文档第 3.2 节，先对相邻 K 线进行包含关系检测和合并。
"""

from typing import List, Optional
from .models import Bar, NormalizedBar


def has_inclusion(bar_a: Bar, bar_b: Bar) -> bool:
    """
    检测 bar_a 是否包含 bar_b。
    仅在严格包含时成立：a.high > b.high 且 a.low < b.low。
    相等高点或相等低点不视为包含。
    """
    return bar_a.high > bar_b.high and bar_a.low < bar_b.low


def merge_bars(
    bar_a: Bar,
    bar_b: Bar,
    direction: str
) -> tuple[float, float]:
    """
    合并两根有包含关系的 K 线。
    
    Args:
        bar_a, bar_b: 两根 K 线
        direction: "up" 或 "down"，表示当前处理方向
    
    Returns:
        (high, low) 合并后的价格范围
    """
    if direction == "up":
        # 向上：取两个的较高低点，较高高点
        return max(bar_a.high, bar_b.high), max(bar_a.low, bar_b.low)
    else:  # direction == "down"
        # 向下：取两个的较低高点，较低低点
        return min(bar_a.high, bar_b.high), min(bar_a.low, bar_b.low)


def _outer_union(bar_a: Bar, bar_b: Bar) -> tuple[float, float]:
    """方向未定时仅用于后续判向的外包范围。"""
    return max(bar_a.high, bar_b.high), min(bar_a.low, bar_b.low)


def _build_temp_bar(
    high: float,
    low: float,
    ts_end,
) -> Bar:
    return Bar(
        ts=ts_end,
        open=high,
        high=high,
        low=low,
        close=low,
        volume=0,
    )


def _infer_direction(prev_bar: Bar, next_bar: Bar) -> Optional[str]:
    if prev_bar.high < next_bar.high and prev_bar.low < next_bar.low:
        return "up"
    if prev_bar.high > next_bar.high and prev_bar.low > next_bar.low:
        return "down"
    return None


def _resolve_pending_chain(pending_bars: List[Bar], direction: Optional[str]) -> tuple[float, float, object, object, object, object, List[int]]:
    first_bar = pending_bars[0]
    if direction is None or len(pending_bars) == 1:
        return (
            first_bar.high,
            first_bar.low,
            first_bar.ts,
            first_bar.ts,
            first_bar.ts,
            first_bar.ts,
            [0],
        )

    current_high = first_bar.high
    current_low = first_bar.low
    current_ts_start = first_bar.ts
    current_ts_end = first_bar.ts
    current_ts_high = first_bar.ts
    current_ts_low = first_bar.ts

    for bar in pending_bars[1:]:
        temp_bar = _build_temp_bar(current_high, current_low, current_ts_end)
        merged_high, merged_low = merge_bars(temp_bar, bar, direction)

        if direction == "up":
            if bar.high > current_high:
                current_ts_high = bar.ts
            if bar.low >= current_low:
                current_ts_low = bar.ts
        else:
            if bar.high <= current_high:
                current_ts_high = bar.ts
            if bar.low < current_low:
                current_ts_low = bar.ts

        current_high = merged_high
        current_low = merged_low
        current_ts_end = bar.ts

    return (
        current_high,
        current_low,
        current_ts_start,
        current_ts_end,
        current_ts_high,
        current_ts_low,
        list(range(len(pending_bars))),
    )


def normalize_bars(bars: List[Bar]) -> List[NormalizedBar]:
    """
    去包含处理，生成标准化 K 线序列。
    
    规则（规格文档 3.2）：
    1. 初始化方向判断
    2. 检测包含关系，按方向合并
    3. 反向时，记录新方向
    4. 输出标准化 K 线及其源索引映射
    
    Args:
        bars: 原始 K 线序列
    
    Returns:
        标准化 K 线列表
    """
    if not bars or len(bars) < 2:
        # 少于 2 根 K 线，无法执行去包含逻辑
        return [
            NormalizedBar(
                idx=i,
                high=bar.high,
                low=bar.low,
                ts_start=bar.ts,
                ts_end=bar.ts,
                src_indices=[i],
                direction=None
            )
            for i, bar in enumerate(bars)
        ]

    normalized = []
    current_high = bars[0].high
    current_low = bars[0].low
    current_ts_start = bars[0].ts
    current_ts_end = bars[0].ts
    current_ts_high = bars[0].ts
    current_ts_low = bars[0].ts
    current_direction = None
    src_indices = [0]
    pending_bars = [bars[0]]

    for i in range(1, len(bars)):
        bar = bars[i]

        # 判断当前 bar 与缓存的 bar 是否有包含关系
        temp_bar = _build_temp_bar(current_high, current_low, current_ts_end)

        if has_inclusion(temp_bar, bar) or has_inclusion(bar, temp_bar):
            pending_bars.append(bar)
            src_indices.append(i)

            if current_direction is None:
                current_high, current_low = _outer_union(temp_bar, bar)
                current_ts_end = bar.ts
                if bar.high >= current_high:
                    current_ts_high = bar.ts
                if bar.low <= current_low:
                    current_ts_low = bar.ts
                continue

            h, l = merge_bars(temp_bar, bar, current_direction)

            if current_direction == "up":
                if bar.high > current_high:
                    current_ts_high = bar.ts
                if bar.low >= current_low:
                    current_ts_low = bar.ts
            else:
                if bar.high <= current_high:
                    current_ts_high = bar.ts
                if bar.low < current_low:
                    current_ts_low = bar.ts

            current_high = h
            current_low = l
            current_ts_end = bar.ts
        else:
            inferred_direction = _infer_direction(temp_bar, bar)
            if current_direction is None and inferred_direction is not None:
                current_direction = inferred_direction
                resolved = _resolve_pending_chain(pending_bars, current_direction)
                current_high = resolved[0]
                current_low = resolved[1]
                current_ts_start = resolved[2]
                current_ts_end = resolved[3]
                current_ts_high = resolved[4]
                current_ts_low = resolved[5]

            # 无包含关系，保存当前标准化 K 线，开始新的一个
            normalized.append(
                NormalizedBar(
                    idx=len(normalized),
                    high=current_high,
                    low=current_low,
                    ts_start=current_ts_start,
                    ts_end=current_ts_end,
                    ts_high=current_ts_high,
                    ts_low=current_ts_low,
                    src_indices=src_indices.copy(),
                    direction=current_direction
                )
            )

            # 判断新方向
            current_direction = _infer_direction(normalized[-1], bar)

            current_high = bar.high
            current_low = bar.low
            current_ts_start = bar.ts
            current_ts_end = bar.ts
            current_ts_high = bar.ts
            current_ts_low = bar.ts
            src_indices = [i]
            pending_bars = [bar]

    # 处理最后一根
    if current_direction is not None and len(pending_bars) > 1:
        resolved = _resolve_pending_chain(pending_bars, current_direction)
        current_high = resolved[0]
        current_low = resolved[1]
        current_ts_start = resolved[2]
        current_ts_end = resolved[3]
        current_ts_high = resolved[4]
        current_ts_low = resolved[5]

    normalized.append(
        NormalizedBar(
            idx=len(normalized),
            high=current_high,
            low=current_low,
            ts_start=current_ts_start,
            ts_end=current_ts_end,
            ts_high=current_ts_high,
            ts_low=current_ts_low,
            src_indices=src_indices,
            direction=current_direction
        )
    )

    return normalized
