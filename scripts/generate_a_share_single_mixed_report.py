from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from batch_prepare_chanlun_reports import build_advice, build_technical_summary, extract_signals
from capital_flow.reporting import save_capital_flow_text
from capital_flow.services import fetch_and_analyze_cn_flow
from chanlun.analysis import build_lower_timeframe_precision_entry, build_precision_window_display
from chanlun.bi import identify_bis
from chanlun.chart_export import save_structure_charts
from chanlun.default_ranges import default_structure_start
from chanlun.data import read_bars_from_csv, read_bars_from_dataframe
from chanlun.data.cleaner import clean_bars
from chanlun.data.kline_fetcher import fetch_kline, get_last_fetch_metadata, save_to_csv as save_cn_kline_csv
from chanlun.data.source_profiles import available_a_share_source_profiles, resolve_a_share_intraday_source_label
from chanlun.fractal import filter_consecutive_fractals, identify_fractals
from chanlun.normalize import normalize_bars
from chanlun.zhongshu import identify_zhongshu
from export_structures_with_boxes import calculate_macd, export_bis, export_confirmed_fractals, export_fractals, export_macd, export_zhongshus, serialize_zhongshu, serialize_zhongshus
from fundamental.reporting.presentation import build_fundamental_presentation, write_base_text
from fundamental.services import fetch_and_analyze_cn_blended_fundamentals
from report_retention import prune_older_outputs
from generate_a_share_combined_overview import (
    CapitalFlowRef,
    CombinedOverviewRow,
    CombinedTarget,
    FundamentalBriefRef,
    TechnicalRef,
    _action_label,
    _build_combined_view,
    _compact_score,
    _management_priority,
)
from run_cn_60m_chanlun_report import analyze_current_state, build_paths, write_normalized_csv
from report_json import write_json
from storage_layout import CAPITAL_FLOW_CACHE_DIR, stock_base_report_path, stock_fund_report_path, stock_overview_report_path, stock_report_dir, timeframe_report_paths


DEFAULT_OUTPUT_DIR = ROOT / "data" / "_meta"
DEFAULT_CACHE_DIR = CAPITAL_FLOW_CACHE_DIR
INTRADAY_SOURCE_PROBE_ROWS = 600
BAR_COUNT_POLICY = "feasible_maximum"
PRIMARY_TECHNICAL_TIMEFRAME = "30m"
PRIMARY_TECHNICAL_LABEL = "30M"
LOWER_PRECISION_TIMEFRAME = "5m"
LOWER_PRECISION_LABEL = "5M"
LOWER_PRECISION_PENDING_REVERSE_MODE = "effective_only"
LAST_TECHNICAL_TIMINGS: dict[str, float] = {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a single-stock A-share mixed report.")
    parser.add_argument("symbol", help="A-share symbol such as 300124")
    parser.add_argument("--name", required=True, help="Security name")
    parser.add_argument("--start", default=default_structure_start(PRIMARY_TECHNICAL_TIMEFRAME), help="30M analysis start time")
    parser.add_argument("--end", default=None, help="Optional 30M analysis end time")
    parser.add_argument("--adjust", default="", choices=["qfq", "hfq", ""], help="Adjustment mode; defaults to raw/no adjustment")
    parser.add_argument("--source-profile", default=None, choices=available_a_share_source_profiles(), help="A股分钟线数据源配置；默认读取 CHANLUN_SOURCE_PROFILE 或 mainland")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory")
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR), help="Capital-flow cache directory")
    parser.add_argument("--max-cache-age-days", type=int, default=7, help="Maximum accepted cache age in days")
    parser.add_argument(
        "--skip-gen-base",
        "--skipGenBase",
        dest="skip_gen_base",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Reuse an existing base.json instead of regenerating the fundamental report when possible. Use --no-skip-gen-base to force refresh.",
    )
    parser.add_argument(
        "--skip-gen-fund",
        "--skipGenFund",
        dest="skip_gen_fund",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Reuse an existing fund.json instead of regenerating the capital-flow report when possible.",
    )
    return parser.parse_args()


