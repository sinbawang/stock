from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from chanlun.bi import identify_bis
from chanlun.data import read_bars_from_csv
from chanlun.data.cleaner import clean_bars
from chanlun.data.hk_minute_fetcher import fetch_hk_minute, save_to_csv
from chanlun.fractal import filter_consecutive_fractals, identify_fractals
from chanlun.models import Bar, Bi, Fractal, NormalizedBar, Zhongshu
from chanlun.normalize import normalize_bars
from chanlun.zhongshu import identify_zhongshu

from export_structures_with_boxes import (
    calculate_macd,
    export_bis,
    export_confirmed_fractals,
    export_fractals,
    export_macd,
    export_zhongshus,
    write_svg_with_inclusion_boxes,
)
from prepare_and_send_wechat_chart import make_sendable_jpg, render_svg
from send_wechat_native import send_message


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="一键执行港股 60M 缠论出图、分析并可选发送到微信")
    parser.add_argument("--symbol", required=True, help="港股代码，如 01339")
    parser.add_argument("--name", required=True, help="标的名称，如 中国人保")
    parser.add_argument("--start", default="2026-01-01 09:30", help="起始时间")
    parser.add_argument("--end", default=None, help="结束时间，默认到当前")
    parser.add_argument("--contact", default=None, help="微信联系人")
    parser.add_argument("--visible-row-index", type=int, default=None, help="微信当前可见会话第几行")
    parser.add_argument("--current-chat-only", action="store_true", help="只向当前已打开会话发送，不自动切换联系人")
    parser.add_argument("--result-index", type=int, default=1, help="微信搜索结果第几项")
    parser.add_argument("--render-only", action="store_true", help="仅抓取、分析、出图，不发微信")
    return parser.parse_args()


def write_normalized_csv(path: Path, rows: list[NormalizedBar]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "idx",
                "ts_start",
                "ts_end",
                "ts_high",
                "ts_low",
                "high",
                "low",
                "direction",
                "src_indices",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "idx": row.idx,
                    "ts_start": row.ts_start.strftime("%Y-%m-%d %H:%M"),
                    "ts_end": row.ts_end.strftime("%Y-%m-%d %H:%M"),
                    "ts_high": row.ts_high.strftime("%Y-%m-%d %H:%M"),
                    "ts_low": row.ts_low.strftime("%Y-%m-%d %H:%M"),
                    "high": row.high,
                    "low": row.low,
                    "direction": row.direction or "",
                    "src_indices": ",".join(str(index) for index in row.src_indices),
                }
            )


def build_paths(symbol: str, name: str, bars: list[dict]) -> dict[str, Path]:
    first_day = bars[0]["ts"][0:10].replace("-", "")
    last_day = bars[-1]["ts"][0:10].replace("-", "")
    base_dir = ROOT / "data" / f"{symbol}_{name}" / "60m"
    base_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{symbol}_60m_{first_day}_to_{last_day}"
    prefix = f"{stem}_normalized"
    return {
        "base_dir": base_dir,
        "raw_csv": base_dir / f"{stem}.csv",
        "normalized_csv": base_dir / f"{stem}_normalized.csv",
        "svg": base_dir / f"{prefix}_with_boxes.svg",
        "png": base_dir / f"{prefix}_full.png",
        "jpg": base_dir / f"{prefix}_wechat.jpg",
        "prefix": base_dir / prefix,
    }


def compute_bi_strengths(bis: list[Bi], macd_points: list[Any]) -> dict[int, dict[str, float]]:
    strengths: dict[int, dict[str, float]] = {}
    for bi in bis:
        segment = [point for point in macd_points if bi.start_ts <= point.ts <= bi.end_ts]
        if not segment:
            continue
        strengths[bi.bi_id] = {
            "macd_sum_abs": sum(abs(point.macd) for point in segment),
            "dif_max": max(point.dif for point in segment),
            "dif_min": min(point.dif for point in segment),
        }
    return strengths


