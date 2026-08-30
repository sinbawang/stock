"""中枢识别单元测试。spec_id: SPEC.ZHONGSHU.CORE。"""

import csv
from datetime import datetime
from pathlib import Path

from chanlun.analysis import _relation_kind, build_structure_state
from chanlun.models import Bi, BiDirection, Segment, Zhongshu
from chanlun.segment import identify_segments
from chanlun.zhongshu import _mark_reabsorbed_lineage, identify_expanded_zhongshus, identify_zhongshu, is_zhongshu_expansion


def _bi(bi_id: int, direction: BiDirection, high: float, low: float) -> Bi:
    start = datetime(2024, 1, 1 + bi_id)
    end = datetime(2024, 1, 1 + bi_id, 1)
    return Bi(
        bi_id=bi_id,
        direction=direction,
        start_fx_id=bi_id,
        end_fx_id=bi_id + 1,
        start_ts=start,
        end_ts=end,
        high=high,
        low=low,
        norm_bar_range=(bi_id, bi_id + 1),
        is_confirmed=True,
    )


def _segment(segment_id: int, direction: BiDirection, high: float, low: float, *, is_confirmed: bool = True) -> Segment:
    start = datetime(2024, 2, 1 + segment_id)
    end = datetime(2024, 2, 1 + segment_id, 1)
    start_price = low if direction == BiDirection.UP else high
    end_price = high if direction == BiDirection.UP else low
    return Segment(
        segment_id=segment_id,
        direction=direction,
        start_bi_id=segment_id * 2,
        end_bi_id=segment_id * 2 + 1,
        start_ts=start,
        end_ts=end,
        start_price=start_price,
        end_price=end_price,
        high=high,
        low=low,
        norm_bar_range=(segment_id * 4, segment_id * 4 + 3),
        bi_ids=[segment_id * 2, segment_id * 2 + 1],
        is_confirmed=is_confirmed,
    )


def _zhongshu(
    zs_id: int,
    *,
    low: float,
    high: float,
    entering_bi_id: int,
    exit_bi_id: int | None,
    terminated: bool,
    structure_level: str = "bi",
) -> Zhongshu:
    start = datetime(2024, 3, 1 + zs_id)
    end = datetime(2024, 3, 1 + zs_id, 1)
    return Zhongshu(
        zs_id=zs_id,
        start_bi_id=zs_id * 10,
        end_bi_id=zs_id * 10 + 2,
        zs_low=low,
        zs_high=high,
        peak_low=low - 1,
        peak_high=high + 1,
        start_ts=start,
        end_ts=end,
        bi_ids=[zs_id * 10, zs_id * 10 + 1, zs_id * 10 + 2],
        is_terminated=terminated,
        entering_bi_id=entering_bi_id,
        core_bi_ids=[zs_id * 10, zs_id * 10 + 1, zs_id * 10 + 2],
        exit_bi_id=exit_bi_id,
        structure_level=structure_level,
    )


def _zhongshu_with_peaks(
    zs_id: int,
    *,
    zone_low: float,
    zone_high: float,
    peak_low: float,
    peak_high: float,
    structure_level: str = "bi",
) -> Zhongshu:
    start = datetime(2024, 4, 1 + zs_id)
    end = datetime(2024, 4, 1 + zs_id, 1)
    return Zhongshu(
        zs_id=zs_id,
        start_bi_id=zs_id * 10,
        end_bi_id=zs_id * 10 + 2,
        zs_low=zone_low,
        zs_high=zone_high,
        peak_low=peak_low,
        peak_high=peak_high,
        start_ts=start,
        end_ts=end,
        bi_ids=[zs_id * 10, zs_id * 10 + 1, zs_id * 10 + 2],
        is_terminated=False,
        entering_bi_id=zs_id * 10 - 1,
        core_bi_ids=[zs_id * 10, zs_id * 10 + 1, zs_id * 10 + 2],
        exit_bi_id=None,
        structure_level=structure_level,
    )


