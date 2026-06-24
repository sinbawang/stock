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


def test_plot_structure_draws_moving_averages_and_confirmed_fractal_prices():
    bars = _bars()
    normalized_bars = _normalized(bars)
    fractals = [
        Fractal(0, FractalType.BOTTOM, bars[1].ts, 9.0, 0, 11.2, 9.0),
        Fractal(1, FractalType.TOP, bars[4].ts, 12.0, 2, 12.0, 9.4),
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

    line_labels = [line.get_label() for line in fig.axes[0].lines]
    labels = [text.get_text() for text in fig.axes[0].texts]

    assert 'MA5' in line_labels
    assert 'MA10' in line_labels
    assert f"{bars[1].low:.2f}" in labels
    assert f"{bars[4].high:.2f}" in labels


def test_plot_structure_uses_formatted_time_axis_labels():
    bars = _bars()

    fig = Plotter().plot_structure(
        bars,
        [],
        [],
        [],
        [],
        normalized_bars=_normalized(bars),
    )

    price_ax = fig.axes[0]
    macd_ax = fig.axes[1]
    tick_labels = [tick.get_text() for tick in price_ax.get_xticklabels() if tick.get_text()]
    macd_texts = [text.get_text() for text in macd_ax.texts if text.get_text()]

    assert macd_ax.get_xlabel() == ''
    assert tick_labels
    assert tick_labels[0] == bars[0].ts.strftime('%m%d%H%M')
    assert tick_labels[-1] == bars[-1].ts.strftime('%m%d%H%M')
    assert all(tick.get_rotation() == 0 for tick in price_ax.get_xticklabels() if tick.get_text())
    assert not any(tick.get_text() for tick in macd_ax.get_xticklabels())
    assert '0' in macd_texts
    assert str(len(bars) - 1) in macd_texts


def test_plot_structure_can_draw_segment_level_zhongshu():
    bars = _bars()
    normalized_bars = _normalized(bars)
    bis = [
        Bi(0, BiDirection.UP, 0, 1, bars[1].ts, bars[4].ts, 12.0, 9.0, (0, 2), True),
        Bi(1, BiDirection.DOWN, 1, 2, bars[4].ts, bars[5].ts, 11.8, 9.5, (2, 3), True),
    ]
    segments = [
        Segment(0, BiDirection.DOWN, 0, 2, bars[0].ts, bars[1].ts, 11.0, 9.2, 11.0, 9.2, (0, 1), [0, 1, 2], True),
        Segment(1, BiDirection.UP, 3, 5, bars[1].ts, bars[2].ts, 9.3, 11.4, 11.4, 9.3, (1, 2), [3, 4, 5], True),
        Segment(2, BiDirection.DOWN, 6, 8, bars[2].ts, bars[3].ts, 11.3, 9.8, 11.3, 9.8, (2, 3), [6, 7, 8], True),
        Segment(3, BiDirection.UP, 9, 11, bars[3].ts, bars[4].ts, 9.9, 11.8, 11.8, 9.9, (2, 3), [9, 10, 11], True),
        Segment(4, BiDirection.DOWN, 12, 14, bars[4].ts, bars[5].ts, 11.7, 9.4, 11.7, 9.4, (3, 3), [12, 13, 14], True),
    ]
    zhongshus = [
        Zhongshu(0, 1, 3, 9.8, 11.3, 9.3, 11.8, bars[1].ts, bars[4].ts, [1, 2, 3], False, 0, [1, 2, 3], 4, structure_level="segment"),
    ]

    fig = Plotter().plot_structure(
        bars,
        [],
        bis,
        segments,
        zhongshus,
        normalized_bars=normalized_bars,
    )

    assert len(fig.axes[0].patches) >= len(bars) + 1
    labels = [text.get_text() for text in fig.axes[0].texts]
    assert any(label == 'S0' for label in labels)
    assert any(label.startswith('ZS0 [9.80, 11.30] S1,2,3') for label in labels)