from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from report_retention import prune_older_outputs

from chanlun.analysis import (
    analyze_chanlun_signals,
    build_signal_explanation_lines,
    build_signal_summary_fields,
    format_signal_point_labels,
)
from chanlun.bi import identify_bis
from chanlun.chart_export import save_structure_charts
from chanlun.default_ranges import (
    default_day_start_for_bar_target,
    default_intraday_start_for_bar_target,
    default_structure_start,
)
from chanlun.data import read_bars_from_csv
from chanlun.data.cleaner import clean_bars
from chanlun.data.hk_fetcher import fetch_hk_daily, save_to_csv as save_hk_daily_csv
from chanlun.data.hk_minute_fetcher import fetch_hk_minute_with_policy, get_last_fetch_metadata as get_last_hk_fetch_metadata, save_to_csv as save_hk_minute_csv
from chanlun.data.kline_fetcher import fetch_kline, get_last_fetch_metadata, save_to_csv as save_kline_csv
from chanlun.data.source_profiles import describe_source_chain, resolve_a_share_intraday_source_label, resolve_hk_minute_source_selection
from chanlun.fractal import filter_consecutive_fractals, identify_fractals
from chanlun.normalize import normalize_bars
from chanlun.segment import identify_segments
from chanlun.zhongshu import identify_zhongshu

from export_structures_with_boxes import (
    calculate_macd,
    export_bis,
    export_confirmed_fractals,
    export_fractals,
    export_macd,
    export_segments,
    format_zhongshu_structure_text,
    serialize_zhongshu,
    serialize_zhongshus,
    export_zhongshus,
)
from report_json import write_json
from run_hk_60m_chanlun_report import analyze_current_state, compute_bi_strengths, write_normalized_csv
from storage_layout import REPORTS_DIR, REPORTS_META_DIR, holdings_file, stock_report_dir, timeframe_report_paths


@dataclass(frozen=True)
class Security:
    symbol: str
    name: str
    market: str


SECURITIES = [
    Security("03690", "美团", "HK"),
    Security("01339", "中国人保", "HK"),
    Security("300124", "汇川技术", "A"),
    Security("00728", "中国电信", "HK"),
    Security("000591", "太阳能", "A"),
    Security("02357", "中航科工", "HK"),
    Security("002555", "三七互娱", "A"),
    Security("01024", "快手", "HK"),
    Security("00700", "腾讯", "HK"),
    Security("00981", "中芯国际", "HK"),
]

DEFAULT_HOLDINGS_FILE = holdings_file()
INTRADAY_SOURCE_PROBE_ROWS = 600
BAR_COUNT_POLICY = "feasible_maximum"
HK_REUSABLE_5M_MIN_ROWS = 480
INTRADAY_TIMEFRAME_SPECS = (
    ("60m", "60", "60M"),
    ("30m", "30", "30M"),
    ("15m", "15", "15M"),
    ("5m", "5", "5M"),
)


@dataclass(frozen=True)
class BatchPrepareResult:
    security_count: int
    selected_timeframes: tuple[str, ...]
    manifest_path: Path
    summary_path: Path | None


def timeframe_display_label(timeframe: str) -> str:
    normalized = timeframe.strip().lower()
    if normalized == "day":
        return "日线"
    return normalized.upper()


