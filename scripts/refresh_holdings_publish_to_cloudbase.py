from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import shlex
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from batch_generate_and_send_portfolio_mixed_reports import generate_bundle as generate_report_bundle
from batch_generate_and_send_portfolio_mixed_reports import load_holdings
from build_miniapp_publish_bundle import generate_bundle as build_publish_bundle
from storage_layout import REPORTS_DIR, holdings_file


DEFAULT_HOLDINGS_FILE = holdings_file()
DEFAULT_PUBLISH_ROOT = ROOT / "build" / "miniapp-publish"
DEFAULT_UPLOAD_SCRIPT = SCRIPTS / "upload_miniapp_publish_bundle.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Regenerate holding reports, rebuild the miniapp publish bundle, and upload it to CloudBase."
    )
    parser.add_argument("--holdings-file", default=str(DEFAULT_HOLDINGS_FILE), help="Combined holdings JSON file")
    parser.add_argument("--market", choices=["ALL", "CN", "HK"], default="ALL", help="Optional market filter")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=None,
        help="Optional symbol filter, for example 09988 or 000651. When set, only these holdings are regenerated.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional max holding count for validation")
    parser.add_argument("--reports-root", default=str(REPORTS_DIR), help="Canonical reports root")
    parser.add_argument("--publish-root", default=str(DEFAULT_PUBLISH_ROOT), help="Publish bundle root")
    parser.add_argument("--snapshot-stamp", default=None, help="Optional explicit snapshot stamp such as 20260531_100500")
    parser.add_argument("--latest-only", action="store_true", help="Only write latest/ and skip snapshots/<stamp>")
    parser.add_argument("--skip-regenerate", action="store_true", help="Skip regenerating holdings reports and charts")
    parser.add_argument("--skip-build", action="store_true", help="Skip rebuilding the publish bundle")
    parser.add_argument("--skip-upload", action="store_true", help="Skip CloudBase upload")
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
    parser.add_argument(
        "--parallelism",
        type=int,
        default=min(4, max(1, os.cpu_count() or 1)),
        help="How many holdings to generate in parallel during regeneration.",
    )
    parser.add_argument(
        "--fail-on-holding-error",
        dest="fail_on_holding_error",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Fail the whole batch when any single holding regeneration fails. Defaults to false so partial failures are recorded and the batch continues.",
    )
    parser.add_argument(
        "--pending-reverse-mode",
        choices=("any", "effective_only", "tail_mixed"),
        default="any",
        help="Forwarded to batch_prepare_chanlun_reports.py to control pending reverse fractal handling.",
    )
    parser.add_argument("--day-bars", type=int, default=600, help="Forwarded to batch_prepare_chanlun_reports.py for daily K-line fetch count.")
    parser.add_argument("--m60-bars", type=int, default=600, help="Forwarded to batch_prepare_chanlun_reports.py for 60M K-line fetch count.")
    parser.add_argument("--m30-bars", type=int, default=600, help="Forwarded to batch_prepare_chanlun_reports.py for 30M K-line fetch count.")
    parser.add_argument("--m15-bars", type=int, default=600, help="Forwarded to batch_prepare_chanlun_reports.py for 15M K-line fetch count.")
    parser.add_argument("--m5-bars", type=int, default=600, help="Forwarded to batch_prepare_chanlun_reports.py for 5M K-line fetch count.")
    parser.add_argument("--zhongshu-level", choices=("bi", "segment"), default="bi", help="Forwarded to batch_prepare_chanlun_reports.py to switch between bi and segment zhongshu rendering.")
    parser.add_argument(
        "--tech-timeframes",
        nargs="+",
        choices=("day", "60m", "30m", "15m", "5m"),
        default=["day", "60m", "15m"],
        help="Technical levels to generate in addition to the mixed report path. Defaults to day/60m/15m because 30m is already produced by the mixed report and 5m precision is already embedded there.",
    )
    parser.add_argument(
        "--publish-timeframes",
        nargs="+",
        choices=("day", "60m", "30m", "15m", "5m"),
        default=None,
        help="Optional chart timeframes to include in the publish bundle. Defaults to all available chart assets.",
    )
    parser.add_argument("--cloud-prefix", default="miniapp-publish/latest", help="Cloud storage prefix for upload")
    parser.add_argument("--env-id", default=None, help="CloudBase env id forwarded to uploader")
    parser.add_argument("--region", default=None, help="CloudBase region forwarded to uploader")
    parser.add_argument("--api-key", default=None, help="CloudBase API key forwarded to uploader")
    parser.add_argument("--api-key-name", default=None, help="Temporary API key name forwarded to uploader")
    parser.add_argument("--api-key-expire-in", type=int, default=None, help="Temporary API key lifetime forwarded to uploader")
    parser.add_argument("--delete-created-api-key", action="store_true", help="Delete temporary API key after upload")
    parser.add_argument("--upload-dry-run", action="store_true", help="Run upload script in dry-run mode")
    return parser.parse_args()