def _extract_prefixed_value(text: str, prefix: str) -> str | None:
    pattern = rf"^{re.escape(prefix)}\s*(.+)$"
    match = re.search(pattern, text, flags=re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip()


def _normalize_symbol(symbol: str) -> str:
    normalized = symbol.strip().lower()
    if normalized.startswith(("sz", "sh", "bj")):
        normalized = normalized[2:]
    return normalized.zfill(6)


def _compact_capital_flow(capital_flow: CapitalFlowRef) -> str:
    if capital_flow.bucket == "failed":
        return "failed" + (f"/{capital_flow.source}" if capital_flow.source else "")
    text = _compact_score(capital_flow.score, capital_flow.rating)
    if capital_flow.source:
        text += f"/{capital_flow.source}"
    return text


def _load_existing_fundamental_ref(base_path: Path) -> FundamentalBriefRef | None:
    if not base_path.exists():
        return None
    payload = json.loads(base_path.read_text(encoding="utf-8"))
    summary = payload.get("summary") or {}
    score = summary.get("score")
    rating = summary.get("rating")
    submodel = summary.get("submodel")
    if score is None or not rating or not submodel:
        return None
    return FundamentalBriefRef(
        score=float(score),
        rating=str(rating),
        submodel=str(submodel),
        path=base_path,
    )


def _load_existing_capital_flow_ref(fund_path: Path) -> CapitalFlowRef | None:
    if not fund_path.exists():
        return None
    payload = json.loads(fund_path.read_text(encoding="utf-8"))
    summary = payload.get("summary") or {}
    score = summary.get("score")
    rating = summary.get("rating")
    source = summary.get("source")
    if score is None or not rating:
        return None
    bucket = summary.get("bucket")
    if not bucket:
        score_value = float(score)
        bucket = "strong" if score_value >= 80 else "watch" if score_value >= 65 else "neutral" if score_value >= 50 else "weak"
    return CapitalFlowRef(score=float(score), rating=str(rating), source=str(source or ""), bucket=str(bucket), path=fund_path)


def _build_lower_precision_entry(
    *,
    symbol: str,
    start: str,
    end: str | None,
    adjust: str,
    source_profile: str | None,
    signals: dict[str, object],
) -> dict[str, object] | None:
    fetch_source, _ = resolve_a_share_intraday_source_label(source_profile)
    rows = fetch_kline(
        symbol,
        start=start,
        end=end,
        interval=LOWER_PRECISION_TIMEFRAME,
        adjust=adjust,
        limit=5000,
        min_rows=INTRADAY_SOURCE_PROBE_ROWS,
        source_profile=source_profile,
    )
    fetch_meta = get_last_fetch_metadata()
    actual_source = str(fetch_meta.get("actual_source") or fetch_source)
    if not rows:
        return None

    raw_bars = clean_bars(read_bars_from_dataframe(pd.DataFrame(rows)))
    normalized_bars = normalize_bars(raw_bars)
    fractals = filter_consecutive_fractals(identify_fractals(normalized_bars))
    bis = identify_bis(fractals, normalized_bars, pending_reverse_mode=LOWER_PRECISION_PENDING_REVERSE_MODE)
    confirmed_bis = [bi for bi in bis if bi.is_confirmed]
    zhongshus = identify_zhongshu(confirmed_bis)
    macd_points = calculate_macd(raw_bars)
    lower_signals = extract_signals(bis, zhongshus, macd_points, raw_bars=raw_bars)
    return build_lower_timeframe_precision_entry(
        signals,
        lower_signals,
        lower_timeframe=LOWER_PRECISION_TIMEFRAME,
        lower_timeframe_label=LOWER_PRECISION_LABEL,
        pending_reverse_mode=LOWER_PRECISION_PENDING_REVERSE_MODE,
        source=fetch_source,
        source_actual=actual_source,
    )


def _save_technical_report(
    *,
    symbol: str,
    name: str,
    output_dir: Path,
    start: str,
    end: str | None,
    adjust: str,
    source_profile: str | None = None,
) -> tuple[TechnicalRef, Path]:
    started_total = time.perf_counter()
    fetch_source, _ = resolve_a_share_intraday_source_label(source_profile)
    rows = fetch_kline(symbol, start=start, end=end, interval=PRIMARY_TECHNICAL_TIMEFRAME, adjust=adjust, limit=5000, min_rows=INTRADAY_SOURCE_PROBE_ROWS, source_profile=source_profile)
    fetch_meta = get_last_fetch_metadata()
    actual_source = str(fetch_meta.get("actual_source") or fetch_source)
    if not rows:
        raise RuntimeError("未抓到任何30M数据")

    normalized_symbol = _normalize_symbol(symbol)
    stock_root = None if output_dir == stock_report_dir(normalized_symbol) else output_dir
    layout = timeframe_report_paths(normalized_symbol, PRIMARY_TECHNICAL_TIMEFRAME, rows, stock_root=stock_root)
    paths = {
        "base_dir": layout.root_dir,
        "raw_csv": layout.raw_csv,
        "normalized_csv": layout.normalized_csv,
        "fractals_csv": layout.fractals_csv,
        "confirmed_fractals_csv": layout.confirmed_fractals_csv,
        "bis_csv": layout.bis_csv,
        "zhongshu_csv": layout.zhongshu_csv,
        "macd_csv": layout.macd_csv,
        "svg": layout.chart_svg,
        "png": layout.chart_png,
        "jpg": layout.chart_jpg,
    }
    save_cn_kline_csv(rows, str(paths["raw_csv"]))

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

    export_fractals(paths["fractals_csv"], normalized_bars, fractals, confirmed_fx_ids, unconfirmed_end_fx_ids)
    export_confirmed_fractals(paths["confirmed_fractals_csv"], normalized_bars, fractals, confirmed_fx_ids)
    export_bis(paths["bis_csv"], bis)
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
        title=f"{normalized_symbol} {name} {PRIMARY_TECHNICAL_TIMEFRAME}",
    )

    analysis_text = analyze_current_state(name, raw_bars, bis, zhongshus, macd_points)
    analysis_text = analysis_text.replace("60M", PRIMARY_TECHNICAL_LABEL)
    signals = extract_signals(bis, zhongshus, macd_points, raw_bars=raw_bars)
    started_precision = time.perf_counter()
    precision_entry = _build_lower_precision_entry(
        symbol=symbol,
        start=start,
        end=end,
        adjust=adjust,
        source_profile=source_profile,
        signals=signals,
    )
    precision_seconds = time.perf_counter() - started_precision
    precision_window_display = build_precision_window_display(precision_entry)
    advice_text = build_advice(name, PRIMARY_TECHNICAL_LABEL, raw_bars, signals)
    if precision_entry is not None:
        advice_text += f"\n区间套定位：{precision_entry['note']}"
        window_basis_label = precision_window_display.get("label") if precision_window_display else None
        if window_basis_label:
            advice_text += f"\n区间套窗口：{window_basis_label}"
    summary_payload = build_technical_summary(
        PRIMARY_TECHNICAL_LABEL,
        signals,
        advice_text,
        raw_bars=raw_bars,
        precision_entry=precision_entry,
    )
    if precision_entry is not None:
        summary_payload["precision_entry"] = precision_entry
        summary_payload["precision_window_display"] = precision_window_display
    conclusion = summary_payload.get("conclusion") or "missing"
    suggestion = summary_payload.get("suggestion") or "等待更多技术面确认。"
    latest_zhongshu = serialize_zhongshu(zhongshus[-1]) if zhongshus else None

    output_path = paths["base_dir"] / "tech.json"
    write_json(
        output_path,
        {
            "report_type": "technical",
            "symbol": normalized_symbol,
            "name": name,
            "timeframe": PRIMARY_TECHNICAL_TIMEFRAME,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source": fetch_source,
            "source_actual": actual_source,
            "data_fetch": {
                "source": fetch_source,
                "actual_source": actual_source,
                "source_attempts": fetch_meta.get("source_attempts") or [],
                "actual_bar_count": len(raw_bars),
                "requested_min_rows": None,
                "fulfilled_min_rows": None,
                "bar_count_policy": BAR_COUNT_POLICY,
                "source_probe_min_rows": INTRADAY_SOURCE_PROBE_ROWS,
            },
            "structure": {
                "latest_zhongshu": latest_zhongshu,
                "zhongshus": serialize_zhongshus(zhongshus),
            },
            "structure_state": signals.get("structure_state"),
            "divergence": signals.get("divergence"),
            "precision_entry": precision_entry,
            "precision_window_display": precision_window_display,
            "summary": summary_payload,
            "analysis_text": analysis_text,
            "advice_text": advice_text,
            "artifacts": {
                "raw_csv": paths["raw_csv"],
                "normalized_csv": paths["normalized_csv"],
                "fractals_csv": paths["fractals_csv"],
                "confirmed_fractals_csv": paths["confirmed_fractals_csv"],
                "bis_csv": paths["bis_csv"],
                "zhongshu_csv": paths["zhongshu_csv"],
                "macd_csv": paths["macd_csv"],
                "structure_svg": paths["svg"],
                "structure_png": paths["png"],
                "structure_jpg": paths["jpg"],
            },
        },
    )
    total_seconds = time.perf_counter() - started_total
    LAST_TECHNICAL_TIMINGS.clear()
    LAST_TECHNICAL_TIMINGS.update(
        {
            "technical_30m_seconds": max(total_seconds - precision_seconds, 0.0),
            "technical_5m_seconds": precision_seconds,
            "technical_total_seconds": total_seconds,
        }
    )
    return TechnicalRef(conclusion=conclusion, suggestion=suggestion, path=output_path), output_path


