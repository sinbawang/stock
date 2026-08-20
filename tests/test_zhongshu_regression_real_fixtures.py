from pathlib import Path

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