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

    def test_stop_after_first_unconfirmed_tail_bi(self):
        """尾部首笔未确认时，不应再从后续分型起出断链新笔。"""
        normalized = [
            NormalizedBar(0, 101.0, 98.0, datetime(2024, 1, 1), datetime(2024, 1, 1), src_indices=[0]),
            NormalizedBar(1, 102.0, 97.0, datetime(2024, 1, 1), datetime(2024, 1, 1), src_indices=[1]),
            NormalizedBar(2, 100.0, 96.0, datetime(2024, 1, 1), datetime(2024, 1, 1), src_indices=[2]),
            NormalizedBar(3, 97.0, 94.0, datetime(2024, 1, 1), datetime(2024, 1, 1), src_indices=[3]),
            NormalizedBar(4, 94.0, 91.0, datetime(2024, 1, 1), datetime(2024, 1, 1), src_indices=[4]),
            NormalizedBar(5, 93.0, 90.0, datetime(2024, 1, 1), datetime(2024, 1, 1), src_indices=[5]),
            NormalizedBar(6, 92.0, 89.0, datetime(2024, 1, 1), datetime(2024, 1, 1), src_indices=[6]),
            NormalizedBar(7, 93.0, 90.0, datetime(2024, 1, 1), datetime(2024, 1, 1), src_indices=[7]),
            NormalizedBar(8, 94.0, 91.0, datetime(2024, 1, 1), datetime(2024, 1, 1), src_indices=[8]),
            NormalizedBar(9, 95.0, 92.0, datetime(2024, 1, 1), datetime(2024, 1, 1), src_indices=[9]),
            NormalizedBar(10, 94.0, 91.0, datetime(2024, 1, 1), datetime(2024, 1, 1), src_indices=[10]),
            NormalizedBar(11, 93.5, 91.0, datetime(2024, 1, 1), datetime(2024, 1, 1), src_indices=[11]),
            NormalizedBar(12, 94.0, 91.5, datetime(2024, 1, 1), datetime(2024, 1, 1), src_indices=[12]),
            NormalizedBar(13, 95.0, 92.5, datetime(2024, 1, 1), datetime(2024, 1, 1), src_indices=[13]),
            NormalizedBar(14, 96.0, 93.0, datetime(2024, 1, 1), datetime(2024, 1, 1), src_indices=[14]),
            NormalizedBar(15, 97.0, 94.0, datetime(2024, 1, 1), datetime(2024, 1, 1), src_indices=[15]),
            NormalizedBar(16, 96.0, 93.0, datetime(2024, 1, 1), datetime(2024, 1, 1), src_indices=[16]),
            NormalizedBar(17, 95.0, 92.0, datetime(2024, 1, 1), datetime(2024, 1, 1), src_indices=[17]),
            NormalizedBar(18, 94.0, 91.0, datetime(2024, 1, 1), datetime(2024, 1, 1), src_indices=[18]),
            NormalizedBar(19, 95.0, 92.0, datetime(2024, 1, 1), datetime(2024, 1, 1), src_indices=[19]),
            NormalizedBar(20, 97.0, 94.0, datetime(2024, 1, 1), datetime(2024, 1, 1), src_indices=[20]),
            NormalizedBar(21, 98.0, 95.0, datetime(2024, 1, 1), datetime(2024, 1, 1), src_indices=[21]),
            NormalizedBar(22, 97.0, 94.0, datetime(2024, 1, 1), datetime(2024, 1, 1), src_indices=[22]),
        ]
        fractals = [
            Fractal(0, FractalType.TOP, datetime(2024, 1, 1), 102.0, 1, 102.0, 97.0),
            Fractal(1, FractalType.BOTTOM, datetime(2024, 1, 2), 90.0, 5, 93.0, 90.0),
            Fractal(2, FractalType.TOP, datetime(2024, 1, 3), 95.0, 9, 95.0, 92.0),
            Fractal(3, FractalType.BOTTOM, datetime(2024, 1, 4), 91.0, 11, 93.5, 91.0),
            Fractal(4, FractalType.TOP, datetime(2024, 1, 5), 97.0, 15, 97.0, 94.0),
            Fractal(5, FractalType.BOTTOM, datetime(2024, 1, 6), 92.0, 17, 95.0, 92.0),
            Fractal(6, FractalType.TOP, datetime(2024, 1, 7), 98.0, 21, 98.0, 95.0),
        ]

        result = identify_bis(fractals, normalized_bars=normalized)

        assert [bi.direction for bi in result] == [BiDirection.DOWN, BiDirection.UP]
        assert [bi.start_fx_id for bi in result] == [0, 1]
        assert [bi.end_fx_id for bi in result] == [1, 6]
        assert [bi.is_confirmed for bi in result] == [True, False]

    def test_leading_unconfirmed_pen_can_shift_first_start_forward(self):
        """头部首笔若长期不能确认，允许把起点右移到更合理的后续分型。"""
        fractals = [
            Fractal(0, FractalType.BOTTOM, datetime(2024, 1, 1), 10.0, 0, 11.0, 10.0),
            Fractal(1, FractalType.TOP, datetime(2024, 1, 2), 15.0, 3, 15.0, 13.0),
            Fractal(2, FractalType.BOTTOM, datetime(2024, 1, 3), 9.0, 5, 10.0, 9.0),
            Fractal(3, FractalType.TOP, datetime(2024, 1, 4), 14.0, 6, 14.0, 12.0),
            Fractal(4, FractalType.BOTTOM, datetime(2024, 1, 5), 9.5, 7, 10.0, 9.5),
        ]

        result = identify_bis(fractals)
        assert len(result) == 1
        assert result[0].start_ts.date().isoformat() == "2024-01-02"
        assert result[0].end_ts.date().isoformat() == "2024-01-05"
        assert result[0].is_confirmed is False

    def test_up_bi_can_form_without_breaking_start_bottom_window_high(self):
        """向上笔不再要求突破起点底分型三K窗口最高点。"""
        fractals = [
            Fractal(0, FractalType.BOTTOM, datetime(2024, 1, 1, 10, 30), 78.84, 1, 79.47, 78.84),
            Fractal(1, FractalType.TOP, datetime(2024, 1, 1, 15, 30), 80.98, 4, 80.98, 79.57),
        ]

        result = identify_bis(fractals)
        assert len(result) == 1
        assert result[0].direction == BiDirection.UP
        assert result[0].is_confirmed is False

    def test_up_bi_requires_end_price_above_start_bottom_price(self):
        """向上笔终点至少要高于起点底分型价格，否则不能成笔。"""
        fractals = [
            Fractal(0, FractalType.BOTTOM, datetime(2024, 1, 1, 10, 30), 88.5, 1, 89.2, 88.5),
            Fractal(1, FractalType.TOP, datetime(2024, 1, 1, 15, 30), 85.5, 5, 85.5, 84.5),
        ]

        result = identify_bis(fractals)
        assert result == []

    def test_down_bi_can_form_without_breaking_start_top_window_low(self):
        """向下笔不再要求跌破起点顶分型三K窗口最低点。"""
        fractals = [
            Fractal(0, FractalType.TOP, datetime(2024, 1, 1, 10, 30), 79.10, 1, 79.10, 78.40),
            Fractal(1, FractalType.BOTTOM, datetime(2024, 1, 1, 15, 30), 77.70, 4, 78.60, 77.70),
        ]

        result = identify_bis(fractals)
        assert len(result) == 1
        assert result[0].direction == BiDirection.DOWN
        assert result[0].is_confirmed is False

    def test_skip_leading_unconfirmed_head_noise_when_later_confirmed_bi_exists(self):
        """首笔若只是头部噪声且后续存在可确认笔，应跳过该未确认首笔。"""
        fractals = [
            Fractal(0, FractalType.BOTTOM, datetime(2024, 1, 1), 10.0, 0, 10.5, 10.0),
            Fractal(1, FractalType.TOP, datetime(2024, 1, 2), 13.0, 3, 13.0, 12.0),
            Fractal(2, FractalType.TOP, datetime(2024, 1, 3), 14.0, 6, 14.0, 13.0),
            Fractal(3, FractalType.BOTTOM, datetime(2024, 1, 4), 9.0, 7, 9.5, 9.0),
        ]

        result = identify_bis(fractals)

        assert len(result) == 1
        assert result[0].direction == BiDirection.DOWN
        assert result[0].start_fx_id == 1
        assert result[0].end_fx_id == 3
        assert result[0].is_confirmed is False

    def test_first_bi_skips_leading_boundary_noise_with_normalized_bars(self):
        """带标准化K线映射时，首笔应跳过左边界不完整头噪声。"""
        normalized = [
            NormalizedBar(i, 100.0 - i, 90.0 - i, datetime(2024, 1, 1), datetime(2024, 1, 1), src_indices=[i])
            for i in range(20)
        ]
        fractals = [
            Fractal(0, FractalType.BOTTOM, datetime(2024, 1, 1, 10, 30), 88.5, 1, 89.2, 88.5),
            Fractal(1, FractalType.TOP, datetime(2024, 1, 1, 11, 30), 89.3, 2, 89.3, 88.8),
            Fractal(2, FractalType.BOTTOM, datetime(2024, 1, 2, 10, 30), 84.45, 4, 85.3, 84.45),
            Fractal(3, FractalType.TOP, datetime(2024, 1, 2, 14, 0), 85.5, 5, 85.5, 84.5),
            Fractal(4, FractalType.BOTTOM, datetime(2024, 1, 3, 10, 30), 80.8, 10, 81.35, 80.8),
            Fractal(5, FractalType.TOP, datetime(2024, 1, 3, 14, 0), 82.7, 12, 82.7, 81.7),
            Fractal(6, FractalType.BOTTOM, datetime(2024, 1, 4, 10, 30), 79.25, 13, 82.2, 79.25),
            Fractal(7, FractalType.TOP, datetime(2024, 1, 5, 10, 30), 87.5, 19, 87.5, 86.1),
        ]

        result = identify_bis(fractals, normalized_bars=normalized)

        assert len(result) >= 1
        assert result[0].direction == BiDirection.DOWN
        assert result[0].start_fx_id == 3
        assert result[0].end_fx_id == 6
        assert result[0].is_confirmed is True
