from pathlib import Path

from tests.segment_regression_support import assert_landmarks_equal, identify_segments_from_csv


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DAY_CSV = ROOT / "data" / "reports" / "00700" / "day" / "analyze" / "00700_day_20230925_to_20260618.csv"
SAMPLE_30M_CSV = ROOT / "data" / "reports" / "00700" / "30m" / "analyze" / "00700_30m_20260511_to_20260717.csv"
SAMPLE_15M_CSV = ROOT / "data" / "reports" / "00700" / "15m" / "analyze" / "00700_15m_20260518_to_20260618.csv"


def test_00700_day_segments_keep_gap_and_tail_landmarks() -> None:
    segments = identify_segments_from_csv(SAMPLE_DAY_CSV)

    assert len(segments) >= 6

    max_bi_count = max(len(segment.bi_ids) for segment in segments)
    assert max_bi_count < 30

    gap_landmarks = [
        (
            segment.direction.value,
            segment.start_bi_id,
            segment.end_bi_id,
            segment.stop_reason,
            segment.is_confirmed,
        )
        for segment in segments
        if segment.start_bi_id in {18, 23}
    ]
    expected = [
        ("up", 18, 22, "feature_sequence_gap_fractal", True),
        ("down", 23, 29, "reverse_break", True),
    ]
    assert_landmarks_equal(expected, gap_landmarks)

    tail = segments[-1]
    assert tail.direction.value == "down"
    assert tail.stop_reason == "exhausted_confirmed_bis"
    assert tail.is_confirmed is False


def test_00700_30m_segments_keep_reverse_break_after_gap_landmark() -> None:
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
        ("up", 0, 2, "reverse_break_after_gap", True, (1, 35)),
        ("down", 3, 25, "reverse_break", True, (35, 214)),
        ("up", 26, 30, "feature_sequence_fractal", True, (214, 249)),
        ("down", 31, 33, "reverse_break", True, (249, 265)),
        ("up", 34, 36, "reverse_break", True, (265, 287)),
    ]

    assert_landmarks_equal(expected, landmarks)


def test_00700_15m_segments_keep_two_consecutive_gap_fractal_turns() -> None:
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
        ("up", 1, 3, "reverse_break", True),
        ("down", 4, 12, "reverse_break", True),
        ("up", 13, 15, "feature_sequence_gap_fractal", True),
        ("down", 16, 18, "feature_sequence_gap_fractal", True),
        ("up", 19, 21, "reverse_break", True),
        ("down", 22, 38, "exhausted_confirmed_bis", False),
    ]

    assert_landmarks_equal(expected, landmarks)

    tail = segments[-1]
    assert tail.direction.value == "down"
    assert tail.start_bi_id == 22
    assert tail.end_bi_id == 38
    assert tail.stop_reason == "exhausted_confirmed_bis"
    assert tail.is_confirmed is False