def _run_command(command: list[str]) -> str:
    print("$ " + " ".join(shlex.quote(part) for part in command), flush=True)
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    if completed.stdout:
        print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n", flush=True)
    if completed.stderr:
        print(completed.stderr, end="" if completed.stderr.endswith("\n") else "\n", flush=True)
    return completed.stdout


def select_holdings(args: argparse.Namespace):
    holdings = load_holdings(Path(args.holdings_file), market_filter=args.market)
    if args.symbols:
        requested = {str(symbol).strip() for symbol in args.symbols if str(symbol).strip()}
        normalized_requested = requested | {symbol.zfill(5) for symbol in requested} | {symbol.zfill(6) for symbol in requested}
        holdings = [holding for holding in holdings if holding.symbol in normalized_requested or holding.symbol.zfill(5) in normalized_requested or holding.symbol.zfill(6) in normalized_requested]
    if args.limit is not None:
        holdings = holdings[: args.limit]
    return holdings


def regenerate_holdings(args: argparse.Namespace) -> dict[str, object]:
    holdings = select_holdings(args)
    if not holdings:
        raise RuntimeError("No holdings found for regeneration")

    worker_count = max(1, min(args.parallelism, len(holdings)))
    print(f"regenerate_holdings={len(holdings)} parallelism={worker_count} skip_gen_base={args.skip_gen_base} skip_gen_fund={args.skip_gen_fund} tech_timeframes={','.join(args.tech_timeframes)}", flush=True)

    failures: list[dict[str, str]] = []
    generated_count = 0
    if worker_count == 1:
        for index, holding in enumerate(holdings, start=1):
            try:
                started = time.perf_counter()
                bundle = generate_report_bundle(
                    holding,
                    skip_gen_base=args.skip_gen_base,
                    skip_gen_fund=args.skip_gen_fund,
                    pending_reverse_mode=args.pending_reverse_mode,
                    day_bars=args.day_bars,
                    m60_bars=args.m60_bars,
                    m30_bars=args.m30_bars,
                    m15_bars=args.m15_bars,
                    m5_bars=args.m5_bars,
                    zhongshu_level=args.zhongshu_level,
                    tech_timeframes=tuple(args.tech_timeframes),
                )
                print(
                    f"generated {index}/{len(holdings)} {holding.market} {holding.symbol} {holding.name} "
                    f"bucket={bundle.combined_bucket} chart={bundle.chart_jpg} seconds={time.perf_counter() - started:.2f}",
                    flush=True,
                )
                generated_count += 1
            except Exception as exc:  # pragma: no cover - operational batch script
                failures.append(
                    {
                        "market": holding.market,
                        "symbol": holding.symbol,
                        "name": holding.name,
                        "error": str(exc),
                    }
                )
                print(f"failed {index}/{len(holdings)} {holding.market} {holding.symbol} {holding.name}: {exc}", flush=True)
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_map = {
                executor.submit(
                    generate_report_bundle,
                    holding,
                    skip_gen_base=args.skip_gen_base,
                    skip_gen_fund=args.skip_gen_fund,
                    pending_reverse_mode=args.pending_reverse_mode,
                    day_bars=args.day_bars,
                    m60_bars=args.m60_bars,
                    m30_bars=args.m30_bars,
                    m15_bars=args.m15_bars,
                    m5_bars=args.m5_bars,
                    zhongshu_level=args.zhongshu_level,
                    tech_timeframes=tuple(args.tech_timeframes),
                ): (index, holding, time.perf_counter())
                for index, holding in enumerate(holdings, start=1)
            }
            for future in as_completed(future_map):
                index, holding, started = future_map[future]
                try:
                    bundle = future.result()
                    print(
                        f"generated {index}/{len(holdings)} {holding.market} {holding.symbol} {holding.name} "
                        f"bucket={bundle.combined_bucket} chart={bundle.chart_jpg} seconds={time.perf_counter() - started:.2f}",
                        flush=True,
                    )
                    generated_count += 1
                except Exception as exc:  # pragma: no cover - operational batch script
                    failures.append(
                        {
                            "market": holding.market,
                            "symbol": holding.symbol,
                            "name": holding.name,
                            "error": str(exc),
                        }
                    )
                    print(f"failed {index}/{len(holdings)} {holding.market} {holding.symbol} {holding.name}: {exc}", flush=True)
    failure_lines = [
        f"{item['market']} {item['symbol']} {item['name']}: {item['error']}"
        for item in failures
    ]
    if generated_count == 0:
        raise RuntimeError("All holdings failed:\n" + "\n".join(failure_lines))
    if failures:
        print("partial failures:\n" + "\n".join(failure_lines), flush=True)
        if getattr(args, "fail_on_holding_error", False):
            raise RuntimeError("Failed holdings:\n" + "\n".join(failure_lines))
    return {
        "requested_count": len(holdings),
        "generated_count": generated_count,
        "failed_count": len(failures),
        "failed_holdings": failures,
    }


