from pathlib import Path

from tests.segment_regression_support import assert_landmarks_equal, identify_segments_from_csv


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DAY_CSV = ROOT / "data" / "reports" / "03690" / "day" / "analyze" / "03690_day_20211022_to_20260904.csv"
SAMPLE_30M_CSV = ROOT / "data" / "reports" / "03690" / "30m" / "analyze" / "03690_30m_20260326_to_20260904.csv"


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
    assert landmarks[0][:4] == ("down", 0, 6, "feature_sequence_fractal")
    assert any(reason == "reverse_break" for _, _, _, reason, _ in landmarks)
    assert landmarks[-1] == ("down", 104, 112, "reverse_break", True)


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
        ("down", 0, 2, "reverse_break", True, (1, 27)),
        ("up", 3, 11, "reverse_break", True, (27, 86)),
        ("down", 12, 22, "reverse_break", True, (86, 140)),
        ("up", 23, 25, "feature_sequence_fractal", True, (140, 161)),
        ("down", 26, 28, "reverse_break", True, (161, 181)),
        ("up", 29, 35, "reverse_break", True, (181, 219)),
        ("down", 36, 58, "reverse_break", True, (219, 436)),
        ("up", 59, 81, "feature_sequence_fractal", True, (436, 607)),
        ("down", 82, 98, "same_direction_not_extending", False, (607, 746)),
    ]


def test_03690_30m_long_up_segment_keeps_current_restart_anchor() -> None:
    segments = identify_segments_from_csv(SAMPLE_30M_CSV)

    assert len(segments) >= 9
    long_up = segments[7]
    following = segments[8]

    assert long_up.direction.value == "up"
    assert long_up.end_bi_id == 81
    assert long_up.break_bi_id == 82
    assert long_up.stop_reason == "feature_sequence_fractal"
    assert following.direction.value == "down"
    assert following.start_bi_id == long_up.break_bi_id
    assert following.start_bi_id == 82