def _save_combined_report(
    *,
    row: CombinedOverviewRow,
    output_dir: Path,
    fundamental_path: Path,
    technical_path: Path,
    capital_flow_path: Path,
) -> Path:
    generated_at = datetime.now()
    file_prefix = f"{row.target.symbol}_{row.target.name}_mixed_overview_"
    archived_path = output_dir / f"{file_prefix}{generated_at.strftime('%Y%m%d_%H%M%S')}.txt"
    latest_path = stock_overview_report_path(row.target.symbol) if output_dir == stock_report_dir(row.target.symbol) else output_dir / "overview.txt"
    text = "\n".join(
        [
            f"# A股单股三轴混合分析: {row.target.symbol} {row.target.name}",
            "",
            f"Generated at: {generated_at.isoformat(timespec='seconds')}",
            f"- 综合分组: {row.combined_bucket}",
            f"- 管理动作: P{_management_priority(row)} {_action_label(row)}",
            f"- 综合判断: {row.combined_comment}",
            "",
            "## 三轴摘要",
            "",
            f"- 基本面: {_compact_score(row.fundamental.score, row.fundamental.rating)}",
            f"- 技术面: {row.technical.conclusion or 'missing'}",
            f"- 技术建议: {row.technical.suggestion or 'missing'}",
            f"- 资金面: {_compact_capital_flow(row.capital_flow)}",
            "",
            "## 原始报告",
            "",
            f"- 基本面简报: {fundamental_path}",
            f"- 技术面报告: {technical_path}",
            f"- 资金面评分卡: {capital_flow_path}",
            "",
            "## 说明",
            "",
            "- mixed_overview 基于最新单股基本面、30M 技术面、A股资金面即时生成。",
            "- 技术面结论口径沿用 30M 缠论操作建议的偏多/偏弱/偏空表达。",
            "- 本报告用于三轴对照，不构成投资建议。",
        ]
    )
    report_text = text + "\n"
    archived_path.write_text(report_text, encoding="utf-8")
    latest_path.write_text(report_text, encoding="utf-8")
    prune_older_outputs(output_dir, f"{file_prefix}*.txt", keep_path=archived_path)
    return latest_path


