"""
笔识别单元测试。
"""

import pytest
from datetime import datetime
from chanlun.models import Fractal, FractalType, BiDirection, NormalizedBar
from chanlun.bi import identify_bis


class TestIdentifyBis:
    """笔识别测试"""

    def test_empty_fractals(self):
        """空列表"""
        result = identify_bis([])
        assert result == []

    def test_single_fractal(self):
        """单个分型"""
        fx = Fractal(
            fx_id=0,
            fx_type=FractalType.BOTTOM,
            ts=datetime(2024, 1, 1),
            price=100.0,
            center_bar_idx=0,
            high=102,
            low=100
        )
        result = identify_bis([fx])
        assert result == []

    def test_identify_up_bi_requires_non_overlapping_windows(self):
        """识别向上笔（两分型窗口不重叠，center idx 差至少为3）"""
        fx_bottom = Fractal(
            fx_id=0,
            fx_type=FractalType.BOTTOM,
            ts=datetime(2024, 1, 1),
            price=100.0,
            center_bar_idx=0,
            high=102,
            low=100
        )
        fx_top = Fractal(
            fx_id=1,
            fx_type=FractalType.TOP,
            ts=datetime(2024, 1, 2),
            price=105.0,
            center_bar_idx=3,
            high=105,
            low=103
        )

        fractals = [fx_bottom, fx_top]
        result = identify_bis(fractals)

        assert len(result) == 1
        assert result[0].direction == BiDirection.UP

    def test_no_bi_when_windows_overlap(self):
        """分型窗口重叠时不能成笔"""
        fx_bottom = Fractal(
            fx_id=0,
            fx_type=FractalType.BOTTOM,
            ts=datetime(2024, 1, 1),
            price=100.0,
            center_bar_idx=10,
            high=102,
            low=100
        )
        fx_top = Fractal(
            fx_id=1,
            fx_type=FractalType.TOP,
            ts=datetime(2024, 1, 2),
            price=105.0,
            center_bar_idx=12,
            high=105,
            low=103
        )

        result = identify_bis([fx_bottom, fx_top])
        assert result == []

    def test_last_pen_can_be_unconfirmed(self):
        """最后一笔在没有后续反向分型时应为未确认"""
        fractals = [
            Fractal(0, FractalType.TOP, datetime(2024, 1, 1), 10.0, 0, 10.0, 9.0),
            Fractal(1, FractalType.BOTTOM, datetime(2024, 1, 2), 6.0, 3, 7.0, 6.0),
            Fractal(2, FractalType.TOP, datetime(2024, 1, 3), 8.0, 6, 8.0, 7.0),
        ]

        result = identify_bis(fractals)
        assert len(result) == 2
        assert result[0].is_confirmed is True
        assert result[1].is_confirmed is False

    def test_weaker_later_reverse_cannot_rescue_invalid_first_reverse(self):
        """首个无效反向分型后，后续更弱同类分型不能补成确认。"""
        fractals = [
            Fractal(0, FractalType.BOTTOM, datetime(2024, 1, 1), 10.0, 0, 11.0, 10.0),
            Fractal(1, FractalType.TOP, datetime(2024, 1, 2), 15.0, 3, 15.0, 13.0),
            Fractal(2, FractalType.BOTTOM, datetime(2024, 1, 3), 9.0, 5, 10.0, 9.0),
            Fractal(3, FractalType.TOP, datetime(2024, 1, 4), 14.0, 6, 14.0, 12.0),
            Fractal(4, FractalType.BOTTOM, datetime(2024, 1, 5), 9.5, 7, 10.0, 9.5),
        ]

        result = identify_bis(fractals)
        assert len(result) == 1
        assert result[0].start_ts.date().isoformat() == "2024-01-01"
        assert result[0].end_ts.date().isoformat() == "2024-01-02"
        assert result[0].is_confirmed is False

    def test_up_bi_requires_breaking_start_bottom_window_high(self):
        """向上笔终点顶分型必须突破起点底分型三K窗口最高点。"""
        normalized = [
            NormalizedBar(0, 81.12, 80.06, datetime(2024, 1, 1, 9, 30), datetime(2024, 1, 1, 9, 30), src_indices=[0]),
            NormalizedBar(1, 79.47, 78.84, datetime(2024, 1, 1, 10, 30), datetime(2024, 1, 1, 10, 30), src_indices=[1]),
            NormalizedBar(2, 81.46, 80.27, datetime(2024, 1, 1, 11, 30), datetime(2024, 1, 1, 11, 30), src_indices=[2]),
            NormalizedBar(3, 79.53, 79.08, datetime(2024, 1, 1, 12, 30), datetime(2024, 1, 1, 12, 30), src_indices=[3]),
            NormalizedBar(4, 80.98, 79.57, datetime(2024, 1, 1, 13, 30), datetime(2024, 1, 1, 13, 30), src_indices=[4]),
            NormalizedBar(5, 80.00, 79.41, datetime(2024, 1, 1, 14, 30), datetime(2024, 1, 1, 14, 30), src_indices=[5]),
        ]
        fractals = [
            Fractal(0, FractalType.BOTTOM, datetime(2024, 1, 1, 10, 30), 78.84, 1, 79.47, 78.84),
            Fractal(1, FractalType.TOP, datetime(2024, 1, 1, 13, 30), 80.98, 4, 80.98, 79.57),
        ]

        result = identify_bis(fractals, normalized)
        assert result == []

    def test_down_bi_requires_breaking_start_top_window_low(self):
        """向下笔终点底分型必须跌破起点顶分型三K窗口最低点。"""
        normalized = [
            NormalizedBar(0, 78.20, 77.60, datetime(2024, 1, 1, 9, 30), datetime(2024, 1, 1, 9, 30), src_indices=[0]),
            NormalizedBar(1, 79.10, 78.40, datetime(2024, 1, 1, 10, 30), datetime(2024, 1, 1, 10, 30), src_indices=[1]),
            NormalizedBar(2, 78.80, 77.90, datetime(2024, 1, 1, 11, 30), datetime(2024, 1, 1, 11, 30), src_indices=[2]),
            NormalizedBar(3, 78.70, 78.00, datetime(2024, 1, 1, 12, 30), datetime(2024, 1, 1, 12, 30), src_indices=[3]),
            NormalizedBar(4, 78.60, 77.70, datetime(2024, 1, 1, 13, 30), datetime(2024, 1, 1, 13, 30), src_indices=[4]),
            NormalizedBar(5, 78.10, 77.80, datetime(2024, 1, 1, 14, 30), datetime(2024, 1, 1, 14, 30), src_indices=[5]),
        ]
        fractals = [
            Fractal(0, FractalType.TOP, datetime(2024, 1, 1, 10, 30), 79.10, 1, 79.10, 78.40),
            Fractal(1, FractalType.BOTTOM, datetime(2024, 1, 1, 13, 30), 77.70, 4, 78.60, 77.70),
        ]

        result = identify_bis(fractals, normalized)
        assert result == []
