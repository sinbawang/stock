from pathlib import Path

from tests.segment_regression_support import assert_landmarks_equal, identify_segments_from_csv


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DAY_CSV = ROOT / "data" / "reports" / "03690" / "day" / "analyze" / "03690_day_20230925_to_20260618.csv"
SAMPLE_30M_CSV = ROOT / "data" / "reports" / "03690" / "30m" / "analyze" / "03690_30m_20260511_to_20260717.csv"
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

    assert landmarks[0][:4] == ("down", 1, 17, "feature_sequence_fractal")
    assert any(reason == "feature_sequence_fractal" for _, _, _, reason, _, _ in landmarks)
    assert landmarks[-1][3] in {"exhausted_confirmed_bis", "same_direction_not_extending"}


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
