from pathlib import Path

from tests.real_fixture_support import frozen_csv
from tests.segment_regression_support import assert_landmarks_equal, identify_segments_from_csv


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DAY_CSV = frozen_csv("03690", "day")
SAMPLE_30M_CSV = frozen_csv("03690", "30m")


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

    assert landmarks
    assert landmarks[0][:4] == ("down", 1, 5, "feature_sequence_fractal")
    assert any(reason == "reverse_break" for _, _, _, reason, _ in landmarks)
    assert landmarks[-1] == ("down", 103, 111, "reverse_break", True)


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

    assert landmarks == [
        ("down", 0, 4, "reverse_break", True, (5, 37)),
        ("up", 5, 7, "reverse_break", True, (37, 54)),
        ("down", 8, 18, "reverse_break", True, (54, 108)),
        ("up", 19, 21, "feature_sequence_fractal", True, (108, 129)),
        ("down", 22, 24, "reverse_break", True, (129, 149)),
        ("up", 25, 31, "reverse_break", True, (149, 187)),
        ("down", 32, 54, "reverse_break", True, (187, 404)),
        ("up", 55, 77, "feature_sequence_fractal", True, (404, 575)),
        ("down", 78, 94, "feature_sequence_fractal", True, (575, 714)),
        ("up", 95, 97, "feature_sequence_gap_fractal", True, (714, 738)),
        ("down", 98, 100, "exhausted_confirmed_bis", False, (738, 764)),
    ]


def test_03690_30m_long_up_segment_keeps_current_restart_anchor() -> None:
    segments = identify_segments_from_csv(SAMPLE_30M_CSV)

    assert len(segments) >= 9
    long_up = segments[7]
    following = segments[8]

    assert long_up.direction.value == "up"
    assert long_up.end_bi_id == 77
    assert long_up.break_bi_id == 78
    assert long_up.stop_reason == "feature_sequence_fractal"
    assert following.direction.value == "down"
    assert following.start_bi_id == long_up.break_bi_id
    assert following.start_bi_id == 78