def test_is_zhongshu_expansion_up_dip_back() -> None:
    # 向上候选：当前中枢波动下沿（85.7）回探到前中枢上沿（91.35）之下 → 扩张
    a = _zhongshu_with_peaks(0, zone_low=89.0, zone_high=91.35, peak_low=88.7, peak_high=94.5)
    b = _zhongshu_with_peaks(1, zone_low=92.05, zone_high=92.2, peak_low=85.7, peak_high=96.45)
    assert is_zhongshu_expansion(a, b) is True


def test_is_zhongshu_expansion_clean_trends() -> None:
    # 向上干净趋势：后DD（11.6）> 前GG（11.5），波动不重叠 → 非扩张
    up_prev = _zhongshu_with_peaks(0, zone_low=10.0, zone_high=11.0, peak_low=9.5, peak_high=11.5)
    up_curr = _zhongshu_with_peaks(1, zone_low=12.0, zone_high=13.0, peak_low=11.6, peak_high=13.5)
    assert is_zhongshu_expansion(up_prev, up_curr) is False
    # 向下干净趋势：后GG（19.4）< 前DD（19.5），波动不重叠 → 非扩张
    dn_prev = _zhongshu_with_peaks(2, zone_low=20.0, zone_high=21.0, peak_low=19.5, peak_high=21.5)
    dn_curr = _zhongshu_with_peaks(3, zone_low=17.0, zone_high=18.0, peak_low=16.5, peak_high=19.4)
    assert is_zhongshu_expansion(dn_prev, dn_curr) is False


def test_is_zhongshu_expansion_overlapping_zones() -> None:
    a = _zhongshu_with_peaks(0, zone_low=80.0, zone_high=85.0, peak_low=79.0, peak_high=86.0)
    b = _zhongshu_with_peaks(1, zone_low=84.0, zone_high=88.0, peak_low=83.0, peak_high=89.0)
    assert is_zhongshu_expansion(a, b) is False


def test_identify_expanded_zhongshus_merges_disjoint_zones_with_overlapping_peaks() -> None:
    zs = [
        _zhongshu_with_peaks(0, zone_low=89.0, zone_high=91.35, peak_low=88.7, peak_high=94.5),
        _zhongshu_with_peaks(1, zone_low=92.05, zone_high=92.2, peak_low=85.7, peak_high=96.45),
    ]
    result = identify_expanded_zhongshus(zs)
    assert len(result) == 1
    exp = result[0]
    assert exp.sub_zs_ids == [0, 1]
    assert exp.expanded_low == 88.7
    assert exp.expanded_high == 94.5
    assert exp.peak_low == 85.7
    assert exp.peak_high == 96.45
    assert exp.recognition_mode == "peak_overlap_expansion"


def test_identify_expanded_zhongshus_skips_trend() -> None:
    zs = [
        _zhongshu_with_peaks(0, zone_low=80.0, zone_high=82.0, peak_low=79.0, peak_high=83.0),
        _zhongshu_with_peaks(1, zone_low=90.0, zone_high=92.0, peak_low=89.0, peak_high=93.0),
    ]
    assert identify_expanded_zhongshus(zs) == []


def test_identify_expanded_zhongshus_skips_overlapping_zones() -> None:
    zs = [
        _zhongshu_with_peaks(0, zone_low=80.0, zone_high=85.0, peak_low=79.0, peak_high=86.0),
        _zhongshu_with_peaks(1, zone_low=84.0, zone_high=88.0, peak_low=83.0, peak_high=89.0),
    ]
    assert identify_expanded_zhongshus(zs) == []


def test_relation_kind_zone_disjoint_stays_trend_despite_peak_overlap() -> None:
    # 同级别分解不处理扩张：区间不重叠即趋势，即使波动（GG/DD）回探重叠也判 up
    prev = _zhongshu_with_peaks(0, zone_low=89.0, zone_high=91.35, peak_low=88.7, peak_high=94.5)
    curr = _zhongshu_with_peaks(1, zone_low=92.05, zone_high=92.2, peak_low=85.7, peak_high=96.45)
    assert _relation_kind(prev, curr) == "up"


