from pathlib import Path

from tests.segment_regression_support import assert_landmarks_equal, identify_segments_from_csv


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DAY_CSV = ROOT / "data" / "reports" / "000591" / "day" / "analyze" / "000591_day_20210914_to_20260828.csv"
SAMPLE_60M_LONG_CSV = ROOT / "data" / "reports" / "000591" / "60m" / "analyze" / "000591_60m_20251210_to_20260618.csv"
SAMPLE_60M_CSV = ROOT / "data" / "reports" / "000591" / "60m" / "analyze" / "000591_60m_20260213_to_20260618.csv"
SAMPLE_15M_CSV = ROOT / "data" / "reports" / "000591" / "15m" / "analyze" / "000591_15m_20260506_to_20260618.csv"


def test_000591_day_segments_do_not_regress_to_oversized_single_leg() -> None:
    segments = identify_segments_from_csv(SAMPLE_DAY_CSV)

    assert segments
    assert len(segments) >= 8

    max_norm_span = max(segment.norm_bar_range[1] - segment.norm_bar_range[0] for segment in segments)
    max_bi_count = max(len(segment.bi_ids) for segment in segments)

    assert max_norm_span < 240
    assert max_bi_count < 25
    assert not any(
        segment.start_bi_id == 6 and segment.end_bi_id == 46
        for segment in segments
    )

    assert any(segment.direction.value == "up" for segment in segments)
    assert any(segment.stop_reason in {"feature_sequence_fractal", "feature_sequence_gap_fractal", "reverse_break"} for segment in segments)


def test_000591_60m_segments_keep_current_landmarks() -> None:
    practical_segments = identify_segments_from_csv(SAMPLE_60M_CSV)
    theory_segments = identify_segments_from_csv(SAMPLE_60M_CSV, termination_mode="theory")

    practical_landmarks = [
        (
            segment.direction.value,
            segment.start_bi_id,
            segment.end_bi_id,
            segment.stop_reason,
            segment.is_confirmed,
            segment.norm_bar_range,
        )
        for segment in practical_segments
    ]
    theory_landmarks = [
        (
            segment.direction.value,
            segment.start_bi_id,
            segment.end_bi_id,
            segment.stop_reason,
            segment.is_confirmed,
            segment.norm_bar_range,
        )
        for segment in theory_segments
    ]

    assert practical_landmarks == [
        ("down", 2, 8, "reverse_break", True, (24, 71)),
        ("up", 9, 15, "reverse_break", True, (71, 137)),
    ]
    assert theory_landmarks == [
        ("up", 1, 5, "exhausted_confirmed_bis", False, (14, 48)),
        ("down", 6, 8, "exhausted_confirmed_bis", False, (48, 71)),
        ("up", 9, 15, "exhausted_confirmed_bis", False, (71, 137)),
    ]


def test_000591_60m_gap_false_lock_keeps_reverse_break_restart_anchor() -> None:
    practical_segments = identify_segments_from_csv(SAMPLE_60M_CSV)

    assert len(practical_segments) >= 2
    first_segment = practical_segments[0]
    second_segment = practical_segments[1]

    assert first_segment.stop_reason == "reverse_break"
    assert first_segment.break_bi_id == 11
    assert first_segment.end_bi_id == 8
    assert second_segment.start_bi_id == 9
    assert 11 in second_segment.bi_ids


def test_000591_60m_long_window_reclaims_middle_ground_breaks() -> None:
    practical_segments = identify_segments_from_csv(SAMPLE_60M_LONG_CSV)
    theory_segments = identify_segments_from_csv(SAMPLE_60M_LONG_CSV, termination_mode="theory")

    practical_landmarks = [
        (
            segment.direction.value,
            segment.start_bi_id,
            segment.end_bi_id,
            segment.stop_reason,
            segment.is_confirmed,
            segment.norm_bar_range,
        )
        for segment in practical_segments
    ]
    theory_landmarks = [
        (
            segment.direction.value,
            segment.start_bi_id,
            segment.end_bi_id,
            segment.stop_reason,
            segment.is_confirmed,
            segment.norm_bar_range,
        )
        for segment in theory_segments
    ]

    assert practical_landmarks == [
        ("up", 1, 15, "feature_sequence_fractal", True, (4, 108)),
        ("down", 16, 22, "reverse_break", True, (108, 155)),
        ("up", 23, 29, "reverse_break", True, (155, 221)),
    ]
    assert theory_landmarks == [
        ("down", 0, 2, "first_bi_break_then_third_extends", True, (1, 11)),
        ("up", 3, 15, "feature_sequence_fractal", True, (11, 108)),
        ("down", 16, 22, "feature_sequence_gap_fractal", True, (108, 155)),
        ("up", 23, 29, "exhausted_confirmed_bis", False, (155, 221)),
    ]


def test_000591_60m_long_window_keeps_middle_reverse_break_overlap_reuse() -> None:
    practical_segments = identify_segments_from_csv(SAMPLE_60M_LONG_CSV)

    assert len(practical_segments) >= 3
    middle = practical_segments[1]
    tail = practical_segments[2]

    assert middle.direction.value == "down"
    assert middle.end_bi_id == 22
    assert middle.break_bi_id == 25
    assert middle.stop_reason == "reverse_break"
    assert tail.direction.value == "up"
    assert tail.start_bi_id == 23
    assert 25 in tail.bi_ids
    assert tail.break_bi_id == 30


def test_000591_15m_current_report_window_keeps_continuous_segments() -> None:
    segments = identify_segments_from_csv(SAMPLE_15M_CSV)

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

    assert len(landmarks) >= 2
    assert landmarks[0][3] in {"reverse_break", "feature_sequence_gap_fractal"}
    assert any(reason in {"reverse_break", "feature_sequence_gap_fractal", "exhausted_confirmed_bis"} for _, _, _, reason, _, _ in landmarks)