def main() -> None:
    args = parse_args()
    output_dir = stock_report_dir(_normalize_symbol(args.symbol)) if Path(args.output_dir) == DEFAULT_OUTPUT_DIR else Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    normalized_symbol = _normalize_symbol(args.symbol)
    base_path = stock_base_report_path(normalized_symbol) if output_dir == stock_report_dir(normalized_symbol) else output_dir / "base.json"
    started_fundamental = time.perf_counter()
    fundamental_ref = _load_existing_fundamental_ref(base_path) if args.skip_gen_base else None
    fundamental_path = base_path
    if fundamental_ref is None:
        fundamental_result = fetch_and_analyze_cn_blended_fundamentals(
            normalized_symbol,
            name=args.name,
        )
        base_text_path = write_base_text(fundamental_result.blended, output_dir)
        fundamental_path = write_json(
            base_path,
            {
                "report_type": "fundamental",
                "symbol": normalized_symbol,
                "name": args.name,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "summary": {
                    "score": fundamental_result.blended.blended_total_score,
                    "rating": fundamental_result.blended.blended_rating,
                    "submodel": fundamental_result.blended.submodel_id,
                    "freshness_label": getattr(fundamental_result.blended, "freshness_label", None),
                    "comment": getattr(fundamental_result.blended, "combined_comment", None),
                },
                "blended": fundamental_result.blended,
                "presentation": build_fundamental_presentation(fundamental_result.blended, base_text_path),
            },
        )
        fundamental_ref = FundamentalBriefRef(
            score=fundamental_result.blended.blended_total_score,
            rating=fundamental_result.blended.blended_rating,
            submodel=fundamental_result.blended.submodel_id,
            path=fundamental_path,
        )
    else:
        print(f"fundamental_reused= {fundamental_path}")
    fundamental_seconds = time.perf_counter() - started_fundamental

    technical_result = _save_technical_report(
        symbol=normalized_symbol,
        name=args.name,
        output_dir=output_dir,
        start=args.start,
        end=args.end,
        adjust=args.adjust,
        source_profile=getattr(args, "source_profile", None),
    )
    technical_ref, technical_path = technical_result[:2]
    technical_timings = dict(LAST_TECHNICAL_TIMINGS)

    started_capital_flow = time.perf_counter()
    capital_flow_path = stock_fund_report_path(normalized_symbol) if output_dir == stock_report_dir(normalized_symbol) else output_dir / "fund.json"
    capital_flow_ref = _load_existing_capital_flow_ref(capital_flow_path) if getattr(args, "skip_gen_fund", False) else None
    if capital_flow_ref is None:
        capital_flow_result = fetch_and_analyze_cn_flow(
            normalized_symbol,
            args.name,
            use_cache=True,
            cache_dir=Path(args.cache_dir),
            max_cache_age_days=args.max_cache_age_days,
        )
        capital_bucket = (
            "strong"
            if capital_flow_result.scorecard.total_score >= 80
            else "watch"
            if capital_flow_result.scorecard.total_score >= 65
            else "neutral"
            if capital_flow_result.scorecard.total_score >= 50
            else "weak"
        )
        capital_flow_path = write_json(
            capital_flow_path,
            {
                "report_type": "capital_flow",
                "symbol": normalized_symbol,
                "name": args.name,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "summary": {
                    "score": capital_flow_result.scorecard.total_score,
                    "rating": capital_flow_result.scorecard.rating,
                    "bucket": capital_bucket,
                    "source": capital_flow_result.snapshot.source,
                    "comment": getattr(capital_flow_result.scorecard, "combined_comment", None),
                },
                "scorecard": capital_flow_result.scorecard,
                "snapshot": capital_flow_result.snapshot,
            },
        )
        capital_flow_ref = CapitalFlowRef(
            score=capital_flow_result.scorecard.total_score,
            rating=capital_flow_result.scorecard.rating,
            source=capital_flow_result.snapshot.source,
            bucket=capital_bucket,
            path=capital_flow_path,
        )
    else:
        print(f"capital_flow_reused= {capital_flow_path}")
    capital_flow_seconds = time.perf_counter() - started_capital_flow

    target = CombinedTarget(symbol=normalized_symbol, name=args.name)
    started_combined = time.perf_counter()
    combined_bucket, combined_comment = _build_combined_view(fundamental_ref, technical_ref, capital_flow_ref)
    row = CombinedOverviewRow(
        target=target,
        fundamental=fundamental_ref,
        technical=technical_ref,
        capital_flow=capital_flow_ref,
        combined_bucket=combined_bucket,
        combined_comment=combined_comment,
    )
    combined_path = _save_combined_report(
        row=row,
        output_dir=stock_report_dir(normalized_symbol) if output_dir == stock_report_dir(normalized_symbol) else output_dir,
        fundamental_path=fundamental_path,
        technical_path=technical_path,
        capital_flow_path=capital_flow_path,
    )
    combined_seconds = time.perf_counter() - started_combined

    print(f"fundamental_brief= {fundamental_path}")
    print(f"technical_report= {technical_path}")
    print(f"capital_flow_report= {capital_flow_path}")
    print(f"combined_report= {combined_path}")
    print(f"combined_bucket= {combined_bucket}")
    print(f"timing_fundamental_seconds= {fundamental_seconds:.2f}")
    print(f"timing_technical_30m_seconds= {technical_timings.get('technical_30m_seconds', 0.0):.2f}")
    print(f"timing_technical_5m_seconds= {technical_timings.get('technical_5m_seconds', 0.0):.2f}")
    print(f"timing_capital_flow_seconds= {capital_flow_seconds:.2f}")
    print(f"timing_combined_seconds= {combined_seconds:.2f}")

if __name__ == "__main__":
    main()