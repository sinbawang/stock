from __future__ import annotations

import argparse
import csv
from datetime import datetime
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from chanlun.bi import identify_bis
from chanlun.default_ranges import default_structure_start
from chanlun.data import read_bars_from_csv
from chanlun.data.cleaner import clean_bars
from chanlun.data.hk_minute_fetcher import fetch_hk_minute_with_policy, get_last_fetch_metadata, save_to_csv
from chanlun.data.source_profiles import available_source_profiles, resolve_hk_minute_source_selection
from chanlun.fractal import filter_consecutive_fractals, identify_fractals
from chanlun.models import Bar, Bi, Fractal, NormalizedBar, Zhongshu
from chanlun.normalize import normalize_bars
from chanlun.segment import identify_segments
from chanlun.zhongshu import identify_zhongshu
from chanlun.chart_export import save_structure_charts

from export_structures_with_boxes import (
    calculate_macd,
    export_bis,
    export_confirmed_fractals,
    export_fractals,
    format_zhongshu_structure_text,
    export_macd,
    export_segments,
    serialize_zhongshu,
    serialize_zhongshus,
    export_zhongshus,
)
from report_json import write_json
from send_wechat_current_chat_bundle import send_current_chat_bundle
from send_wechat_native import send_message
from storage_layout import timeframe_report_paths

