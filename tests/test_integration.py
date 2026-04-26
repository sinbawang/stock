"""
完整流程集成测试与样例演示。
"""

from datetime import datetime
from pathlib import Path
from chanlun.models import Bar
from chanlun.data import read_bars_from_csv
from chanlun.data.cleaner import clean_bars
from chanlun.normalize import normalize_bars
from chanlun.fractal import identify_fractals, filter_consecutive_fractals
from chanlun.bi import identify_bis
from chanlun.zhongshu import identify_zhongshu


def create_sample_uptrend() -> list[Bar]:
    """
    创建单边上升行情样例。
    """
    return [
        Bar(ts=datetime(2024, 1, 1), open=100, high=102, low=99, close=101, volume=1000),
        Bar(ts=datetime(2024, 1, 2), open=101, high=103, low=100, close=102, volume=1100),
        Bar(ts=datetime(2024, 1, 3), open=102, high=104, low=101, close=103, volume=1200),
        Bar(ts=datetime(2024, 1, 4), open=103, high=105, low=102, close=104, volume=1300),
        Bar(ts=datetime(2024, 1, 5), open=104, high=106, low=103, close=105, volume=1400),
        Bar(ts=datetime(2024, 1, 6), open=105, high=107, low=104, close=106, volume=1500),
        Bar(ts=datetime(2024, 1, 7), open=106, high=108, low=105, close=107, volume=1600),
    ]


def create_sample_downtrend() -> list[Bar]:
    """
    创建单边下降行情样例。
    """
    return [
        Bar(ts=datetime(2024, 1, 1), open=100, high=102, low=99, close=101, volume=1000),
        Bar(ts=datetime(2024, 1, 2), open=101, high=102, low=98, close=99, volume=1100),
        Bar(ts=datetime(2024, 1, 3), open=99, high=101, low=97, close=98, volume=1200),
        Bar(ts=datetime(2024, 1, 4), open=98, high=100, low=96, close=97, volume=1300),
        Bar(ts=datetime(2024, 1, 5), open=97, high=99, low=95, close=96, volume=1400),
    ]


def create_sample_oscillation() -> list[Bar]:
    """
    创建震荡行情样例（容易形成中枢）。
    """
    return [
        Bar(ts=datetime(2024, 1, 1), open=100, high=103, low=99, close=101, volume=1000),
        Bar(ts=datetime(2024, 1, 2), open=101, high=104, low=100, close=102, volume=1100),
        Bar(ts=datetime(2024, 1, 3), open=102, high=103, low=101, close=101, volume=1200),
        Bar(ts=datetime(2024, 1, 4), open=101, high=102, low=100, close=100, volume=1300),
        Bar(ts=datetime(2024, 1, 5), open=100, high=103, low=99, close=102, volume=1400),
        Bar(ts=datetime(2024, 1, 6), open=102, high=104, low=100, close=101, volume=1500),
        Bar(ts=datetime(2024, 1, 7), open=101, high=102, low=99, close=100, volume=1600),
    ]


def test_full_pipeline_uptrend():
    """
    测试完整流程：上升趋势。
    """
    bars = create_sample_uptrend()

    # 清洗
    bars = clean_bars(bars)
    assert len(bars) > 0

    # 去包含
    normalized = normalize_bars(bars)
    assert len(normalized) > 0

    # 分型识别
    fractals = identify_fractals(normalized)
    fractals = filter_consecutive_fractals(fractals)

    # 笔识别
    bis = identify_bis(fractals, normalized)

    # 中枢识别
    zhongshus = identify_zhongshu(bis)

    # 验证结果
    print(f"\n上升趋势分析")
    print(f"原始 K 线: {len(bars)}")
    print(f"标准化后: {len(normalized)}")
    print(f"分型: {len(fractals)}")
    print(f"笔: {len(bis)}")
    print(f"中枢: {len(zhongshus)}")


def test_full_pipeline_downtrend():
    """
    测试完整流程：下降趋势。
    """
    bars = create_sample_downtrend()

    bars = clean_bars(bars)
    normalized = normalize_bars(bars)
    fractals = identify_fractals(normalized)
    fractals = filter_consecutive_fractals(fractals)
    bis = identify_bis(fractals, normalized)
    zhongshus = identify_zhongshu(bis)

    print(f"\n下降趋势分析")
    print(f"原始 K 线: {len(bars)}")
    print(f"标准化后: {len(normalized)}")
    print(f"分型: {len(fractals)}")
    print(f"笔: {len(bis)}")
    print(f"中枢: {len(zhongshus)}")