def _data_fetch_payload(
    source: str,
    rows: list[dict],
    requested_min_rows: int | None,
    *,
    actual_source: str | None = None,
    source_attempts: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    actual_bar_count = len(rows)
    return {
        "source": source,
        "actual_source": actual_source or source,
        "source_attempts": source_attempts or [],
        "actual_bar_count": actual_bar_count,
        "requested_min_rows": requested_min_rows,
        "fulfilled_min_rows": actual_bar_count >= requested_min_rows if requested_min_rows is not None else None,
        "bar_count_policy": BAR_COUNT_POLICY,
        "source_probe_min_rows": INTRADAY_SOURCE_PROBE_ROWS if requested_min_rows is None else requested_min_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量生成最新日线、60M、30M、15M、5M 缠论图、分析文本、操作建议")
    parser.add_argument("--day-start", default=None, help="日线起始日期；未指定时按日线根数自动回推")
    parser.add_argument("--day-bars", type=int, default=600, help="日线抓取目标根数，默认 600")
    parser.add_argument("--m60-start", default=None, help="60M 起始时间；未指定时按 60M 根数自动回推")
    parser.add_argument("--m60-bars", type=int, default=INTRADAY_SOURCE_PROBE_ROWS, help="60M 抓取目标根数，默认 600")
    parser.add_argument("--m30-start", default=None, help="30M 起始时间；未指定时按 30M 根数自动回推")
    parser.add_argument("--m30-bars", type=int, default=INTRADAY_SOURCE_PROBE_ROWS, help="30M 抓取目标根数，默认 600")
    parser.add_argument("--m15-start", default=None, help="15M 起始时间；未指定时按 15M 根数自动回推")
    parser.add_argument("--m15-bars", type=int, default=INTRADAY_SOURCE_PROBE_ROWS, help="15M 抓取目标根数，默认 600")
    parser.add_argument("--m5-start", default=None, help="5M 起始时间；未指定时按 5M 根数自动回推")
    parser.add_argument("--m5-bars", type=int, default=INTRADAY_SOURCE_PROBE_ROWS, help="5M 抓取目标根数，默认 600")
    parser.add_argument(
        "--holdings-file",
        default=str(DEFAULT_HOLDINGS_FILE),
        help="持仓清单 JSON 文件，默认读取 data/stock_holdings.json；不存在时回退到脚本内置名单。",
    )
    parser.add_argument(
        "--pending-reverse-mode",
        choices=("any", "effective_only", "tail_mixed"),
        default="any",
        help="笔尾部反向分型占位口径：any=当前保守口径，effective_only=全局仅允许满足间隔的反向分型占位，tail_mixed=仅对最后未确认尾笔链路启用 effective_only。",
    )
    parser.add_argument(
        "--zhongshu-level",
        choices=("bi", "segment"),
        default="bi",
        help="中枢绘制层级：bi=笔中枢，segment=线段中枢。",
    )
    parser.add_argument(
        "--timeframes",
        nargs="+",
        choices=("day", "60m", "30m", "15m", "5m"),
        default=["day", "60m", "30m", "15m", "5m"],
        help="需要生成的技术级别；默认全部生成。",
    )
    return parser.parse_args()


def _market_code_to_security_market(market_code: str, symbol: str) -> str:
    if market_code == "HK":
        return "HK"
    if market_code == "CN":
        return "A"
    return "HK" if len(symbol) == 5 else "A"


def load_securities(holdings_file: Path | None = None) -> list[Security]:
    holdings_path = holdings_file or DEFAULT_HOLDINGS_FILE
    if not holdings_path.exists():
        return SECURITIES

    payload = json.loads(holdings_path.read_text(encoding="utf-8"))
    raw_entries: list[tuple[str | None, dict]] = []
    markets = payload.get("markets")
    if isinstance(markets, dict):
        for market_code, market_holdings in markets.items():
            if not isinstance(market_holdings, list):
                continue
            raw_entries.extend((market_code, entry) for entry in market_holdings if isinstance(entry, dict))
    else:
        for entry in payload.get("holdings", []):
            if isinstance(entry, dict):
                raw_entries.append((payload.get("market"), entry))

    dedup: dict[str, Security] = {}
    for market_code, entry in raw_entries:
        symbol = str(entry.get("symbol") or "").strip()
        name = str(entry.get("name") or "").strip()
        if not symbol or not name:
            continue
        dedup[f"{symbol}:{name}"] = Security(
            symbol=symbol,
            name=name,
            market=_market_code_to_security_market(str(market_code or "").upper(), symbol),
        )
    return list(dedup.values()) or SECURITIES


def fetch_day_rows(security: Security, start: str, day_bars: int) -> tuple[list[dict], dict[str, object]]:
    if security.market == "HK":
        rows = fetch_hk_daily(security.symbol, start=start, limit=day_bars)
        return rows, _data_fetch_payload("tencent.hk_daily", rows, day_bars)
    rows = fetch_kline(security.symbol, start=start, interval="day", limit=day_bars)
    return rows, _data_fetch_payload("tencent.day", rows, day_bars)


def fetch_m60_rows(security: Security, start: str, m60_bars: int) -> tuple[list[dict], dict[str, object]]:
    return fetch_intraday_rows(security, timeframe="60m", period="60", start=start, bar_count=m60_bars)


def fetch_intraday_rows(
    security: Security,
    *,
    timeframe: str,
    period: str,
    start: str,
    bar_count: int,
) -> tuple[list[dict], dict[str, object]]:
    interval = f"m{period}"
    if security.market == "HK":
        if timeframe == "5m":
            reused_rows = _load_reusable_hk_intraday_rows(security, timeframe, min(bar_count, HK_REUSABLE_5M_MIN_ROWS))
            if reused_rows is not None:
                return reused_rows, _data_fetch_payload("local.hk_5m_cache", reused_rows, bar_count, actual_source="local.hk_5m_cache")
        primary_source, fallback_sources, _ = resolve_hk_minute_source_selection()
        rows, _ = fetch_hk_minute_with_policy(
            security.symbol,
            period=period,
            start=start,
            adjust="",
            primary_source=primary_source,
            fallback_sources=fallback_sources,
            min_rows=bar_count,
        )
        fetch_meta = get_last_hk_fetch_metadata()
        return rows, _data_fetch_payload(
            describe_source_chain(primary_source, fallback_sources),
            rows,
            bar_count,
            actual_source=str(fetch_meta.get("actual_source") or primary_source),
            source_attempts=list(fetch_meta.get("source_attempts") or []),
        )
    fetch_source, _ = resolve_a_share_intraday_source_label()
    rows = fetch_kline(security.symbol, start=start, interval=interval, limit=bar_count, min_rows=bar_count)
    fetch_meta = get_last_fetch_metadata()
    return rows, _data_fetch_payload(
        fetch_source,
        rows,
        bar_count,
        actual_source=str(fetch_meta.get("actual_source") or fetch_source),
        source_attempts=list(fetch_meta.get("source_attempts") or []),
    )


def _load_reusable_hk_intraday_rows(security: Security, timeframe: str, min_rows: int) -> list[dict] | None:
    analyze_dir = stock_report_dir(security.symbol) / timeframe / "analyze"
    if not analyze_dir.exists():
        return None

    candidates = [
        path
        for path in analyze_dir.glob(f"{security.symbol}_{timeframe}_*.csv")
        if "_normalized" not in path.name
    ]
    if not candidates:
        return None

    latest_path = max(candidates, key=lambda item: item.stat().st_mtime)
    with latest_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [
            {
                "ts": str(row.get("ts") or "").strip(),
                "open": float(row.get("open") or 0),
                "high": float(row.get("high") or 0),
                "low": float(row.get("low") or 0),
                "close": float(row.get("close") or 0),
                "volume": int(float(row.get("volume") or 0)),
            }
            for row in reader
            if str(row.get("ts") or "").strip()
        ]
    if len(rows) < min_rows:
        return None
    return rows


def fetch_m15_rows(security: Security, start: str, m15_bars: int) -> tuple[list[dict], dict[str, object]]:
    return fetch_intraday_rows(security, timeframe="15m", period="15", start=start, bar_count=m15_bars)


def save_rows(security: Security, timeframe: str, rows: list[dict], path: Path) -> None:
    if timeframe == "day":
        if security.market == "HK":
            save_hk_daily_csv(rows, str(path))
        else:
            save_kline_csv(rows, str(path))
        return

    if security.market == "HK":
        save_hk_minute_csv(rows, str(path))
    else:
        save_kline_csv(rows, str(path))


def extract_signals(bis, zhongshus, macd_points, *, raw_bars=None) -> dict[str, object]:
    return analyze_chanlun_signals(raw_bars or [], bis, zhongshus, macd_points)


def _clamp_score(value: int | float) -> int:
    return max(0, min(100, int(round(value))))


def _technical_rating(score: int) -> str:
    if score >= 80:
        return "A"
    if score >= 65:
        return "B"
    if score >= 45:
        return "C"
    return "D"


def _technical_bias(conclusion: str | None) -> str | None:
    text = (conclusion or "").strip()
    for prefix in ("偏多", "偏强", "震荡", "偏弱", "偏空"):
        if text.startswith(prefix):
            return prefix
    return text.split("，", 1)[0] if text else None


def _score_structure_component(signals: dict[str, object]) -> int:
    structure_state = signals.get("structure_state") or {}
    ongoing = structure_state.get("current_ongoing") or {}
    ongoing_type = ongoing.get("type")
    score = 10
    if ongoing_type in {"up", "down"}:
        score = 20
    elif ongoing_type == "range":
        score = 14
    if signals.get("current_zs") is not None:
        score += 6
    relationship_kind = ((structure_state.get("relationship") or {}).get("kind") or "").strip()
    if relationship_kind and relationship_kind != "undetermined":
        score += 4
    if signals.get("buy_points") or signals.get("sell_points"):
        score += 2
    return min(score, 30)


def _score_location_component(raw_bars, signals: dict[str, object]) -> int:
    current_zs = signals.get("current_zs")
    close_price = getattr(raw_bars[-1], "close", None) if raw_bars else None
    if current_zs is None or close_price is None:
        return 10
    if signals.get("buy_points"):
        return 18
    if signals.get("sell_points"):
        return 17
    if close_price >= current_zs.zs_high:
        return 15
    if close_price <= current_zs.zs_low:
        return 7
    return 11


def _score_signal_component(signals: dict[str, object]) -> int:
    active_points = [str(point) for point in [*(signals.get("buy_points") or []), *(signals.get("sell_points") or [])]]
    if not active_points:
        return 10
    strength_map = {
        "buy_1": 20,
        "buy_2": 22,
        "buy_3": 18,
        "sell_1": 20,
        "sell_2": 22,
        "sell_3": 18,
    }
    return max(strength_map.get(point, 10) for point in active_points)


def _score_divergence_component(signals: dict[str, object]) -> int:
    divergence = signals.get("divergence") or {}
    if (divergence.get("trend") or {}).get("active"):
        return 15
    if (divergence.get("range") or {}).get("active"):
        return 11
    if (divergence.get("top") or {}).get("active") or (divergence.get("bottom") or {}).get("active"):
        return 8
    return 4


def _score_execution_component(precision_entry: dict[str, object] | None) -> int:
    if not precision_entry:
        return 0
    if precision_entry.get("status") == "actionable":
        return 10
    if precision_entry.get("status") == "watch":
        return 5
    return 3


def build_technical_score_summary(
    raw_bars,
    signals: dict[str, object],
    *,
    conclusion: str | None,
    precision_entry: dict[str, object] | None = None,
) -> dict[str, object]:
    structure = _score_structure_component(signals)
    location = _score_location_component(raw_bars, signals)
    signal = _score_signal_component(signals)
    divergence = _score_divergence_component(signals)
    execution = _score_execution_component(precision_entry)
    score = _clamp_score(structure + location + signal + divergence + execution)
    return {
        "score": score,
        "rating": _technical_rating(score),
        "bias": _technical_bias(conclusion),
        "score_breakdown": {
            "structure": structure,
            "location": location,
            "signal": signal,
            "divergence": divergence,
            "execution": execution,
        },
    }


def build_technical_summary(
    timeframe_label: str,
    signals: dict[str, object],
    advice_text: str,
    *,
    raw_bars=None,
    precision_entry: dict[str, object] | None = None,
) -> dict[str, object]:
    conclusion = _extract_prefixed_value_from_text(advice_text, "结论：") or None
    return {
        "operation_level": timeframe_label,
        "conclusion": conclusion,
        "suggestion": _extract_prefixed_value_from_text(advice_text, "建议：") or None,
        **build_technical_score_summary(raw_bars, signals, conclusion=conclusion, precision_entry=precision_entry),
        **build_signal_summary_fields(signals),
    }


def build_advice(name: str, timeframe_label: str, raw_bars, signals: dict[str, object]) -> str:
    current_zs = signals["current_zs"]
    latest_up = signals["latest_confirmed_up"]
    latest_down = signals["latest_down"]
    buy_points = signals["buy_points"]
    sell_points = signals["sell_points"]
    top_divergence = signals["top_divergence"]
    bottom_divergence = signals["bottom_divergence"]
    close_price = raw_bars[-1].close
    signal_explanations = build_signal_explanation_lines(signals)
    buy_labels = "、".join(format_signal_point_labels(buy_points))
    sell_labels = "、".join(format_signal_point_labels(sell_points))

    lines = [f"【{name} {timeframe_label} 操作建议】"]
    if buy_points:
        stop_hint = f"{latest_down.low:.2f}" if latest_down else "最近低点"
        lines.extend(
            [
                "结论：偏多，允许轻仓试错。",
                f"理由：出现 {buy_labels}，结构上已有缠论买点雏形。",
                f"建议：分批试仓，跌破 {stop_hint} 则严格止损。",
            ]
        )
    elif sell_points:
        reduce_hint = f"{latest_up.high:.2f}" if latest_up else "最近高点"
        lines.extend(
            [
                "结论：偏空，优先减仓或兑现。",
                f"理由：出现 {sell_labels}，结构偏向卖点。",
                f"建议：反抽不过 {reduce_hint} 以减仓为主，不逆势加仓。",
            ]
        )
    elif current_zs and latest_down and latest_down.low < current_zs.zs_low:
        lines.extend(
            [
                "结论：偏弱，先观望。",
                f"理由：价格仍在最新中枢下沿 {current_zs.zs_low:.2f} 下方。",
                f"建议：等待重新站回 {current_zs.zs_low:.2f}-{current_zs.zs_high:.2f} 再考虑参与，未站回前不追。",
            ]
        )
    elif current_zs and close_price >= current_zs.zs_high:
        lines.extend(
            [
                "结论：偏强，持有为主。",
                f"理由：价格运行在中枢上沿 {current_zs.zs_high:.2f} 附近或上方。",
                f"建议：已有仓位可继续持有，回踩不破 {current_zs.zs_high:.2f} 再考虑加仓。",
            ]
        )
    elif current_zs:
        lines.extend(
            [
                "结论：震荡，等待方向选择。",
                f"理由：当前主要围绕中枢 {current_zs.zs_low:.2f}-{current_zs.zs_high:.2f} 波动。",
                "建议：中枢内少折腾，等向上离开或向下跌破后再做决策。",
            ]
        )
    else:
        lines.extend(
            [
                "结论：信号一般，保持耐心。",
                "理由：当前尚未形成清晰中枢和明确买卖点。",
                "建议：只做跟踪，不做主观重仓下注。",
            ]
        )

    if current_zs:
        lines.append(f"结构说明：{format_zhongshu_structure_text(current_zs)}。")
    if signal_explanations:
        lines.append(f"信号说明：{'；'.join(signal_explanations)}。")

    if bottom_divergence and not buy_points:
        lines.append("补充：已有底背驰迹象，但买点尚未确认，最多列入观察名单。")
    if top_divergence and not sell_points:
        lines.append("补充：已有顶背驰迹象，若后续反弹无力，应优先考虑保护利润。")
    if timeframe_label == "30M":
        lines.append("次级别说明：5M 主要用于区间套趋势背驰定位更精确的买卖点，同时承担日内短线做T节奏。")
    lines.append("说明：以上仅基于缠论结构与 MACD 强弱，不构成投资建议。")
    return "\n".join(lines)


def export_case(
    security: Security,
    timeframe: str,
    rows: list[dict],
    title: str,
    data_fetch: dict[str, object] | None = None,
    pending_reverse_mode: str = "any",
    zhongshu_level: str = "bi",
) -> dict[str, Path]:
    layout = timeframe_report_paths(security.symbol, timeframe, rows)
    raw_csv = layout.raw_csv
    normalized_csv = layout.normalized_csv
    svg = layout.chart_svg
    png = layout.chart_png
    jpg = layout.chart_jpg
    analysis_path = layout.root_dir / "analysis.txt"
    advice_path = layout.root_dir / "advice.txt"
    report_path = layout.root_dir / "report.txt"
    tech_json_path = layout.technical_report_json

    save_rows(security, timeframe, rows, raw_csv)
    raw_bars = clean_bars(read_bars_from_csv(str(raw_csv)))
    normalized_bars = normalize_bars(raw_bars)
    write_normalized_csv(normalized_csv, normalized_bars)
    fractals = filter_consecutive_fractals(identify_fractals(normalized_bars))
    bis = identify_bis(
        fractals,
        normalized_bars,
        pending_reverse_mode=pending_reverse_mode,
    )
    segments = identify_segments(bis)
    confirmed_bis = [bi for bi in bis if bi.is_confirmed]
    confirmed_segments = [segment for segment in segments if segment.is_confirmed]
    if zhongshu_level == "segment":
        zhongshus = identify_zhongshu(confirmed_segments, structure_level="segment")
    else:
        zhongshus = identify_zhongshu(confirmed_bis, structure_level="bi")
    macd_points = calculate_macd(raw_bars)

    confirmed_fx_ids: set[int] = set()
    for bi in bis:
        if bi.is_confirmed:
            confirmed_fx_ids.add(bi.start_fx_id)
            confirmed_fx_ids.add(bi.end_fx_id)
    unconfirmed_end_fx_ids = {bi.end_fx_id for bi in bis if not bi.is_confirmed}

    export_fractals(layout.fractals_csv, normalized_bars, fractals, confirmed_fx_ids, unconfirmed_end_fx_ids)
    export_confirmed_fractals(layout.confirmed_fractals_csv, normalized_bars, fractals, confirmed_fx_ids)
    export_bis(layout.bis_csv, bis)
    export_segments(layout.segments_csv, segments)
    export_zhongshus(layout.zhongshu_csv, zhongshus)
    export_macd(layout.macd_csv, macd_points)
    save_structure_charts(
        bars=raw_bars,
        normalized_bars=normalized_bars,
        fractals=fractals,
        bis=bis,
        zhongshus=zhongshus,
        svg_path=svg,
        png_path=png,
        jpg_path=jpg,
        title=title,
    )

    analysis_text = analyze_current_state(security.name, raw_bars, bis, zhongshus, macd_points)
    timeframe_label = timeframe_display_label(timeframe)
    if timeframe != "60m":
        analysis_text = analysis_text.replace("60M", timeframe_label)
    signals = extract_signals(bis, zhongshus, macd_points, raw_bars=raw_bars)
    advice_text = build_advice(security.name, timeframe_label, raw_bars, signals)
    summary_payload = build_technical_summary(
        timeframe_label,
        signals,
        advice_text,
        raw_bars=raw_bars,
    )
    report_text = analysis_text + "\n\n" + advice_text + "\n"
    latest_zhongshu = serialize_zhongshu(zhongshus[-1]) if zhongshus else None

    analysis_path.write_text(analysis_text + "\n", encoding="utf-8")
    advice_path.write_text(advice_text + "\n", encoding="utf-8")
    report_path.write_text(report_text, encoding="utf-8")
    write_json(
        tech_json_path,
        {
            "report_type": "technical",
            "symbol": security.symbol,
            "name": security.name,
            "timeframe": timeframe,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source": (data_fetch or {}).get("source"),
            "data_fetch": data_fetch,
            "pending_reverse_mode": pending_reverse_mode,
            "zhongshu_level": zhongshu_level,
            "structure": {
                "latest_zhongshu": latest_zhongshu,
                "zhongshus": serialize_zhongshus(zhongshus),
            },
            "structure_state": signals.get("structure_state"),
            "divergence": signals.get("divergence"),
            "summary": summary_payload,
            "analysis_text": analysis_text,
            "advice_text": advice_text,
            "artifacts": {
                "raw_csv": raw_csv,
                "normalized_csv": normalized_csv,
                "fractals_csv": layout.fractals_csv,
                "confirmed_fractals_csv": layout.confirmed_fractals_csv,
                "bis_csv": layout.bis_csv,
                "segments_csv": layout.segments_csv,
                "zhongshu_csv": layout.zhongshu_csv,
                "macd_csv": layout.macd_csv,
                "structure_svg": svg,
                "structure_png": png,
                "structure_jpg": jpg,
                "report_txt": report_path,
            },
        },
    )
    return {
        "analysis": analysis_path,
        "advice": advice_path,
        "report": report_path,
        "tech_json": tech_json_path,
        "jpg": jpg,
        "png": png,
        "svg": svg,
    }


def build_send_text(security: Security, day_report: Path, m60_report: Path) -> str:
    return (
        f"【{security.name} {security.symbol}】\n\n"
        f"{day_report.read_text(encoding='utf-8').strip()}\n\n"
        f"{m60_report.read_text(encoding='utf-8').strip()}"
    )


def build_send_text_60m_only(security: Security, m60_report: Path) -> str:
    return f"【{security.name} {security.symbol} 60M】\n\n{m60_report.read_text(encoding='utf-8').strip()}"


def _extract_prefixed_value_from_text(text: str, prefix: str) -> str:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    return ""


def _extract_summary_line(advice_path: Path, prefix: str) -> str:
    for raw_line in advice_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    return ""


def build_group_operation_summary(bundle: list[tuple[Security, dict[str, Path], dict[str, Path]]]) -> str:
    lines = [
        "【全部持仓 60M 缠论综合操作建议】",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"覆盖数量：{len(bundle)} 只持仓",
        "",
        "逐只建议：",
    ]

    bullish: list[str] = []
    neutral: list[str] = []
    bearish: list[str] = []

    for security, _day_case, m60_case in bundle:
        conclusion = _extract_summary_line(m60_case["advice"], "结论：") or "信号一般，保持耐心。"
        suggestion = _extract_summary_line(m60_case["advice"], "建议：") or "继续跟踪后续一笔与中枢突破。"
        lines.append(f"- {security.name}({security.symbol})：{conclusion} 建议：{suggestion}")

        if any(keyword in conclusion for keyword in ("偏多", "偏强", "持有为主", "允许轻仓试错")):
            bullish.append(f"{security.name}({security.symbol})")
        elif any(keyword in conclusion for keyword in ("偏空", "偏弱", "减仓", "兑现")):
            bearish.append(f"{security.name}({security.symbol})")
        else:
            neutral.append(f"{security.name}({security.symbol})")

    lines.extend(
        [
            "",
            "组合层结论：",
            f"- 偏强观察组：{'、'.join(bullish) if bullish else '无'}",
            f"- 震荡观察组：{'、'.join(neutral) if neutral else '无'}",
            f"- 风险控制组：{'、'.join(bearish) if bearish else '无'}",
            "- 操作原则：60M 只用于节奏和仓位管理，真正加减仓以中枢突破/跌破后的确认笔为准。",
            "- 说明：以上仅基于最新 60M 缠论结构与 MACD 强弱，不构成投资建议。",
        ]
    )
    return "\n".join(lines) + "\n"


def write_group_operation_summary(bundle: list[tuple[Security, dict[str, Path], dict[str, Path]]]) -> Path:
    file_prefix = "group888_60m_operation_summary_"
    REPORTS_META_DIR.mkdir(parents=True, exist_ok=True)
    output_path = REPORTS_META_DIR / f"{file_prefix}{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    output_path.write_text(build_group_operation_summary(bundle), encoding="utf-8")
    prune_older_outputs(output_path.parent, f"{file_prefix}*.txt", keep_path=output_path)
    return output_path


def load_existing_case(security: Security, timeframe: str) -> dict[str, Path]:
    base_dir = REPORTS_DIR / security.symbol / timeframe
    if (base_dir / "report.txt").exists():
        return {
            "report": base_dir / "report.txt",
            "analysis": base_dir / "analysis.txt",
            "advice": base_dir / "advice.txt",
            "tech_json": base_dir / "tech.json",
            "jpg": base_dir / "structure.jpg",
            "png": base_dir / "structure.png",
            "svg": base_dir / "structure.svg",
        }
    raise FileNotFoundError(f"未找到规范技术报告目录: {base_dir}")


def _reuse_existing_hk_5m_case(
    security: Security,
    rows: list[dict],
    *,
    pending_reverse_mode: str,
    zhongshu_level: str,
) -> dict[str, Path] | None:
    if security.market != "HK" or pending_reverse_mode not in {"any", "effective_only"} or zhongshu_level != "bi":
        return None

    layout = timeframe_report_paths(security.symbol, "5m", rows)
    required_paths = [
        layout.raw_csv,
        layout.normalized_csv,
        layout.fractals_csv,
        layout.confirmed_fractals_csv,
        layout.bis_csv,
        layout.segments_csv,
        layout.zhongshu_csv,
        layout.macd_csv,
        layout.chart_svg,
        layout.chart_png,
        layout.chart_jpg,
        layout.technical_report_json,
        layout.root_dir / "analysis.txt",
        layout.root_dir / "advice.txt",
        layout.root_dir / "report.txt",
    ]
    if any(not path.exists() for path in required_paths):
        return None

    payload = json.loads(layout.technical_report_json.read_text(encoding="utf-8"))
    if payload.get("timeframe") != "5m":
        return None
    if payload.get("pending_reverse_mode") != "effective_only":
        return None
    if str(payload.get("zhongshu_level") or "bi") != "bi":
        return None

    data_fetch = payload.get("data_fetch") or {}
    if int(data_fetch.get("actual_bar_count") or 0) < len(rows):
        return None

    return load_existing_case(security, "5m")


def run_batch_prepare(
    *,
    holdings_path: Path | None = None,
    day_start: str | None = None,
    day_bars: int = 600,
    m60_start: str | None = None,
    m60_bars: int = INTRADAY_SOURCE_PROBE_ROWS,
    m30_start: str | None = None,
    m30_bars: int = INTRADAY_SOURCE_PROBE_ROWS,
    m15_start: str | None = None,
    m15_bars: int = INTRADAY_SOURCE_PROBE_ROWS,
    m5_start: str | None = None,
    m5_bars: int = INTRADAY_SOURCE_PROBE_ROWS,
    pending_reverse_mode: str = "any",
    zhongshu_level: str = "bi",
    timeframes: tuple[str, ...] = ("day", "60m", "30m", "15m", "5m"),
) -> BatchPrepareResult:
    selected_timeframes = tuple(dict.fromkeys(timeframes))
    resolved_day_start = day_start or default_day_start_for_bar_target(day_bars)
    resolved_m60_start = m60_start or default_intraday_start_for_bar_target("60m", m60_bars)
    resolved_m30_start = m30_start or default_intraday_start_for_bar_target("30m", m30_bars)
    resolved_m15_start = m15_start or default_intraday_start_for_bar_target("15m", m15_bars)
    resolved_m5_start = m5_start or default_intraday_start_for_bar_target("5m", m5_bars)
    securities = load_securities(holdings_path or DEFAULT_HOLDINGS_FILE)
    bundle: list[tuple[Security, dict[str, Path], dict[str, Path]]] = []
    for security in securities:
        day_case: dict[str, Path] = {}
        m60_case: dict[str, Path] = {}

        if "day" in selected_timeframes:
            started = time.perf_counter()
            day_rows, day_fetch = fetch_day_rows(security, resolved_day_start, day_bars)
            day_case = export_case(
                security,
                "day",
                day_rows,
                f"{security.symbol} {security.name} day",
                data_fetch=day_fetch,
                pending_reverse_mode=pending_reverse_mode,
                zhongshu_level=zhongshu_level,
            )
            print(f"timing {security.symbol} day seconds={time.perf_counter() - started:.2f}", flush=True)

        timeframe_specs = {
            "60m": ("60", resolved_m60_start, m60_bars),
            "30m": ("30", resolved_m30_start, m30_bars),
            "15m": ("15", resolved_m15_start, m15_bars),
            "5m": ("5", resolved_m5_start, m5_bars),
        }
        for timeframe in ("60m", "30m", "15m", "5m"):
            if timeframe not in selected_timeframes:
                continue
            period, start, bar_count = timeframe_specs[timeframe]
            started = time.perf_counter()
            if timeframe == "60m":
                rows, fetch_meta = fetch_m60_rows(security, start, bar_count)
            elif timeframe == "15m":
                rows, fetch_meta = fetch_m15_rows(security, start, bar_count)
            else:
                rows, fetch_meta = fetch_intraday_rows(security, timeframe=timeframe, period=period, start=start, bar_count=bar_count)
            exported = None
            if timeframe == "5m":
                exported = _reuse_existing_hk_5m_case(
                    security,
                    rows,
                    pending_reverse_mode=pending_reverse_mode,
                    zhongshu_level=zhongshu_level,
                )
                if exported is not None:
                    print(f"reuse {security.symbol} 5m existing_effective_only_case", flush=True)
            if exported is None:
                exported = export_case(
                    security,
                    timeframe,
                    rows,
                    f"{security.symbol} {security.name} {timeframe}",
                    data_fetch=fetch_meta,
                    pending_reverse_mode=pending_reverse_mode,
                    zhongshu_level=zhongshu_level,
                )
            if timeframe == "60m":
                m60_case = exported
            print(f"timing {security.symbol} {timeframe} seconds={time.perf_counter() - started:.2f}", flush=True)

        if m60_case:
            bundle.append((security, day_case, m60_case))
        print(f"Prepared {security.name}")

    REPORTS_META_DIR.mkdir(parents=True, exist_ok=True)
    manifest = REPORTS_META_DIR / f"group888_generation_manifest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    lines = ["group888 生成清单", ""]
    for security, day_case, m60_case in bundle:
        lines.append(f"{security.name} ({security.symbol})")
        lines.append(f"- 60M 报告: {m60_case['report']}")
        lines.append(f"- 60M 图片: {m60_case['jpg']}")
        lines.append("")
    manifest.write_text("\n".join(lines), encoding="utf-8")
    print(f"Manifest: {manifest}")

    summary_path: Path | None = None
    if bundle:
        summary_path = write_group_operation_summary(bundle)
        print(f"Summary: {summary_path}")

    return BatchPrepareResult(
        security_count=len(securities),
        selected_timeframes=selected_timeframes,
        manifest_path=manifest,
        summary_path=summary_path,
    )


def main() -> None:
    args = parse_args()
    run_batch_prepare(
        holdings_path=Path(args.holdings_file) if args.holdings_file else None,
        day_start=args.day_start,
        day_bars=args.day_bars,
        m60_start=args.m60_start,
        m60_bars=args.m60_bars,
        m30_start=args.m30_start,
        m30_bars=args.m30_bars,
        m15_start=args.m15_start,
        m15_bars=args.m15_bars,
        m5_start=args.m5_start,
        m5_bars=args.m5_bars,
        pending_reverse_mode=args.pending_reverse_mode,
        zhongshu_level=args.zhongshu_level,
        timeframes=tuple(args.timeframes),
    )


if __name__ == "__main__":
    main()