def analyze_current_state(
    instrument_name: str,
    raw_bars: list[Bar],
    bis: list[Bi],
    zhongshus: list[Zhongshu],
    macd_points: list[Any],
) -> str:
    confirmed_bis = [bi for bi in bis if bi.is_confirmed]
    strengths = compute_bi_strengths(bis, macd_points)
    latest_confirmed_up = next((bi for bi in reversed(confirmed_bis) if bi.is_up()), None)
    previous_confirmed_up = None
    if latest_confirmed_up is not None:
        seen_latest = False
        for bi in reversed(confirmed_bis):
            if bi.bi_id == latest_confirmed_up.bi_id:
                seen_latest = True
                continue
            if seen_latest and bi.is_up():
                previous_confirmed_up = bi
                break

    latest_down = next((bi for bi in reversed(bis) if bi.is_down()), None)
    top_divergence = False
    if latest_confirmed_up and previous_confirmed_up:
        last_strength = strengths.get(latest_confirmed_up.bi_id, {})
        prev_strength = strengths.get(previous_confirmed_up.bi_id, {})
        top_divergence = (
            latest_confirmed_up.high > previous_confirmed_up.high
            and last_strength.get("macd_sum_abs", 0.0) < prev_strength.get("macd_sum_abs", 0.0)
        )

    bottom_divergence = False
    previous_confirmed_down = next((bi for bi in reversed(confirmed_bis) if bi.is_down()), None)
    if latest_down and previous_confirmed_down and latest_down.bi_id != previous_confirmed_down.bi_id:
        last_strength = strengths.get(latest_down.bi_id, {})
        prev_strength = strengths.get(previous_confirmed_down.bi_id, {})
        bottom_divergence = (
            latest_down.low < previous_confirmed_down.low
            and last_strength.get("macd_sum_abs", 0.0) < prev_strength.get("macd_sum_abs", 0.0)
        )

    current_zs = zhongshus[-1] if zhongshus else None
    buy_points: list[str] = []
    sell_points: list[str] = []
    if current_zs and latest_down and bottom_divergence and latest_down.low <= current_zs.zs_low:
        buy_points.append("buy_1")
    if current_zs and latest_confirmed_up and top_divergence and latest_confirmed_up.high >= current_zs.zs_high:
        sell_points.append("sell_1")
    if current_zs and latest_confirmed_up and latest_confirmed_up.high > current_zs.zs_high and latest_down and latest_down.low >= current_zs.zs_high:
        buy_points.append("buy_3")
    if current_zs and latest_down and latest_down.low < current_zs.zs_low and latest_confirmed_up and latest_confirmed_up.high <= current_zs.zs_low:
        sell_points.append("sell_3")

    actual_start = raw_bars[0].ts.strftime("%Y-%m-%d %H:%M")
    actual_end = raw_bars[-1].ts.strftime("%Y-%m-%d %H:%M")
    overview_lines = [
        f"时间区间：{actual_start} 到 {actual_end}",
        f"K线数量：共 {len(raw_bars)} 根 60M K线",
        f"中枢数量：当前识别到 {len(zhongshus)} 个中枢",
    ]
    if current_zs:
        overview_lines.append(
            f"最新中枢：{current_zs.zs_low:.2f}-{current_zs.zs_high:.2f}，覆盖 {current_zs.start_ts.strftime('%m-%d %H:%M')} 到 {current_zs.end_ts.strftime('%m-%d %H:%M')}"
        )

    structure_lines: list[str] = []
    if latest_confirmed_up:
        structure_lines.append(
            f"最新确认向上笔：{latest_confirmed_up.start_ts.strftime('%m-%d %H:%M')} 到 {latest_confirmed_up.end_ts.strftime('%m-%d %H:%M')}，高点 {latest_confirmed_up.high:.2f}"
        )
    if latest_down:
        label = "未确认向下笔" if not latest_down.is_confirmed else "最新确认向下笔"
        structure_lines.append(
            f"{label}：{latest_down.start_ts.strftime('%m-%d %H:%M')} 到 {latest_down.end_ts.strftime('%m-%d %H:%M')}，低点 {latest_down.low:.2f}"
        )

    signal_lines = [
        "顶背驰：有" if top_divergence else "顶背驰：无",
        "底背驰：有" if bottom_divergence else "底背驰：无",
        f"买点：{', '.join(buy_points)}" if buy_points else "买点：当前无确认一二三类买点",
        f"卖点：{', '.join(sell_points)}" if sell_points else "卖点：当前无确认一二三类卖点",
    ]

    focus_lines: list[str] = []
    if current_zs:
        focus_lines.append(
            f"观察重点：是否重新站回中枢 {current_zs.zs_low:.2f}-{current_zs.zs_high:.2f}，以及后续一笔是否形成有效突破"
        )

    sections = [
        f"【{instrument_name} 60M 缠论观察】",
        "",
        "概览：",
        *[f"- {line}" for line in overview_lines],
    ]
    if structure_lines:
        sections.extend([
            "",
            "结构：",
            *[f"- {line}" for line in structure_lines],
        ])
    sections.extend([
        "",
        "信号：",
        *[f"- {line}" for line in signal_lines],
    ])
    if focus_lines:
        sections.extend([
            "",
            "观察重点：",
            *[f"- {line}" for line in focus_lines],
        ])
    return "\n".join(sections)


