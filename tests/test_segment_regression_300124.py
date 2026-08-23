from pathlib import Path

from tests.segment_regression_support import assert_landmarks_equal, identify_segments_from_csv


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DAY_CSV = ROOT / "data" / "reports" / "300124" / "day" / "analyze" / "300124_day_20210902_to_20260818.csv"
SAMPLE_30M_CSV = ROOT / "data" / "reports" / "300124" / "30m" / "analyze" / "300124_30m_20260430_to_20260818.csv"
SAMPLE_15M_CSV = ROOT / "data" / "reports" / "300124" / "15m" / "analyze" / "300124_15m_20260506_to_20260618.csv"

def test_300124_day_segments_keep_current_landmarks() -> None:
    segments = identify_segments_from_csv(SAMPLE_DAY_CSV)

    landmarks = [
        (
            segment.direction.value,
            segment.start_bi_id,
            segment.end_bi_id,
            segment.stop_reason,
            segment.is_confirmed,
        )
        for segment in segments
    ]

    expected = [
        ("down", 2, 12, "reverse_break", True),
        ("up", 13, 21, "reverse_break", True),
        ("down", 22, 26, "reverse_break", True),
        ("up", 27, 29, "reverse_break", True),
        ("down", 30, 46, "reverse_break", True),
        ("up", 47, 49, "reverse_break", True),
        ("down", 50, 54, "reverse_break", True),
        ("up", 55, 77, "feature_sequence_fractal", True),
        ("down", 78, 88, "exhausted_confirmed_bis", False),
    ]

    assert_landmarks_equal(expected, landmarks)


def test_300124_30m_segments_keep_tail_and_no_followup_state() -> None:
    segments = identify_segments_from_csv(SAMPLE_30M_CSV)

    landmarks = [
        (
            segment.direction.value,
            segment.start_bi_id,
            segment.end_bi_id,
            segment.stop_reason,
            segment.is_confirmed,
            segment.norm_bar_range,
        )
        for segment in segments
    ]

    expected = [
        ("down", 0, 2, "feature_sequence_fractal", True, (6, 28)),
        ("up", 3, 7, "reverse_break", True, (28, 79)),
        ("down", 8, 12, "reverse_break", True, (79, 156)),
        ("up", 13, 15, "reverse_break", True, (156, 172)),
        ("down", 16, 18, "reverse_break", True, (172, 206)),
        ("up", 19, 21, "reverse_break", True, (206, 229)),
        ("down", 22, 24, "reverse_break", True, (229, 291)),
        ("up", 25, 31, "feature_sequence_fractal", True, (291, 368)),
        ("down", 32, 34, "exhausted_confirmed_bis", False, (368, 392)),
    ]

    assert_landmarks_equal(expected, landmarks)


def test_300124_15m_segments_keep_gap_and_reverse_break_landmarks() -> None:
    # 注：旧名 `..._keep_reverse_break_after_gap_landmark` 已过时——该窗口实际产出的
    # stop_reason 是 `feature_sequence_gap_fractal` + `reverse_break`，并不产出
    # `reverse_break_after_gap`（后者是契约中保留但实现当前不产出的码，见
    # tests/test_segment_rediscrimination_matrix.py 中对应 synthetic 引脚）。
    segments = identify_segments_from_csv(SAMPLE_15M_CSV)

    landmarks = [
        (
            segment.direction.value,
            segment.start_bi_id,
            segment.end_bi_id,
            segment.stop_reason,
            segment.is_confirmed,
        )
        for segment in segments
    ]

    expected = [
        ("up", 0, 2, "feature_sequence_gap_fractal", True),
        ("down", 3, 9, "reverse_break", True),
        ("up", 10, 18, "reverse_break", True),
        ("down", 19, 21, "feature_sequence_fractal", True),
        ("up", 22, 24, "feature_sequence_fractal", True),
        ("down", 25, 29, "same_direction_not_extending", False),
    ]

    assert_landmarks_equal(expected, landmarks)
