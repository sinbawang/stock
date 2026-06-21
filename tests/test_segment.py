"""线段识别与映射测试。"""

from datetime import datetime, timedelta

from chanlun.models import Bar, Bi, BiDirection, NormalizedBar
from chanlun.segment import identify_segments
from chanlun.visualization import Plotter


def _bi(bi_id: int, direction: BiDirection, high: float, low: float) -> Bi:
    start = datetime(2024, 1, 1) + timedelta(hours=bi_id)
    end = start + timedelta(minutes=30)
    return Bi(
        bi_id=bi_id,
        direction=direction,
        start_fx_id=bi_id,
        end_fx_id=bi_id + 1,
        start_ts=start,
        end_ts=end,
        high=high,
        low=low,
        norm_bar_range=(bi_id, bi_id + 1),
        is_confirmed=True,
    )


class TestIdentifySegments:
    def test_empty_bis(self):
        assert identify_segments([]) == []

    def test_requires_three_bis(self):
        bis = [_bi(0, BiDirection.UP, 110, 100), _bi(1, BiDirection.DOWN, 108, 103)]
        assert identify_segments(bis) == []

    def test_identify_confirmed_up_segment_when_reverse_hits_last_high(self):
        bis = [
            _bi(0, BiDirection.UP, 110, 100),
            _bi(1, BiDirection.DOWN, 108, 103),
            _bi(2, BiDirection.UP, 115, 104),
            _bi(3, BiDirection.DOWN, 116, 101),
            _bi(4, BiDirection.UP, 109, 102),
            _bi(5, BiDirection.DOWN, 106, 98),
        ]

        result = identify_segments(bis)

        assert len(result) == 2
        assert result[0].direction == BiDirection.UP
        assert result[0].bi_ids == [0, 1, 2]
        assert result[0].is_confirmed is True
        assert result[0].start_price == 100
        assert result[0].end_price == 115
        assert result[1].direction == BiDirection.DOWN
        assert result[1].bi_ids == [3, 4, 5]
        assert result[1].is_confirmed is False

    def test_identify_confirmed_up_segment_after_gap_reverse_fails_to_retake_high(self):
        bis = [
            _bi(0, BiDirection.UP, 110, 100),
            _bi(1, BiDirection.DOWN, 108, 103),
            _bi(2, BiDirection.UP, 115, 104),
            _bi(3, BiDirection.DOWN, 114, 106),
            _bi(4, BiDirection.UP, 113, 107),
            _bi(5, BiDirection.DOWN, 112, 102),
        ]

        result = identify_segments(bis)

        assert len(result) == 2
        assert result[0].direction == BiDirection.UP
        assert result[0].bi_ids == [0, 1, 2]
        assert result[0].is_confirmed is True
        assert result[0].break_bi_id == 3
        assert result[0].stop_reason == "feature_sequence_fractal"
        assert result[1].direction == BiDirection.DOWN
        assert result[1].bi_ids == [3, 4, 5]
        assert result[1].is_confirmed is False

    def test_identify_confirmed_down_segment_when_reverse_hits_last_low(self):
        bis = [
            _bi(0, BiDirection.DOWN, 120, 110),
            _bi(1, BiDirection.UP, 118, 112),
            _bi(2, BiDirection.DOWN, 116, 105),
            _bi(3, BiDirection.UP, 117, 104),
            _bi(4, BiDirection.DOWN, 116, 106),
            _bi(5, BiDirection.UP, 121, 108),
        ]

        result = identify_segments(bis)

        assert len(result) == 2
        assert result[0].direction == BiDirection.DOWN
        assert result[0].bi_ids == [0, 1, 2]
        assert result[0].is_confirmed is True
        assert result[1].direction == BiDirection.UP
        assert result[1].bi_ids == [3, 4, 5]
        assert result[1].is_confirmed is False

    def test_identify_confirmed_down_segment_after_gap_reverse_fails_to_retake_low(self):
        bis = [
            _bi(0, BiDirection.DOWN, 120, 110),
            _bi(1, BiDirection.UP, 118, 112),
            _bi(2, BiDirection.DOWN, 116, 105),
            _bi(3, BiDirection.UP, 117, 106),
            _bi(4, BiDirection.DOWN, 115, 107),
            _bi(5, BiDirection.UP, 119, 108),
        ]

        result = identify_segments(bis)

        assert len(result) == 2
        assert result[0].direction == BiDirection.DOWN
        assert result[0].bi_ids == [0, 1, 2]
        assert result[0].is_confirmed is True
        assert result[0].break_bi_id == 3
        assert result[0].stop_reason == "feature_sequence_fractal"
        assert result[1].direction == BiDirection.UP
        assert result[1].bi_ids == [3, 4, 5]
        assert result[1].is_confirmed is False

    def test_requires_overlap_for_initial_three_bis(self):
        bis = [
            _bi(0, BiDirection.UP, 110, 100),
            _bi(1, BiDirection.DOWN, 95, 90),
            _bi(2, BiDirection.UP, 115, 105),
        ]

        assert identify_segments(bis) == []

    def test_overlap_only_three_bis_can_start_segment(self):
        bis = [
            _bi(0, BiDirection.UP, 120, 100),
            _bi(1, BiDirection.DOWN, 118, 105),
            _bi(2, BiDirection.UP, 119, 106),
        ]

        result = identify_segments(bis)

        assert len(result) == 1
        assert result[0].direction == BiDirection.UP
        assert result[0].bi_ids == [0, 1, 2]
        assert result[0].is_confirmed is False

    def test_feature_sequence_fractal_confirms_long_up_segment_earlier(self):
        bis = [
            _bi(0, BiDirection.UP, 120, 100),
            _bi(1, BiDirection.DOWN, 112, 104),
            _bi(2, BiDirection.UP, 125, 106),
            _bi(3, BiDirection.DOWN, 111, 105),
            _bi(4, BiDirection.UP, 126, 107),
            _bi(5, BiDirection.DOWN, 118, 108),
            _bi(6, BiDirection.UP, 130, 109),
            _bi(7, BiDirection.DOWN, 110, 102),
        ]

        result = identify_segments(bis)

        assert len(result) == 2
        assert result[0].direction == BiDirection.UP
        assert result[0].bi_ids == [0, 1, 2, 3, 4]
        assert result[0].break_bi_id == 5
        assert result[0].stop_reason == "feature_sequence_fractal"
        assert result[0].is_confirmed is True
        assert result[1].direction == BiDirection.DOWN
        assert result[1].bi_ids == [5, 6, 7]
        assert result[1].is_confirmed is False

    def test_feature_sequence_inclusion_is_normalized_before_fractal_check(self):
        bis = [
            _bi(0, BiDirection.UP, 120, 100),
            _bi(1, BiDirection.DOWN, 110, 105),
            _bi(2, BiDirection.UP, 125, 106),
            _bi(3, BiDirection.DOWN, 112, 107),
            _bi(4, BiDirection.UP, 126, 108),
            _bi(5, BiDirection.DOWN, 111, 107.5),
            _bi(6, BiDirection.UP, 127, 109),
            _bi(7, BiDirection.DOWN, 109, 107.2),
        ]

        result = identify_segments(bis)

        assert len(result) == 2
        assert result[0].direction == BiDirection.UP
        assert result[0].bi_ids == [0, 1, 2]
        assert result[0].break_bi_id == 3
        assert result[0].stop_reason == "feature_sequence_fractal"
        assert result[0].is_confirmed is True
        assert result[1].direction == BiDirection.DOWN
        assert result[1].bi_ids == [3, 4, 5]
        assert result[1].stop_reason == "reverse_break"
        assert result[1].is_confirmed is True

    def test_gap_feature_sequence_waits_for_opposite_sequence_fractal(self):
        bis = [
            _bi(0, BiDirection.UP, 120, 100),
            _bi(1, BiDirection.DOWN, 108, 104),
            _bi(2, BiDirection.UP, 125, 106),
            _bi(3, BiDirection.DOWN, 112, 109),
            _bi(4, BiDirection.UP, 111.5, 110),
            _bi(5, BiDirection.DOWN, 110, 107),
            _bi(6, BiDirection.UP, 114, 108),
            _bi(7, BiDirection.DOWN, 109, 103),
            _bi(8, BiDirection.UP, 116, 109),
        ]

        result = identify_segments(bis)

        assert len(result) >= 2
        assert result[0].direction == BiDirection.UP
        assert result[0].bi_ids == [0, 1, 2]
        assert result[0].break_bi_id == 3
        assert result[0].stop_reason == "feature_sequence_gap_fractal"
        assert result[0].is_confirmed is True

    def test_same_direction_not_extending_can_be_reclaimed_by_prior_segment(self):
        bis = [
            _bi(0, BiDirection.UP, 110, 100),
            _bi(1, BiDirection.DOWN, 108, 103),
            _bi(2, BiDirection.UP, 115, 104),
            _bi(3, BiDirection.DOWN, 114, 105),
            _bi(4, BiDirection.UP, 113, 106),
            _bi(5, BiDirection.DOWN, 112, 106.5),
            _bi(6, BiDirection.UP, 116, 107),
        ]

        result = identify_segments(bis)

        assert len(result) == 1
        assert result[0].direction == BiDirection.UP
        assert result[0].bi_ids == [0, 1, 2, 3, 4, 5, 6]
        assert result[0].is_confirmed is False
        assert result[0].stop_reason == "exhausted_confirmed_bis"

    def test_reverse_break_can_be_reclaimed_by_prior_segment(self):
        bis = [
            _bi(0, BiDirection.UP, 110, 100),
            _bi(1, BiDirection.DOWN, 108, 103),
            _bi(2, BiDirection.UP, 115, 104),
            _bi(3, BiDirection.DOWN, 114, 102),
            _bi(4, BiDirection.UP, 113, 103),
            _bi(5, BiDirection.DOWN, 112, 103.5),
            _bi(6, BiDirection.UP, 116, 104),
        ]

        result = identify_segments(bis)

        assert len(result) == 1
        assert result[0].direction == BiDirection.UP
        assert result[0].bi_ids == [0, 1, 2, 3, 4, 5, 6]
        assert result[0].is_confirmed is False
        assert result[0].stop_reason == "exhausted_confirmed_bis"

    def test_next_segment_waits_for_fresh_three_bi_seed_after_break(self):
        bis = [
            _bi(0, BiDirection.DOWN, 16.99, 14.96),
            _bi(1, BiDirection.UP, 19.14, 14.96),
            _bi(2, BiDirection.DOWN, 19.14, 17.54),
            _bi(3, BiDirection.UP, 21.58, 17.54),
            _bi(4, BiDirection.DOWN, 21.58, 20.42),
            _bi(5, BiDirection.UP, 24.98, 20.42),
            _bi(6, BiDirection.DOWN, 24.98, 23.92),
            _bi(7, BiDirection.UP, 25.62, 23.92),
            _bi(8, BiDirection.DOWN, 25.62, 23.64),
            _bi(9, BiDirection.UP, 25.18, 23.64),
            _bi(10, BiDirection.DOWN, 25.18, 23.66),
            _bi(11, BiDirection.UP, 25.06, 23.66),
            _bi(12, BiDirection.DOWN, 25.06, 21.58),
        ]

        result = identify_segments(bis)

        assert len(result) == 2
        assert result[0].direction == BiDirection.UP
        assert result[0].bi_ids == [1, 2, 3, 4, 5, 6, 7]
        assert result[0].break_bi_id == 8
        assert result[0].is_confirmed is True
        assert result[1].direction == BiDirection.DOWN
        assert result[1].bi_ids == [8, 9, 10, 11, 12]
        assert result[1].stop_reason == "exhausted_confirmed_bis"
        assert result[1].is_confirmed is False

    def test_extend_unconfirmed_segment_by_rising_pair(self):
        bis = [
            _bi(0, BiDirection.UP, 110, 100),
            _bi(1, BiDirection.DOWN, 108, 103),
            _bi(2, BiDirection.UP, 115, 104),
            _bi(3, BiDirection.DOWN, 112, 105),
            _bi(4, BiDirection.UP, 118, 106),
        ]

        result = identify_segments(bis)

        assert len(result) == 1
        assert result[0].bi_ids == [0, 1, 2, 3, 4]
        assert result[0].is_confirmed is False
        assert result[0].norm_bar_range == (0, 5)

    def test_ignore_unconfirmed_bis_when_identifying_segments(self):
        bis = [
            _bi(0, BiDirection.UP, 110, 100),
            _bi(1, BiDirection.DOWN, 108, 103),
            _bi(2, BiDirection.UP, 115, 104),
            _bi(3, BiDirection.DOWN, 107, 101),
        ]
        bis[-1].is_confirmed = False

        result = identify_segments(bis)

        assert len(result) == 1
        assert result[0].bi_ids == [0, 1, 2]
        assert result[0].is_confirmed is False


class TestPlotterMapping:
    def test_normalized_index_maps_by_ts_end(self):
        bars = [
            Bar(datetime(2024, 1, 1, 9, 30), 10, 11, 9, 10.5),
            Bar(datetime(2024, 1, 1, 10, 30), 10.5, 11.2, 10.2, 11),
            Bar(datetime(2024, 1, 1, 11, 30), 11, 12, 10.8, 11.5),
            Bar(datetime(2024, 1, 1, 12, 30), 11.5, 11.8, 10.9, 11.1),
            Bar(datetime(2024, 1, 1, 13, 30), 11.1, 12.5, 11.0, 12.2),
        ]
        normalized_bars = [
            NormalizedBar(0, 11.2, 9.0, bars[0].ts, bars[1].ts, src_indices=[0, 1]),
            NormalizedBar(1, 12.0, 10.8, bars[2].ts, bars[2].ts, src_indices=[2]),
            NormalizedBar(2, 12.5, 10.9, bars[3].ts, bars[4].ts, src_indices=[3, 4]),
        ]

        plotter = Plotter()

        assert plotter._normalized_index_to_bar_index(bars, normalized_bars, 0) == 1
        assert plotter._normalized_index_to_bar_index(bars, normalized_bars, 2) == 4