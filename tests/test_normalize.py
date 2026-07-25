"""
包含关系处理单元测试。
"""

import pytest
from datetime import datetime
from chanlun.models import Bar
from chanlun.fractal import identify_fractals
from chanlun.models import FractalType
from chanlun.normalize import has_inclusion, merge_bars, normalize_bars


class TestHasInclusion:
    """包含关系检测测试"""

    def test_bar_a_contains_bar_b(self):
        """A 包含 B"""
        a = Bar(ts=datetime(2024, 1, 1), open=100, high=105, low=95, close=102)
        b = Bar(ts=datetime(2024, 1, 2), open=100, high=103, low=97, close=101)
        assert has_inclusion(a, b) is True

    def test_bar_b_contains_bar_a(self):
        """B 包含 A"""
        a = Bar(ts=datetime(2024, 1, 1), open=100, high=102, low=98, close=101)
        b = Bar(ts=datetime(2024, 1, 2), open=100, high=105, low=95, close=102)
        assert has_inclusion(b, a) is True

    def test_no_inclusion(self):
        """无包含关系"""
        a = Bar(ts=datetime(2024, 1, 1), open=100, high=102, low=98, close=101)
        b = Bar(ts=datetime(2024, 1, 2), open=102, high=105, low=101, close=103)
        assert has_inclusion(a, b) is False
        assert has_inclusion(b, a) is False

    def test_equal_low_counts_as_inclusion(self):
        """相等低点、较高高点视为包含。"""
        a = Bar(ts=datetime(2024, 1, 1), open=100, high=110, low=65, close=101)
        b = Bar(ts=datetime(2024, 1, 2), open=102, high=108, low=65, close=103)
        assert has_inclusion(a, b) is True
        assert has_inclusion(b, a) is False

    def test_identical_range_is_not_inclusion(self):
        """高低点完全相同不算包含。"""
        a = Bar(ts=datetime(2024, 1, 1), open=100, high=110, low=65, close=101)
        b = Bar(ts=datetime(2024, 1, 2), open=102, high=110, low=65, close=103)
        assert has_inclusion(a, b) is False
        assert has_inclusion(b, a) is False


class TestMergeBars:
    """K 线合并测试"""

    def test_merge_up_direction(self):
        """向上方向合并"""
        a = Bar(ts=datetime(2024, 1, 1), open=100, high=105, low=95, close=102)
        b = Bar(ts=datetime(2024, 1, 2), open=100, high=103, low=97, close=101)
        high, low = merge_bars(a, b, "up")
        assert high == 105
        assert low == 97

    def test_merge_down_direction(self):
        """向下方向合并"""
        a = Bar(ts=datetime(2024, 1, 1), open=100, high=105, low=95, close=102)
        b = Bar(ts=datetime(2024, 1, 2), open=100, high=103, low=97, close=101)
        high, low = merge_bars(a, b, "down")
        assert high == 103
        assert low == 95


class TestNormalizeBars:
    """标准化处理测试"""

    def test_empty_bars(self):
        """空列表"""
        result = normalize_bars([])
        assert result == []

    def test_single_bar(self):
        """单根 K 线"""
        bar = Bar(ts=datetime(2024, 1, 1), open=100, high=102, low=99, close=101)
        result = normalize_bars([bar])
        assert len(result) == 1
        assert result[0].high == 102
        assert result[0].low == 99

    def test_no_inclusion(self, sample_bars):
        """无包含关系的序列"""
        result = normalize_bars(sample_bars)
        assert len(result) == len(sample_bars)

    def test_with_inclusion(self, sample_bars_with_inclusion):
        """有包含关系的序列"""
        result = normalize_bars(sample_bars_with_inclusion)
        # 第 2、3 根有包含，应该合并
        assert len(result) <= len(sample_bars_with_inclusion)

    def test_inclusion_inherits_prior_direction_for_bottom_fractal(self):
        """下行过程中遇到包含时应继承前序方向，避免抬高底分型。"""
        bars = [
            Bar(ts=datetime(2024, 1, 1, 10, 30), open=0, high=6.64, low=6.58, close=0),
            Bar(ts=datetime(2024, 1, 1, 11, 30), open=0, high=6.61, low=6.55, close=0),
            Bar(ts=datetime(2024, 1, 1, 14, 0), open=0, high=6.57, low=6.52, close=0),
            Bar(ts=datetime(2024, 1, 1, 15, 0), open=0, high=6.54, low=6.52, close=0),
            Bar(ts=datetime(2024, 1, 2, 10, 30), open=0, high=6.58, low=6.50, close=0),
            Bar(ts=datetime(2024, 1, 2, 11, 30), open=0, high=6.58, low=6.55, close=0),
        ]

        normalized = normalize_bars(bars)

        merged = next(
            row for row in normalized
            if row.ts_start == datetime(2024, 1, 1, 14, 0)
        )
        assert merged.ts_end == datetime(2024, 1, 2, 10, 30)
        assert merged.high == 6.54
        assert merged.low == 6.50
        assert merged.direction == "down"

        fractals = identify_fractals(normalized)
        assert any(
            fx.fx_type == FractalType.BOTTOM and fx.price == 6.50
            for fx in fractals
        )

    def test_regression_600900_window_keeps_2651_low(self):
        """回归：600900 30m 在 06-22 10:00 的低点 26.51 不应被抬高。"""
        bars = [
            Bar(ts=datetime(2026, 6, 18, 11, 30), open=26.74, high=26.78, low=26.72, close=26.76),
            Bar(ts=datetime(2026, 6, 18, 13, 30), open=26.76, high=26.77, low=26.66, close=26.68),
            Bar(ts=datetime(2026, 6, 18, 14, 0), open=26.69, high=26.75, low=26.65, close=26.70),
            Bar(ts=datetime(2026, 6, 18, 14, 30), open=26.70, high=26.72, low=26.65, close=26.66),
            Bar(ts=datetime(2026, 6, 18, 15, 0), open=26.67, high=26.71, low=26.65, close=26.66),
            Bar(ts=datetime(2026, 6, 22, 10, 0), open=26.66, high=26.74, low=26.51, close=26.61),
            Bar(ts=datetime(2026, 6, 22, 10, 30), open=26.61, high=26.72, low=26.58, close=26.61),
            Bar(ts=datetime(2026, 6, 22, 11, 0), open=26.60, high=26.77, low=26.56, close=26.74),
        ]

        normalized = normalize_bars(bars)

        # The inclusion chain starting at 06-18 14:00 must inherit down direction,
        # keeping 06-22 10:00 low=26.51 instead of being lifted.
        target = next(
            row for row in normalized
            if row.ts_start == datetime(2026, 6, 18, 14, 0)
        )
        assert target.ts_end == datetime(2026, 6, 22, 10, 0)
        assert target.direction == "down"
        assert target.high == 26.71
        assert target.low == 26.51

        fractals = identify_fractals(normalized)
        assert any(
            fx.fx_type == FractalType.BOTTOM and fx.price == 26.51
            for fx in fractals
        )
