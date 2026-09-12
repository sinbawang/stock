from pathlib import Path

import pytest

from chanlun.analysis import build_structure_state
from chanlun.bi import identify_bis
from chanlun.data import read_bars_from_csv
from chanlun.data.cleaner import clean_bars
from chanlun.fractal import filter_consecutive_fractals, identify_fractals
from chanlun.normalize import normalize_bars
from chanlun.segment import SEGMENT_BOOTSTRAP_FIRST_VALID_SEED, identify_segments
from chanlun.zhongshu import identify_zhongshu
from tests.real_fixture_support import frozen_csv
from tests.segment_regression_support import identify_segments_from_csv


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_00700_30M_CSV = frozen_csv("00700", "30m")
SAMPLE_03690_30M_CSV = frozen_csv("03690", "30m")

# 首选级别（1m / 5m）多中枢真实窗口：作为 T3 "多中枢不残留旧中枢幽灵 / 不相交不误标 reabsorbed" 的正面真实窗口 gate。
SAMPLE_600900_1M_CSV = frozen_csv("600900", "1m")
SAMPLE_09988_1M_CSV = frozen_csv("09988", "1m")
SAMPLE_03690_5M_CSV = frozen_csv("03690", "5m")
SAMPLE_00700_1M_CSV = frozen_csv("00700", "1m")


def _build_structure_state_from_csv_cutoff(path: Path, cutoff_iso: str):
    bars = clean_bars(read_bars_from_csv(str(path)))
    cutoff_bars = [bar for bar in bars if bar.ts.isoformat(timespec="seconds") <= cutoff_iso]
    normalized_bars = normalize_bars(cutoff_bars)
    fractals = filter_consecutive_fractals(identify_fractals(normalized_bars))
    bis = identify_bis(fractals, normalized_bars, pending_reverse_mode="effective_only")
    segments = identify_segments(
        bis,
        bootstrap_mode=SEGMENT_BOOTSTRAP_FIRST_VALID_SEED,
        termination_mode="practical",
    )
    zhongshus = identify_zhongshu(segments, structure_level="segment")
    return cutoff_bars, segments, zhongshus, build_structure_state(cutoff_bars, zhongshus)


def test_00700_30m_segment_zhongshu_keeps_single_active_center_after_data_refresh() -> None:
    """00700 30m（冻结快照 00700_30m_20260402_to_20260911）：当前持有一个未终结 segment 级标准中枢（盘整 single_active）。"""
    segments = identify_segments_from_csv(SAMPLE_00700_30M_CSV)

    zhongshus = identify_zhongshu(segments, structure_level="segment")
    structure_state = build_structure_state([], zhongshus)

    assert len(zhongshus) == 1
    current = zhongshus[0]
    assert current.structure_level == "segment"
    assert current.entering_bi_id == 2
    assert current.start_bi_id == 3
    assert current.end_bi_id == 14
    assert current.exit_bi_id is None
    assert round(current.zs_low, 6) == 443.2
    assert round(current.zs_high, 6) == 479.0
    assert current.is_terminated is False
    assert current.superseded_by_zs_id is None
    assert current.is_reabsorbed_by_larger_expansion is False
    assert structure_state["last_completed"] is None
    assert structure_state["current_ongoing"]["type"] == "range"
    assert structure_state["current_ongoing"]["confirmation_basis"] == "single_active_zhongshu"
    assert structure_state["relationship"]["transition_state"] == "none"
    assert structure_state["consumption_level"] == "pending"


def test_03690_30m_segment_zhongshu_keeps_single_active_center_after_gap_restart() -> None:
    """03690 30m（新窗口 2026-08-28）：gap-restart 后窗口当前持有一个未终结 segment 级标准中枢。

    旧窗口曾断言「无 segment 级幽灵中枢」（zhongshus==[]）；数据刷新后该窗口
    现有一个真实活动中枢，改锁 single_active_zhongshu。无幽灵覆盖由
    000591 60m-long / 300124 60m 两个窗口继续承担。
    """
    segments = identify_segments_from_csv(SAMPLE_03690_30M_CSV)

    zhongshus = identify_zhongshu(segments, structure_level="segment")
    structure_state = build_structure_state([], zhongshus)

    assert len(zhongshus) == 1
    current = zhongshus[0]
    assert current.structure_level == "segment"
    assert current.entering_bi_id == 0
    assert current.start_bi_id == 1
    assert current.end_bi_id == 9
    assert current.exit_bi_id is None
    assert round(current.zs_low, 6) == 83.75
    assert round(current.zs_high, 6) == 86.8
    assert current.is_terminated is False
    assert current.superseded_by_zs_id is None
    assert current.is_reabsorbed_by_larger_expansion is False
    assert structure_state["last_completed"] is None
    assert structure_state["current_ongoing"]["confirmation_basis"] == "single_active_zhongshu"
    assert structure_state["relationship"]["transition_state"] == "none"
    assert structure_state["consumption_level"] == "pending"