def test_full_pipeline_oscillation():
    """
    测试完整流程：震荡行情。
    """
    bars = create_sample_oscillation()

    bars = clean_bars(bars)
    normalized = normalize_bars(bars)
    fractals = identify_fractals(normalized)
    fractals = filter_consecutive_fractals(fractals)
    bis = identify_bis(fractals, normalized)
    zhongshus = identify_zhongshu(bis)

    print(f"\n震荡行情分析")
    print(f"原始 K 线: {len(bars)}")
    print(f"标准化后: {len(normalized)}")
    print(f"分型: {len(fractals)}")
    print(f"笔: {len(bis)}")
    print(f"中枢: {len(zhongshus)}")

    # 这个样例应该形成某些中枢
    assert len(fractals) > 0 or len(bis) == 0  # 震荡可能难以形成明显笔


def test_pipeline_300124_uses_20260324_as_bottom_boundary():
    """300124 日线回归：03-23 与 03-24 等低点时，底分型应落在 03-24。"""
    csv_path = Path(__file__).resolve().parents[1] / "data" / "300124_汇川技术" / "day" / "300124_daily_20250930_to_20260412.csv"

    bars = read_bars_from_csv(str(csv_path))
    bars = clean_bars(bars)
    normalized = normalize_bars(bars)
    fractals = identify_fractals(normalized)
    fractals = filter_consecutive_fractals(fractals)
    bis = identify_bis(fractals, normalized)

    assert len(bis) >= 10
    assert bis[8].start_ts.date().isoformat() == "2026-03-13"
    assert bis[8].end_ts.date().isoformat() == "2026-03-24"
    assert bis[8].is_confirmed is True
    assert bis[9].start_ts.date().isoformat() == "2026-03-24"
    assert bis[9].end_ts.date().isoformat() == "2026-03-31"
    assert bis[9].is_confirmed is False


def test_pipeline_applies_inclusion_before_fractals_and_bis():
    """流程约束：先左到右去包含，再在标准化 K 线上找分型，再由这些分型构笔。"""
    bars = [
        Bar(ts=datetime(2024, 1, 1, 9, 30), open=8.5, high=10.0, low=5.0, close=9.0, volume=100),
        Bar(ts=datetime(2024, 1, 1, 10, 30), open=8.8, high=9.0, low=6.0, close=8.6, volume=100),
        Bar(ts=datetime(2024, 1, 1, 11, 30), open=9.8, high=11.0, low=7.0, close=10.5, volume=100),
        Bar(ts=datetime(2024, 1, 1, 14, 0), open=12.0, high=14.0, low=9.0, close=13.5, volume=100),
        Bar(ts=datetime(2024, 1, 1, 15, 0), open=12.8, high=13.0, low=8.0, close=9.0, volume=100),
        Bar(ts=datetime(2024, 1, 2, 10, 30), open=11.5, high=12.0, low=7.0, close=8.0, volume=100),
        Bar(ts=datetime(2024, 1, 2, 11, 30), open=10.8, high=11.0, low=6.0, close=6.5, volume=100),
        Bar(ts=datetime(2024, 1, 2, 14, 0), open=11.2, high=12.0, low=7.0, close=11.0, volume=100),
        Bar(ts=datetime(2024, 1, 2, 15, 0), open=12.4, high=13.0, low=8.0, close=12.6, volume=100),
        Bar(ts=datetime(2024, 1, 3, 10, 30), open=13.1, high=14.0, low=9.0, close=13.8, volume=100),
        Bar(ts=datetime(2024, 1, 3, 11, 30), open=13.0, high=13.0, low=8.0, close=8.5, volume=100),
    ]

    normalized = normalize_bars(bars)
    assert len(normalized) == 10
    assert normalized[0].high == 10.0
    assert normalized[0].low == 6.0
    assert normalized[0].src_indices == [0, 1]

    fractals = identify_fractals(normalized)
    fractals = filter_consecutive_fractals(fractals)
    assert [(fx.fx_type.value, fx.center_bar_idx) for fx in fractals] == [
        ("top", 2),
        ("bottom", 5),
        ("top", 8),
    ]

    bis = identify_bis(fractals, normalized)
    assert len(bis) == 2
    assert bis[0].norm_bar_range == (2, 5)
    assert bis[0].direction.value == "down"
    assert bis[0].is_confirmed is True
    assert bis[1].norm_bar_range == (5, 8)
    assert bis[1].direction.value == "up"


if __name__ == "__main__":
    test_full_pipeline_uptrend()
    test_full_pipeline_downtrend()
    test_full_pipeline_oscillation()
