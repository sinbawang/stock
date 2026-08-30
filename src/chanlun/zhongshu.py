"""中枢识别。"""

from typing import List

from .models import Bi, BiDirection, ExpandedZhongshu, Segment, Zhongshu


def _item_id(item: Bi | Segment) -> int:
    if isinstance(item, Bi):
        return item.bi_id
    return item.segment_id


def _has_alternating_directions(items: List[Bi | Segment]) -> bool:
    return all(current.direction != previous.direction for previous, current in zip(items, items[1:]))


def _overlaps_zone(item: Bi | Segment, zs_low: float, zs_high: float) -> bool:
    return max(zs_low, item.low) < min(zs_high, item.high)


def _extend_zhongshu_with_item(zs: Zhongshu, item: Bi | Segment) -> None:
    zs.end_bi_id = _item_id(item)
    zs.end_ts = item.end_ts
    zs.bi_ids.append(_item_id(item))
    zs.peak_low = min(zs.peak_low, item.low)
    zs.peak_high = max(zs.peak_high, item.high)
    zs.render_end_bi_id = _item_id(item)


def _zones_overlap(previous: Zhongshu, current: Zhongshu) -> bool:
    return max(previous.zs_low, current.zs_low) < min(previous.zs_high, current.zs_high)


def _primary_segment_items(items: List[Bi | Segment]) -> List[Bi | Segment]:
    last_usable_index = len(items) - 1
    while last_usable_index >= 0:
        item = items[last_usable_index]
        if getattr(item, "is_confirmed", False):
            break
        last_usable_index -= 1
    return items[:last_usable_index + 1]


def _mark_reabsorbed_lineage(zhongshus: List[Zhongshu]) -> None:
    for previous, current in zip(zhongshus, zhongshus[1:]):
        if not previous.is_terminated:
            continue
        if previous.exit_bi_id is None or current.entering_bi_id != previous.exit_bi_id:
            continue
        if previous.structure_level != current.structure_level:
            continue
        if not _zones_overlap(previous, current):
            continue
        previous.superseded_by_zs_id = current.zs_id
        previous.is_reabsorbed_by_larger_expansion = True

    zhongshu_by_id = {zs.zs_id: zs for zs in zhongshus}
    changed = True
    while changed:
        changed = False
        for current in zhongshus:
            successor_id = current.superseded_by_zs_id
            if successor_id is None:
                continue
            successor = zhongshu_by_id.get(successor_id)
            if successor is None or successor.superseded_by_zs_id is None:
                continue
            final_successor = zhongshu_by_id.get(successor.superseded_by_zs_id)
            if final_successor is None:
                continue
            if current.structure_level != final_successor.structure_level:
                continue
            if not _zones_overlap(current, final_successor):
                continue
            if current.superseded_by_zs_id != final_successor.zs_id:
                current.superseded_by_zs_id = final_successor.zs_id
                current.is_reabsorbed_by_larger_expansion = True
                changed = True


def is_zhongshu_expansion(previous: Zhongshu, current: Zhongshu) -> bool:
    """第20课中枢中心定理二：相邻同级别中枢是否构成更高级别中枢（扩张）。

    仅区间不重叠、且波动区间（GG/DD）回探重叠时构成扩张：
    - 向上：后ZD>前ZG，后DD<=前GG → 扩张；后DD>前GG → 上涨延续（趋势）。
    - 向下：后ZG<前ZD，后GG>=前DD → 扩张；后GG<前DD → 下跌延续（趋势）。
    - 区间重叠 → 同级别盘整/延伸，不算扩张。

    注意：这是「纯粹按中枢」视角；同级别分解（第38/39课）不处理扩张。
    """
    if current.zs_low > previous.zs_high:
        return current.peak_low <= previous.peak_high
    if current.zs_high < previous.zs_low:
        return current.peak_high >= previous.peak_low
    return False


