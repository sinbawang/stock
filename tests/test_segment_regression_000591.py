from pathlib import Path

from tests.segment_regression_support import assert_landmarks_equal, identify_segments_from_csv


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DAY_CSV = ROOT / "data" / "reports" / "000591" / "day" / "analyze" / "000591_day_20230925_to_20260618.csv"
SAMPLE_60M_LONG_CSV = ROOT / "data" / "reports" / "000591" / "60m" / "analyze" / "000591_60m_20251210_to_20260618.csv"
SAMPLE_60M_CSV = ROOT / "data" / "reports" / "000591" / "60m" / "analyze" / "000591_60m_20260213_to_20260618.csv"
SAMPLE_15M_CSV = ROOT / "data" / "reports" / "000591" / "15m" / "analyze" / "000591_15m_20260506_to_20260618.csv"


def test_000591_day_segments_do_not_regress_to_oversized_single_leg() -> None:
    segments = identify_segments_from_csv(SAMPLE_DAY_CSV)

    assert segments

    max_norm_span = max(segment.norm_bar_range[1] - segment.norm_bar_range[0] for segment in segments)
    max_bi_count = max(len(segment.bi_ids) for segment in segments)

    assert max_norm_span < 210
    assert max_bi_count < 20
    assert not any(
        segment.start_bi_id == 6 and segment.end_bi_id == 46
        for segment in segments
    )

    assert any(segment.direction.value == "up" for segment in segments)
    assert any(segment.stop_reason in {"feature_sequence_fractal", "feature_sequence_gap_fractal", "reverse_break"} for segment in segments)


def test_000591_60m_segments_keep_current_landmarks() -> None:
    segments = identify_segments_from_csv(SAMPLE_60M_CSV)

    assert len(segments) == 3

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

    assert len(landmarks) == 3
    assert landmarks[0][:4] == ("up", 0, 2, "reverse_break")
    assert landmarks[1][3] in {"feature_sequence_gap_fractal", "reverse_break"}
    assert landmarks[2][3] in {"reverse_break", "exhausted_confirmed_bis"}


def test_000591_60m_long_window_reclaims_middle_ground_breaks() -> None:
    segments = identify_segments_from_csv(SAMPLE_60M_LONG_CSV)

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
    assert any(reason in {"feature_sequence_fractal", "feature_sequence_gap_fractal", "reverse_break"} for _, _, _, reason, _, _ in landmarks)


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