def test_relation_kind_zone_disjoint_directions() -> None:
    prev = _zhongshu_with_peaks(0, zone_low=80.0, zone_high=82.0, peak_low=79.0, peak_high=83.0)
    curr_up = _zhongshu_with_peaks(1, zone_low=90.0, zone_high=92.0, peak_low=89.0, peak_high=93.0)
    assert _relation_kind(prev, curr_up) == "up"
    curr_down = _zhongshu_with_peaks(1, zone_low=70.0, zone_high=72.0, peak_low=69.0, peak_high=73.0)
    assert _relation_kind(prev, curr_down) == "down"


def _load_segments_from_normalized_csv(path: Path) -> list[Segment]:
    segments = []
    with open(path, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            segments.append(
                Segment(
                    segment_id=int(r["segment_id"]),
                    direction=BiDirection(r["direction"]),
                    start_bi_id=int(r["start_bi_id"]),
                    end_bi_id=int(r["end_bi_id"]),
                    start_ts=datetime.fromisoformat(r["start_ts"]),
                    end_ts=datetime.fromisoformat(r["end_ts"]),
                    start_price=float(r["start_price"]),
                    end_price=float(r["end_price"]),
                    high=float(r["high"]),
                    low=float(r["low"]),
                    norm_bar_range=(int(r["start_norm_idx"]), int(r["end_norm_idx"])),
                    bi_ids=[int(x) for x in r["bi_ids"].split(",")],
                    is_confirmed=r["is_confirmed"] == "True",
                    stop_reason=r["stop_reason"],
                )
            )
    return segments


def test_03690_5m_same_level_decomp_down_trend_and_expansion_detected_separately() -> None:
    """第20课真实锚点：ZS0/ZS1 区间不重叠但波动回探，ZS1/ZS2 构成下跌趋势。

    同级别分解不处理扩张 → ZS0/ZS1 按区间不重叠判 up，扩张由独立的「按中枢」层
    identify_expanded_zhongshus 单独检出，不改变同级别分解的类型；s6 为 ZS0 的
    走出段（第三类买点），ZS1=(s7,s8,s9)=[92.05,93.95] 复用 s6 为进入段，随后
    s11 反向跌破 ZD 触发趋势反转，ZS2=(s12,s13,s14)=[85.7,88.2] 成型，最终走势
    类型为「ZS0 盘整 + ZS1/ZS2 下跌趋势」。
    """
    path = (
        Path(__file__).resolve().parents[1]
        / "data" / "reports" / "03690" / "5m" / "analyze"
        / "03690_5m_20260722_to_20260828_normalized_segments.csv"
    )
    segments = _load_segments_from_normalized_csv(path)

    zhongshus = identify_zhongshu(segments, structure_level="segment")
    expanded = identify_expanded_zhongshus(zhongshus)
    state = build_structure_state([], zhongshus)

    assert [(z.zs_id, z.zs_low, z.zs_high) for z in zhongshus] == [
        (0, 89.0, 91.35),
        (1, 92.05, 93.95),
        (2, 85.7, 88.2),
    ]
    assert len(expanded) == 1
    assert expanded[0].sub_zs_ids == [0, 1]
    assert expanded[0].expanded_low == 89.8
    assert expanded[0].expanded_high == 94.5
    assert state["current_ongoing"]["type"] == "down"


class TestIdentifyZhongshu:
    def test_empty_bis(self):
        assert identify_zhongshu([]) == []

    def test_insufficient_bis(self):
        bis = [
            _bi(0, BiDirection.DOWN, 110, 100),
            _bi(1, BiDirection.UP, 108, 101),
            _bi(2, BiDirection.DOWN, 107, 102),
            _bi(3, BiDirection.UP, 106, 103),
        ]
        assert identify_zhongshu(bis) == []

    def test_require_enter_exit_same_direction(self):
        bis = [
            _bi(0, BiDirection.DOWN, 110, 98),   # entering
            _bi(1, BiDirection.UP, 106, 100),
            _bi(2, BiDirection.DOWN, 104, 101),
            _bi(3, BiDirection.UP, 103, 102),
            _bi(4, BiDirection.DOWN, 102, 96),   # exit
        ]

        result = identify_zhongshu(bis)

        assert len(result) == 1
        assert result[0].start_bi_id == 1
        assert result[0].end_bi_id == 3
        assert result[0].entering_bi_id == 0
        assert result[0].core_bi_ids == [1, 2, 3]
        assert result[0].render_start_bi_id == 1
        assert result[0].render_end_bi_id == 3
        assert result[0].exit_bi_id == 4
        assert result[0].structure_level == "bi"
        assert result[0].bi_ids == [1, 2, 3]
        assert result[0].zs_low == 102
        assert result[0].zs_high == 103
        assert result[0].is_terminated is True

    def test_entering_bi_must_overlap_body_zone(self):
        bis = [
            _bi(0, BiDirection.UP, 120, 115),    # does not overlap [102,103]
            _bi(1, BiDirection.DOWN, 106, 100),
            _bi(2, BiDirection.UP, 104, 101),
            _bi(3, BiDirection.DOWN, 103, 102),
            _bi(4, BiDirection.UP, 112, 101),
        ]

        result = identify_zhongshu(bis)

        # i=0 以 bi0 为进入段、与本体区间 [102,103] 无交集 → 不成立；
        # i=1 以 bi1 为进入段（与本体重叠）成立，故结果只含进入段为 bi1 的中枢。
        assert len(result) == 1
        assert result[0].entering_bi_id == 1
        assert result[0].start_bi_id == 2
        assert result[0].end_bi_id == 4
        assert result[0].zs_low == 102
        assert result[0].zs_high == 103
        assert result[0].exit_bi_id is None
        assert result[0].is_terminated is False

    def test_fixed_zone_does_not_recompute_on_extension(self):
        bis = [
            _bi(0, BiDirection.DOWN, 110, 98),
            _bi(1, BiDirection.UP, 106, 100),
            _bi(2, BiDirection.DOWN, 104, 101),
            _bi(3, BiDirection.UP, 103, 102),
            _bi(4, BiDirection.DOWN, 103.2, 101.5),   # 与区间重叠，并回本体延伸
            _bi(5, BiDirection.UP, 103.5, 101.8),     # 继续延伸
            _bi(6, BiDirection.DOWN, 101.9, 96),      # 真正跌破 ZD，才是离开笔
        ]

        result = identify_zhongshu(bis)

        assert len(result) == 1
        zs = result[0]
        assert zs.zs_low == 102
        assert zs.zs_high == 103
        assert zs.bi_ids == [1, 2, 3, 4, 5]
        assert zs.core_bi_ids == [1, 2, 3]
        assert zs.render_end_bi_id == 5
        assert zs.exit_bi_id == 6
        assert zs.superseded_by_zs_id is None
        assert zs.is_reabsorbed_by_larger_expansion is False

    def test_next_center_reuses_previous_exit_as_entering(self):
        bis = [
            _bi(0, BiDirection.DOWN, 110, 98),
            _bi(1, BiDirection.UP, 106, 100),
            _bi(2, BiDirection.DOWN, 104, 101),
            _bi(3, BiDirection.UP, 103, 102),
            _bi(4, BiDirection.DOWN, 102, 96),   # first exit / second entering
            _bi(5, BiDirection.UP, 99, 97),
            _bi(6, BiDirection.DOWN, 99, 97),
            _bi(7, BiDirection.UP, 101, 97),
            _bi(8, BiDirection.DOWN, 98, 95),    # second exit
        ]

        result = identify_zhongshu(bis)

        assert len(result) == 2
        assert result[0].bi_ids == [1, 2, 3]
        assert result[1].bi_ids == [5, 6, 7, 8]
        assert result[0].exit_bi_id == 4
        assert result[1].entering_bi_id == 4
        assert result[1].render_end_bi_id == 8

    def test_identify_segment_zhongshu(self):
        segments = [
            _segment(0, BiDirection.DOWN, 110, 98),
            _segment(1, BiDirection.UP, 106, 100),
            _segment(2, BiDirection.DOWN, 104, 101),
            _segment(3, BiDirection.UP, 103, 102),
            _segment(4, BiDirection.DOWN, 102, 96),
        ]

        result = identify_zhongshu(segments, structure_level="segment")

        assert len(result) == 1
        zs = result[0]
        assert zs.structure_level == "segment"
        assert zs.entering_bi_id == 0
        assert zs.core_bi_ids == [1, 2, 3]
        assert zs.bi_ids == [1, 2, 3]
        assert zs.exit_bi_id == 4
        assert zs.zs_low == 102
        assert zs.zs_high == 103
        assert zs.is_terminated is True
        assert zs.render_start_bi_id == 1
        assert zs.render_end_bi_id == 3

    def test_segment_zhongshu_entering_segment_must_overlap_body_zone(self):
        segments = [
            _segment(0, BiDirection.UP, 120, 115),    # does not overlap [102,103]
            _segment(1, BiDirection.DOWN, 106, 100),
            _segment(2, BiDirection.UP, 104, 101),
            _segment(3, BiDirection.DOWN, 103, 102),
            _segment(4, BiDirection.UP, 112, 101),
        ]

        result = identify_zhongshu(segments, structure_level="segment")

        # i=0 以 segment0 为进入段、与本体区间 [102,103] 无交集 → 不成立；
        # i=1 以 segment1 为进入段（与本体重叠）成立。
        assert len(result) == 1
        assert result[0].entering_bi_id == 1
        assert result[0].start_bi_id == 2
        assert result[0].end_bi_id == 4
        assert result[0].zs_low == 102
        assert result[0].zs_high == 103
        assert result[0].exit_bi_id is None
        assert result[0].is_terminated is False

    def test_segment_zhongshu_exit_failure_merges_back_into_body(self):
        segments = [
            _segment(0, BiDirection.DOWN, 110, 98),
            _segment(1, BiDirection.UP, 106, 100),
            _segment(2, BiDirection.DOWN, 104, 101),
            _segment(3, BiDirection.UP, 103, 102),
            _segment(4, BiDirection.DOWN, 103.2, 101.5),   # 离开失败，并回本体延伸
            _segment(5, BiDirection.UP, 103.5, 101.8),     # 继续延伸
            _segment(6, BiDirection.DOWN, 101.9, 95),      # 真正跌破 ZD，才是离开段
        ]

        result = identify_zhongshu(segments, structure_level="segment")

        assert len(result) == 1
        zs = result[0]
        assert zs.zs_low == 102
        assert zs.zs_high == 103
        assert zs.core_bi_ids == [1, 2, 3]
        assert zs.bi_ids == [1, 2, 3, 4, 5]
        assert zs.render_end_bi_id == 5
        assert zs.exit_bi_id == 6
        assert zs.is_terminated is True
        assert zs.superseded_by_zs_id is None
        assert zs.is_reabsorbed_by_larger_expansion is False

    def test_segment_zhongshu_next_center_reuses_previous_exit_as_entering(self):
        segments = [
            _segment(0, BiDirection.DOWN, 110, 98),
            _segment(1, BiDirection.UP, 106, 100),
            _segment(2, BiDirection.DOWN, 104, 101),
            _segment(3, BiDirection.UP, 103, 102),
            _segment(4, BiDirection.DOWN, 102, 96),   # 第一个中枢离开段 / 第二个中枢进入段
            _segment(5, BiDirection.UP, 99, 97),
            _segment(6, BiDirection.DOWN, 99, 97),
            _segment(7, BiDirection.UP, 101, 97),
            _segment(8, BiDirection.DOWN, 98, 95),
        ]

        result = identify_zhongshu(segments, structure_level="segment")

        assert len(result) == 2
        assert result[0].bi_ids == [1, 2, 3]
        assert result[0].exit_bi_id == 4
        assert result[0].is_terminated is True
        assert result[1].entering_bi_id == 4
        assert result[1].bi_ids == [5, 6, 7, 8]
        assert result[1].render_end_bi_id == 8
        assert result[1].exit_bi_id is None
        assert result[1].is_terminated is False

    def test_identify_segment_zhongshu_ignores_unconfirmed_tail_segment(self):
        segments = [
            _segment(0, BiDirection.DOWN, 110, 98),
            _segment(1, BiDirection.UP, 106, 100),
            _segment(2, BiDirection.DOWN, 104, 101),
            _segment(3, BiDirection.UP, 103, 102),
            _segment(4, BiDirection.DOWN, 102, 96, is_confirmed=False),
        ]

        result = identify_zhongshu(segments, structure_level="segment")

        assert len(result) == 0

    def test_identify_segment_zhongshu_keeps_historical_pending_segments_before_confirmed_follow_on(self):
        segments = [
            _segment(0, BiDirection.DOWN, 110, 98, is_confirmed=True),
            _segment(1, BiDirection.UP, 106, 100, is_confirmed=True),
            _segment(2, BiDirection.DOWN, 104, 101, is_confirmed=False),
            _segment(3, BiDirection.UP, 103, 102, is_confirmed=True),
            _segment(4, BiDirection.DOWN, 102, 96, is_confirmed=True),
        ]

        result = identify_zhongshu(segments, structure_level="segment")

        assert len(result) == 1
        assert result[0].structure_level == "segment"
        assert result[0].entering_bi_id == 0
        assert result[0].core_bi_ids == [1, 2, 3]
        assert result[0].bi_ids == [1, 2, 3]
        assert result[0].exit_bi_id == 4

    def test_identify_segment_zhongshu_trims_only_unconfirmed_tail_and_still_forms(self):
        segments = [
            _segment(0, BiDirection.DOWN, 110, 98),
            _segment(1, BiDirection.UP, 106, 100),
            _segment(2, BiDirection.DOWN, 104, 101),
            _segment(3, BiDirection.UP, 103, 102),
            _segment(4, BiDirection.DOWN, 102, 96),
            _segment(5, BiDirection.UP, 103.5, 101.8, is_confirmed=False),
        ]

        result = identify_zhongshu(segments, structure_level="segment")

        assert len(result) == 1
        zs = result[0]
        assert zs.entering_bi_id == 0
        assert zs.core_bi_ids == [1, 2, 3]
        assert zs.bi_ids == [1, 2, 3]
        assert zs.exit_bi_id == 4
        assert zs.is_terminated is True

    def test_identify_segment_zhongshu_ignores_transition_pending_tail_from_segment_pipeline(self):
        bis = [
            _bi(0, BiDirection.UP, 100, 90),
            _bi(1, BiDirection.DOWN, 95, 85),
            _bi(2, BiDirection.UP, 105, 95),
            _bi(3, BiDirection.DOWN, 94, 80),
            _bi(4, BiDirection.UP, 96, 87),
        ]

        segments = identify_segments(bis)
        result = identify_zhongshu(segments, structure_level="segment")

        assert len(segments) == 1
        assert segments[0].is_confirmed is False
        assert segments[0].stop_reason == "transition_pending"
        assert result == []

    def test_identify_segment_zhongshu_recomputes_to_empty_after_same_direction_reclaim(self):
        bis = [
            _bi(0, BiDirection.UP, 110, 100),
            _bi(1, BiDirection.DOWN, 108, 103),
            _bi(2, BiDirection.UP, 115, 104),
            _bi(3, BiDirection.DOWN, 114, 105),
            _bi(4, BiDirection.UP, 113, 106),
            _bi(5, BiDirection.DOWN, 112, 106.5),
            _bi(6, BiDirection.UP, 116, 107),
        ]

        segments = identify_segments(bis)
        result = identify_zhongshu(segments, structure_level="segment")

        assert len(segments) == 1
        assert segments[0].direction == BiDirection.UP
        assert segments[0].bi_ids == [0, 1, 2, 3, 4, 5, 6]
        assert segments[0].is_confirmed is False
        assert segments[0].stop_reason == "exhausted_confirmed_bis"
        assert result == []

    def test_identify_segment_zhongshu_recomputes_to_empty_after_reverse_break_reclaim(self):
        bis = [
            _bi(0, BiDirection.UP, 110, 100),
            _bi(1, BiDirection.DOWN, 108, 103),
            _bi(2, BiDirection.UP, 115, 104),
            _bi(3, BiDirection.DOWN, 114, 102),
            _bi(4, BiDirection.UP, 113, 103),
            _bi(5, BiDirection.DOWN, 112, 103.5),
            _bi(6, BiDirection.UP, 116, 104),
        ]

        segments = identify_segments(bis)
        result = identify_zhongshu(segments, structure_level="segment")

        assert len(segments) == 1
        assert segments[0].direction == BiDirection.UP
        assert segments[0].bi_ids == [0, 1, 2, 3, 4, 5, 6]
        assert segments[0].is_confirmed is False
        assert segments[0].stop_reason == "exhausted_confirmed_bis"
        assert result == []

    def test_overlapping_followup_center_marks_previous_as_reabsorbed(self):
        bis = [
            _bi(0, BiDirection.DOWN, 110, 98),
            _bi(1, BiDirection.UP, 106, 100),
            _bi(2, BiDirection.DOWN, 104, 101),
            _bi(3, BiDirection.UP, 103, 102),
            _bi(4, BiDirection.DOWN, 102, 96),
            _bi(5, BiDirection.UP, 102.5, 101.5),
            _bi(6, BiDirection.DOWN, 102.3, 101.8),
            _bi(7, BiDirection.UP, 102.8, 101.7),
            _bi(8, BiDirection.DOWN, 102.1, 95.0),
        ]

        result = identify_zhongshu(bis)

        assert len(result) == 2
        assert result[0].exit_bi_id == 4
        assert result[1].entering_bi_id == 4
        assert result[0].is_reabsorbed_by_larger_expansion is True
        assert result[0].superseded_by_zs_id == result[1].zs_id
        assert result[1].is_reabsorbed_by_larger_expansion is False

    def test_reabsorbed_lineage_can_collapse_to_later_overlapping_successor(self):
        first = _zhongshu(1, low=102.0, high=103.0, entering_bi_id=0, exit_bi_id=4, terminated=True)
        second = _zhongshu(2, low=101.7, high=102.4, entering_bi_id=4, exit_bi_id=8, terminated=True)
        third = _zhongshu(3, low=101.9, high=102.2, entering_bi_id=8, exit_bi_id=None, terminated=False)

        _mark_reabsorbed_lineage([first, second, third])

        assert first.is_reabsorbed_by_larger_expansion is True
        assert second.is_reabsorbed_by_larger_expansion is True
        assert second.superseded_by_zs_id == third.zs_id
        assert first.superseded_by_zs_id == third.zs_id

    def test_overlapping_followup_segment_center_marks_previous_as_reabsorbed(self):
        segments = [
            _segment(0, BiDirection.DOWN, 110, 98),
            _segment(1, BiDirection.UP, 106, 100),
            _segment(2, BiDirection.DOWN, 104, 101),
            _segment(3, BiDirection.UP, 103, 102),
            _segment(4, BiDirection.DOWN, 102, 96),
            _segment(5, BiDirection.UP, 102.5, 101.5),
            _segment(6, BiDirection.DOWN, 102.3, 101.8),
            _segment(7, BiDirection.UP, 102.8, 101.7),
            _segment(8, BiDirection.DOWN, 102.1, 95.0),
        ]

        result = identify_zhongshu(segments, structure_level="segment")

        assert len(result) == 2
        assert result[0].structure_level == "segment"
        assert result[1].structure_level == "segment"
        assert result[0].exit_bi_id == 4
        assert result[1].entering_bi_id == 4
        assert result[0].is_reabsorbed_by_larger_expansion is True
        assert result[0].superseded_by_zs_id == result[1].zs_id

    def test_reabsorbed_lineage_does_not_collapse_across_non_overlapping_final_successor(self):
        first = _zhongshu(1, low=102.0, high=103.0, entering_bi_id=0, exit_bi_id=4, terminated=True, structure_level="segment")
        second = _zhongshu(2, low=101.7, high=102.4, entering_bi_id=4, exit_bi_id=8, terminated=True, structure_level="segment")
        third = _zhongshu(3, low=98.8, high=99.5, entering_bi_id=8, exit_bi_id=None, terminated=False, structure_level="segment")

        _mark_reabsorbed_lineage([first, second, third])

        assert second.is_reabsorbed_by_larger_expansion is False
        assert second.superseded_by_zs_id is None
        assert first.is_reabsorbed_by_larger_expansion is True
        assert first.superseded_by_zs_id == second.zs_id
