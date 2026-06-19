from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

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
from chanlun.bi import identify_bis
from chanlun.chart_export import save_structure_charts
from chanlun.default_ranges import default_structure_start
from chanlun.data import read_bars_from_csv
from chanlun.data.cleaner import clean_bars
from chanlun.data.kline_fetcher import fetch_kline, save_to_csv as save_cn_kline_csv
from chanlun.fractal import filter_consecutive_fractals, identify_fractals
from chanlun.normalize import normalize_bars
from chanlun.zhongshu import identify_zhongshu
from export_structures_with_boxes import calculate_macd, export_bis, export_confirmed_fractals, export_fractals, export_macd, export_zhongshus
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
from run_cn_60m_chanlun_to_wechat import analyze_current_state, build_paths, write_normalized_csv
from send_wechat_current_chat_text import send_current_chat_text_file
from report_json import write_json
from storage_layout import CAPITAL_FLOW_CACHE_DIR, stock_base_report_path, stock_fund_report_path, stock_overview_report_path, stock_report_dir, timeframe_report_paths


DEFAULT_OUTPUT_DIR = ROOT / "data" / "_meta"
DEFAULT_CACHE_DIR = CAPITAL_FLOW_CACHE_DIR
INTRADAY_SOURCE_PROBE_ROWS = 600
BAR_COUNT_POLICY = "feasible_maximum"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a single-stock A-share mixed report and optionally send it to the current WeChat chat.")
    parser.add_argument("symbol", help="A-share symbol such as 300124")
    parser.add_argument("--name", required=True, help="Security name")
    parser.add_argument("--start", default=default_structure_start("60m"), help="60M analysis start time")
    parser.add_argument("--end", default=None, help="Optional 60M analysis end time")
    parser.add_argument("--adjust", default="qfq", choices=["qfq", "hfq", ""], help="Adjustment mode")
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
    parser.add_argument("--send-wechat", action="store_true", help="Send the combined mixed report to the current WeChat chat")
    parser.add_argument("--disable-dedupe", action="store_true", help="Disable short-window duplicate-send protection")
    parser.add_argument("--duplicate-send-window-seconds", type=float, default=300.0, help="Skip duplicate sends within this many seconds; set to 0 to disable")
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


def _save_technical_report(
    *,
    symbol: str,
    name: str,
    output_dir: Path,
    start: str,
    end: str | None,
    adjust: str,
) -> tuple[TechnicalRef, Path]:
    rows = fetch_kline(symbol, start=start, end=end, interval="60m", adjust=adjust, limit=5000, min_rows=INTRADAY_SOURCE_PROBE_ROWS)
    if not rows:
        raise RuntimeError("未抓到任何60M数据")

    normalized_symbol = _normalize_symbol(symbol)
    paths = build_paths(normalized_symbol, name, rows) if output_dir == stock_report_dir(normalized_symbol) else {
        "base_dir": timeframe_report_paths(normalized_symbol, "60m", rows, stock_root=output_dir).root_dir,
        "raw_csv": timeframe_report_paths(normalized_symbol, "60m", rows, stock_root=output_dir).raw_csv,
        "normalized_csv": timeframe_report_paths(normalized_symbol, "60m", rows, stock_root=output_dir).normalized_csv,
    }
    if "svg" not in paths:
        layout = timeframe_report_paths(normalized_symbol, "60m", rows, stock_root=output_dir)
        paths.update(
            {
                "fractals_csv": layout.fractals_csv,
                "confirmed_fractals_csv": layout.confirmed_fractals_csv,
                "bis_csv": layout.bis_csv,
                "zhongshu_csv": layout.zhongshu_csv,
                "macd_csv": layout.macd_csv,
                "svg": layout.chart_svg,
                "png": layout.chart_png,
                "jpg": layout.chart_jpg,
            }
        )
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
        title=f"{normalized_symbol} {name} 60m",
    )

    analysis_text = analyze_current_state(name, raw_bars, bis, zhongshus, macd_points)
    signals = extract_signals(bis, zhongshus, macd_points)
    advice_text = build_advice(name, "60M", raw_bars, signals)
    summary_payload = build_technical_summary("60M", signals, advice_text)
    conclusion = summary_payload.get("conclusion") or "missing"
    suggestion = summary_payload.get("suggestion") or "等待更多技术面确认。"

    output_path = paths["base_dir"] / "tech.json"
    write_json(
        output_path,
        {
            "report_type": "technical",
            "symbol": normalized_symbol,
            "name": name,
            "timeframe": "60m",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source": "fetch_kline.a_share_intraday",
            "data_fetch": {
                "source": "fetch_kline.a_share_intraday",
                "actual_bar_count": len(raw_bars),
                "requested_min_rows": None,
                "fulfilled_min_rows": None,
                "bar_count_policy": BAR_COUNT_POLICY,
                "source_probe_min_rows": INTRADAY_SOURCE_PROBE_ROWS,
            },
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
            "- mixed_overview 基于最新单股基本面、60M 技术面、A股资金面即时生成。",
            "- 技术面结论口径沿用 60M 缠论操作建议的偏多/偏弱/偏空表达。",
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

    technical_ref, technical_path = _save_technical_report(
        symbol=normalized_symbol,
        name=args.name,
        output_dir=output_dir,
        start=args.start,
        end=args.end,
        adjust=args.adjust,
    )

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
        stock_fund_report_path(normalized_symbol) if output_dir == stock_report_dir(normalized_symbol) else output_dir / "fund.json",
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

    target = CombinedTarget(symbol=normalized_symbol, name=args.name)
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

    print(f"fundamental_brief= {fundamental_path}")
    print(f"technical_report= {technical_path}")
    print(f"capital_flow_report= {capital_flow_path}")
    print(f"combined_report= {combined_path}")
    print(f"combined_bucket= {combined_bucket}")

    if args.send_wechat:
        send_current_chat_text_file(
            combined_path,
            duplicate_send_window_seconds=args.duplicate_send_window_seconds,
            disable_dedupe=args.disable_dedupe,
        )
        print(f"wechat_sent= {combined_path}")


if __name__ == "__main__":
    main()