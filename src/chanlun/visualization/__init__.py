"""
可视化模块。

生成缠论结构叠加在 K 线图上。
"""

from typing import List
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from ..models import Bar, NormalizedBar, Fractal, Bi, Zhongshu


class Plotter:
    """K 线及缠论结构可视化"""

    def __init__(self, figsize=(14, 8)):
        self.figsize = figsize

    def plot_klines_with_fractals(
        self,
        bars: List[Bar],
        fractals: List[Fractal],
        title: str = "K-line with Fractals"
    ):
        """
        绘制 K 线和分型。
        
        Args:
            bars: K 线列表
            fractals: 分型列表
            title: 图表标题
        """
        fig, ax = plt.subplots(figsize=self.figsize)

        # 绘制 K 线
        for i, bar in enumerate(bars):
            if bar.close >= bar.open:
                color = 'red'
            else:
                color = 'green'

            # 绘制影线
            ax.plot([i, i], [bar.low, bar.high], color=color, linewidth=0.5)

            # 绘制实体
            height = abs(bar.close - bar.open)
            ax.bar(i, height, width=0.6, bottom=min(bar.open, bar.close), color=color)

        # 绘制分型标记
        for fractal in fractals:
            if fractal.center_bar_idx < len(bars):
                bar = bars[fractal.center_bar_idx]
                if fractal.is_top():
                    ax.plot(fractal.center_bar_idx, bar.high, 'r*', markersize=12)
                else:
                    ax.plot(fractal.center_bar_idx, bar.low, 'g*', markersize=12)

        ax.set_title(title)
        ax.set_xlabel("Bar Index")
        ax.set_ylabel("Price")
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        return fig

    def plot_bis(
        self,
        bars: List[Bar],
        bis: List[Bi],
        title: str = "K-line with Strokes (Bi)"
    ):
        """
        绘制 K 线和笔。
        """
        fig, ax = plt.subplots(figsize=self.figsize)

        # 绘制 K 线
        for i, bar in enumerate(bars):
            if bar.close >= bar.open:
                color = 'red'
            else:
                color = 'green'
            ax.plot([i, i], [bar.low, bar.high], color=color, linewidth=0.5)
            height = abs(bar.close - bar.open)
            ax.bar(i, height, width=0.6, bottom=min(bar.open, bar.close), color=color)

        # 绘制笔
        for bi in bis:
            start_idx, end_idx = bi.norm_bar_range
            if start_idx < len(bars) and end_idx < len(bars):
                start_price = bars[start_idx].high if bi.is_down() else bars[start_idx].low
                end_price = bars[end_idx].low if bi.is_down() else bars[end_idx].high
                ax.plot([start_idx, end_idx], [start_price, end_price], 'b-', linewidth=2)

        ax.set_title(title)
        ax.set_xlabel("Bar Index")
        ax.set_ylabel("Price")
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        return fig
