from pathlib import Path

from tests.segment_regression_support import assert_landmarks_equal, identify_segments_from_csv


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DAY_CSV = ROOT / "data" / "reports" / "300124" / "day" / "analyze" / "300124_day_20210914_to_20260828.csv"
SAMPLE_30M_CSV = ROOT / "data" / "reports" / "300124" / "30m" / "analyze" / "300124_30m_20260116_to_20260828.csv"
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
        ("up", 0, 2, "feature_sequence_fractal", True),
        ("down", 3, 13, "reverse_break", True),
        ("up", 14, 16, "reverse_break", True),
        ("down", 17, 23, "reverse_break", True),
        ("up", 24, 26, "reverse_break", True),
        ("down", 27, 33, "reverse_break", True),
        ("up", 34, 36, "reverse_break", True),
        ("down", 37, 55, "reverse_break", True),
        ("up", 56, 58, "reverse_break", True),
        ("down", 59, 65, "feature_sequence_fractal", True),
        ("up", 66, 88, "reverse_break", True),
        ("down", 89, 103, "exhausted_confirmed_bis", False),
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
        ("up", 0, 2, "reverse_break", True, (5, 19)),
        ("down", 3, 5, "same_direction_not_extending", False, (19, 50)),
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
        ("up", 10, 20, "feature_sequence_fractal", True),
        ("down", 21, 25, "feature_sequence_fractal", True),
        ("up", 26, 28, "feature_sequence_fractal", True),
        ("down", 29, 41, "reverse_break", True),
    ]

    assert_landmarks_equal(expected, landmarks)
