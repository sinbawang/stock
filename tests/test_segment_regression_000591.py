from pathlib import Path

from chanlun.bi import identify_bis
from chanlun.data import read_bars_from_csv
from chanlun.data.cleaner import clean_bars
from chanlun.fractal import filter_consecutive_fractals, identify_fractals
from chanlun.normalize import normalize_bars
from chanlun.segment import identify_segments


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_DAY_CSV = ROOT / "data" / "reports" / "000591" / "day" / "analyze" / "000591_day_20230925_to_20260618.csv"
SAMPLE_60M_LONG_CSV = ROOT / "data" / "reports" / "000591" / "60m" / "analyze" / "000591_60m_20251210_to_20260618.csv"
SAMPLE_60M_CSV = ROOT / "data" / "reports" / "000591" / "60m" / "analyze" / "000591_60m_20260213_to_20260618.csv"
SAMPLE_15M_CSV = ROOT / "data" / "reports" / "000591" / "15m" / "analyze" / "000591_15m_20260506_to_20260618.csv"


def test_000591_day_segments_do_not_regress_to_oversized_single_leg() -> None:
    bars = clean_bars(read_bars_from_csv(str(SAMPLE_DAY_CSV)))
    normalized_bars = normalize_bars(bars)
    fractals = filter_consecutive_fractals(identify_fractals(normalized_bars))
    bis = identify_bis(fractals, normalized_bars, pending_reverse_mode="any")
    segments = identify_segments(bis)

    assert segments

    max_norm_span = max(segment.norm_bar_range[1] - segment.norm_bar_range[0] for segment in segments)
    max_bi_count = max(len(segment.bi_ids) for segment in segments)

    assert max_norm_span < 210
    assert max_bi_count < 20
    assert not any(
        segment.start_bi_id == 6 and segment.end_bi_id == 46
        for segment in segments
    )

    # Lock the most sensitive manual-review landmarks around the former oversized leg
    # without freezing the entire segmentation output.
    landmarks = [
        (
            segment.direction.value,
            segment.start_bi_id,
            segment.end_bi_id,
            segment.stop_reason,
            segment.is_confirmed,
        )
        for segment in segments
        if segment.start_bi_id in {20, 23, 26, 29, 34, 43, 46}
    ]

    assert landmarks == [
        ("up", 20, 22, "reverse_break_after_gap", True),
        ("down", 23, 25, "feature_sequence_gap_fractal", True),
        ("up", 26, 28, "feature_sequence_fractal", True),
        ("down", 29, 33, "same_direction_not_extending", False),
        ("up", 34, 42, "feature_sequence_fractal", True),
        ("down", 43, 45, "reverse_break", True),
        ("up", 46, 52, "exhausted_confirmed_bis", False),
    ]


def test_000591_60m_segments_keep_current_landmarks() -> None:
    bars = clean_bars(read_bars_from_csv(str(SAMPLE_60M_CSV)))
    normalized_bars = normalize_bars(bars)
    fractals = filter_consecutive_fractals(identify_fractals(normalized_bars))
    bis = identify_bis(fractals, normalized_bars, pending_reverse_mode="any")
    segments = identify_segments(bis)

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

    assert landmarks == [
        ("up", 0, 2, "feature_sequence_fractal", True, (1, 32)),
        ("down", 3, 5, "feature_sequence_gap_fractal", True, (32, 93)),
        ("up", 6, 12, "reverse_break", True, (93, 181)),
    ]


def test_000591_60m_long_window_reclaims_middle_ground_breaks() -> None:
    bars = clean_bars(read_bars_from_csv(str(SAMPLE_60M_LONG_CSV)))
    normalized_bars = normalize_bars(bars)
    fractals = filter_consecutive_fractals(identify_fractals(normalized_bars))
    bis = identify_bis(fractals, normalized_bars, pending_reverse_mode="any")
    segments = identify_segments(bis)

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
        ("down", 0, 2, "reverse_break", True, (1, 15)),
        ("up", 3, 11, "feature_sequence_fractal", True, (15, 170)),
        ("down", 12, 14, "feature_sequence_gap_fractal", True, (170, 231)),
        ("up", 15, 21, "reverse_break", True, (231, 319)),
    ]


def test_000591_15m_current_report_window_keeps_continuous_segments() -> None:
    bars = clean_bars(read_bars_from_csv(str(SAMPLE_15M_CSV)))
    normalized_bars = normalize_bars(bars)
    fractals = filter_consecutive_fractals(identify_fractals(normalized_bars))
    bis = identify_bis(fractals, normalized_bars, pending_reverse_mode="any")
    segments = identify_segments(bis)

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
        ("up", 0, 10, "reverse_break", True, (4, 164)),
        ("down", 11, 21, "reverse_break", True, (164, 293)),
        ("up", 22, 24, "exhausted_confirmed_bis", False, (293, 357)),
    ]