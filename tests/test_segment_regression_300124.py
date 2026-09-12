from pathlib import Path

from tests.real_fixture_support import frozen_csv
from tests.segment_regression_support import assert_landmarks_equal, identify_segments_from_csv


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DAY_CSV = frozen_csv("300124", "day")
SAMPLE_30M_CSV = frozen_csv("300124", "30m")

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
        ("up", 13, 15, "reverse_break", True),
        ("down", 16, 22, "reverse_break", True),
        ("up", 23, 25, "reverse_break", True),
        ("down", 26, 32, "reverse_break", True),
        ("up", 33, 35, "reverse_break", True),
        ("down", 36, 54, "reverse_break", True),
        ("up", 55, 57, "reverse_break", True),
        ("down", 58, 64, "feature_sequence_fractal", True),
        ("up", 65, 87, "reverse_break", True),
        ("down", 88, 102, "same_direction_not_extending", False),
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
        ("up", 0, 10, "feature_sequence_fractal", True, (1, 85)),
        ("down", 11, 17, "same_direction_not_extending", False, (85, 138)),
        ("up", 20, 22, "feature_sequence_fractal", True, (150, 182)),
        ("down", 23, 31, "reverse_break", True, (182, 262)),
        ("up", 32, 34, "reverse_break", True, (262, 278)),
        ("down", 35, 37, "reverse_break", True, (278, 305)),
        ("up", 38, 40, "feature_sequence_fractal", True, (305, 327)),
        ("down", 41, 45, "reverse_break", True, (327, 364)),
        ("up", 46, 50, "reverse_break", True, (364, 393)),
        ("down", 51, 57, "reverse_break", True, (393, 438)),
        ("up", 58, 64, "feature_sequence_fractal", True, (438, 496)),
        ("down", 65, 67, "reverse_break", True, (496, 513)),
        ("up", 68, 70, "reverse_break", True, (513, 533)),
        ("down", 71, 77, "feature_sequence_fractal", True, (533, 610)),
        ("up", 78, 80, "reverse_break", True, (610, 626)),
        ("down", 81, 83, "reverse_break", True, (626, 660)),
        ("up", 84, 86, "reverse_break", True, (660, 683)),
        ("down", 87, 91, "reverse_break", True, (683, 745)),
        ("up", 92, 96, "feature_sequence_gap_fractal", True, (745, 793)),
        ("down", 97, 107, "reverse_break", True, (793, 882)),
        ("up", 108, 113, "exhausted_confirmed_bis", False, (882, 911)),
    ]

    assert_landmarks_equal(expected, landmarks)

    assert_landmarks_equal(expected, landmarks)

