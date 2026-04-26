"""中枢识别。"""

from typing import List
from .models import Bi, BiDirection, Zhongshu


def _has_alternating_directions(bis: List[Bi]) -> bool:
    return all(current.direction != previous.direction for previous, current in zip(bis, bis[1:]))


def _overlaps_zone(bi: Bi, zs_low: float, zs_high: float) -> bool:
    return max(zs_low, bi.low) < min(zs_high, bi.high)


def identify_zhongshu(bis: List[Bi]) -> List[Zhongshu]:
    """
    识别中枢。

    规格文档 7.2-7.3:
    - 必须存在进入笔；走出笔用于确认中枢终结
    - 中枢本体位于进入与走出之间，至少由 3 笔构成
    - 中枢本体前三笔必须连续、方向交替，且存在价格重叠
    - 中枢区间(ZD/ZG)固定为中枢本体前三笔的重叠区间
    - 走出笔必须与进入笔同向，并向对应方向突破中枢区间

    Args:
        bis: 笔列表

    Returns:
        识别到的中枢列表
    """
    if len(bis) < 5:
        return []

    zhongshus = []
    zs_id = 0

    # 从前往后扫描：bis[i] 视为进入笔，中枢本体起始候选为 bis[i+1:i+4]
    i = 0
    while i < len(bis) - 4:
        entering_bi = bis[i]
        internal_bis = bis[i + 1:i + 4]
        if not _has_alternating_directions(internal_bis):
            i += 1
            continue

        # 中枢本体前三笔必须相对进入笔呈“反向-同向-反向”
        if (
            internal_bis[0].direction == entering_bi.direction
            or internal_bis[1].direction != entering_bi.direction
            or internal_bis[2].direction == entering_bi.direction
        ):
            i += 1
            continue

        bi1, bi2, bi3 = internal_bis

        zs_low = max(bi1.low, bi2.low, bi3.low)
        zs_high = min(bi1.high, bi2.high, bi3.high)

        if zs_low < zs_high and _overlaps_zone(entering_bi, zs_low, zs_high):
            # 存在有效重叠，且进入笔必须与中枢区间有重叠（进入笔须经过中枢区间）
            peak_low = min(bi1.low, bi2.low, bi3.low)
            peak_high = max(bi1.high, bi2.high, bi3.high)

            zs = Zhongshu(
                zs_id=zs_id,
                start_bi_id=bi1.bi_id,
                end_bi_id=bi3.bi_id,
                zs_low=zs_low,
                zs_high=zs_high,
                peak_low=peak_low,
                peak_high=peak_high,
                start_ts=bi1.start_ts,
                end_ts=bi3.end_ts,
                bi_ids=[bi1.bi_id, bi2.bi_id, bi3.bi_id],
                is_terminated=False
            )

            # 中枢区间固定为前三笔重叠(ZD/ZG)，后续仅扩展本体参与笔列表
            # 优先判断重叠：与区间重叠则纳入本体延伸；
            # 不重叠时再判断是否是走出段（同向+突破ZG/ZD）
            j = i + 4
            while j < len(bis):
                cand = bis[j]
                if _overlaps_zone(cand, zs_low, zs_high):
                    # 与中枢区间重叠，纳入本体延伸
                    zs.end_bi_id = cand.bi_id
                    zs.end_ts = cand.end_ts
                    zs.bi_ids.append(cand.bi_id)
                    zs.peak_low = min(zs.peak_low, cand.low)
                    zs.peak_high = max(zs.peak_high, cand.high)
                    j += 1
                else:
                    # 不与区间重叠，检查是否是走出段
                    same_dir_cand = cand.direction == entering_bi.direction
                    breaks_out_cand = (
                        (entering_bi.direction == BiDirection.UP and cand.high > zs_high)
                        or (entering_bi.direction == BiDirection.DOWN and cand.low < zs_low)
                    )
                    if same_dir_cand and breaks_out_cand:
                        break  # 视为走出段，停止延伸
                    else:
                        break  # 既不延伸也不走出，终止

            # 走出笔：与进入笔同向，且向对应方向突破中枢区间
            # 上升中枢(进/出向上): exit_bi.high > zs_high (突破ZG)
            # 下降中枢(进/出向下): exit_bi.low  < zs_low  (跌破ZD)
            if j < len(bis):
                exit_bi = bis[j]
                same_dir = exit_bi.direction == entering_bi.direction
                breaks_out = (
                    (entering_bi.direction == BiDirection.UP and exit_bi.high > zs_high)
                    or (entering_bi.direction == BiDirection.DOWN and exit_bi.low < zs_low)
                )
                if same_dir and breaks_out:
                    zs.is_terminated = True
                    zhongshus.append(zs)
                    zs_id += 1
                    # 走出笔可作为下一中枢的进入笔
                    i = j
                    continue

            # 没有有效走出笔时，保留未终结中枢
            zhongshus.append(zs)
            zs_id += 1
            i = j
        else:
            i += 1

    return zhongshus