def _assert_centers_no_reabsorbed(zhongshus, expected):
    """锁定 segment 级标准中枢的精确身份 + 区间，并断言不残留 reabsorbed/superseded 幽灵。"""
    assert len(zhongshus) == len(expected)
    for zs, (enter, start, end, low, high, exit_bi) in zip(zhongshus, expected):
        assert zs.structure_level == "segment"
        assert zs.entering_bi_id == enter
        assert zs.start_bi_id == start
        assert zs.end_bi_id == end
        assert zs.exit_bi_id == exit_bi
        assert round(zs.zs_low, 6) == low
        assert round(zs.zs_high, 6) == high
        assert zs.is_terminated is (exit_bi is not None)
        # T3 关键断言：真实多中枢窗口不允许旧中枢幽灵 / 误标 reabsorbed。
        assert zs.superseded_by_zs_id is None
        assert zs.is_reabsorbed_by_larger_expansion is False


def test_600900_1m_segment_zhongshu_keeps_multiple_centers_without_false_reabsorption() -> None:
    """600900 1m（首选级别）：数据刷新后该窗口为多个标准中枢，不得误标 reabsorbed。"""
    segments = identify_segments_from_csv(SAMPLE_600900_1M_CSV)

    zhongshus = identify_zhongshu(segments, structure_level="segment")

    _assert_centers_no_reabsorbed(
        zhongshus,
        [
            (0, 1, 3, 28.2, 28.35, 4),
            (4, 5, 8, 28.01, 28.13, None),
            (11, 12, 14, 28.65, 28.82, None),
            (16, 17, 20, 27.78, 27.88, None),
        ],
    )


def test_09988_1m_segment_zhongshu_keeps_disjoint_centers_without_false_reabsorption() -> None:
    """09988 1m（首选级别，冻结快照 09988_1m_20260828_to_20260911）：两个区间不相交的标准中枢，不得误标 reabsorbed。"""
    segments = identify_segments_from_csv(SAMPLE_09988_1M_CSV)

    zhongshus = identify_zhongshu(segments, structure_level="segment")

    _assert_centers_no_reabsorbed(
        zhongshus,
        [
            (0, 1, 3, 113.5, 115.0, 4),
            (4, 5, 13, 109.5, 110.1, 14),
        ],
    )


def test_09988_1m_structure_state_keeps_real_down_type_chain() -> None:
    """09988 1m（首选级别，冻结快照 09988_1m_20260828_to_20260911）：稳定给出 down ongoing(2) 类型链。

    当前窗口不含已完成前段（`last_completed is None`），但 down 走势已由 2 个中枢确认
    （`forming_next_same_level_zhongshu`），消费等级 `confirmed`。
    """
    segments = identify_segments_from_csv(SAMPLE_09988_1M_CSV)

    zhongshus = identify_zhongshu(segments, structure_level="segment")
    structure_state = build_structure_state([], zhongshus)

    assert structure_state["last_completed"] is None
    assert structure_state["current_ongoing"]["type"] == "down"
    assert structure_state["current_ongoing"]["zs_count_so_far"] == 2
    assert structure_state["current_ongoing"]["confirmation_basis"] == "forming_next_same_level_zhongshu"
    assert structure_state["consumption_level"] == "confirmed"
    assert structure_state["type_chain"] == [
        {
            "type": "down",
            "status": "ongoing",
            "zs_count": 2,
            "start_zs_id": 0,
            "end_zs_id": 1,
            "start_ts": "2026-08-28T14:12:00",
            "end_ts": None,
        },
    ]



def test_03690_5m_segment_zhongshu_keeps_disjoint_centers_without_false_reabsorption() -> None:
    """03690 5m（首选级别）：三个区间不相交的标准中枢，不得误标 reabsorbed。

    s6 同向突破 ZG 且下一段 s7 不回中枢 → 为 ZS0 的走出段（第三类买点）；
    ZS1 复用 s6 为进入段，区间 [92.05, 93.95]，随后 s11 反向跌破 ZD 触发趋势
    反转（无走出段）。effective_only 后 s12/s13/s14 形成 ZS2=[85.7, 88.75]。
    """
    segments = identify_segments_from_csv(SAMPLE_03690_5M_CSV)

    zhongshus = identify_zhongshu(segments, structure_level="segment")

    _assert_centers_no_reabsorbed(
        zhongshus,
        [
            (0, 1, 6, 92.05, 93.95, None),
            (7, 8, 10, 85.7, 88.75, 11),
            (13, 14, 17, 76.9, 79.5, None),
        ],
    )


