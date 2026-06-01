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

from batch_prepare_chanlun_reports import build_advice, extract_signals
from capital_flow.reporting import save_capital_flow_text
from capital_flow.services import fetch_and_analyze_hk_flow
from chanlun.bi import identify_bis
from chanlun.data import read_bars_from_csv
from chanlun.data.cleaner import clean_bars
from chanlun.data.hk_minute_fetcher import fetch_hk_minute_with_policy, save_to_csv as save_hk_minute_csv
from chanlun.fractal import filter_consecutive_fractals, identify_fractals
from chanlun.normalize import normalize_bars
from chanlun.zhongshu import identify_zhongshu
from export_structures_with_boxes import calculate_macd
from fundamental.reporting import render_blended_fundamental_brief
from fundamental.reporting.brief_report import _format_component_name, _format_dimension_name, _format_metric_name
from fundamental.reporting.text_report import _display_metric_name, _format_score_basis_for_display
from fundamental.services import fetch_and_analyze_hk_blended_fundamentals
from report_retention import prune_older_outputs
from generate_h_share_combined_overview import (
    CapitalFlowRef,
    CombinedOverviewRow,
    CombinedTarget,
    FundamentalBriefRef,
    TechnicalRef,
    _build_combined_view,
    _compact_capital_flow,
    _compact_score,
    _management_priority,
    _action_label,
)
from run_hk_60m_chanlun_to_wechat import analyze_current_state, build_paths
from send_wechat_current_chat_text import send_current_chat_text_file
from report_json import write_json
from storage_layout import CAPITAL_FLOW_CACHE_DIR, stock_base_report_path, stock_fund_report_path, stock_overview_report_path, stock_report_dir


DEFAULT_OUTPUT_DIR = ROOT / "data" / "_meta"
DEFAULT_CACHE_DIR = CAPITAL_FLOW_CACHE_DIR
DEFAULT_MANUAL_SUPPLEMENT_DIR = ROOT / "data" / "_meta" / "manual_supplements"
DEFAULT_HK_MINUTE_SOURCE = "xueqiu"
DEFAULT_HK_MINUTE_FALLBACK_SOURCES = ("akshare",)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a single-stock H-share mixed report and optionally send it to the current WeChat chat.")
    parser.add_argument("symbol", help="HK symbol such as 09988")
    parser.add_argument("--name", required=True, help="Security name")
    parser.add_argument("--start", default="2026-01-01 09:30", help="60M analysis start time")
    parser.add_argument("--end", default=None, help="Optional 60M analysis end time")
    parser.add_argument("--source", default=DEFAULT_HK_MINUTE_SOURCE, choices=["xueqiu", "akshare"], help="Primary HK minute source")
    parser.add_argument("--fallback-source", action="append", choices=["xueqiu", "akshare"], default=None, help="Optional fallback HK minute sources; defaults to akshare when primary source is xueqiu")
    parser.add_argument("--quote-overlay-source", default=None, help="Optional HK quote overlay source for fundamentals")
    parser.add_argument("--manual-supplement-path", default=None, help="Optional JSON or brief txt supplement file for HK fundamentals")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory")
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR), help="Capital-flow cache directory")
    parser.add_argument("--max-cache-age-days", type=int, default=7, help="Maximum accepted cache age in days")
    parser.add_argument("--send-wechat", action="store_true", help="Send the combined mixed report to the current WeChat chat")
    parser.add_argument("--disable-dedupe", action="store_true", help="Disable short-window duplicate-send protection")
    parser.add_argument("--duplicate-send-window-seconds", type=float, default=300.0, help="Skip duplicate sends within this many seconds; set to 0 to disable")
    return parser.parse_args()


def _resolve_manual_supplement_path(symbol: str, explicit_path: str | None) -> str | None:
    if explicit_path:
        return explicit_path
    candidates = sorted(DEFAULT_MANUAL_SUPPLEMENT_DIR.glob(f"{symbol}_*.*"))
    if not candidates:
        return None
    return str(candidates[0])


