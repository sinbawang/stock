"""Chart export helpers for Chanlun structure reports."""

from pathlib import Path

import matplotlib.pyplot as plt

from .fractal import Fractal
from .models import Bar, Bi, NormalizedBar, Zhongshu
from .segment import identify_segments
from .visualization import Plotter


def save_structure_charts(
    *,
    bars: list[Bar],
    normalized_bars: list[NormalizedBar],
    fractals: list[Fractal],
    bis: list[Bi],
    zhongshus: list[Zhongshu],
    svg_path: Path,
    png_path: Path,
    jpg_path: Path,
    title: str,
) -> None:
    """Render the unified structure chart to svg/png/jpg artifacts."""
    plotter = Plotter(figsize=(16, 10))
    segments = identify_segments(bis)
    fig = plotter.plot_structure(
        bars,
        fractals,
        bis,
        segments,
        zhongshus,
        normalized_bars=normalized_bars,
        title=title,
    )
    try:
        fig.savefig(svg_path)
        fig.savefig(png_path, dpi=120)
        fig.savefig(jpg_path, dpi=120)
    finally:
        plt.close(fig)