def identify_expanded_zhongshus(zhongshus: List[Zhongshu]) -> List[ExpandedZhongshu]:
    """第20课：相邻同级别中枢区间不重叠、但当前中枢波动回探进前中枢区间 → 合并为更大级别中枢。

    - 区间重叠 → 已是同级别盘整/延伸，不算扩张。
    - 区间不重叠 + 波动不回探 → 趋势（up/down），不算扩张。
    - 区间不重叠 + 波动回探 → 扩张：产出更大级别中枢，区间=两段波动区间重叠。
    """
    expanded: List[ExpandedZhongshu] = []
    eid = 0
    i = 0
    while i < len(zhongshus) - 1:
        previous = zhongshus[i]
        current = zhongshus[i + 1]
        if is_zhongshu_expansion(previous, current):
            low = max(previous.peak_low, current.peak_low)
            high = min(previous.peak_high, current.peak_high)
            expanded.append(
                ExpandedZhongshu(
                    expanded_id=eid,
                    sub_zs_ids=[previous.zs_id, current.zs_id],
                    expanded_low=low,
                    expanded_high=high,
                    peak_low=min(previous.peak_low, current.peak_low),
                    peak_high=max(previous.peak_high, current.peak_high),
                    start_ts=previous.start_ts,
                    end_ts=current.end_ts,
                    structure_level=previous.structure_level,
                )
            )
            eid += 1
        i += 1
    return expanded


def identify_zhongshu(items: List[Bi | Segment], *, structure_level: str = "bi") -> List[Zhongshu]:
    """
    识别中枢。

    spec_id: SPEC.ZHONGSHU.CORE（见 docs/chanlun/zhongshu-core-spec.md）。

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

    if structure_level == "segment":
        # Keep the primary chain stable by trimming only the active pending tail.
        # Historical middle segments may still carry pending stop labels while already
        # being part of the realized alternating chain; dropping them would distort the
        # segment sequence and suppress valid same-level centers.
        items = _primary_segment_items(items)

    if len(items) < 5:
        return []

    zhongshus = []
    zs_id = 0

    # 从前往后扫描：items[i] 视为进入单元，中枢本体起始候选为 items[i+1:i+4]
    i = 0
    while i < len(items) - 3:
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

            # 中枢区间固定为前三笔重叠(ZD/ZG)，后续仅扩展本体参与笔列表。
            # 突破 / 趋势反转判定（第三类买卖点口径，均需前瞻确认）：
            # - 干净突破（同向破 ZG/ZD 未贯穿、或反向破 ZD/ZG 未贯穿）：
            #   - 不与区间重叠 → 立即离开（同向）或反转（反向）。
            #   - 与区间重叠 → 前瞻下一段，不回中枢才确认离开 / 反转；
            #     回中枢或已无下一段 → 突破失败，并入延伸。
            # - 贯穿区间（从对侧穿越整个区间）→ 震荡穿越，并入延伸。
            # - 与区间重叠（无突破）→ 并入延伸。
            # - 否则 → 终止扫描。
            j = i + 4
            while j < len(items):
                cand = items[j]
                same_dir_cand = cand.direction == entering_item.direction
                # 与进入段同向的突破（上行破 ZG / 下行破 ZD）
                breaks_out = (
                    (entering_item.direction == BiDirection.UP and cand.high > zs_high)
                    or (entering_item.direction == BiDirection.DOWN and cand.low < zs_low)
                )
                # 反方向突破（上行中枢被下行破 ZD / 下行中枢被上行破 ZG）
                crosses_opposite = (
                    (entering_item.direction == BiDirection.UP and cand.low < zs_low)
                    or (entering_item.direction == BiDirection.DOWN and cand.high > zs_high)
                )
                # 干净突破：同向未贯穿（走出候选）或反向未贯穿（反转候选）
                clean_breakout = (
                    (same_dir_cand and breaks_out and not crosses_opposite)
                    or ((not same_dir_cand) and crosses_opposite and not breaks_out)
                )
                if clean_breakout:
                    if not _overlaps_zone(cand, zs_low, zs_high):
                        break  # 干净突破不与区间重叠：走出段 / 反转段
                    next_item = items[j + 1] if j + 1 < len(items) else None
                    if next_item is not None and not _overlaps_zone(next_item, zs_low, zs_high):
                        break  # 突破 + 下一段不回中枢：确认离开 / 反转
                    # 突破失败（下一段回中枢/无法确认）：并入延伸
                    _extend_zhongshu_with_item(zs, cand)
                    j += 1
                    continue
                if _overlaps_zone(cand, zs_low, zs_high):
                    # 与中枢区间重叠，纳入本体延伸
                    _extend_zhongshu_with_item(zs, cand)
                    j += 1
                else:
                    break  # 既不延伸也不突破，终止扫描

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

    _mark_reabsorbed_lineage(zhongshus)
    return zhongshus
