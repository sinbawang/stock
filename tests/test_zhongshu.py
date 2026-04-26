"""中枢识别单元测试。"""

from datetime import datetime
from chanlun.models import Bi, BiDirection
from chanlun.zhongshu import identify_zhongshu


def _bi(bi_id: int, direction: BiDirection, high: float, low: float) -> Bi:
    start = datetime(2024, 1, 1 + bi_id)
    end = datetime(2024, 1, 1 + bi_id, 1)
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


class TestIdentifyZhongshu:
    def test_empty_bis(self):
        assert identify_zhongshu([]) == []

    def test_insufficient_bis(self):
        bis = [
            _bi(0, BiDirection.DOWN, 110, 100),
            _bi(1, BiDirection.UP, 108, 101),
            _bi(2, BiDirection.DOWN, 107, 102),
            _bi(3, BiDirection.UP, 106, 103),
        ]
        assert identify_zhongshu(bis) == []

    def test_require_enter_exit_same_direction(self):
        bis = [
            _bi(0, BiDirection.DOWN, 110, 98),   # entering
            _bi(1, BiDirection.UP, 106, 100),
            _bi(2, BiDirection.DOWN, 104, 101),
            _bi(3, BiDirection.UP, 103, 102),
            _bi(4, BiDirection.DOWN, 102, 96),   # exit
        ]

        result = identify_zhongshu(bis)

        assert len(result) == 1
        assert result[0].start_bi_id == 1
        assert result[0].end_bi_id == 3
        assert result[0].bi_ids == [1, 2, 3]
        assert result[0].zs_low == 102
        assert result[0].zs_high == 103
        assert result[0].is_terminated is True

    def test_entering_bi_must_overlap_body_zone(self):
        bis = [
            _bi(0, BiDirection.UP, 120, 115),    # does not overlap [102,103]
            _bi(1, BiDirection.DOWN, 106, 100),
            _bi(2, BiDirection.UP, 104, 101),
            _bi(3, BiDirection.DOWN, 103, 102),
            _bi(4, BiDirection.UP, 112, 101),
        ]
        assert identify_zhongshu(bis) == []

    def test_next_center_reuses_previous_exit_as_entering(self):
        bis = [
            _bi(0, BiDirection.DOWN, 110, 98),
            _bi(1, BiDirection.UP, 106, 100),
            _bi(2, BiDirection.DOWN, 104, 101),
            _bi(3, BiDirection.UP, 103, 102),
            _bi(4, BiDirection.DOWN, 102, 96),   # first exit / second entering
            _bi(5, BiDirection.UP, 99, 97),
            _bi(6, BiDirection.DOWN, 99, 97),
            _bi(7, BiDirection.UP, 101, 97),
            _bi(8, BiDirection.DOWN, 98, 95),    # second exit
        ]

        result = identify_zhongshu(bis)

        assert len(result) == 2
        assert result[0].bi_ids == [1, 2, 3]
        assert result[1].bi_ids == [5, 6, 7]
