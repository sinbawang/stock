from pathlib import Path

from tests.segment_regression_support import assert_landmarks_equal, identify_segments_from_csv


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DAY_CSV = ROOT / "data" / "reports" / "000591" / "day" / "analyze" / "000591_day_20210923_to_20260904.csv"


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