def test_03690_5m_structure_state_keeps_real_completed_then_new_type_chain() -> None:
    """03690 5m（首选级别，冻结快照 03690_5m_20260731_to_20260911）：down completed -> range ongoing。"""
    segments = identify_segments_from_csv(SAMPLE_03690_5M_CSV)

    zhongshus = identify_zhongshu(segments, structure_level="segment")
    structure_state = build_structure_state([], zhongshus)

    assert structure_state["last_completed"] == {
        "type": "down",
        "status": "completed",
        "start_ts": "2026-08-03T11:30:00",
        "end_ts": "2026-08-20T09:50:00",
        "latest_ts": "2026-08-20T09:50:00",
        "zs_count": 2,
        "zs_count_so_far": 2,
        "confirmation_basis": "confirmed_by_following_same_level_structure",
        "start_zs_id": 0,
        "end_zs_id": 1,
    }
    assert structure_state["current_ongoing"]["type"] == "range"
    assert structure_state["current_ongoing"]["zs_count_so_far"] == 1
    assert structure_state["current_ongoing"]["confirmation_basis"] == "single_active_zhongshu"
    assert structure_state["relationship"]["kind"] == "completed_then_new_type_ongoing"
    assert structure_state["relationship"]["transition_state"] == "candidate_new_type"
    assert structure_state["consumption_level"] == "pending"
    assert structure_state["type_chain"] == [
        {
            "type": "down",
            "status": "completed",
            "zs_count": 2,
            "start_zs_id": 0,
            "end_zs_id": 1,
            "start_ts": "2026-08-03T11:30:00",
            "end_ts": "2026-08-20T09:50:00",
        },
        {
            "type": "range",
            "status": "ongoing",
            "zs_count": 1,
            "start_zs_id": 2,
            "end_zs_id": 2,
            "start_ts": "2026-08-28T09:50:00",
            "end_ts": None,
        },
    ]


def test_00700_1m_segment_zhongshu_keeps_single_center_after_data_refresh() -> None:
    """00700 1m（首选级别，冻结快照 00700_1m_20260828_to_20260911）：一个已终结 segment 级中枢，不得误标 reabsorbed。"""
    segments = identify_segments_from_csv(SAMPLE_00700_1M_CSV)

    zhongshus = identify_zhongshu(segments, structure_level="segment")

    _assert_centers_no_reabsorbed(
        zhongshus,
        [
            (0, 1, 9, 441.4, 444.4, 10),
        ],
    )


def _segment_landmarks(segments):
    return [
        (segment.direction.value, segment.start_bi_id, segment.end_bi_id, segment.break_bi_id, segment.stop_reason)
        for segment in segments
    ]


def _zhongshu_snapshot(zs):
    return (
        zs.zs_id,
        zs.start_bi_id,
        zs.end_bi_id,
        round(zs.zs_low, 6),
        round(zs.zs_high, 6),
        zs.is_terminated,
        zs.entering_bi_id,
        zs.exit_bi_id,
        zs.structure_level,
        zs.superseded_by_zs_id,
        zs.is_reabsorbed_by_larger_expansion,
    )


REAL_REBUILD_WINDOWS = [
    SAMPLE_00700_30M_CSV,
    SAMPLE_03690_30M_CSV,
    SAMPLE_600900_1M_CSV,
    SAMPLE_09988_1M_CSV,
    SAMPLE_03690_5M_CSV,
    SAMPLE_00700_1M_CSV,
]


@pytest.mark.parametrize("sample_csv", REAL_REBUILD_WINDOWS)
def test_repeated_rebuild_produces_identical_segments_zhongshus_and_structure_state(sample_csv) -> None:
    """同一真实窗口重复重算，segments / zhongshus / structure_state 必须逐次一致。

    这是 ZS3.3 “把 repeated rebuild / publish 纳入最小回归集”的确定性 gate，
    避免只在单次本地运行正确。
    """
    runs = []
    for _ in range(3):
        segments = identify_segments_from_csv(sample_csv)
        zhongshus = identify_zhongshu(segments, structure_level="segment")
        structure_state = build_structure_state([], zhongshus)
        runs.append(
            (
                _segment_landmarks(segments),
                [_zhongshu_snapshot(zs) for zs in zhongshus],
                structure_state,
            )
        )

    first = runs[0]
    for index, run in enumerate(runs[1:], start=1):
        assert run == first, f"repeated rebuild run {index} drifted for {sample_csv.name}"


def _first_zhongshu_identity(zs):
    return (
        zs.entering_bi_id,
        zs.start_bi_id,
        zs.end_bi_id,
        zs.zs_low,
        zs.zs_high,
        zs.exit_bi_id,
        zs.is_terminated,
    )


def test_first_standard_zhongshu_identity_is_stable_across_rebuilds() -> None:
    """首个标准中枢的进入段 / 本体区间 / 离开段边界必须跨重算稳定。

    这是 ZS1.3 “首个中枢成立位置不漂移”的 review 锚点：锁住 00700 30m
    首个 segment 级标准中枢的进入段、本体区间与已终结状态。
    """
    identities = []
    for _ in range(3):
        segments = identify_segments_from_csv(SAMPLE_00700_30M_CSV)
        zhongshus = identify_zhongshu(segments, structure_level="segment")
        assert zhongshus, "00700 30m 必须至少有一个标准中枢"
        identities.append(_first_zhongshu_identity(zhongshus[0]))

    assert identities == [
        (2, 3, 14, 443.2, 479.0, None, False),
        (2, 3, 14, 443.2, 479.0, None, False),
        (2, 3, 14, 443.2, 479.0, None, False),
    ]