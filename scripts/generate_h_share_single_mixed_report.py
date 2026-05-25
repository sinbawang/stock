from __future__ import annotations

import argparse
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
from fundamental.reporting import save_blended_fundamental_brief
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


DEFAULT_OUTPUT_DIR = ROOT / "data" / "_meta"
DEFAULT_CACHE_DIR = DEFAULT_OUTPUT_DIR / "capital_flow_cache"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a single-stock H-share mixed report and optionally send it to the current WeChat chat.")
    parser.add_argument("symbol", help="HK symbol such as 09988")
    parser.add_argument("--name", required=True, help="Security name")
    parser.add_argument("--start", default="2026-01-01 09:30", help="60M analysis start time")
    parser.add_argument("--end", default=None, help="Optional 60M analysis end time")
    parser.add_argument("--source", default="xueqiu", choices=["xueqiu", "akshare"], help="Primary HK minute source")
    parser.add_argument("--fallback-source", action="append", choices=["xueqiu", "akshare"], default=None, help="Optional fallback HK minute sources")
    parser.add_argument("--quote-overlay-source", default=None, help="Optional HK quote overlay source for fundamentals")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory")
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR), help="Capital-flow cache directory")
    parser.add_argument("--max-cache-age-days", type=int, default=7, help="Maximum accepted cache age in days")
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

    generated_at = datetime.now()
    file_prefix = f"{symbol}_{name}_tech_60m_"
    output_path = output_dir / f"{file_prefix}{generated_at.strftime('%Y%m%d_%H%M%S')}.txt"
    report_text = "\n".join(
        [
            f"# 技术面观察: {symbol} {name}",
            "",
            f"- 周期: 60M",
            f"- 数据源: {used_source}",
            f"- 结论: {conclusion}",
            f"- 建议: {suggestion}",
            "",
            analysis_text,
            "",
            advice_text,
            "",
            f"Generated at: {generated_at.isoformat(timespec='seconds')}",
        ]
    )
    output_path.write_text(report_text + "\n", encoding="utf-8")
    prune_older_outputs(output_dir, f"{file_prefix}*.txt", keep_path=output_path)
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
    path = output_dir / f"{file_prefix}{generated_at.strftime('%Y%m%d_%H%M%S')}.txt"
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
    path.write_text(text + "\n", encoding="utf-8")
    prune_older_outputs(output_dir, f"{file_prefix}*.txt", keep_path=path)
    return path


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fundamental_result = fetch_and_analyze_hk_blended_fundamentals(
        args.symbol,
        name=args.name,
        quote_overlay_source=args.quote_overlay_source,
    )
    fundamental_path = save_blended_fundamental_brief(
        blended=fundamental_result.blended,
        output_dir=output_dir,
    )
    fundamental_ref = FundamentalBriefRef(
        score=fundamental_result.blended.blended_total_score,
        rating=fundamental_result.blended.blended_rating,
        submodel=fundamental_result.blended.submodel_id,
        path=fundamental_path,
    )

    technical_ref, technical_path = _save_technical_report(
        symbol=args.symbol,
        name=args.name,
        output_dir=output_dir,
        start=args.start,
        end=args.end,
        primary_source=args.source,
        fallback_sources=tuple(args.fallback_source) if args.fallback_source else None,
    )

    capital_flow_result = fetch_and_analyze_hk_flow(
        args.symbol,
        args.name,
        use_cache=True,
        cache_dir=Path(args.cache_dir),
        max_cache_age_days=args.max_cache_age_days,
    )
    capital_flow_path = save_capital_flow_text(
        scorecard=capital_flow_result.scorecard,
        snapshot=capital_flow_result.snapshot,
        output_dir=output_dir,
    )
    capital_flow_ref = CapitalFlowRef(
        score=capital_flow_result.scorecard.total_score,
        rating=capital_flow_result.scorecard.rating,
        source=capital_flow_result.snapshot.source,
        bucket=(
            "strong"
            if capital_flow_result.scorecard.total_score >= 80
            else "watch"
            if capital_flow_result.scorecard.total_score >= 65
            else "neutral"
            if capital_flow_result.scorecard.total_score >= 50
            else "weak"
        ),
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