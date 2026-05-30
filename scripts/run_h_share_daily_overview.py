from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SRC = ROOT / "src"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import batch_generate_h_share_capital_flow_reports as capital_batch
import generate_h_share_combined_overview as combined_overview
import send_wechat_current_chat_text as wechat_text
from storage_layout import CAPITAL_FLOW_CACHE_DIR, REPORTS_META_DIR, holdings_file


DEFAULT_HOLDINGS_FILE = holdings_file()
DEFAULT_META_DIR = REPORTS_META_DIR
DEFAULT_CACHE_DIR = CAPITAL_FLOW_CACHE_DIR


@dataclass(frozen=True)
class HShareDailyOverviewResult:
    capital_flow_summary_path: Path
    combined_overview_path: Path
    manifest_path: Path | None
    capital_flow_succeeded: int
    capital_flow_failed: int
    wechat_sent: bool = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate H-share capital-flow reports and the combined management overview in one run.")
    parser.add_argument("--holdings-file", default=str(DEFAULT_HOLDINGS_FILE), help="H-share holdings JSON file")
    parser.add_argument("--meta-dir", default=str(DEFAULT_META_DIR), help="Directory containing and receiving report text files")
    parser.add_argument("--trade-date", default=None, help="Optional capital-flow trade date, formatted as YYYY-MM-DD")
    parser.add_argument("--limit", type=int, default=None, help="Optional target count limit")
    parser.add_argument("--fail-fast", action="store_true", help="Stop capital-flow generation after the first failed target")
    parser.add_argument("--no-cache", action="store_true", help="Disable local capital-flow cache fallback")
    parser.add_argument("--send-wechat", action="store_true", help="Send the combined overview text to the current foreground WeChat chat")
    parser.add_argument("--no-manifest", action="store_true", help="Do not write a daily overview run manifest JSON file")
    parser.add_argument("--disable-dedupe", action="store_true", help="Disable short-window duplicate-send protection when sending to WeChat")
    parser.add_argument(
        "--duplicate-send-window-seconds",
        type=float,
        default=300.0,
        help="Skip duplicate WeChat sends within this many seconds; set to 0 to disable",
    )
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR), help="Local capital-flow cache directory")
    parser.add_argument(
        "--max-cache-age-days",
        type=int,
        default=7,
        help="Maximum accepted cache age in days; use -1 to allow any cache age",
    )
    return parser.parse_args()


