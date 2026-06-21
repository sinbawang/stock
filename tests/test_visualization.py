"""可视化结构图测试。"""

from datetime import datetime, timedelta

from chanlun.models import Bar, Bi, BiDirection, Fractal, FractalType, NormalizedBar, Segment, Zhongshu
from chanlun.visualization import Plotter


def _bars() -> list[Bar]:
    base = datetime(2024, 1, 1, 9, 30)
    return [
        Bar(base + timedelta(hours=index), 10 + index * 0.1, 11 + index * 0.2, 9 + index * 0.1, 10.5 + index * 0.1)
        for index in range(6)
    ]


def _normalized(bars: list[Bar]) -> list[NormalizedBar]:
    return [
        NormalizedBar(0, 11.2, 9.0, bars[0].ts, bars[1].ts, src_indices=[0, 1]),
        NormalizedBar(1, 11.6, 9.2, bars[2].ts, bars[2].ts, src_indices=[2]),
        NormalizedBar(2, 12.0, 9.4, bars[3].ts, bars[4].ts, src_indices=[3, 4]),
        NormalizedBar(3, 12.2, 9.5, bars[5].ts, bars[5].ts, src_indices=[5]),
    ]


def test_plot_structure_overlays_all_layers():
    bars = _bars()
    normalized_bars = _normalized(bars)
    fractals = [
        Fractal(0, FractalType.BOTTOM, bars[1].ts, 9.0, 0, 11.2, 9.0),
        Fractal(1, FractalType.TOP, bars[4].ts, 12.0, 2, 12.0, 9.4),
    ]
    bis = [
        Bi(0, BiDirection.UP, 0, 1, bars[1].ts, bars[4].ts, 12.0, 9.0, (0, 2), True),
        Bi(1, BiDirection.DOWN, 1, 2, bars[4].ts, bars[5].ts, 11.8, 9.5, (2, 3), False),
    ]
    segments = [
        Segment(0, BiDirection.UP, 0, 0, bars[1].ts, bars[4].ts, 9.0, 12.0, 12.0, 9.0, (0, 2), [0], True),
    ]
    zhongshus = [
        Zhongshu(0, 0, 1, 9.6, 11.5, 9.0, 12.0, bars[1].ts, bars[5].ts, [0, 1], False),
    ]

    fig = Plotter().plot_structure(
        bars,
        fractals,
        bis,
        segments,
        zhongshus,
        normalized_bars=normalized_bars,
    )

    ax = fig.axes[0]
    macd_ax = fig.axes[1]
    assert len(fig.axes) == 2
    assert len(ax.patches) >= len(bars) + 1
    assert len(ax.lines) >= 3
    assert len(macd_ax.lines) >= 3


def test_plot_structure_uses_smaller_markers_for_unconfirmed_fractals():
    bars = _bars()
    normalized_bars = _normalized(bars)
    fractals = [
        Fractal(0, FractalType.BOTTOM, bars[1].ts, 9.0, 0, 11.2, 9.0),
        Fractal(1, FractalType.TOP, bars[4].ts, 12.0, 2, 12.0, 9.4),
        Fractal(2, FractalType.BOTTOM, bars[5].ts, 9.5, 3, 12.2, 9.5),
    ]
    bis = [
        Bi(0, BiDirection.UP, 0, 1, bars[1].ts, bars[4].ts, 12.0, 9.0, (0, 2), True),
    ]

    fig = Plotter().plot_structure(
        bars,
        fractals,
        bis,
        [],
        [],
        normalized_bars=normalized_bars,
        confirmed_fractal_ids={0, 1},
    )

    texts_by_marker = {text.get_text(): [] for text in fig.axes[0].texts}
    for text in fig.axes[0].texts:
        texts_by_marker.setdefault(text.get_text(), []).append((text.get_fontsize(), text.get_alpha()))

    assert (6, 1.0) in texts_by_marker['▲']
    assert (3, 0.55) in texts_by_marker['▲']
    assert (6, 1.0) in texts_by_marker['▼']