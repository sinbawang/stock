from datetime import datetime, timedelta
from pathlib import Path

from chanlun.chart_export import save_structure_charts
from chanlun.models import Bar, Bi, BiDirection, Fractal, FractalType, NormalizedBar, Zhongshu


def test_save_structure_charts_writes_all_formats(tmp_path: Path) -> None:
    base = datetime(2024, 1, 1, 9, 30)
    bars = [
        Bar(base + timedelta(hours=index), 10 + index * 0.1, 10.8 + index * 0.2, 9.2 + index * 0.1, 10.2 + index * 0.1)
        for index in range(6)
    ]
    normalized_bars = [
        NormalizedBar(0, 11.0, 9.2, bars[0].ts, bars[1].ts, src_indices=[0, 1]),
        NormalizedBar(1, 11.4, 9.4, bars[2].ts, bars[2].ts, src_indices=[2]),
        NormalizedBar(2, 11.8, 9.6, bars[3].ts, bars[4].ts, src_indices=[3, 4]),
        NormalizedBar(3, 12.0, 9.8, bars[5].ts, bars[5].ts, src_indices=[5]),
    ]
    fractals = [
        Fractal(0, FractalType.BOTTOM, bars[1].ts, 9.2, 0, 11.0, 9.2),
        Fractal(1, FractalType.TOP, bars[4].ts, 11.8, 2, 11.8, 9.6),
    ]
    bis = [
        Bi(0, BiDirection.UP, 0, 1, bars[1].ts, bars[4].ts, 11.8, 9.2, (0, 2), True),
        Bi(1, BiDirection.DOWN, 1, 2, bars[4].ts, bars[5].ts, 11.6, 9.8, (2, 3), False),
    ]
    zhongshus = [
        Zhongshu(0, 0, 1, 9.8, 11.2, 9.2, 11.8, bars[1].ts, bars[5].ts, [0, 1], False),
    ]

    svg_path = tmp_path / "structure.svg"
    png_path = tmp_path / "structure.png"
    jpg_path = tmp_path / "structure.jpg"

    save_structure_charts(
        bars=bars,
        normalized_bars=normalized_bars,
        fractals=fractals,
        bis=bis,
        zhongshus=zhongshus,
        svg_path=svg_path,
        png_path=png_path,
        jpg_path=jpg_path,
        title="demo 60m",
    )

    assert svg_path.exists()
    assert png_path.exists()
    assert jpg_path.exists()