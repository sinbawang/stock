from pathlib import Path

from tests.segment_regression_support import assert_landmarks_equal, identify_segments_from_csv


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DAY_CSV = ROOT / "data" / "reports" / "03690" / "day" / "analyze" / "03690_day_20230925_to_20260618.csv"
SAMPLE_30M_CSV = ROOT / "data" / "reports" / "03690" / "30m" / "analyze" / "03690_30m_20260511_to_20260717.csv"
SAMPLE_15M_CSV = ROOT / "data" / "reports" / "03690" / "15m" / "analyze" / "03690_15m_20260518_to_20260618.csv"


def test_03690_day_segments_keep_current_landmarks() -> None:
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
        ("up", 0, 2, "reverse_break", True),
        ("down", 3, 5, "reverse_break", True),
        ("up", 6, 10, "same_direction_not_extending", False),
        ("down", 11, 17, "reverse_break", True),
        ("up", 18, 20, "same_direction_not_extending", False),
        ("down", 21, 27, "feature_sequence_fractal", True),
        ("up", 28, 32, "reverse_break", True),
        ("down", 33, 43, "feature_sequence_fractal", True),
        ("up", 44, 48, "reverse_break", True),
        ("down", 49, 51, "same_direction_not_extending", False),
        ("up", 52, 54, "reverse_break", True),
    ]

    assert_landmarks_equal(expected, landmarks)


def test_03690_30m_segments_keep_gap_landmarks_and_tail() -> None:
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
        ("up", 0, 4, "reverse_break", True, (1, 59)),
        ("down", 5, 9, "feature_sequence_gap_fractal", True, (59, 94)),
        ("up", 10, 12, "feature_sequence_gap_fractal", True, (94, 126)),
        ("down", 13, 15, "feature_sequence_fractal", True, (126, 156)),
        ("up", 16, 20, "reverse_break", True, (156, 192)),
        ("down", 21, 27, "reverse_break", True, (192, 265)),
        ("up", 28, 40, "exhausted_confirmed_bis", False, (265, 364)),
    ]

    assert_landmarks_equal(expected, landmarks)


def test_03690_15m_segments_keep_gap_turns_and_preprocess_tail() -> None:
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
        ("down", 0, 10, "feature_sequence_gap_fractal", True),
        ("up", 11, 17, "reverse_break", True),
        ("down", 18, 24, "feature_sequence_fractal", True),
        ("up", 25, 27, "feature_sequence_gap_fractal", True),
        ("down", 28, 32, "feature_sequence_fractal", True),
        ("up", 33, 35, "reverse_break", True),
        ("down", 36, 40, "no_followup_same_direction", False),
    ]

    assert_landmarks_equal(expected, landmarks)