def _extract_prefixed_value(text: str, prefix: str) -> str | None:
    pattern = rf"^{re.escape(prefix)}\s*(.+)$"
    match = re.search(pattern, text, flags=re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip()


def _resolve_minute_fallback_sources(primary_source: str, fallback_sources: tuple[str, ...] | None) -> tuple[str, ...] | None:
    if fallback_sources:
        normalized = tuple(source for source in fallback_sources if source != primary_source)
        return normalized or None
    if primary_source == DEFAULT_HK_MINUTE_SOURCE:
        return DEFAULT_HK_MINUTE_FALLBACK_SOURCES
    return None


def _metric_detail(snapshot, metric_name: str) -> dict[str, object]:
    return {
        "name": metric_name,
        "label": _format_metric_name(metric_name),
        "value": getattr(snapshot, metric_name, None),
    }


def _annual_dimension_presentation(blended) -> list[dict[str, object]]:
    snapshot = blended.annual_anchor.snapshot
    scorecard = blended.annual_anchor.scorecard
    payloads: list[dict[str, object]] = []
    for dimension in scorecard.dimension_scores:
        payloads.append(
            {
                "dimension": dimension.dimension,
                "title": _format_dimension_name(dimension.dimension),
                "score": dimension.score,
                "weight": dimension.weight,
                "max_score": dimension.max_score,
                "red_flag": scorecard.red_flag,
                "formula": _format_score_basis_for_display(dimension.score_basis, snapshot),
                "covered_metrics": [_metric_detail(snapshot, metric_name) for metric_name in dimension.used_metrics if metric_name],
                "missing_metrics": [_metric_detail(snapshot, metric_name) for metric_name in dimension.missing_metrics if metric_name],
                "passed_rules": list(dimension.passed_rules),
                "failed_rules": list(dimension.failed_rules),
                "notes": list(dimension.notes),
            }
        )
    return payloads


def _interim_component_presentation(blended) -> list[dict[str, object]]:
    overlay = blended.interim_overlay
    if overlay is None:
        return []
    snapshot = overlay.snapshot
    payloads: list[dict[str, object]] = []
    for component in overlay.components:
        payloads.append(
            {
                "component": component.component,
                "title": _format_component_name(component.component),
                "score": component.score,
                "weight": component.weight,
                "weighted_score": round(component.score * component.weight, 4),
                "formula": "单指标刷新" if len(component.covered_metrics) <= 1 else "覆盖指标均值刷新",
                "covered_metrics": [_metric_detail(snapshot, metric_name) for metric_name in component.covered_metrics if metric_name],
                "missing_metrics": [_metric_detail(snapshot, metric_name) for metric_name in component.missing_metrics if metric_name],
                "note": component.note,
            }
        )
    return payloads


def _build_fundamental_presentation(blended, base_text_path: Path) -> dict[str, object]:
    annual_scorecard = blended.annual_anchor.scorecard
    interim_overlay = blended.interim_overlay
    return {
        "periods": {
            "annual": blended.annual_anchor.snapshot.report_period.isoformat(),
            "annual_label": blended.annual_anchor.snapshot.period_label or "年报",
            "interim": interim_overlay.snapshot.report_period.isoformat() if interim_overlay is not None else None,
            "interim_label": (interim_overlay.snapshot.period_label or "中间报告期") if interim_overlay is not None else None,
        },
        "summary": {
            "score": blended.blended_total_score,
            "rating": blended.blended_rating,
            "red_flag": annual_scorecard.red_flag,
            "annual_anchor_score": annual_scorecard.total_score,
            "annual_anchor_rating": annual_scorecard.rating,
            "annual_anchor_label": blended.annual_anchor.snapshot.period_label or "年报",
            "interim_overlay_score": interim_overlay.overlay_score if interim_overlay is not None else None,
            "interim_overlay_rating": interim_overlay.rating_hint if interim_overlay is not None else None,
            "interim_overlay_label": (interim_overlay.snapshot.period_label or "中间报告期") if interim_overlay is not None else None,
            "annual_weight": blended.annual_weight,
            "interim_weight": blended.interim_weight,
            "freshness_label": blended.freshness_label,
            "comment": blended.combined_comment,
        },
        "red_flag": {
            "triggered": annual_scorecard.red_flag,
            "rules": list(annual_scorecard.triggered_rules),
        },
        "current_missing_fields": list(annual_scorecard.missing_metrics),
        "annual_dimensions": _annual_dimension_presentation(blended),
        "interim_components": _interim_component_presentation(blended),
        "warnings": list(blended.warnings),
        "assumptions": list(blended.assumptions),
        "base_text_path": str(base_text_path),
    }


def _write_base_text(blended, output_dir: Path) -> Path:
    output_path = output_dir / "base.txt"
    output_path.write_text(render_blended_fundamental_brief(blended=blended), encoding="utf-8")
    return output_path


def _save_technical_report(
    *,
    symbol: str,
    name: str,
    output_dir: Path,
    start: str,
    end: str | None,
    primary_source: str,
    fallback_sources: tuple[str, ...] | None,
) -> tuple[TechnicalRef, Path]:
    rows, used_source = fetch_hk_minute_with_policy(
        symbol,
        period="60",
        start=start,
        end=end,
        adjust="qfq",
        primary_source=primary_source,
        fallback_sources=fallback_sources,
    )
    if not rows:
        raise RuntimeError("未抓到任何60M数据")

    paths = build_paths(symbol, name, rows)
    save_hk_minute_csv(rows, str(paths["raw_csv"]))

    raw_bars = clean_bars(read_bars_from_csv(str(paths["raw_csv"])))
    normalized_bars = normalize_bars(raw_bars)
    fractals = filter_consecutive_fractals(identify_fractals(normalized_bars))
    bis = identify_bis(fractals, normalized_bars)
    confirmed_bis = [bi for bi in bis if bi.is_confirmed]
    zhongshus = identify_zhongshu(confirmed_bis)
    macd_points = calculate_macd(raw_bars)

    analysis_text = analyze_current_state(name, raw_bars, bis, zhongshus, macd_points)
    advice_text = build_advice(name, "60M", raw_bars, extract_signals(bis, zhongshus, macd_points))
    conclusion = _extract_prefixed_value(advice_text, "结论：") or "missing"
    suggestion = _extract_prefixed_value(advice_text, "建议：") or "等待更多技术面确认。"

    output_path = output_dir / "60m" / "tech.json"
    write_json(
        output_path,
        {
            "report_type": "technical",
            "symbol": symbol,
            "name": name,
            "timeframe": "60m",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source": used_source,
            "summary": {"conclusion": conclusion, "suggestion": suggestion},
            "analysis_text": analysis_text,
            "advice_text": advice_text,
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
            f"# 港股单股三轴混合分析: {row.target.symbol} {row.target.name}",
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
            "- mixed_overview 基于最新单股基本面、60M 技术面、港股资金面即时生成。",
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
    output_dir = stock_report_dir(args.symbol.zfill(5)) if Path(args.output_dir) == DEFAULT_OUTPUT_DIR else Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manual_supplement_path = _resolve_manual_supplement_path(args.symbol.zfill(5), args.manual_supplement_path)

    fundamental_result = fetch_and_analyze_hk_blended_fundamentals(
        args.symbol,
        name=args.name,
        quote_overlay_source=args.quote_overlay_source,
        manual_supplement_path=manual_supplement_path,
    )
    base_text_path = _write_base_text(fundamental_result.blended, output_dir)
    fundamental_path = write_json(
        stock_base_report_path(args.symbol.zfill(5)) if output_dir == stock_report_dir(args.symbol.zfill(5)) else output_dir / "base.json",
        {
            "report_type": "fundamental",
            "symbol": args.symbol.zfill(5),
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
            "presentation": _build_fundamental_presentation(fundamental_result.blended, base_text_path),
        },
    )
    fundamental_ref = FundamentalBriefRef(
        score=fundamental_result.blended.blended_total_score,
        rating=fundamental_result.blended.blended_rating,
        submodel=fundamental_result.blended.submodel_id,
        path=fundamental_path,
    )

    resolved_fallback_sources = _resolve_minute_fallback_sources(
        args.source,
        tuple(args.fallback_source) if args.fallback_source else None,
    )

    technical_ref, technical_path = _save_technical_report(
        symbol=args.symbol,
        name=args.name,
        output_dir=output_dir,
        start=args.start,
        end=args.end,
        primary_source=args.source,
        fallback_sources=resolved_fallback_sources,
    )

    capital_flow_result = fetch_and_analyze_hk_flow(
        args.symbol,
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
        stock_fund_report_path(args.symbol.zfill(5)) if output_dir == stock_report_dir(args.symbol.zfill(5)) else output_dir / "fund.json",
        {
            "report_type": "capital_flow",
            "symbol": args.symbol.zfill(5),
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

    target = CombinedTarget(symbol=args.symbol.zfill(5), name=args.name)
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
        output_dir=output_dir,
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