"""中枢识别。"""

from typing import List

from .models import Bi, BiDirection, Segment, Zhongshu


def _item_id(item: Bi | Segment) -> int:
    if isinstance(item, Bi):
        return item.bi_id
    return item.segment_id


def _has_alternating_directions(items: List[Bi | Segment]) -> bool:
    return all(current.direction != previous.direction for previous, current in zip(items, items[1:]))


def _overlaps_zone(item: Bi | Segment, zs_low: float, zs_high: float) -> bool:
    return max(zs_low, item.low) < min(zs_high, item.high)


def identify_zhongshu(items: List[Bi | Segment], *, structure_level: str = "bi") -> List[Zhongshu]:
    """
    识别中枢。

    规格文档 7.2-7.3:
    - 必须存在进入笔；走出笔用于确认中枢终结
    - 中枢本体位于进入与走出之间，至少由 3 笔构成
    - 中枢本体前三笔必须连续、方向交替，且存在价格重叠
    - 中枢区间(ZD/ZG)固定为中枢本体前三笔的重叠区间
    - 走出笔必须与进入笔同向，并向对应方向突破中枢区间

    Args:
        items: 笔列表或线段列表
        structure_level: `bi` 或 `segment`

    Returns:
        识别到的中枢列表
    """
    if structure_level not in {"bi", "segment"}:
        raise ValueError(f"Unsupported structure_level: {structure_level}")

    if len(items) < 5:
        return []

    zhongshus = []
    zs_id = 0

    # 从前往后扫描：items[i] 视为进入单元，中枢本体起始候选为 items[i+1:i+4]
    i = 0
    while i < len(items) - 4:
        entering_item = items[i]
        internal_items = items[i + 1:i + 4]
        if not _has_alternating_directions(internal_items):
            i += 1
            continue

        # 中枢本体前三单元必须相对进入单元呈“反向-同向-反向”
        if (
            internal_items[0].direction == entering_item.direction
            or internal_items[1].direction != entering_item.direction
            or internal_items[2].direction == entering_item.direction
        ):
            i += 1
            continue

        item1, item2, item3 = internal_items

        zs_low = max(item1.low, item2.low, item3.low)
        zs_high = min(item1.high, item2.high, item3.high)

        if zs_low < zs_high and _overlaps_zone(entering_item, zs_low, zs_high):
            # 存在有效重叠，且进入单元必须与中枢区间有重叠（进入单元须经过中枢区间）
            peak_low = min(item1.low, item2.low, item3.low)
            peak_high = max(item1.high, item2.high, item3.high)

            zs = Zhongshu(
                zs_id=zs_id,
                start_bi_id=_item_id(item1),
                end_bi_id=_item_id(item3),
                zs_low=zs_low,
                zs_high=zs_high,
                peak_low=peak_low,
                peak_high=peak_high,
                start_ts=item1.start_ts,
                end_ts=item3.end_ts,
                bi_ids=[_item_id(item1), _item_id(item2), _item_id(item3)],
                is_terminated=False,
                entering_bi_id=_item_id(entering_item),
                core_bi_ids=[_item_id(item1), _item_id(item2), _item_id(item3)],
                exit_bi_id=None,
                zone_mode="fixed_first_three_overlap",
                render_start_bi_id=_item_id(item1),
                render_end_bi_id=_item_id(item3),
                structure_level=structure_level,
                recognition_mode="fixed_first_three_overlap",
                render_mode="core_plus_extension",
            )

            # 中枢区间固定为前三笔重叠(ZD/ZG)，后续仅扩展本体参与笔列表
            # 优先判断重叠：与区间重叠则纳入本体延伸；
            # 不重叠时再判断是否是走出段（同向+突破ZG/ZD）
            j = i + 4
            while j < len(items):
                cand = items[j]
                if _overlaps_zone(cand, zs_low, zs_high):
                    # 与中枢区间重叠，纳入本体延伸
                    zs.end_bi_id = _item_id(cand)
                    zs.end_ts = cand.end_ts
                    zs.bi_ids.append(_item_id(cand))
                    zs.peak_low = min(zs.peak_low, cand.low)
                    zs.peak_high = max(zs.peak_high, cand.high)
                    zs.render_end_bi_id = _item_id(cand)
                    j += 1
                else:
                    # 不与区间重叠，检查是否是走出段
                    same_dir_cand = cand.direction == entering_item.direction
                    breaks_out_cand = (
                        (entering_item.direction == BiDirection.UP and cand.high > zs_high)
                        or (entering_item.direction == BiDirection.DOWN and cand.low < zs_low)
                    )
                    if same_dir_cand and breaks_out_cand:
                        break  # 视为走出段，停止延伸
                    else:
                        break  # 既不延伸也不走出，终止

            # 走出笔：与进入笔同向，且向对应方向突破中枢区间
            # 上升中枢(进/出向上): exit_bi.high > zs_high (突破ZG)
            # 下降中枢(进/出向下): exit_bi.low  < zs_low  (跌破ZD)
            if j < len(items):
                exit_item = items[j]
                same_dir = exit_item.direction == entering_item.direction
                breaks_out = (
                    (entering_item.direction == BiDirection.UP and exit_item.high > zs_high)
                    or (entering_item.direction == BiDirection.DOWN and exit_item.low < zs_low)
                )
                if same_dir and breaks_out:
                    zs.is_terminated = True
                    zs.exit_bi_id = _item_id(exit_item)
                    zhongshus.append(zs)
                    zs_id += 1
                    # 走出单元可作为下一中枢的进入单元
                    i = j
                    continue

            # 没有有效走出笔时，保留未终结中枢
            zhongshus.append(zs)
            zs_id += 1
            i = j
        else:
            i += 1

    return zhongshus
