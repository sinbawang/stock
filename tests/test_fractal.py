"""
分型识别单元测试。
"""

import pytest
from datetime import datetime
from chanlun.models import NormalizedBar, FractalType
from chanlun.fractal import identify_fractals, filter_consecutive_fractals


class TestIdentifyFractals:
    """分型识别测试"""

    def test_identify_top_fractal(self, sample_normalized_bars):
        """识别顶分型"""
        bars = [
            NormalizedBar(0, 100, 90, datetime(2024, 1, 1), datetime(2024, 1, 1), src_indices=[0]),
            NormalizedBar(1, 110, 95, datetime(2024, 1, 2), datetime(2024, 1, 2), src_indices=[1]),
            NormalizedBar(2, 105, 92, datetime(2024, 1, 3), datetime(2024, 1, 3), src_indices=[2]),
        ]

        fractals = identify_fractals(bars)
        assert len(fractals) == 1
        assert fractals[0].fx_type == FractalType.TOP

    def test_empty_bars(self):
        """空列表"""
        result = identify_fractals([])
        assert result == []

    def test_insufficient_bars(self):
        """K 线数量不足 3 根"""
        bar = NormalizedBar(
            idx=0,
            high=102,
            low=99,
            ts_start=datetime(2024, 1, 1),
            ts_end=datetime(2024, 1, 1),
            src_indices=[0]
        )
        result = identify_fractals([bar])
        assert result == []

    def test_bottom_fractal_allows_equal_low_with_lower_high(self):
        """等低但高点更低时，仍可构成有效底分型。"""
        bars = [
            NormalizedBar(0, 68.26, 65.0, datetime(2026, 3, 23), datetime(2026, 3, 23), src_indices=[0]),
            NormalizedBar(1, 67.10, 65.0, datetime(2026, 3, 24), datetime(2026, 3, 24), src_indices=[1]),
            NormalizedBar(2, 68.12, 66.12, datetime(2026, 3, 25), datetime(2026, 3, 25), src_indices=[2]),
        ]

        fractals = identify_fractals(bars)
        assert len(fractals) == 1
        assert fractals[0].fx_type == FractalType.BOTTOM
        assert fractals[0].ts.date().isoformat() == "2026-03-24"


class TestFilterConsecutiveFractals:
    """分型去重测试"""

    def test_filter_consecutive_tops(self):
        """连续顶分型去重"""
        from chanlun.models import Fractal

        fx1 = Fractal(
            fx_id=0,
            fx_type=FractalType.TOP,
            ts=datetime(2024, 1, 1),
            price=102.0,
            center_bar_idx=1,
            high=102,
            low=100
        )
        fx2 = Fractal(
            fx_id=1,
            fx_type=FractalType.TOP,
            ts=datetime(2024, 1, 2),
            price=105.0,  # 更高
            center_bar_idx=2,
            high=105,
            low=101
        )

        fractals = [fx1, fx2]
        result = filter_consecutive_fractals(fractals)

        # 应该只保留更高的那个
        assert len(result) == 1
        assert result[0].price == 105.0

    def test_no_filtering_on_different_types(self):
        """不同类型分型不去重"""
        from chanlun.models import Fractal

        fx_top = Fractal(
            fx_id=0,
            fx_type=FractalType.TOP,
            ts=datetime(2024, 1, 1),
            price=102.0,
            center_bar_idx=1,
            high=102,
            low=100
        )
        fx_bottom = Fractal(
            fx_id=1,
            fx_type=FractalType.BOTTOM,
            ts=datetime(2024, 1, 2),
            price=99.0,
            center_bar_idx=2,
            high=101,
            low=99
        )

        fractals = [fx_top, fx_bottom]
        result = filter_consecutive_fractals(fractals)

        assert len(result) == 2
