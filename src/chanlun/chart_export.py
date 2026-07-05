"""Chart export helpers for Chanlun structure reports."""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager

from .analysis import build_structure_state
from .fractal import Fractal
from .models import Bar, Bi, NormalizedBar, Zhongshu
from .segment import identify_segments
from .visualization import Plotter


_PREFERRED_CJK_FONTS = (
    "Microsoft YaHei",
    "Microsoft JhengHei",
    "SimHei",
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "PingFang SC",
    "WenQuanYi Zen Hei",
)
_FONT_CONFIGURED = False
_STRUCTURE_CHART_HEIGHT = 10.0
_STRUCTURE_CHART_MIN_WIDTH = 14.0
_STRUCTURE_CHART_MAX_WIDTH = 32.0
_STRUCTURE_CHART_BASE_WIDTH = 8.0
_STRUCTURE_CHART_WIDTH_PER_BAR = 0.12


def _configure_matplotlib_cjk_font() -> str | None:
    global _FONT_CONFIGURED

    if _FONT_CONFIGURED:
        font_list = plt.rcParams.get("font.sans-serif", [])
        return font_list[0] if font_list else None

    available_fonts = {entry.name for entry in font_manager.fontManager.ttflist}
    for font_name in _PREFERRED_CJK_FONTS:
        if font_name not in available_fonts:
            continue

        existing_fonts = [name for name in plt.rcParams.get("font.sans-serif", []) if name != font_name]
        plt.rcParams["font.family"] = "sans-serif"
        plt.rcParams["font.sans-serif"] = [font_name, *existing_fonts]
        plt.rcParams["axes.unicode_minus"] = False
        _FONT_CONFIGURED = True
        return font_name

    _FONT_CONFIGURED = True
    return None


def structure_chart_figsize(bar_count: int) -> tuple[float, float]:
    """Return a fixed-height, variable-width figure size for structure charts."""
    normalized_count = max(bar_count, 0)
    width = _STRUCTURE_CHART_BASE_WIDTH + normalized_count * _STRUCTURE_CHART_WIDTH_PER_BAR
    width = max(_STRUCTURE_CHART_MIN_WIDTH, min(width, _STRUCTURE_CHART_MAX_WIDTH))
    return (width, _STRUCTURE_CHART_HEIGHT)


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
    _configure_matplotlib_cjk_font()
    plotter = Plotter(figsize=structure_chart_figsize(len(bars)))
    segments = identify_segments(bis)
    structure_state = build_structure_state(bars, zhongshus)
    confirmed_fractal_ids = {
        fractal_id
        for bi in bis
        if bi.is_confirmed
        for fractal_id in (bi.start_fx_id, bi.end_fx_id)
    }
    fig = plotter.plot_structure(
        bars,
        fractals,
        bis,
        segments,
        zhongshus,
        normalized_bars=normalized_bars,
        confirmed_fractal_ids=confirmed_fractal_ids,
        structure_state=structure_state,
        title=title,
    )
    try:
        fig.savefig(svg_path)
        fig.savefig(png_path, dpi=120)
        fig.savefig(jpg_path, dpi=120)
    finally:
        plt.close(fig)