def _parse_trade_date(value: str | None) -> date | None:
    if value is None:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def save_daily_overview_manifest(
    *,
    meta_dir: Path,
    holdings_file: Path,
    trade_date: date | None,
    limit: int | None,
    fail_fast: bool,
    use_cache: bool,
    cache_dir: Path | None,
    max_cache_age_days: int | None,
    capital_target_count: int,
    combined_target_count: int,
    capital_summary_path: Path,
    combined_path: Path,
    capital_flow_succeeded: int,
    capital_flow_failed: int,
    send_wechat: bool,
    wechat_sent: bool,
    disable_dedupe: bool,
    duplicate_send_window_seconds: float,
) -> Path:
    meta_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now()
    manifest_path = meta_dir / f"h_share_daily_overview_manifest_{generated_at.strftime('%Y%m%d_%H%M%S')}.json"
    payload = {
        "task": "h_share_daily_overview",
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "inputs": {
            "holdings_file": str(holdings_file),
            "trade_date": trade_date.isoformat() if trade_date else None,
            "capital_target_count": capital_target_count,
            "combined_target_count": combined_target_count,
        },
        "parameters": {
            "limit": limit,
            "fail_fast": fail_fast,
            "use_cache": use_cache,
            "cache_dir": str(cache_dir) if cache_dir else None,
            "max_cache_age_days": max_cache_age_days,
        },
        "outputs": {
            "capital_flow_summary": str(capital_summary_path),
            "combined_overview": str(combined_path),
        },
        "capital_flow": {
            "succeeded": capital_flow_succeeded,
            "failed": capital_flow_failed,
        },
        "wechat": {
            "requested": send_wechat,
            "sent": wechat_sent,
            "disable_dedupe": disable_dedupe,
            "duplicate_send_window_seconds": duplicate_send_window_seconds,
        },
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def run_daily_overview(
    holdings_file: Path,
    meta_dir: Path,
    trade_date: date | None = None,
    limit: int | None = None,
    fail_fast: bool = False,
    use_cache: bool = True,
    cache_dir: Path | None = None,
    max_cache_age_days: int | None = 7,
    send_wechat: bool = False,
    write_manifest: bool = True,
    disable_dedupe: bool = False,
    duplicate_send_window_seconds: float = 300.0,
) -> HShareDailyOverviewResult:
    capital_targets = capital_batch.discover_targets_from_holdings_file(holdings_file)
    combined_targets = combined_overview.discover_targets_from_holdings_file(holdings_file)
    if limit is not None:
        capital_targets = capital_targets[:limit]
        combined_targets = combined_targets[:limit]
    if not capital_targets:
        raise RuntimeError(f"No valid HK holdings found in: {holdings_file}")
    if not combined_targets:
        raise RuntimeError(f"No valid H-share holdings found in: {holdings_file}")

    capital_results = capital_batch.run_batch(
        targets=capital_targets,
        output_dir=meta_dir,
        trade_date=trade_date,
        fail_fast=fail_fast,
        use_cache=use_cache,
        cache_dir=cache_dir,
        max_cache_age_days=max_cache_age_days,
    )
    capital_summary_path = capital_batch.save_batch_summary(capital_results, output_dir=meta_dir)

    rows, technical_summary_path, capital_flow_summary_path = combined_overview.build_rows(combined_targets, meta_dir)
    combined_text = combined_overview.render_combined_overview(rows, technical_summary_path, capital_flow_summary_path)
    combined_path = combined_overview.save_combined_overview(combined_text, meta_dir)
    wechat_sent = False
    if send_wechat:
        wechat_text.send_current_chat_text_file(
            combined_path,
            duplicate_send_window_seconds=duplicate_send_window_seconds,
            disable_dedupe=disable_dedupe,
        )
        wechat_sent = True

    capital_flow_succeeded = sum(1 for item in capital_results if item.status == "ok")
    capital_flow_failed = sum(1 for item in capital_results if item.status != "ok")
    manifest_path: Path | None = None
    if write_manifest:
        manifest_path = save_daily_overview_manifest(
            meta_dir=meta_dir,
            holdings_file=holdings_file,
            trade_date=trade_date,
            limit=limit,
            fail_fast=fail_fast,
            use_cache=use_cache,
            cache_dir=cache_dir,
            max_cache_age_days=max_cache_age_days,
            capital_target_count=len(capital_targets),
            combined_target_count=len(combined_targets),
            capital_summary_path=capital_summary_path,
            combined_path=combined_path,
            capital_flow_succeeded=capital_flow_succeeded,
            capital_flow_failed=capital_flow_failed,
            send_wechat=send_wechat,
            wechat_sent=wechat_sent,
            disable_dedupe=disable_dedupe,
            duplicate_send_window_seconds=duplicate_send_window_seconds,
        )

    return HShareDailyOverviewResult(
        capital_flow_summary_path=capital_summary_path,
        combined_overview_path=combined_path,
        manifest_path=manifest_path,
        capital_flow_succeeded=capital_flow_succeeded,
        capital_flow_failed=capital_flow_failed,
        wechat_sent=wechat_sent,
    )


def main() -> None:
    args = parse_args()
    result = run_daily_overview(
        holdings_file=Path(args.holdings_file),
        meta_dir=Path(args.meta_dir),
        trade_date=_parse_trade_date(args.trade_date),
        limit=args.limit,
        fail_fast=args.fail_fast,
        use_cache=not args.no_cache,
        cache_dir=Path(args.cache_dir),
        max_cache_age_days=None if args.max_cache_age_days < 0 else args.max_cache_age_days,
        send_wechat=args.send_wechat,
        write_manifest=not args.no_manifest,
        disable_dedupe=args.disable_dedupe,
        duplicate_send_window_seconds=args.duplicate_send_window_seconds,
    )
    print(f"capital_flow_summary={result.capital_flow_summary_path}")
    print(f"combined_overview={result.combined_overview_path}")
    print(f"manifest={result.manifest_path if result.manifest_path is not None else 'disabled'}")
    print(f"capital_flow_succeeded={result.capital_flow_succeeded}")
    print(f"capital_flow_failed={result.capital_flow_failed}")
    print(f"wechat_sent={result.wechat_sent}")


if __name__ == "__main__":
    main()