from pathlib import Path

from tests.segment_regression_support import assert_landmarks_equal, identify_segments_from_csv


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DAY_CSV = ROOT / "data" / "reports" / "03690" / "day" / "analyze" / "03690_day_20230925_to_20260618.csv"
SAMPLE_30M_CSV = ROOT / "data" / "reports" / "03690" / "30m" / "analyze" / "03690_30m_20260527_to_20260814.csv"
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
    assert landmarks[0][:4] == ("down", 1, 3, "reverse_break")
    assert any(reason == "reverse_break" for _, _, _, reason, _ in landmarks)
    assert landmarks[-1][3] in {"exhausted_confirmed_bis", "same_direction_not_extending"}


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
        ("down", 2, 4, "feature_sequence_fractal", True, (35, 60)),
        ("up", 5, 7, "reverse_break", True, (60, 93)),
        ("down", 8, 12, "feature_sequence_fractal", True, (93, 144)),
        ("up", 13, 31, "feature_sequence_fractal", True, (144, 324)),
        ("down", 32, 36, "exhausted_confirmed_bis", False, (324, 362)),
    ]


def test_03690_30m_long_up_segment_keeps_current_restart_anchor() -> None:
    segments = identify_segments_from_csv(SAMPLE_30M_CSV)

    assert len(segments) >= 5
    fourth = segments[3]
    fifth = segments[4]

    assert fourth.direction.value == "up"
    assert fourth.end_bi_id == 31
    assert fourth.break_bi_id == 32
    assert fourth.stop_reason == "feature_sequence_fractal"
    assert fifth.direction.value == "down"
    assert fifth.start_bi_id == fourth.break_bi_id
    assert fifth.start_bi_id == 32


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
    assert second.stop_reason == "same_direction_not_extending"
    assert second.is_confirmed is False