INTRADAY_SOURCE_PROBE_ROWS = 600
BAR_COUNT_POLICY = "feasible_maximum"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="一键执行港股 60M 缠论出图、分析并可选发送到微信")
    parser.add_argument("--symbol", required=True, help="港股代码，如 01339")
    parser.add_argument("--name", required=True, help="标的名称，如 中国人保")
    parser.add_argument("--start", default=default_structure_start("60m"), help="起始时间")
    parser.add_argument("--end", default=None, help="结束时间，默认到当前")
    parser.add_argument("--adjust", default="", choices=["qfq", "hfq", ""], help="复权方式，默认不复权")
    parser.add_argument("--source-profile", default=None, choices=available_source_profiles(), help="港股分钟线数据源配置；默认读取 CHANLUN_SOURCE_PROFILE 或 mainland")
    parser.add_argument("--source", default=None, choices=["xueqiu", "akshare"], help="港股分钟数据源；默认跟随 source profile")
    parser.add_argument("--fallback-source", action="append", choices=["xueqiu", "akshare"], default=None, help="显式允许的回退数据源，可重复指定；默认跟随 source profile")
    parser.add_argument("--contact", default=None, help="微信联系人")
    parser.add_argument("--visible-row-index", type=int, default=None, help="微信当前可见会话第几行")
    parser.add_argument("--current-chat-only", action="store_true", help="只向当前已打开会话发送，不自动切换联系人")
    parser.add_argument("--allow-search-switch", action="store_true", help="允许按联系人/群名搜索并切换会话")
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
    layout = timeframe_report_paths(symbol, "60m", bars)
    return {
        "base_dir": layout.root_dir,
        "analyze_dir": layout.analyze_dir,
        "raw_csv": layout.raw_csv,
        "normalized_csv": layout.normalized_csv,
        "fractals_csv": layout.fractals_csv,
        "confirmed_fractals_csv": layout.confirmed_fractals_csv,
        "bis_csv": layout.bis_csv,
        "segments_csv": layout.segments_csv,
        "zhongshu_csv": layout.zhongshu_csv,
        "macd_csv": layout.macd_csv,
        "svg": layout.chart_svg,
        "png": layout.chart_png,
        "jpg": layout.chart_jpg,
        "prefix": Path(layout.stem + "_normalized"),
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
    if current_zs:
        structure_lines.append(f"最新中枢结构：{format_zhongshu_structure_text(current_zs)}")

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


def _extract_prefixed_value(text: str, prefix: str) -> str | None:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    return None


def write_technical_report_json(
    *,
    path: Path,
    symbol: str,
    name: str,
    timeframe: str,
    source: str,
    actual_source: str,
    source_attempts: list[dict[str, object]],
    analysis_text: str,
    advice_text: str,
    raw_csv: Path,
    normalized_csv: Path,
    chart_svg: Path,
    chart_png: Path,
    chart_jpg: Path,
    fractal_count: int,
    bi_count: int,
    confirmed_bi_count: int,
    zhongshu_count: int,
    actual_bar_count: int,
    requested_min_rows: int | None,
    zhongshus: list[Zhongshu],
) -> Path:
    latest_zhongshu = serialize_zhongshu(zhongshus[-1]) if zhongshus else None
    return write_json(
        path,
        {
            "report_type": "technical",
            "symbol": symbol,
            "name": name,
            "timeframe": timeframe,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source": source,
            "source_actual": actual_source,
            "data_fetch": {
                "source": source,
                "actual_source": actual_source,
                "source_attempts": source_attempts,
                "actual_bar_count": actual_bar_count,
                "requested_min_rows": requested_min_rows,
                "fulfilled_min_rows": actual_bar_count >= requested_min_rows if requested_min_rows is not None else None,
                "bar_count_policy": BAR_COUNT_POLICY,
                "source_probe_min_rows": INTRADAY_SOURCE_PROBE_ROWS,
            },
            "structure": {
                "latest_zhongshu": latest_zhongshu,
                "zhongshus": serialize_zhongshus(zhongshus),
            },
            "summary": {
                "conclusion": _extract_prefixed_value(advice_text, "结论："),
                "suggestion": _extract_prefixed_value(advice_text, "建议："),
            },
            "analysis_text": analysis_text,
            "advice_text": advice_text,
            "artifacts": {
                "raw_csv": raw_csv,
                "normalized_csv": normalized_csv,
                "structure_svg": chart_svg,
                "structure_png": chart_png,
                "structure_jpg": chart_jpg,
            },
            "stats": {
                "fractals": fractal_count,
                "bis": bi_count,
                "confirmed_bis": confirmed_bi_count,
                "zhongshus": zhongshu_count,
            },
        },
    )


def main() -> None:
    args = parse_args()
    primary_source, fallback_sources, _ = resolve_hk_minute_source_selection(
        primary_source=args.source,
        fallback_sources=tuple(args.fallback_source) if args.fallback_source else None,
        source_profile=args.source_profile,
    )
    rows, used_source = fetch_hk_minute_with_policy(
        args.symbol,
        period="60",
        start=args.start,
        end=args.end,
        adjust=args.adjust,
        primary_source=primary_source,
        fallback_sources=fallback_sources,
        min_rows=INTRADAY_SOURCE_PROBE_ROWS,
    )
    fetch_meta = get_last_fetch_metadata()
    actual_source = str(fetch_meta.get("actual_source") or used_source)
    if not rows:
        raise RuntimeError("未抓到任何60M数据")

    paths = build_paths(args.symbol, args.name, rows)
    save_to_csv(rows, str(paths["raw_csv"]))

    raw_bars = clean_bars(read_bars_from_csv(str(paths["raw_csv"])))
    normalized_bars = normalize_bars(raw_bars)
    write_normalized_csv(paths["normalized_csv"], normalized_bars)

    fractals = filter_consecutive_fractals(identify_fractals(normalized_bars))
    bis = identify_bis(fractals, normalized_bars)
    segments = identify_segments(bis)
    confirmed_bis = [bi for bi in bis if bi.is_confirmed]
    zhongshus = identify_zhongshu(confirmed_bis)
    macd_points = calculate_macd(raw_bars)

    confirmed_fx_ids: set[int] = set()
    for bi in bis:
        if bi.is_confirmed:
            confirmed_fx_ids.add(bi.start_fx_id)
            confirmed_fx_ids.add(bi.end_fx_id)
    unconfirmed_end_fx_ids = {bi.end_fx_id for bi in bis if not bi.is_confirmed}

    export_fractals(paths["fractals_csv"], normalized_bars, fractals, confirmed_fx_ids, unconfirmed_end_fx_ids)
    export_confirmed_fractals(paths["confirmed_fractals_csv"], normalized_bars, fractals, confirmed_fx_ids)
    export_bis(paths["bis_csv"], bis)
    export_segments(paths["segments_csv"], segments)
    export_zhongshus(paths["zhongshu_csv"], zhongshus)
    export_macd(paths["macd_csv"], macd_points)
    save_structure_charts(
        bars=raw_bars,
        normalized_bars=normalized_bars,
        fractals=fractals,
        bis=bis,
        zhongshus=zhongshus,
        svg_path=paths["svg"],
        png_path=paths["png"],
        jpg_path=paths["jpg"],
        title=f"{args.symbol} {args.name} 60m",
    )
    analysis_text = analyze_current_state(args.name, raw_bars, bis, zhongshus, macd_points)
    advice_text = ""
    technical_report_path = write_technical_report_json(
        path=paths["base_dir"] / "tech.json",
        symbol=args.symbol,
        name=args.name,
        timeframe="60m",
        source=used_source,
        actual_source=actual_source,
        source_attempts=list(fetch_meta.get("source_attempts") or []),
        analysis_text=analysis_text,
        advice_text=advice_text,
        raw_csv=paths["raw_csv"],
        normalized_csv=paths["normalized_csv"],
        chart_svg=paths["svg"],
        chart_png=paths["png"],
        chart_jpg=paths["jpg"],
        fractal_count=len(fractals),
        bi_count=len(bis),
        confirmed_bi_count=len(confirmed_bis),
        zhongshu_count=len(zhongshus),
        actual_bar_count=len(raw_bars),
        requested_min_rows=None,
        zhongshus=zhongshus,
    )

    print(f"原始 CSV: {paths['raw_csv']}")
    print(f"分钟数据源: {used_source}")
    print(f"实际K线数量: {len(raw_bars)}")
    print(f"标准化 CSV: {paths['normalized_csv']}")
    print(f"结构图 SVG: {paths['svg']}")
    print(f"完整 PNG: {paths['png']}")
    print(f"微信 JPG: {paths['jpg']}")
    print(f"技术报告 JSON: {technical_report_path}")
    print(f"分析文本: {analysis_text}")

    if args.render_only:
        return
    if not args.contact:
        raise ValueError("非 render-only 模式必须提供 --contact")
    if not args.current_chat_only and args.visible_row_index is None and not args.allow_search_switch:
        raise ValueError("默认禁止自动切会话。请先手动打开目标聊天并使用 --current-chat-only，或明确提供 --visible-row-index。")

    if args.current_chat_only:
        message_file = paths["base_dir"] / f"{paths['prefix'].name}_wechat_message.txt"
        message_file.write_text(analysis_text, encoding="utf-8")
        send_current_chat_bundle(
            message_file=message_file,
            files=[paths["jpg"]],
        )
        return

    send_message(
        args.contact,
        message=analysis_text,
        result_index=args.result_index,
        visible_row_index=args.visible_row_index,
        filepaths=[str(paths["jpg"])],
        current_chat_only=args.current_chat_only,
        allow_search_switch=args.allow_search_switch,
    )


if __name__ == "__main__":
    main()