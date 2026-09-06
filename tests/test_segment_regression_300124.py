from pathlib import Path

from tests.segment_regression_support import assert_landmarks_equal, identify_segments_from_csv


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DAY_CSV = ROOT / "data" / "reports" / "300124" / "day" / "analyze" / "300124_day_20210923_to_20260904.csv"
SAMPLE_30M_CSV = ROOT / "data" / "reports" / "300124" / "30m" / "analyze" / "300124_30m_20260123_to_20260904.csv"

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
        ("down", 3, 15, "reverse_break", True, (27, 146)),
        ("up", 16, 18, "reverse_break", True, (146, 162)),
        ("down", 19, 21, "reverse_break", True, (162, 189)),
        ("up", 22, 24, "feature_sequence_fractal", True, (189, 211)),
        ("down", 25, 29, "reverse_break", True, (211, 248)),
        ("up", 30, 34, "reverse_break", True, (248, 277)),
        ("down", 35, 41, "reverse_break", True, (277, 322)),
        ("up", 42, 48, "feature_sequence_fractal", True, (322, 380)),
        ("down", 49, 51, "reverse_break", True, (380, 397)),
        ("up", 52, 54, "reverse_break", True, (397, 417)),
        ("down", 55, 61, "feature_sequence_fractal", True, (417, 494)),
        ("up", 62, 64, "reverse_break", True, (494, 510)),
        ("down", 65, 67, "reverse_break", True, (510, 544)),
        ("up", 68, 70, "reverse_break", True, (544, 567)),
        ("down", 71, 75, "reverse_break", True, (567, 629)),
        ("up", 76, 80, "feature_sequence_gap_fractal", True, (629, 677)),
        ("down", 81, 91, "reverse_break", True, (677, 766)),
        ("up", 92, 97, "exhausted_confirmed_bis", False, (766, 795)),
    ]

    assert_landmarks_equal(expected, landmarks)

