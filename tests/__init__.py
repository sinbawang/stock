"""
测试初始化和 fixtures。
"""

import pytest
from datetime import datetime
from chanlun.models import Bar, NormalizedBar


@pytest.fixture
def sample_bars():
    """
    构造简单的上升行情样例。
    """
    return [
        Bar(ts=datetime(2024, 1, 1), open=100, high=102, low=99, close=101, volume=1000),
        Bar(ts=datetime(2024, 1, 2), open=101, high=103, low=100, close=102, volume=1100),
        Bar(ts=datetime(2024, 1, 3), open=102, high=104, low=101, close=103, volume=1200),
        Bar(ts=datetime(2024, 1, 4), open=103, high=105, low=102, close=104, volume=1300),
        Bar(ts=datetime(2024, 1, 5), open=104, high=106, low=103, close=105, volume=1400),
    ]


@pytest.fixture
def sample_bars_with_inclusion():
    """
    包含有包含关系的样例：第 2、3 根有包含。
    """
    return [
        Bar(ts=datetime(2024, 1, 1), open=100, high=102, low=99, close=101, volume=1000),
        Bar(ts=datetime(2024, 1, 2), open=101, high=105, low=98, close=102, volume=1100),
        Bar(ts=datetime(2024, 1, 3), open=102, high=103, low=100, close=101, volume=1200),
        Bar(ts=datetime(2024, 1, 4), open=101, high=104, low=99, close=103, volume=1300),
    ]


@pytest.fixture
def sample_normalized_bars():
    """
    构造标准化 K 线样例。
    """
    return [
        NormalizedBar(
            idx=0,
            high=102,
            low=99,
            ts_start=datetime(2024, 1, 1),
            ts_end=datetime(2024, 1, 1),
            src_indices=[0]
        ),
        NormalizedBar(
            idx=1,
            high=103,
            low=100,
            ts_start=datetime(2024, 1, 2),
            ts_end=datetime(2024, 1, 2),
            src_indices=[1]
        ),
        NormalizedBar(
            idx=2,
            high=104,
            low=101,
            ts_start=datetime(2024, 1, 3),
            ts_end=datetime(2024, 1, 3),
            src_indices=[2]
        ),
        NormalizedBar(
            idx=3,
            high=105,
            low=102,
            ts_start=datetime(2024, 1, 4),
            ts_end=datetime(2024, 1, 4),
            src_indices=[3]
        ),
        NormalizedBar(
            idx=4,
            high=106,
            low=103,
            ts_start=datetime(2024, 1, 5),
            ts_end=datetime(2024, 1, 5),
            src_indices=[4]
        ),
    ]
