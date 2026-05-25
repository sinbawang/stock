from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from capital_flow.reporting import save_capital_flow_text
from capital_flow.services import fetch_and_analyze_hk_flow
from report_retention import prune_older_outputs


DEFAULT_HOLDINGS_FILE = ROOT / "data" / "_meta" / "current_h_share_holdings.json"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "_meta"
DEFAULT_CACHE_DIR = ROOT / "data" / "_meta" / "capital_flow_cache"
DEFAULT_HK_FLOW_SOURCE = "eastmoney.hk_connect_components+eastmoney.southbound_net_buy+eastmoney.southbound_holding+hkex.short_selling_turnover"


@dataclass(frozen=True)
class CapitalFlowTarget:
    symbol: str
    name: str
    market: str = "HK"


@dataclass(frozen=True)
class BatchCapitalFlowResult:
    target: CapitalFlowTarget
    status: str
    report_path: Path | None = None
    total_score: float | None = None
    rating: str | None = None
    trade_date: date | None = None
    source: str | None = None
    notes: str | None = None
    error: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch generate H-share capital-flow scorecard reports.")
    parser.add_argument("--holdings-file", default=str(DEFAULT_HOLDINGS_FILE), help="H-share holdings JSON file")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Report output directory")
    parser.add_argument("--trade-date", default=None, help="Optional trade date, formatted as YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=None, help="Optional target count limit")
    parser.add_argument("--fail-fast", action="store_true", help="Stop after the first failed target")
    parser.add_argument("--no-cache", action="store_true", help="Disable local HK capital-flow cache fallback")
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR), help="Local capital-flow cache directory")
    parser.add_argument(
        "--max-cache-age-days",
        type=int,
        default=7,
        help="Maximum accepted cache age in days; use -1 to allow any cache age",
    )
    return parser.parse_args()


def _normalize_hk_symbol(symbol: str) -> str:
    text = symbol.strip().upper()
    if text.startswith("HK"):
        text = text[2:]
    if text.endswith(".HK"):
        text = text[:-3]
    text = text.strip(".")
    return text.zfill(5)


def discover_targets_from_holdings_file(holdings_file: Path) -> list[CapitalFlowTarget]:
    payload = json.loads(holdings_file.read_text(encoding="utf-8"))
    entries = payload.get("holdings", [])
    if isinstance(payload.get("markets"), dict):
        entries = payload["markets"].get("HK", [])

    dedup: dict[str, CapitalFlowTarget] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        symbol = str(entry.get("symbol") or "").strip()
        name = str(entry.get("name") or "").strip()
        if not symbol or not name:
            continue
        normalized_symbol = _normalize_hk_symbol(symbol)
        dedup[f"{normalized_symbol}:{name}"] = CapitalFlowTarget(symbol=normalized_symbol, name=name)
    return list(dedup.values())


def _parse_trade_date(value: str | None) -> date | None:
    if value is None:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def generate_one(
    target: CapitalFlowTarget,
    output_dir: Path,
    trade_date: date | None = None,
    use_cache: bool = True,
    cache_dir: Path | None = None,
    max_cache_age_days: int | None = 7,
) -> BatchCapitalFlowResult:
    result = fetch_and_analyze_hk_flow(
        target.symbol,
        target.name,
        trade_date=trade_date,
        use_cache=use_cache,
        cache_dir=cache_dir,
        max_cache_age_days=max_cache_age_days,
    )
    report_path = save_capital_flow_text(scorecard=result.scorecard, snapshot=result.snapshot, output_dir=output_dir)
    return BatchCapitalFlowResult(
        target=target,
        status="ok",
        report_path=report_path,
        total_score=result.scorecard.total_score,
        rating=result.scorecard.rating,
        trade_date=result.snapshot.trade_date,
        source=result.snapshot.source,
        notes=result.snapshot.notes,
    )


def _source_bucket(source: str | None) -> str:
    if not source:
        return "unknown"
    parts = [part.strip() for part in source.split("+") if part.strip()]
    if not parts:
        return "unknown"
    cache_count = sum(1 for part in parts if part.endswith(".cache"))
    if cache_count == len(parts):
        return "cache"
    if cache_count > 0:
        return "mixed"
    return "primary"


def _source_alias(part: str) -> str:
    is_cache = part.endswith(".cache")
    base = part[:-6] if is_cache else part
    aliases = {
        "eastmoney.hk_connect_components": "components",
        "eastmoney.southbound_net_buy": "net_buy",
        "eastmoney.southbound_holding": "holding",
        "hkex.short_selling_turnover": "short_sell",
    }
    label = aliases.get(base, base.split(".")[-1])
    if is_cache:
        label += ".cache"
    return label


def _source_summary(source: str | None) -> str:
    bucket = _source_bucket(source)
    if not source:
        return bucket
    parts = [part.strip() for part in source.split("+") if part.strip()]
    if not parts:
        return bucket
    return f"{bucket}({'+'.join(_source_alias(part) for part in parts)})"


def _score_bucket(item: BatchCapitalFlowResult) -> str:
    if item.status != "ok" or item.total_score is None:
        return "failed"
    if item.total_score >= 80:
        return "strong"
    if item.total_score >= 65:
        return "watch"
    if item.total_score >= 50:
        return "neutral"
    return "weak"


