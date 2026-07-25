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
        ("down", 1, 7, "reverse_break", True),
        ("up", 8, 10, "reverse_break", True),
        ("down", 11, 19, "feature_sequence_fractal", True),
        ("up", 20, 38, "reverse_break", True),
        ("down", 39, 49, "reverse_break", True),
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
        ("up", 0, 2, "reverse_break", True, (1, 15)),
        ("down", 3, 5, "reverse_break", True, (15, 36)),
        ("up", 6, 8, "reverse_break", True, (36, 65)),
        ("down", 9, 13, "reverse_break", True, (65, 114)),
        ("up", 14, 22, "feature_sequence_fractal", True, (114, 178)),
        ("down", 23, 25, "reverse_break", True, (178, 195)),
        ("up", 26, 28, "reverse_break", True, (195, 218)),
        ("down", 29, 35, "feature_sequence_fractal", True, (218, 297)),
        ("up", 36, 38, "reverse_break", True, (297, 313)),
        ("down", 39, 41, "reverse_break", True, (313, 350)),
        ("up", 42, 44, "reverse_break", True, (350, 374)),
        ("down", 45, 47, "no_followup_same_direction", False, (374, 415)),
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
        ("up", 1, 7, "feature_sequence_fractal", True),
        ("down", 8, 12, "feature_sequence_fractal", True),
        ("up", 13, 19, "feature_sequence_fractal", True),
        ("down", 20, 24, "feature_sequence_fractal", True),
        ("up", 25, 27, "reverse_break", True),
        ("down", 28, 30, "same_direction_not_extending", False),
        ("up", 31, 33, "reverse_break_after_gap", True),
        ("down", 34, 38, "reverse_break", True),
        ("up", 39, 41, "no_followup_same_direction", False),
    ]

    assert_landmarks_equal(expected, landmarks)