def main() -> None:
    args = parse_args()
    rows = fetch_hk_minute(args.symbol, period="60", start=args.start, end=args.end, adjust="qfq")
    if not rows:
        raise RuntimeError("未抓到任何60M数据")

    paths = build_paths(args.symbol, args.name, rows)
    save_to_csv(rows, str(paths["raw_csv"]))

    raw_bars = clean_bars(read_bars_from_csv(str(paths["raw_csv"])))
    normalized_bars = normalize_bars(raw_bars)
    write_normalized_csv(paths["normalized_csv"], normalized_bars)

    fractals = filter_consecutive_fractals(identify_fractals(normalized_bars))
    bis = identify_bis(fractals, normalized_bars)
    confirmed_bis = [bi for bi in bis if bi.is_confirmed]
    zhongshus = identify_zhongshu(confirmed_bis)
    macd_points = calculate_macd(raw_bars)

    confirmed_fx_ids: set[int] = set()
    for bi in bis:
        if bi.is_confirmed:
            confirmed_fx_ids.add(bi.start_fx_id)
            confirmed_fx_ids.add(bi.end_fx_id)
    unconfirmed_end_fx_ids = {bi.end_fx_id for bi in bis if not bi.is_confirmed}

    prefix_name = paths["prefix"].name
    export_fractals(paths["base_dir"] / f"{prefix_name}_fractals.csv", normalized_bars, fractals, confirmed_fx_ids, unconfirmed_end_fx_ids)
    export_confirmed_fractals(paths["base_dir"] / f"{prefix_name}_confirmed_fractals.csv", normalized_bars, fractals, confirmed_fx_ids)
    export_bis(paths["base_dir"] / f"{prefix_name}_bis.csv", bis)
    export_zhongshus(paths["base_dir"] / f"{prefix_name}_zhongshu.csv", zhongshus)
    export_macd(paths["base_dir"] / f"{prefix_name}_macd.csv", macd_points)
    write_svg_with_inclusion_boxes(
        raw_bars,
        [
            type("NormalizedCsvRowShim", (), {
                "idx": bar.idx,
                "ts_start": bar.ts_start,
                "ts_end": bar.ts_end,
                "ts_high": bar.ts_high,
                "ts_low": bar.ts_low,
                "high": bar.high,
                "low": bar.low,
                "direction": bar.direction or "",
                "src_indices": bar.src_indices,
            })()
            for bar in normalized_bars
        ],
        fractals,
        confirmed_fx_ids,
        bis,
        zhongshus,
        macd_points,
        paths["svg"],
        f"{args.symbol} {args.name} 60m",
    )

    render_svg(paths["svg"], paths["png"])
    make_sendable_jpg(paths["png"], paths["jpg"])
    analysis_text = analyze_current_state(args.name, raw_bars, bis, zhongshus, macd_points)

    print(f"原始 CSV: {paths['raw_csv']}")
    print(f"标准化 CSV: {paths['normalized_csv']}")
    print(f"结构图 SVG: {paths['svg']}")
    print(f"完整 PNG: {paths['png']}")
    print(f"微信 JPG: {paths['jpg']}")
    print(f"分析文本: {analysis_text}")

    if args.render_only:
        return
    if not args.contact:
        raise ValueError("非 render-only 模式必须提供 --contact")
    if not args.current_chat_only and args.visible_row_index is None:
        raise ValueError("默认禁止自动切会话。请先手动打开目标聊天并使用 --current-chat-only，或明确提供 --visible-row-index。")

    send_message(
        args.contact,
        message=analysis_text,
        result_index=args.result_index,
        visible_row_index=args.visible_row_index,
        filepaths=None,
        current_chat_only=args.current_chat_only,
    )
    send_message(
        args.contact,
        message=None,
        result_index=args.result_index,
        visible_row_index=args.visible_row_index,
        filepaths=[str(paths["jpg"])],
        current_chat_only=args.current_chat_only,
    )


if __name__ == "__main__":
    main()