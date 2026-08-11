from pathlib import Path

from tests.segment_regression_support import assert_landmarks_equal, identify_segments_from_csv


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DAY_CSV = ROOT / "data" / "reports" / "300124" / "day" / "analyze" / "300124_day_20230925_to_20260618.csv"
SAMPLE_30M_CSV = ROOT / "data" / "reports" / "300124" / "30m" / "analyze" / "300124_30m_20260330_to_20260717.csv"
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
        ("up", 2, 4, "reverse_break", True),
        ("down", 5, 7, "reverse_break", True),
        ("up", 8, 10, "reverse_break", True),
        ("down", 11, 15, "reverse_break", True),
        ("up", 16, 34, "same_direction_not_extending", False),
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
        ("up", 0, 2, "feature_sequence_fractal", True, (1, 65)),
        ("down", 3, 7, "reverse_break", True, (65, 111)),
        ("up", 8, 16, "reverse_break", True, (111, 206)),
        ("down", 17, 21, "reverse_break", True, (206, 283)),
        ("up", 22, 24, "reverse_break", True, (283, 299)),
        ("down", 25, 27, "reverse_break", True, (299, 333)),
        ("up", 28, 30, "reverse_break", True, (333, 356)),
    ]

    assert_landmarks_equal(expected, landmarks)


def test_300124_15m_segments_keep_reverse_break_after_gap_landmark() -> None:
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
        ("down", 3, 5, "same_direction_not_extending", False),
    ]

    assert_landmarks_equal(expected, landmarks)
