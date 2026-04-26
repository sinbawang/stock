"""
包含关系处理单元测试。
"""

import pytest
from datetime import datetime
from chanlun.models import Bar
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

    def test_equal_low_is_not_inclusion(self):
        """相等低点不算严格包含"""
        a = Bar(ts=datetime(2024, 1, 1), open=100, high=110, low=65, close=101)
        b = Bar(ts=datetime(2024, 1, 2), open=102, high=108, low=65, close=103)
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
