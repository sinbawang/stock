"""
可视化模块。

生成缠论结构叠加在 K 线图上。
"""

from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

from ..models import Bar, NormalizedBar, Fractal, Bi, Segment, Zhongshu


class Plotter:
    """K 线及缠论结构可视化"""

    def __init__(self, figsize=(14, 8)):
        self.figsize = figsize
        self.background = '#0e0e0e'
        self.panel_background = '#141414'
        self.up_color = '#e84040'
        self.down_color = '#26a69a'
        self.bi_color = '#33c3ff'
        self.segment_color = '#f7b500'
        self.ma5_color = '#60a5fa'
        self.ma10_color = '#f59e0b'
        self.dif_color = '#f0e040'
        self.dea_color = '#ff8c00'
        self.zero_color = '#808080'
        self.zhongshu_colors = ['#4fc3f7', '#ffb74d', '#81c784', '#e57373']
        self.confirmed_fractal_fontsize = 6
        self.unconfirmed_fractal_fontsize = 3
        self.bi_linewidth = 0.8
        self.segment_linewidth = 1.7

    @staticmethod
    def _build_ts_to_bar_index(bars: List[Bar]) -> Dict:
        return {bar.ts: index for index, bar in enumerate(bars)}

    @staticmethod
    def _ema(values: List[float], period: int) -> np.ndarray:
        ema = np.zeros(len(values), dtype=float)
        if not values:
            return ema
        multiplier = 2.0 / (period + 1)
        ema[0] = values[0]
        for index in range(1, len(values)):
            ema[index] = (values[index] - ema[index - 1]) * multiplier + ema[index - 1]
        return ema

    def _compute_macd(self, bars: List[Bar]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        closes = [bar.close for bar in bars]
        ema12 = self._ema(closes, 12)
        ema26 = self._ema(closes, 26)
        dif = ema12 - ema26
        dea = self._ema(dif.tolist(), 9)
        histogram = dif - dea
        return dif, dea, histogram

    @staticmethod
    def _sma(values: List[float], period: int) -> np.ndarray:
        averages = np.full(len(values), np.nan, dtype=float)
        if period <= 0 or len(values) < period:
            return averages

        cumulative = np.cumsum(np.asarray(values, dtype=float))
        cumulative[period:] = cumulative[period:] - cumulative[:-period]
        averages[period - 1:] = cumulative[period - 1:] / period
        return averages

    def _style_axis(self, ax, show_x: bool = False) -> None:
        ax.set_facecolor(self.panel_background)
        for spine in ax.spines.values():
            spine.set_color('#444444')
        ax.tick_params(colors='#d0d0d0', labelbottom=show_x)
        ax.yaxis.label.set_color('#d0d0d0')
        ax.xaxis.label.set_color('#d0d0d0')
        ax.title.set_color('#f3f3f3')
        ax.grid(True, alpha=0.18, color='#666666', linestyle='--')

    def _apply_time_axis(
        self,
        ax,
        bars: List[Bar],
        *,
        max_ticks: int = 8,
        time_format: str = "%m%d%H%M",
        label_size: int = 7,
    ) -> list[int]:
        if not bars:
            return []

        tick_budget = max(max_ticks, 2)
        step = max(1, int(np.ceil(len(bars) / tick_budget)))
        tick_positions = list(range(0, len(bars), step))
        last_index = len(bars) - 1
        if tick_positions[-1] != last_index:
            tick_positions.append(last_index)

        tick_labels = [bars[index].ts.strftime(time_format) for index in tick_positions]
        ax.set_xticks(tick_positions)
        ax.set_xticklabels(tick_labels, rotation=0, ha='center', fontsize=label_size)
        return tick_positions

    def _draw_index_scale(
        self,
        ax,
        tick_positions: List[int],
        *,
        label_size: int = 7,
    ) -> None:
        if not tick_positions:
            return

        for index in tick_positions:
            ax.plot(
                [index, index],
                [0.0, -0.04],
                transform=ax.get_xaxis_transform(),
                color='#7a7a7a',
                linewidth=0.7,
                clip_on=False,
            )
            ax.text(
                index,
                -0.12,
                str(index),
                transform=ax.get_xaxis_transform(),
                color='#bdbdbd',
                fontsize=label_size,
                ha='center',
                va='top',
                clip_on=False,
            )

    def _normalized_index_to_bar_index(
        self,
        bars: List[Bar],
        normalized_bars: Optional[List[NormalizedBar]],
        normalized_index: int,
    ) -> int:
        if normalized_bars is None or normalized_index >= len(normalized_bars):
            return min(normalized_index, len(bars) - 1)

        ts_to_index = self._build_ts_to_bar_index(bars)
        normalized_bar = normalized_bars[normalized_index]
        if normalized_bar.ts_end in ts_to_index:
            return ts_to_index[normalized_bar.ts_end]

        if normalized_bar.src_indices:
            return min(max(normalized_bar.src_indices[-1], 0), len(bars) - 1)

        return min(normalized_index, len(bars) - 1)

    def _normalized_range_to_bar_range(
        self,
        bars: List[Bar],
        normalized_bars: Optional[List[NormalizedBar]],
        start_idx: int,
        end_idx: int,
    ) -> tuple[int, int]:
        return (
            self._normalized_index_to_bar_index(bars, normalized_bars, start_idx),
            self._normalized_index_to_bar_index(bars, normalized_bars, end_idx),
        )

    def _draw_bars(self, ax, bars: List[Bar]) -> None:
        for i, bar in enumerate(bars):
            color = self.up_color if bar.close >= bar.open else self.down_color
            ax.plot([i, i], [bar.low, bar.high], color=color, linewidth=0.6)
            height = abs(bar.close - bar.open)
            ax.bar(i, height, width=0.6, bottom=min(bar.open, bar.close), color=color)

    def _draw_moving_averages(self, ax, bars: List[Bar]) -> None:
        closes = [bar.close for bar in bars]
        x = np.arange(len(bars))
        ma5 = self._sma(closes, 5)
        ma10 = self._sma(closes, 10)
        ax.plot(x, ma5, color=self.ma5_color, linewidth=1.2, alpha=0.95, label='MA5', zorder=2)
        ax.plot(x, ma10, color=self.ma10_color, linewidth=1.2, alpha=0.95, label='MA10', zorder=2)

    def _draw_fractals(
        self,
        ax,
        bars: List[Bar],
        fractals: List[Fractal],
        normalized_bars: Optional[List[NormalizedBar]],
        confirmed_fractal_ids: Optional[set[int]] = None,
    ) -> None:
        if bars:
            price_span = max(bar.high for bar in bars) - min(bar.low for bar in bars)
        else:
            price_span = 0.0
        price_offset = max(price_span * 0.015, 0.08)

        for fractal in fractals:
            bar_index = self._normalized_index_to_bar_index(
                bars,
                normalized_bars,
                fractal.center_bar_idx,
            )
            bar = bars[bar_index]
            is_confirmed = confirmed_fractal_ids is None or fractal.fx_id in confirmed_fractal_ids
            fontsize = self.confirmed_fractal_fontsize if is_confirmed else self.unconfirmed_fractal_fontsize
            alpha = 1.0 if is_confirmed else 0.55
            if fractal.is_top():
                ax.text(bar_index, bar.high, '▼', color='#ff6b6b', fontsize=fontsize, alpha=alpha, ha='center', va='bottom')
                if is_confirmed:
                    ax.text(
                        bar_index,
                        bar.high + price_offset,
                        f"{bar.high:.2f}",
                        color='#ffb4b4',
                        fontsize=7,
                        alpha=0.92,
                        ha='center',
                        va='bottom',
                        zorder=5,
                    )
            else:
                ax.text(bar_index, bar.low, '▲', color='#4ecdc4', fontsize=fontsize, alpha=alpha, ha='center', va='top')
                if is_confirmed:
                    ax.text(
                        bar_index,
                        bar.low - price_offset,
                        f"{bar.low:.2f}",
                        color='#9ff3eb',
                        fontsize=7,
                        alpha=0.92,
                        ha='center',
                        va='top',
                        zorder=5,
                    )

    def _draw_bis(
        self,
        ax,
        bars: List[Bar],
        bis: List[Bi],
        normalized_bars: Optional[List[NormalizedBar]],
    ) -> None:
        for bi in bis:
            start_idx, end_idx = self._normalized_range_to_bar_range(
                bars,
                normalized_bars,
                bi.norm_bar_range[0],
                bi.norm_bar_range[1],
            )
            start_price = bi.high if bi.is_down() else bi.low
            end_price = bi.low if bi.is_down() else bi.high
            linestyle = '-' if bi.is_confirmed else '--'
            ax.plot(
                [start_idx, end_idx],
                [start_price, end_price],
                color=self.bi_color,
                linewidth=self.bi_linewidth,
                linestyle=linestyle,
                zorder=4,
            )

    def _draw_segments(
        self,
        ax,
        bars: List[Bar],
        segments: List[Segment],
        normalized_bars: Optional[List[NormalizedBar]],
        *,
        show_segment_ids: bool = False,
    ) -> None:
        for segment in segments:
            start_idx, end_idx = self._normalized_range_to_bar_range(
                bars,
                normalized_bars,
                segment.norm_bar_range[0],
                segment.norm_bar_range[1],
            )
            linestyle = '-' if segment.is_confirmed else '--'
            ax.plot(
                [start_idx, end_idx],
                [segment.start_price, segment.end_price],
                color=self.segment_color,
                linewidth=self.segment_linewidth,
                linestyle=linestyle,
                alpha=0.72,
                zorder=3,
            )
            if show_segment_ids:
                label_x = (start_idx + end_idx) / 2
                label_y = (segment.start_price + segment.end_price) / 2
                ax.text(
                    label_x,
                    label_y,
                    f"S{segment.segment_id}",
                    color=self.segment_color,
                    fontsize=8,
                    alpha=0.88,
                    ha='center',
                    va='center',
                    bbox={
                        'boxstyle': 'round,pad=0.15',
                        'facecolor': self.panel_background,
                        'edgecolor': 'none',
                        'alpha': 0.65,
                    },
                    zorder=5,
                )

    def _draw_zhongshus(
        self,
        ax,
        bars: List[Bar],
        zhongshus: List[Zhongshu],
        bis: List[Bi],
        segments: List[Segment],
        normalized_bars: Optional[List[NormalizedBar]],
    ) -> None:
        bi_by_id = {bi.bi_id: bi for bi in bis}
        segment_by_id = {segment.segment_id: segment for segment in segments}
        for color_index, zs in enumerate(zhongshus):
            if not zs.bi_ids:
                continue

            if zs.structure_level == "segment":
                start_unit = segment_by_id.get(zs.bi_ids[0])
                end_unit = segment_by_id.get(zs.bi_ids[-1])
            else:
                start_unit = bi_by_id.get(zs.bi_ids[0])
                end_unit = bi_by_id.get(zs.bi_ids[-1])

            if start_unit is None or end_unit is None:
                continue

            start_idx, _ = self._normalized_range_to_bar_range(
                bars,
                normalized_bars,
                start_unit.norm_bar_range[0],
                start_unit.norm_bar_range[1],
            )
            _, end_idx = self._normalized_range_to_bar_range(
                bars,
                normalized_bars,
                end_unit.norm_bar_range[0],
                end_unit.norm_bar_range[1],
            )
            width = max(end_idx - start_idx, 1)
            color = self.zhongshu_colors[color_index % len(self.zhongshu_colors)]
            rect = Rectangle(
                (start_idx, zs.zs_low),
                width,
                zs.zs_high - zs.zs_low,
                linewidth=1.2,
                linestyle='--',
                edgecolor=color,
                facecolor=color,
                alpha=0.18,
            )
            ax.add_patch(rect)
            ax.text(
                end_idx + 0.2,
                zs.zs_high,
                (
                    f"ZS{zs.zs_id} [{zs.zs_low:.2f}, {zs.zs_high:.2f}]"
                    if zs.structure_level != "segment"
                    else f"ZS{zs.zs_id} [{zs.zs_low:.2f}, {zs.zs_high:.2f}] S{','.join(str(bi_id) for bi_id in zs.bi_ids)}"
                ),
                color=color,
                fontsize=9,
                va='bottom',
            )

    def _draw_macd(self, ax, bars: List[Bar]) -> None:
        dif, dea, histogram = self._compute_macd(bars)
        x = np.arange(len(bars))
        positive = np.where(histogram >= 0, histogram, 0)
        negative = np.where(histogram < 0, histogram, 0)
        ax.bar(x, positive, color=self.up_color, width=0.6, alpha=0.7)
        ax.bar(x, negative, color=self.down_color, width=0.6, alpha=0.7)
        ax.plot(x, dif, color=self.dif_color, linewidth=1.4)
        ax.plot(x, dea, color=self.dea_color, linewidth=1.4)
        ax.axhline(0, color=self.zero_color, linestyle='--', linewidth=1)
        ax.set_ylabel('MACD')

    def plot_klines_with_fractals(
        self,
        bars: List[Bar],
        fractals: List[Fractal],
        normalized_bars: Optional[List[NormalizedBar]] = None,
        confirmed_fractal_ids: Optional[set[int]] = None,
        title: str = "K-line with Fractals"
    ):
        """
        绘制 K 线和分型。
        """
        fig, ax = plt.subplots(figsize=self.figsize)
        fig.patch.set_facecolor(self.background)

        self._draw_bars(ax, bars)
        self._draw_fractals(ax, bars, fractals, normalized_bars, confirmed_fractal_ids)
        self._style_axis(ax, show_x=True)

        ax.set_title(title)
        ax.set_xlabel("Bar Index")
        ax.set_ylabel("Price")

        plt.tight_layout()
        return fig

    def plot_bis(
        self,
        bars: List[Bar],
        bis: List[Bi],
        normalized_bars: Optional[List[NormalizedBar]] = None,
        title: str = "K-line with Strokes (Bi)"
    ):
        """
        绘制 K 线和笔。
        """
        fig, ax = plt.subplots(figsize=self.figsize)
        fig.patch.set_facecolor(self.background)

        self._draw_bars(ax, bars)
        self._draw_bis(ax, bars, bis, normalized_bars)
        self._style_axis(ax, show_x=True)

        ax.set_title(title)
        ax.set_xlabel("Bar Index")
        ax.set_ylabel("Price")

        plt.tight_layout()
        return fig

    def plot_segments(
        self,
        bars: List[Bar],
        segments: List[Segment],
        normalized_bars: Optional[List[NormalizedBar]] = None,
        title: str = "K-line with Segments"
    ):
        """
        绘制 K 线和线段。
        """
        fig, ax = plt.subplots(figsize=self.figsize)
        fig.patch.set_facecolor(self.background)

        self._draw_bars(ax, bars)
        self._draw_segments(ax, bars, segments, normalized_bars)
        self._style_axis(ax, show_x=True)

        ax.set_title(title)
        ax.set_xlabel("Bar Index")
        ax.set_ylabel("Price")

        plt.tight_layout()
        return fig

    def plot_structure(
        self,
        bars: List[Bar],
        fractals: List[Fractal],
        bis: List[Bi],
        segments: List[Segment],
        zhongshus: List[Zhongshu],
        normalized_bars: Optional[List[NormalizedBar]] = None,
        confirmed_fractal_ids: Optional[set[int]] = None,
        title: str = "Chanlun Structure"
    ):
        """
        绘制主图总览：K 线 + 分型 + 笔 + 线段 + 中枢 + MACD。
        """
        show_segment_ids = any(zs.structure_level == "segment" for zs in zhongshus)
        fig, (price_ax, macd_ax) = plt.subplots(
            2,
            1,
            figsize=self.figsize,
            gridspec_kw={"height_ratios": [3.5, 1.2], "hspace": 0.04},
            sharex=True,
        )
        fig.patch.set_facecolor(self.background)

        self._draw_bars(price_ax, bars)
        self._draw_moving_averages(price_ax, bars)
        self._draw_zhongshus(price_ax, bars, zhongshus, bis, segments, normalized_bars)
        self._draw_segments(price_ax, bars, segments, normalized_bars, show_segment_ids=show_segment_ids)
        self._draw_bis(price_ax, bars, bis, normalized_bars)
        self._draw_fractals(price_ax, bars, fractals, normalized_bars, confirmed_fractal_ids)
        self._draw_macd(macd_ax, bars)

        self._style_axis(price_ax, show_x=True)
        self._style_axis(macd_ax, show_x=False)
        tick_positions = self._apply_time_axis(price_ax, bars)
        self._draw_index_scale(macd_ax, tick_positions)
        price_ax.tick_params(axis='x', pad=2)
        macd_ax.tick_params(axis='x', labelbottom=False)

        price_ax.set_title(title)
        price_ax.set_ylabel("Price")
        macd_ax.set_xlabel("")

        fig.subplots_adjust(left=0.06, right=0.98, top=0.95, bottom=0.08, hspace=0.08)
        return fig