def rebuild_publish_bundle(args: argparse.Namespace) -> Path:
    outputs = build_publish_bundle(
        holdings_path=Path(args.holdings_file),
        reports_root=Path(args.reports_root),
        publish_root=Path(args.publish_root),
        snapshot_stamp=args.snapshot_stamp,
        latest_only=args.latest_only,
        publish_timeframes=tuple(args.publish_timeframes) if args.publish_timeframes else None,
    )
    print(f"latest= {outputs['latest']}", flush=True)
    if not args.latest_only:
        print(f"snapshot= {outputs['snapshot']}", flush=True)
    return outputs["latest"]


def upload_publish_bundle(args: argparse.Namespace, source_dir: Path) -> None:
    command = [
        sys.executable,
        str(DEFAULT_UPLOAD_SCRIPT),
        "--source-dir",
        str(source_dir),
        "--cloud-prefix",
        args.cloud_prefix,
    ]
    if args.env_id:
        command.extend(["--env-id", args.env_id])
    if args.region:
        command.extend(["--region", args.region])
    if args.api_key:
        command.extend(["--api-key", args.api_key])
    if args.api_key_name:
        command.extend(["--api-key-name", args.api_key_name])
    if args.api_key_expire_in is not None:
        command.extend(["--api-key-expire-in", str(args.api_key_expire_in)])
    if args.delete_created_api_key:
        command.append("--delete-created-api-key")
    if args.upload_dry_run:
        command.append("--dry-run")
    _run_command(command)


def main() -> None:
    args = parse_args()

    started_total = time.perf_counter()
    if not args.skip_regenerate:
        started_regenerate = time.perf_counter()
        regenerate_holdings(args)
        print(f"timing regenerate_seconds={time.perf_counter() - started_regenerate:.2f}", flush=True)

    latest_dir = Path(args.publish_root) / "latest"
    if not args.skip_build:
        started_build = time.perf_counter()
        latest_dir = rebuild_publish_bundle(args)
        print(f"timing build_seconds={time.perf_counter() - started_build:.2f}", flush=True)

    if not args.skip_upload:
        started_upload = time.perf_counter()
        upload_publish_bundle(args, latest_dir)
        print(f"timing upload_seconds={time.perf_counter() - started_upload:.2f}", flush=True)
    print(f"timing total_seconds={time.perf_counter() - started_total:.2f}", flush=True)


if __name__ == "__main__":
    main()