def _sorted_results(results: list[BatchCapitalFlowResult]) -> list[BatchCapitalFlowResult]:
    return sorted(results, key=lambda item: (item.status != "ok", -(item.total_score or -1), item.target.symbol))


def _build_overall_comment(results: list[BatchCapitalFlowResult]) -> str:
    succeeded = [item for item in results if item.status == "ok" and item.total_score is not None]
    failed_count = len(results) - len(succeeded)
    if not succeeded:
        return "本次未生成有效港股资金面评分，需先修复数据源或缓存。"
    average_score = sum(item.total_score or 0 for item in succeeded) / len(succeeded)
    weak_count = sum(1 for item in succeeded if _score_bucket(item) == "weak")
    tone = "整体港股资金面线索偏弱" if weak_count >= max(1, len(succeeded) // 2) else "整体港股资金面线索分化"
    suffix = f"；{failed_count} 只失败" if failed_count else ""
    return (
        f"{tone}，有效样本均分 {average_score:.1f}{suffix}。"
        "当前 HK V1 已接入成交额/换手率、个股南向净买额、南向持股变化和 HKEX 沽空成交额；"
        "其中个股南向净买额仅在进入港股通成交榜的交易日可用，沽空比例依赖成交额可用性。"
    )


def save_batch_summary(results: list[BatchCapitalFlowResult], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    file_prefix = "group_h_share_capital_flow_overview_"
    path = output_dir / f"{file_prefix}{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    source_counts: dict[str, int] = {}
    for item in results:
        source_counts[_source_bucket(item.source)] = source_counts.get(_source_bucket(item.source), 0) + 1

    lines = [
        "# 港股持仓资金面批量概览",
        "",
        f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"Total: {len(results)}",
        f"Succeeded: {sum(1 for item in results if item.status == 'ok')}",
        f"Failed: {sum(1 for item in results if item.status != 'ok')}",
        "",
        "## 组合观察",
        "",
        _build_overall_comment(results),
        "",
        "数据源分布: " + ", ".join(f"{key}={value}" for key, value in sorted(source_counts.items())),
        "",
        "## 排名表",
        "",
        "| symbol | name | status | trade_date | score | rating | source | bucket | report |",
        "|---|---|---|---|---:|---|---|---|---|",
    ]
    for item in _sorted_results(results):
        trade_date_text = item.trade_date.isoformat() if item.trade_date else ""
        score_text = f"{item.total_score:.1f}" if item.total_score is not None else ""
        report_or_error = str(item.report_path) if item.report_path else (item.error or "")
        lines.append(
            "| "
            + " | ".join(
                [
                    item.target.symbol,
                    item.target.name,
                    item.status,
                    trade_date_text,
                    score_text,
                    item.rating or "",
                    _source_summary(item.source),
                    _score_bucket(item),
                    report_or_error.replace("|", "/"),
                ]
            )
            + " |"
        )

    detail_lines: list[str] = []
    for item in _sorted_results(results):
        if item.notes:
            detail_lines.append(f"- {item.target.symbol} {item.target.name}: {item.notes}")
        elif item.error:
            detail_lines.append(f"- {item.target.symbol} {item.target.name}: {item.error}")
    if detail_lines:
        lines.extend(["", "## 口径与失败说明", ""])
        lines.extend(detail_lines)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    prune_older_outputs(output_dir, f"{file_prefix}*.txt", keep_path=path)
    return path


def run_batch(
    targets: list[CapitalFlowTarget],
    output_dir: Path,
    trade_date: date | None = None,
    fail_fast: bool = False,
    use_cache: bool = True,
    cache_dir: Path | None = None,
    max_cache_age_days: int | None = 7,
) -> list[BatchCapitalFlowResult]:
    results: list[BatchCapitalFlowResult] = []
    for target in targets:
        try:
            results.append(
                generate_one(
                    target,
                    output_dir=output_dir,
                    trade_date=trade_date,
                    use_cache=use_cache,
                    cache_dir=cache_dir,
                    max_cache_age_days=max_cache_age_days,
                )
            )
        except Exception as exc:
            results.append(BatchCapitalFlowResult(target=target, status="failed", source=DEFAULT_HK_FLOW_SOURCE, error=str(exc)))
            if fail_fast:
                break
    return results


def main() -> None:
    args = parse_args()
    holdings_file = Path(args.holdings_file)
    output_dir = Path(args.output_dir)
    targets = discover_targets_from_holdings_file(holdings_file)
    if args.limit is not None:
        targets = targets[: args.limit]
    if not targets:
        raise RuntimeError(f"No valid HK holdings found in: {holdings_file}")

    results = run_batch(
        targets=targets,
        output_dir=output_dir,
        trade_date=_parse_trade_date(args.trade_date),
        fail_fast=args.fail_fast,
        use_cache=not args.no_cache,
        cache_dir=Path(args.cache_dir),
        max_cache_age_days=None if args.max_cache_age_days < 0 else args.max_cache_age_days,
    )
    summary_path = save_batch_summary(results, output_dir=output_dir)
    for item in results:
        if item.report_path:
            print(item.report_path)
        elif item.error:
            print(f"FAILED {item.target.symbol} {item.target.name}: {item.error}")
    print(summary_path)


if __name__ == "__main__":
    main()