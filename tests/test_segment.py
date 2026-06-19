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

    def test_identify_confirmed_up_segment_when_reverse_breaks_key_low(self):
        bis = [
            _bi(0, BiDirection.UP, 110, 100),
            _bi(1, BiDirection.DOWN, 108, 103),
            _bi(2, BiDirection.UP, 115, 104),
            _bi(3, BiDirection.DOWN, 107, 101),
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