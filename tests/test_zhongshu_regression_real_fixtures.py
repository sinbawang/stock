from pathlib import Path

import pytest

from chanlun.analysis import build_structure_state
from chanlun.zhongshu import identify_zhongshu
from tests.segment_regression_support import identify_segments_from_csv


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_00700_30M_CSV = ROOT / "data" / "reports" / "00700" / "30m" / "analyze" / "00700_30m_20260527_to_20260814.csv"
SAMPLE_03690_30M_CSV = ROOT / "data" / "reports" / "03690" / "30m" / "analyze" / "03690_30m_20260527_to_20260814.csv"
SAMPLE_000591_60M_LONG_CSV = ROOT / "data" / "reports" / "000591" / "60m" / "analyze" / "000591_60m_20251210_to_20260618.csv"
SAMPLE_300124_60M_CSV = ROOT / "data" / "reports" / "300124" / "60m" / "analyze" / "300124_60m_20260213_to_20260618.csv"


def test_00700_30m_segment_zhongshu_keeps_single_active_center_after_multiple_rewrites() -> None:
    segments = identify_segments_from_csv(SAMPLE_00700_30M_CSV)

    zhongshus = identify_zhongshu(segments, structure_level="segment")
    structure_state = build_structure_state([], zhongshus)

    assert len(zhongshus) == 1
    current = zhongshus[0]
    assert current.structure_level == "segment"
    assert current.entering_bi_id == 0
    assert current.start_bi_id == 1
    assert current.end_bi_id == 4
    assert current.exit_bi_id is None
    assert current.zs_low == 432.0
    assert current.zs_high == 486.2
    assert current.is_terminated is False
    assert current.superseded_by_zs_id is None
    assert current.is_reabsorbed_by_larger_expansion is False
    assert structure_state["last_completed"] is None
    assert structure_state["current_ongoing"]["start_zs_id"] == current.zs_id
    assert structure_state["current_ongoing"]["end_zs_id"] == current.zs_id
    assert structure_state["current_ongoing"]["confirmation_basis"] == "single_active_zhongshu"
    assert structure_state["relationship"]["transition_state"] == "none"
    assert structure_state["consumption_level"] == "pending"


def test_03690_30m_gap_restart_chain_does_not_leave_segment_level_ghost_center() -> None:
    segments = identify_segments_from_csv(SAMPLE_03690_30M_CSV)

    zhongshus = identify_zhongshu(segments, structure_level="segment")
    structure_state = build_structure_state([], zhongshus)

    landmarks = [
        (segment.direction.value, segment.start_bi_id, segment.end_bi_id, segment.break_bi_id, segment.stop_reason)
        for segment in segments
    ]

    assert landmarks[:5] == [
        ("down", 2, 4, 5, "feature_sequence_fractal"),
        ("up", 5, 7, 8, "reverse_break"),
        ("down", 8, 12, 13, "feature_sequence_fractal"),
        ("up", 13, 31, 32, "feature_sequence_fractal"),
        ("down", 32, 36, 37, "exhausted_confirmed_bis"),
    ]
    assert zhongshus == []
    assert structure_state["last_completed"] is None
    assert structure_state["current_ongoing"]["confirmation_basis"] == "no_same_level_zhongshu"
    assert structure_state["relationship"]["transition_state"] == "none"
    assert structure_state["consumption_level"] == "auxiliary"


def test_000591_60m_long_segment_zhongshu_does_not_leave_ghost_center_after_overlap_reuse() -> None:
    segments = identify_segments_from_csv(SAMPLE_000591_60M_LONG_CSV)

    zhongshus = identify_zhongshu(segments, structure_level="segment")
    structure_state = build_structure_state([], zhongshus)

    assert len(segments) == 3
    assert zhongshus == []
    assert structure_state["last_completed"] is None
    assert structure_state["current_ongoing"]["confirmation_basis"] == "no_same_level_zhongshu"
    assert structure_state["relationship"]["transition_state"] == "none"
    assert structure_state["consumption_level"] == "auxiliary"


def test_300124_60m_mixed_overlap_restart_chain_does_not_leave_segment_level_ghost_center() -> None:
    segments = identify_segments_from_csv(SAMPLE_300124_60M_CSV)

    zhongshus = identify_zhongshu(segments, structure_level="segment")
    structure_state = build_structure_state([], zhongshus)

    landmarks = [
        (segment.direction.value, segment.start_bi_id, segment.end_bi_id, segment.break_bi_id, segment.stop_reason)
        for segment in segments
    ]

    assert landmarks[:5] == [
        ("down", 1, 3, 4, "feature_sequence_fractal"),
        ("up", 4, 8, 11, "reverse_break"),
        ("down", 9, 11, 12, "reverse_break"),
        ("up", 12, 16, 17, "reverse_break"),
        ("down", 17, 19, 20, "exhausted_confirmed_bis"),
    ]
    assert zhongshus == []
    assert structure_state["last_completed"] is None
    assert structure_state["current_ongoing"]["confirmation_basis"] == "no_same_level_zhongshu"
    assert structure_state["relationship"]["transition_state"] == "none"
    assert structure_state["consumption_level"] == "auxiliary"


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
    SAMPLE_000591_60M_LONG_CSV,
    SAMPLE_300124_60M_CSV,
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
    首个 segment 级标准中枢的进入段、本体区间与未终结状态。
    """
    identities = []
    for _ in range(3):
        segments = identify_segments_from_csv(SAMPLE_00700_30M_CSV)
        zhongshus = identify_zhongshu(segments, structure_level="segment")
        assert zhongshus, "00700 30m 必须至少有一个标准中枢"
        identities.append(_first_zhongshu_identity(zhongshus[0]))

    assert identities == [
        (0, 1, 4, 432.0, 486.2, None, False),
        (0, 1, 4, 432.0, 486.2, None, False),
        (0, 1, 4, 432.0, 486.2, None, False),
    ]