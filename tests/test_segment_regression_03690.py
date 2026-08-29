from pathlib import Path

from tests.segment_regression_support import assert_landmarks_equal, identify_segments_from_csv


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DAY_CSV = ROOT / "data" / "reports" / "03690" / "day" / "analyze" / "03690_day_20211015_to_20260828.csv"
SAMPLE_30M_CSV = ROOT / "data" / "reports" / "03690" / "30m" / "analyze" / "03690_30m_20260319_to_20260828.csv"
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

    assert landmarks
    assert landmarks[0][:4] == ("up", 0, 2, "reverse_break")
    assert any(reason == "reverse_break" for _, _, _, reason, _ in landmarks)
    assert landmarks[-1][3] in {"exhausted_confirmed_bis", "same_direction_not_extending", "transition_pending"}


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
        ("up", 0, 2, "feature_sequence_gap_fractal", True, (1, 22)),
        ("down", 3, 11, "reverse_break", True, (22, 99)),
        ("up", 12, 14, "reverse_break", True, (99, 116)),
        ("down", 15, 21, "reverse_break", True, (116, 170)),
        ("up", 22, 24, "feature_sequence_fractal", True, (170, 191)),
        ("down", 25, 27, "reverse_break", True, (191, 211)),
        ("up", 28, 30, "reverse_break", True, (211, 249)),
        ("down", 31, 49, "feature_sequence_fractal", True, (249, 457)),
        ("up", 50, 68, "feature_sequence_fractal", True, (457, 637)),
        ("down", 69, 79, "exhausted_confirmed_bis", False, (637, 728)),
    ]


def test_03690_30m_long_up_segment_keeps_current_restart_anchor() -> None:
    segments = identify_segments_from_csv(SAMPLE_30M_CSV)

    assert len(segments) >= 10
    long_up = segments[8]
    following = segments[9]

    assert long_up.direction.value == "up"
    assert long_up.end_bi_id == 68
    assert long_up.break_bi_id == 69
    assert long_up.stop_reason == "feature_sequence_fractal"
    assert following.direction.value == "down"
    assert following.start_bi_id == long_up.break_bi_id
    assert following.start_bi_id == 69


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

    assert landmarks
    assert any(reason == "feature_sequence_gap_fractal" for _, _, _, reason, _ in landmarks)
    assert any(reason == "feature_sequence_fractal" for _, _, _, reason, _ in landmarks)
    assert landmarks[-1][3] in {"no_followup_same_direction", "exhausted_confirmed_bis", "same_direction_not_extending"}


def test_03690_60m_keeps_overlap_reuse_and_preprocess_tail() -> None:
    sample_60m_csv = ROOT / "data" / "reports" / "03690" / "60m" / "analyze" / "03690_60m_20260223_to_20260626.csv"
    segments = identify_segments_from_csv(sample_60m_csv)

    assert len(segments) >= 2
    first = segments[0]
    second = segments[1]

    assert first.direction.value == "down"
    assert first.end_bi_id == 2
    assert first.break_bi_id == 5
    assert first.stop_reason == "reverse_break"
    assert first.is_confirmed is True
    assert second.direction.value == "up"
    assert second.start_bi_id == 3
    assert 5 in second.bi_ids
    assert second.stop_reason == "feature_sequence_gap_fractal_delayed_true"
    assert second.is_confirmed is True
