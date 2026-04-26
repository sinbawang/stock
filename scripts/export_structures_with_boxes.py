"""从标准化 K 线导出分型、笔，并绘制包含关系方框图。"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from chanlun.bi import identify_bis
from chanlun.fractal import filter_consecutive_fractals, identify_fractals
from chanlun.models import Bar, Fractal, NormalizedBar
from chanlun.zhongshu import identify_zhongshu


@dataclass
class NormalizedCsvRow:
    idx: int
    ts_start: datetime
    ts_end: datetime
    ts_high: datetime
    ts_low: datetime
    high: float
    low: float
    direction: str
    src_indices: list[int]


@dataclass
class MacdPoint:
    ts: datetime
    close: float
    ema12: float
    ema26: float
    dif: float
    dea: float
    macd: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="从标准化 K 线导出包含处理、顶底分型、笔、笔中枢和 MACD 图表")
    parser.add_argument("--raw", required=True, help="原始 K 线 CSV")
    parser.add_argument("--normalized", required=True, help="标准化 K 线 CSV")
    parser.add_argument("--output-dir", required=True, help="输出目录")
    parser.add_argument("--prefix", required=True, help="输出文件名前缀")
    parser.add_argument("--title", default="K-line with Inclusion Boxes, Fractals, Bis, Zhongshu and MACD", help="图表标题")
    return parser.parse_args()


def parse_ts(value: str) -> datetime:
    value = value.strip()
    if len(value) == 10:  # date-only: 2025-01-02
        return datetime.strptime(value, "%Y-%m-%d")
    return datetime.strptime(value, "%Y-%m-%d %H:%M")


def read_raw_bars(path: Path) -> list[Bar]:
    bars: list[Bar] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            bars.append(
                Bar(
                    ts=parse_ts(row["ts"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=int(float(row.get("volume", 0) or 0)),
                )
            )
    return bars


def parse_src_indices(value: str) -> list[int]:
    if not value:
        return []
    return [int(part) for part in value.split(",") if part]


def read_normalized_bars(path: Path) -> tuple[list[NormalizedBar], list[NormalizedCsvRow]]:
    bars: list[NormalizedBar] = []
    rows: list[NormalizedCsvRow] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            src_indices = parse_src_indices(row["src_indices"])
            csv_row = NormalizedCsvRow(
                idx=int(row["idx"]),
                ts_start=parse_ts(row["ts_start"]),
                ts_end=parse_ts(row["ts_end"]),
                ts_high=parse_ts(row["ts_high"]),
                ts_low=parse_ts(row["ts_low"]),
                high=float(row["high"]),
                low=float(row["low"]),
                direction=row.get("direction", "") or "",
                src_indices=src_indices,
            )
            rows.append(csv_row)
            bars.append(
                NormalizedBar(
                    idx=csv_row.idx,
                    high=csv_row.high,
                    low=csv_row.low,
                    ts_start=csv_row.ts_start,
                    ts_end=csv_row.ts_end,
                    ts_high=csv_row.ts_high,
                    ts_low=csv_row.ts_low,
                    src_indices=src_indices,
                    direction=csv_row.direction or None,
                )
            )
    return bars, rows


def _bar_context_row(norm_bars: list[NormalizedBar], index: int, prefix: str) -> dict:
    if index < 0 or index >= len(norm_bars):
        return {
            f"{prefix}_bar_idx": None,
            f"{prefix}_bar_ts_start": None,
            f"{prefix}_bar_ts_end": None,
            f"{prefix}_bar_high": None,
            f"{prefix}_bar_low": None,
        }

    bar = norm_bars[index]
    return {
        f"{prefix}_bar_idx": bar.idx,
        f"{prefix}_bar_ts_start": bar.ts_start.strftime("%Y-%m-%d %H:%M"),
        f"{prefix}_bar_ts_end": bar.ts_end.strftime("%Y-%m-%d %H:%M"),
        f"{prefix}_bar_high": bar.high,
        f"{prefix}_bar_low": bar.low,
    }


def export_fractals(path: Path, norm_bars: list[NormalizedBar], fractals: list[Fractal], confirmed_fx_ids: set[int], unconfirmed_end_fx_ids: set[int]) -> None:
    rows: list[dict] = []
    for fx in fractals:
        is_confirmed = fx.fx_id in confirmed_fx_ids
        note = "confirmed" if is_confirmed else "candidate"
        if fx.fx_id in unconfirmed_end_fx_ids:
            note = "pre_bi_candidate"

        row = {
            "fx_id": fx.fx_id,
            "fx_type": fx.fx_type.value,
            "ts": fx.ts.strftime("%Y-%m-%d %H:%M"),
            "price": fx.price,
            "center_bar_idx": fx.center_bar_idx,
            "high": fx.high,
            "low": fx.low,
            "is_confirmed": is_confirmed,
            "note": note,
        }
        row.update(_bar_context_row(norm_bars, fx.center_bar_idx - 1, "left"))
        row.update(_bar_context_row(norm_bars, fx.center_bar_idx, "center"))
        row.update(_bar_context_row(norm_bars, fx.center_bar_idx + 1, "right"))
        rows.append(row)

    fieldnames = list(rows[0].keys()) if rows else [
        "fx_id",
        "fx_type",
        "ts",
        "price",
        "center_bar_idx",
        "high",
        "low",
        "is_confirmed",
        "note",
        "left_bar_idx",
        "left_bar_ts_start",
        "left_bar_ts_end",
        "left_bar_high",
        "left_bar_low",
        "center_bar_idx",
        "center_bar_ts_start",
        "center_bar_ts_end",
        "center_bar_high",
        "center_bar_low",
        "right_bar_idx",
        "right_bar_ts_start",
        "right_bar_ts_end",
        "right_bar_high",
        "right_bar_low",
    ]

    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def export_confirmed_fractals(path: Path, norm_bars: list[NormalizedBar], fractals: list[Fractal], confirmed_fx_ids: set[int]) -> None:
    confirmed = [fx for fx in fractals if fx.fx_id in confirmed_fx_ids]
    export_fractals(path, norm_bars, confirmed, confirmed_fx_ids, set())


def export_bis(path: Path, bis) -> None:
    rows = [
        {
            "bi_id": bi.bi_id,
            "direction": bi.direction.value,
            "start_fx_id": bi.start_fx_id,
            "end_fx_id": bi.end_fx_id,
            "start_ts": bi.start_ts.strftime("%Y-%m-%d %H:%M"),
            "end_ts": bi.end_ts.strftime("%Y-%m-%d %H:%M"),
            "high": bi.high,
            "low": bi.low,
            "start_norm_idx": bi.norm_bar_range[0],
            "end_norm_idx": bi.norm_bar_range[1],
            "is_confirmed": bi.is_confirmed,
            "status": "confirmed" if bi.is_confirmed else "preprocessing",
            "note": "auto_generated",
        }
        for bi in bis
    ]
    fieldnames = list(rows[0].keys()) if rows else [
        "bi_id",
        "direction",
        "start_fx_id",
        "end_fx_id",
        "start_ts",
        "end_ts",
        "high",
        "low",
        "start_norm_idx",
        "end_norm_idx",
        "is_confirmed",
        "status",
        "note",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def export_zhongshus(path: Path, zhongshus) -> None:
    rows = [
        {
            "zs_id": zs.zs_id,
            "start_bi_id": zs.start_bi_id,
            "end_bi_id": zs.end_bi_id,
            "zs_low": zs.zs_low,
            "zs_high": zs.zs_high,
            "peak_low": zs.peak_low,
            "peak_high": zs.peak_high,
            "start_ts": zs.start_ts.strftime("%Y-%m-%d %H:%M"),
            "end_ts": zs.end_ts.strftime("%Y-%m-%d %H:%M"),
            "bi_ids": ",".join(str(bi_id) for bi_id in zs.bi_ids),
            "is_terminated": zs.is_terminated,
        }
        for zs in zhongshus
    ]

    fieldnames = list(rows[0].keys()) if rows else [
        "zs_id",
        "start_bi_id",
        "end_bi_id",
        "zs_low",
        "zs_high",
        "peak_low",
        "peak_high",
        "start_ts",
        "end_ts",
        "bi_ids",
        "is_terminated",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def calculate_macd(raw_bars: list[Bar], short_period: int = 12, long_period: int = 26, signal_period: int = 9) -> list[MacdPoint]:
    points: list[MacdPoint] = []
    if not raw_bars:
        return points

    short_alpha = 2 / (short_period + 1)
    long_alpha = 2 / (long_period + 1)
    signal_alpha = 2 / (signal_period + 1)

    first_close = raw_bars[0].close
    ema12 = first_close
    ema26 = first_close
    dea = 0.0

    for bar in raw_bars:
        close = bar.close
        ema12 = ema12 * (1 - short_alpha) + close * short_alpha
        ema26 = ema26 * (1 - long_alpha) + close * long_alpha
        dif = ema12 - ema26
        dea = dea * (1 - signal_alpha) + dif * signal_alpha
        macd = (dif - dea) * 2
        points.append(
            MacdPoint(
                ts=bar.ts,
                close=close,
                ema12=ema12,
                ema26=ema26,
                dif=dif,
                dea=dea,
                macd=macd,
            )
        )

    return points


def export_macd(path: Path, macd_points: list[MacdPoint]) -> None:
    rows = [
        {
            "ts": point.ts.strftime("%Y-%m-%d %H:%M"),
            "close": point.close,
            "ema12": point.ema12,
            "ema26": point.ema26,
            "dif": point.dif,
            "dea": point.dea,
            "macd": point.macd,
        }
        for point in macd_points
    ]
    fieldnames = list(rows[0].keys()) if rows else ["ts", "close", "ema12", "ema26", "dif", "dea", "macd"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _svg_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def write_svg_with_inclusion_boxes(
    raw_bars: list[Bar],
    normalized_rows: list[NormalizedCsvRow],
    fractals: list[Fractal],
    confirmed_fx_ids: set[int],
    bis,
    zhongshus,
    macd_points: list[MacdPoint],
    output_svg: Path,
    title: str,
) -> None:
    width = 1800
    height = 1120
    left_margin = 80
    right_margin = 30
    top_margin = 60
    bottom_margin = 80
    macd_height = 190
    gap = 28
    price_height = height - top_margin - bottom_margin - macd_height - gap
    plot_width = width - left_margin - right_margin

    all_prices = [bar.high for bar in raw_bars] + [bar.low for bar in raw_bars]
    min_price = min(all_prices)
    max_price = max(all_prices)
    price_padding = (max_price - min_price) * 0.06 or 1.0
    min_price -= price_padding
    max_price += price_padding

    slot_width = plot_width / max(len(raw_bars), 1)
    candle_width = max(3.0, slot_width * 0.58)

    def x_for(index: int) -> float:
        return left_margin + slot_width * (index + 0.5)

    def price_y(price: float) -> float:
        scale = (price - min_price) / (max_price - min_price)
        return top_margin + price_height * (1.0 - scale)

    macd_values = [point.macd for point in macd_points] or [0.0]
    dif_values = [point.dif for point in macd_points] or [0.0]
    dea_values = [point.dea for point in macd_points] or [0.0]
    macd_panel_values = macd_values + dif_values + dea_values + [0.0]
    macd_abs_max = max(abs(value) for value in macd_panel_values) or 1.0
    macd_top = top_margin + price_height + gap
    macd_bottom = macd_top + macd_height

    def macd_y(value: float) -> float:
        center = (macd_top + macd_bottom) / 2
        scale = (macd_height * 0.42) / macd_abs_max
        return center - value * scale

    ts_to_index = {bar.ts: index for index, bar in enumerate(raw_bars)}
    svg_parts: list[str] = []
    svg_parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
    )
    svg_parts.append('<rect width="100%" height="100%" fill="#fbfcfe"/>')
    svg_parts.append(
        f'<text x="{width / 2:.1f}" y="34" text-anchor="middle" font-size="24" font-family="Segoe UI, Arial, sans-serif" fill="#1f2d3d">{_svg_escape(title)}</text>'
    )

    for step in range(6):
        price = min_price + (max_price - min_price) * step / 5
        y_value = price_y(price)
        svg_parts.append(
            f'<line x1="{left_margin}" y1="{y_value:.2f}" x2="{width - right_margin}" y2="{y_value:.2f}" stroke="#d9e2ec" stroke-dasharray="4 6" stroke-width="1"/>'
        )
        svg_parts.append(
            f'<text x="{left_margin - 10}" y="{y_value + 4:.2f}" text-anchor="end" font-size="11" font-family="Consolas, monospace" fill="#52606d">{price:.2f}</text>'
        )

    svg_parts.append(
        f'<line x1="{left_margin}" y1="{macd_top:.2f}" x2="{width - right_margin}" y2="{macd_top:.2f}" stroke="#cbd2d9" stroke-width="1"/>'
    )

    for row in normalized_rows:
        if len(row.src_indices) < 2:
            continue
        left = x_for(min(row.src_indices)) - slot_width * 0.5
        right = x_for(max(row.src_indices)) + slot_width * 0.5
        top = price_y(row.high)
        bottom = price_y(row.low)
        box_height = max(bottom - top, 1.0)
        svg_parts.append(
            f'<rect x="{left:.2f}" y="{top:.2f}" width="{right - left:.2f}" height="{box_height:.2f}" fill="#5dade2" fill-opacity="0.12" stroke="#1f618d" stroke-width="1.2" stroke-dasharray="6 4"/>'
        )

    for zs in zhongshus:
        start_index = ts_to_index.get(zs.start_ts)
        end_index = ts_to_index.get(zs.end_ts)
        if start_index is None or end_index is None:
            continue
        left = x_for(start_index) - slot_width * 0.5
        right = x_for(end_index) + slot_width * 0.5
        top = price_y(zs.zs_high)
        bottom = price_y(zs.zs_low)
        band_height = max(bottom - top, 1.0)
        svg_parts.append(
            f'<rect x="{left:.2f}" y="{top:.2f}" width="{right - left:.2f}" height="{band_height:.2f}" fill="#f5b041" fill-opacity="0.18" stroke="#b9770e" stroke-width="1.4"/>'
        )
        svg_parts.append(
            f'<text x="{left + 6:.2f}" y="{max(top - 6, 18):.2f}" font-size="11" font-family="Consolas, monospace" fill="#935116">ZS{zs.zs_id}</text>'
        )

    for index, bar in enumerate(raw_bars):
        color = "#c0392b" if bar.close >= bar.open else "#1f7a4d"
        x_value = x_for(index)
        wick_top = price_y(bar.high)
        wick_bottom = price_y(bar.low)
        body_top = price_y(max(bar.open, bar.close))
        body_bottom = price_y(min(bar.open, bar.close))
        body_height = max(body_bottom - body_top, 1.2)
        svg_parts.append(
            f'<line x1="{x_value:.2f}" y1="{wick_top:.2f}" x2="{x_value:.2f}" y2="{wick_bottom:.2f}" stroke="{color}" stroke-width="1.2"/>'
        )
        svg_parts.append(
            f'<rect x="{x_value - candle_width / 2:.2f}" y="{body_top:.2f}" width="{candle_width:.2f}" height="{body_height:.2f}" fill="{color}" stroke="{color}" stroke-width="0.8" fill-opacity="0.9"/>'
        )

    zero_y = macd_y(0.0)
    svg_parts.append(
        f'<line x1="{left_margin}" y1="{zero_y:.2f}" x2="{width - right_margin}" y2="{zero_y:.2f}" stroke="#94a3b8" stroke-dasharray="4 4" stroke-width="1"/>'
    )

    for step in (-1.0, -0.5, 0.5, 1.0):
        value = macd_abs_max * step
        y_value = macd_y(value)
        svg_parts.append(
            f'<line x1="{left_margin}" y1="{y_value:.2f}" x2="{width - right_margin}" y2="{y_value:.2f}" stroke="#e5e7eb" stroke-dasharray="3 5" stroke-width="1"/>'
        )
        svg_parts.append(
            f'<text x="{left_margin - 10}" y="{y_value + 4:.2f}" text-anchor="end" font-size="11" font-family="Consolas, monospace" fill="#52606d">{value:.2f}</text>'
        )

    if macd_points:
        dif_path: list[str] = []
        dea_path: list[str] = []
        hist_width = max(2.0, candle_width * 0.8)
        for index, point in enumerate(macd_points):
            x_value = x_for(index)
            hist_top = macd_y(max(point.macd, 0.0))
            hist_bottom = macd_y(min(point.macd, 0.0))
            hist_height = max(abs(hist_bottom - hist_top), 1.0)
            hist_y = min(hist_top, hist_bottom)
            hist_color = "#ef4444" if point.macd >= 0 else "#22c55e"
            svg_parts.append(
                f'<rect x="{x_value - hist_width / 2:.2f}" y="{hist_y:.2f}" width="{hist_width:.2f}" height="{hist_height:.2f}" fill="{hist_color}" fill-opacity="0.72"/>'
            )
            dif_path.append(f'{"M" if index == 0 else "L"}{x_value:.2f},{macd_y(point.dif):.2f}')
            dea_path.append(f'{"M" if index == 0 else "L"}{x_value:.2f},{macd_y(point.dea):.2f}')

        svg_parts.append(
            f'<path d="{" ".join(dif_path)}" fill="none" stroke="#2563eb" stroke-width="1.8"/>'
        )
        svg_parts.append(
            f'<path d="{" ".join(dea_path)}" fill="none" stroke="#f59e0b" stroke-width="1.8"/>'
        )

    svg_parts.append(
        f'<text x="{left_margin}" y="{macd_top - 8:.2f}" font-size="13" font-family="Segoe UI, Arial, sans-serif" fill="#334155">MACD (12, 26, 9)</text>'
    )

    fx_points: dict[int, tuple[int, float]] = {}
    for fx in fractals:
        x_value = ts_to_index.get(fx.ts)
        if x_value is None:
            continue
        fx_points[fx.fx_id] = (x_value, fx.price)
        if fx.fx_id not in confirmed_fx_ids:
            continue
        cx = x_for(x_value)
        cy = price_y(fx.price)
        color = "#e74c3c" if fx.is_top() else "#27ae60"
        if fx.is_top():
            points = [
                (cx - 7, cy - 10),
                (cx + 7, cy - 10),
                (cx, cy + 8),
            ]
        else:
            points = [
                (cx - 7, cy + 10),
                (cx + 7, cy + 10),
                (cx, cy - 8),
            ]
        points_text = " ".join(f"{px:.2f},{py:.2f}" for px, py in points)
        svg_parts.append(
            f'<polygon points="{points_text}" fill="{color}" stroke="{color}" stroke-width="1"/>'
        )

    for bi in bis:
        start = fx_points.get(bi.start_fx_id)
        end = fx_points.get(bi.end_fx_id)
        if start is None or end is None:
            continue
        color = "#2874a6" if bi.direction.value == "up" else "#d68910"
        dash = "" if bi.is_confirmed else ' stroke-dasharray="5 5"'
        linewidth = 2.2 if bi.is_confirmed else 1.5
        svg_parts.append(
            f'<line x1="{x_for(start[0]):.2f}" y1="{price_y(start[1]):.2f}" x2="{x_for(end[0]):.2f}" y2="{price_y(end[1]):.2f}" stroke="{color}" stroke-width="{linewidth}"{dash}/>'
        )

    tick_step = max(1, math.ceil(len(raw_bars) / 12))
    for index in range(0, len(raw_bars), tick_step):
        x_value = x_for(index)
        svg_parts.append(
            f'<line x1="{x_value:.2f}" y1="{macd_bottom:.2f}" x2="{x_value:.2f}" y2="{macd_bottom + 6:.2f}" stroke="#7b8794" stroke-width="1"/>'
        )
        svg_parts.append(
            f'<text x="{x_value:.2f}" y="{macd_bottom + 24:.2f}" text-anchor="middle" font-size="10" font-family="Consolas, monospace" fill="#52606d">{raw_bars[index].ts.strftime("%m-%d %H:%M")}</text>'
        )

    legend_x = width - 280
    legend_y = 74
    svg_parts.append(f'<rect x="{legend_x}" y="{legend_y}" width="240" height="146" rx="8" fill="#ffffff" stroke="#d9e2ec"/>')
    svg_parts.append(f'<rect x="{legend_x + 12}" y="{legend_y + 14}" width="22" height="12" fill="#5dade2" fill-opacity="0.12" stroke="#1f618d" stroke-dasharray="6 4"/>')
    svg_parts.append(f'<text x="{legend_x + 44}" y="{legend_y + 24}" font-size="12" font-family="Segoe UI, Arial, sans-serif" fill="#1f2d3d">Inclusion box</text>')
    svg_parts.append(f'<rect x="{legend_x + 12}" y="{legend_y + 34}" width="22" height="12" fill="#f5b041" fill-opacity="0.18" stroke="#b9770e"/>')
    svg_parts.append(f'<text x="{legend_x + 44}" y="{legend_y + 44}" font-size="12" font-family="Segoe UI, Arial, sans-serif" fill="#1f2d3d">Bi zhongshu</text>')
    svg_parts.append(f'<line x1="{legend_x + 12}" y1="{legend_y + 62}" x2="{legend_x + 34}" y2="{legend_y + 62}" stroke="#2874a6" stroke-width="2.2"/>')
    svg_parts.append(f'<text x="{legend_x + 44}" y="{legend_y + 66}" font-size="12" font-family="Segoe UI, Arial, sans-serif" fill="#1f2d3d">Confirmed bi</text>')
    svg_parts.append(f'<line x1="{legend_x + 12}" y1="{legend_y + 80}" x2="{legend_x + 34}" y2="{legend_y + 80}" stroke="#d68910" stroke-width="1.5" stroke-dasharray="5 5"/>')
    svg_parts.append(f'<text x="{legend_x + 44}" y="{legend_y + 84}" font-size="12" font-family="Segoe UI, Arial, sans-serif" fill="#1f2d3d">Unconfirmed bi</text>')
    svg_parts.append(f'<rect x="{legend_x + 12}" y="{legend_y + 96}" width="22" height="12" fill="#ef4444" fill-opacity="0.72"/>')
    svg_parts.append(f'<text x="{legend_x + 44}" y="{legend_y + 106}" font-size="12" font-family="Segoe UI, Arial, sans-serif" fill="#1f2d3d">MACD histogram+</text>')
    svg_parts.append(f'<rect x="{legend_x + 12}" y="{legend_y + 114}" width="22" height="12" fill="#22c55e" fill-opacity="0.72"/>')
    svg_parts.append(f'<text x="{legend_x + 44}" y="{legend_y + 124}" font-size="12" font-family="Segoe UI, Arial, sans-serif" fill="#1f2d3d">MACD histogram-</text>')
    svg_parts.append(f'<line x1="{legend_x + 12}" y1="{legend_y + 138}" x2="{legend_x + 34}" y2="{legend_y + 138}" stroke="#2563eb" stroke-width="1.8"/>')
    svg_parts.append(f'<text x="{legend_x + 44}" y="{legend_y + 142}" font-size="12" font-family="Segoe UI, Arial, sans-serif" fill="#1f2d3d">DIF / DEA</text>')

    svg_parts.append('</svg>')
    output_svg.parent.mkdir(parents=True, exist_ok=True)
    output_svg.write_text("\n".join(svg_parts), encoding="utf-8")


def main() -> None:
    args = parse_args()
    raw_path = Path(args.raw)
    normalized_path = Path(args.normalized)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_bars = read_raw_bars(raw_path)
    normalized_bars, normalized_rows = read_normalized_bars(normalized_path)

    fractals = identify_fractals(normalized_bars)
    fractals = filter_consecutive_fractals(fractals)
    bis = identify_bis(fractals, normalized_bars)
    zhongshus = identify_zhongshu([bi for bi in bis if bi.is_confirmed])
    macd_points = calculate_macd(raw_bars)

    confirmed_fx_ids: set[int] = set()
    for bi in bis:
        if bi.is_confirmed:
            confirmed_fx_ids.add(bi.start_fx_id)
            confirmed_fx_ids.add(bi.end_fx_id)

    unconfirmed_end_fx_ids = {bi.end_fx_id for bi in bis if not bi.is_confirmed}

    fractals_path = output_dir / f"{args.prefix}_fractals.csv"
    confirmed_fractals_path = output_dir / f"{args.prefix}_confirmed_fractals.csv"
    bis_path = output_dir / f"{args.prefix}_bis.csv"
    zhongshu_path = output_dir / f"{args.prefix}_zhongshu.csv"
    macd_path = output_dir / f"{args.prefix}_macd.csv"
    plot_path = output_dir / f"{args.prefix}_with_boxes.svg"

    export_fractals(fractals_path, normalized_bars, fractals, confirmed_fx_ids, unconfirmed_end_fx_ids)
    export_confirmed_fractals(confirmed_fractals_path, normalized_bars, fractals, confirmed_fx_ids)
    export_bis(bis_path, bis)
    export_zhongshus(zhongshu_path, zhongshus)
    export_macd(macd_path, macd_points)
    write_svg_with_inclusion_boxes(raw_bars, normalized_rows, fractals, confirmed_fx_ids, bis, zhongshus, macd_points, plot_path, args.title)

    print(f"标准化K线: {len(normalized_bars)} 根")
    print(f"分型总数: {len(fractals)}")
    print(f"笔总数: {len(bis)}")
    print(f"中枢总数: {len(zhongshus)}")
    print(f"分型已保存: {fractals_path}")
    print(f"确认分型已保存: {confirmed_fractals_path}")
    print(f"笔已保存: {bis_path}")
    print(f"中枢已保存: {zhongshu_path}")
    print(f"MACD已保存: {macd_path}")
    print(f"图像已保存: {plot_path}")


if __name__ == "__main__":
    main()