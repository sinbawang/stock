from pathlib import Path

from tests.segment_regression_support import assert_landmarks_equal, identify_segments_from_csv


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DAY_CSV = ROOT / "data" / "reports" / "00700" / "day" / "analyze" / "00700_day_20230925_to_20260618.csv"
SAMPLE_30M_CSV = ROOT / "data" / "reports" / "00700" / "30m" / "analyze" / "00700_30m_20260511_to_20260717.csv"
SAMPLE_15M_CSV = ROOT / "data" / "reports" / "00700" / "15m" / "analyze" / "00700_15m_20260518_to_20260618.csv"


def test_00700_day_segments_keep_gap_and_tail_landmarks() -> None:
    segments = identify_segments_from_csv(SAMPLE_DAY_CSV)

    assert len(segments) >= 4

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
    assert gap_landmarks == []

    assert any(segment.stop_reason in {"feature_sequence_gap_fractal", "reverse_break"} for segment in segments)

    tail = segments[-1]
    assert tail.direction.value == "down"
    assert tail.stop_reason in {"exhausted_confirmed_bis", "no_followup_same_direction"}
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

    assert landmarks
    assert landmarks[0][:4] == ("up", 0, 2, "reverse_break")
    assert landmarks[0][4] is True
    assert any(reason in {"feature_sequence_gap_fractal", "feature_sequence_fractal"} for _, _, _, reason, _, _ in landmarks)
    assert any(reason == "reverse_break" for _, _, _, reason, _, _ in landmarks)
    assert landmarks[-1][0] == "up"


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

    assert landmarks[0][:4] == ("down", 2, 8, "reverse_break")
    assert any(reason == "feature_sequence_gap_fractal" for _, _, _, reason, _ in landmarks)
    assert any(reason == "reverse_break" for _, _, _, reason, _ in landmarks)

    tail = segments[-1]
    assert tail.direction.value == "down"
    assert tail.start_bi_id == 24
    assert tail.stop_reason in {"exhausted_confirmed_bis", "reverse_break"}
    assert tail.is_confirmed is False
