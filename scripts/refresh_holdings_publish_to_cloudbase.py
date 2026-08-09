from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import json
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
from storage_layout import REPORTS_DIR, REPORTS_META_DIR, holdings_file


DEFAULT_HOLDINGS_FILE = holdings_file()
DEFAULT_PUBLISH_ROOT = ROOT / "build" / "miniapp-publish"
DEFAULT_UPLOAD_SCRIPT = SCRIPTS / "upload_miniapp_publish_bundle.py"
DEFAULT_UPLOAD_MANIFEST_PATH = ROOT / "build" / "miniapp-publish" / "cloudbase-upload-manifest.json"
DEFAULT_SYNC_KLINE_SCRIPT = SCRIPTS / "sync_kline_cache_cloudbase.py"
DEFAULT_KLINE_CACHE_SOURCE_DIR = ROOT / "data" / "cache" / "kline"
DEFAULT_KLINE_CACHE_MANIFEST_PATH = ROOT / "build" / "stock-kline-cache" / "cloudbase-upload-manifest.json"
DEFAULT_KLINE_CACHE_POINTER_PATH = ROOT / "build" / "stock-kline-cache" / "manifest-pointer.json"
DEFAULT_KLINE_CACHE_CLOUD_PREFIX = "stock-kline-cache/latest"


def _round_seconds(value: float) -> float:
    return round(value, 2)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _summarize_holding_timings(per_holding: list[dict[str, object]]) -> list[dict[str, object]]:
    by_market: dict[str, list[dict[str, object]]] = {}
    for item in per_holding:
        by_market.setdefault(str(item["market"]), []).append(item)

    summaries: list[dict[str, object]] = []
    for market, rows in sorted(by_market.items()):
        successful = [float(row["seconds"]) for row in rows if row.get("status") == "generated" and isinstance(row.get("seconds"), (int, float))]
        summaries.append(
            {
                "market": market,
                "count": len(rows),
                "generated_count": sum(1 for row in rows if row.get("status") == "generated"),
                "failed_count": sum(1 for row in rows if row.get("status") != "generated"),
                "avg_seconds": _round_seconds(sum(successful) / len(successful)) if successful else None,
                "min_seconds": _round_seconds(min(successful)) if successful else None,
                "max_seconds": _round_seconds(max(successful)) if successful else None,
                "total_seconds": _round_seconds(sum(successful)),
            }
        )
    return summaries


def _write_timing_report(
    args: argparse.Namespace,
    *,
    started_at: datetime,
    completed_at: datetime,
    stage_seconds: dict[str, float],
    regeneration_summary: dict[str, object] | None,
    latest_dir: Path,
    build_summary: dict[str, object] | None,
) -> Path:
    REPORTS_META_DIR.mkdir(parents=True, exist_ok=True)
    stamp = completed_at.strftime("%Y%m%d_%H%M%S")
    archive_path = REPORTS_META_DIR / f"holdings_refresh_timing_{stamp}.json"
    latest_path = REPORTS_META_DIR / "holdings_refresh_timing_latest.json"

    payload: dict[str, object] = {
        "report_type": "holdings_refresh_timing",
        "generated_at": completed_at.isoformat(timespec="seconds"),
        "started_at": started_at.isoformat(timespec="seconds"),
        "completed_at": completed_at.isoformat(timespec="seconds"),
        "request": {
            "holdings_file": str(args.holdings_file),
            "market": args.market,
            "symbols": list(args.symbols) if args.symbols else None,
            "limit": args.limit,
            "parallelism": args.parallelism,
            "skip_regenerate": args.skip_regenerate,
            "skip_build": args.skip_build,
            "skip_upload": args.skip_upload,
            "skip_gen_base": args.skip_gen_base,
            "skip_gen_fund": args.skip_gen_fund,
            "day_bars": args.day_bars,
            "m60_bars": args.m60_bars,
            "m30_bars": args.m30_bars,
            "m15_bars": args.m15_bars,
            "m5_bars": args.m5_bars,
            "m1_bars": args.m1_bars,
            "pending_reverse_mode": args.pending_reverse_mode,
            "zhongshu_level": args.zhongshu_level,
            "tech_timeframes": list(args.tech_timeframes),
            "export_structure_images": bool(args.export_structure_images),
            "publish_timeframes": list(args.publish_timeframes) if args.publish_timeframes else None,
            "publish_json_only": bool(args.publish_json_only),
            "force_upload": bool(getattr(args, "force_upload", False)),
            "sync_kline_cache": bool(getattr(args, "sync_kline_cache", False)),
            "sync_kline_cache_restore_before_regenerate": bool(getattr(args, "sync_kline_cache_restore_before_regenerate", False)),
            "local_store_read_only": bool(getattr(args, "local_store_read_only", False)),
            "kline_cache_cloud_prefix": str(getattr(args, "kline_cache_cloud_prefix", "")),
        },
        "stages": {name: _round_seconds(value) for name, value in stage_seconds.items()},
        "artifacts": {
            "latest_dir": str(latest_dir),
            "missing_artifact_alert_count": (build_summary or {}).get("missing_artifact_alert_count"),
            "missing_artifact_alert_path": str((build_summary or {}).get("missing_artifact_alert_path")) if (build_summary or {}).get("missing_artifact_alert_path") else None,
        },
    }
    if regeneration_summary is not None:
        per_holding = list(regeneration_summary.get("per_holding", []))
        payload["regeneration"] = {
            "requested_count": regeneration_summary.get("requested_count"),
            "generated_count": regeneration_summary.get("generated_count"),
            "failed_count": regeneration_summary.get("failed_count"),
            "failed_holdings": regeneration_summary.get("failed_holdings"),
            "per_market": _summarize_holding_timings(per_holding),
            "per_holding": per_holding,
        }

    _write_json(archive_path, payload)
    _write_json(latest_path, payload)
    return archive_path


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
        "--trust-existing-base",
        dest="trust_existing_base",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="When --skip-gen-base is enabled, reuse existing base.json without checking the latest report period.",
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
        "--local-store-read-only",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Force child technical generation to use local K-line store only (no remote incremental fetch).",
    )
    parser.add_argument(
        "--pending-reverse-mode",
        choices=("any", "effective_only", "tail_mixed"),
        default="effective_only",
        help="Forwarded to batch_prepare_chanlun_reports.py to control pending reverse fractal handling.",
    )
    parser.add_argument("--day-bars", type=int, default=1200, help="Forwarded to batch_prepare_chanlun_reports.py for daily K-line fetch count.")
    parser.add_argument("--m60-bars", type=int, default=1200, help="Forwarded to batch_prepare_chanlun_reports.py for 60M K-line fetch count.")
    parser.add_argument("--m30-bars", type=int, default=1200, help="Forwarded to batch_prepare_chanlun_reports.py for 30M K-line fetch count.")
    parser.add_argument("--m15-bars", type=int, default=1200, help="Forwarded to batch_prepare_chanlun_reports.py for 15M K-line fetch count.")
    parser.add_argument("--m5-bars", type=int, default=1200, help="Forwarded to batch_prepare_chanlun_reports.py for 5M K-line fetch count.")
    parser.add_argument("--m1-bars", type=int, default=1200, help="Forwarded to batch_prepare_chanlun_reports.py for 1M K-line fetch count.")
    parser.add_argument("--zhongshu-level", choices=("bi", "segment"), default="bi", help="Forwarded to batch_prepare_chanlun_reports.py to switch between bi and segment zhongshu rendering.")
    parser.add_argument(
        "--tech-timeframes",
        nargs="+",
        choices=("day", "60m", "30m", "15m", "5m", "1m"),
        default=["day", "30m", "5m", "1m"],
        help="Technical levels to generate in addition to the mixed report path. Defaults to day/30m/5m/1m.",
    )
    parser.add_argument(
        "--export-structure-images",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Whether to export structure images for extra timeframe generation. Use --no-export-structure-images for JSON-first publishing.",
    )
    parser.add_argument(
        "--publish-timeframes",
        nargs="+",
        choices=("day", "60m", "30m", "15m", "5m", "1m"),
        default=None,
        help="Optional chart timeframes to include in the publish bundle. Defaults to all available chart assets.",
    )
    parser.add_argument(
        "--publish-json-only",
        action="store_true",
        help="Build/upload chart JSON payloads only and skip chart image assets in miniapp publish bundle.",
    )
    parser.add_argument("--cloud-prefix", default="miniapp-publish/latest", help="Cloud storage prefix for upload")
    parser.add_argument("--env-id", default=None, help="CloudBase env id forwarded to uploader")
    parser.add_argument("--region", default=None, help="CloudBase region forwarded to uploader")
    parser.add_argument("--api-key", default=None, help="CloudBase API key forwarded to uploader")
    parser.add_argument("--api-key-name", default=None, help="Temporary API key name forwarded to uploader")
    parser.add_argument("--api-key-expire-in", type=int, default=None, help="Temporary API key lifetime forwarded to uploader")
    parser.add_argument("--delete-created-api-key", action="store_true", help="Delete temporary API key after upload")
    parser.add_argument(
        "--force-upload",
        action="store_true",
        help="Force uploader to skip manifest-diff optimization and upload all files.",
    )
    parser.add_argument("--upload-dry-run", action="store_true", help="Run upload script in dry-run mode")
    parser.add_argument(
        "--sync-kline-cache-restore-before-regenerate",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Restore data/cache/kline from CloudBase stock-kline-cache/latest before local regeneration.",
    )
    parser.add_argument(
        "--kline-cache-target-dir",
        default=str(DEFAULT_KLINE_CACHE_SOURCE_DIR),
        help="Local kline cache target root for restore.",
    )
    parser.add_argument(
        "--kline-cache-clean-target-before-restore",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Clean local kline cache target directory before restore.",
    )
    parser.add_argument(
        "--sync-kline-cache",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Sync local data/cache/kline to CloudBase stock-kline-cache/latest via backup command.",
    )
    parser.add_argument(
        "--sync-kline-cache-script",
        default=str(DEFAULT_SYNC_KLINE_SCRIPT),
        help="Path to sync_kline_cache_cloudbase.py",
    )
    parser.add_argument(
        "--kline-cache-source-dir",
        default=str(DEFAULT_KLINE_CACHE_SOURCE_DIR),
        help="Local kline cache root for sync backup.",
    )
    parser.add_argument(
        "--kline-cache-cloud-prefix",
        default=DEFAULT_KLINE_CACHE_CLOUD_PREFIX,
        help="Cloud prefix for expanded kline CSV backup.",
    )
    parser.add_argument(
        "--kline-cache-manifest-path",
        default=str(DEFAULT_KLINE_CACHE_MANIFEST_PATH),
        help="Local manifest path for kline cache sync backup.",
    )
    parser.add_argument(
        "--kline-cache-pointer-path",
        default=str(DEFAULT_KLINE_CACHE_POINTER_PATH),
        help="Local pointer path for kline cache sync backup.",
    )
    return parser.parse_args()


def _run_command(command: list[str]) -> str:
    print("$ " + " ".join(shlex.quote(part) for part in command), flush=True)
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.CalledProcessError as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if stdout:
            print(stdout, end="" if stdout.endswith("\n") else "\n", flush=True)
        if stderr:
            print(stderr, end="" if stderr.endswith("\n") else "\n", flush=True)
        details = [
            f"Command failed with exit code {exc.returncode}: {exc.cmd!r}",
        ]
        if stdout.strip():
            details.append("stdout:")
            details.append(stdout.strip())
        if stderr.strip():
            details.append("stderr:")
            details.append(stderr.strip())
        raise RuntimeError("\n".join(details)) from exc
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
    print(
        f"regenerate_holdings={len(holdings)} parallelism={worker_count} "
        f"skip_gen_base={args.skip_gen_base} trust_existing_base={args.trust_existing_base} "
        f"skip_gen_fund={args.skip_gen_fund} tech_timeframes={','.join(args.tech_timeframes)} "
        f"export_structure_images={bool(args.export_structure_images)}",
        flush=True,
    )

    failures: list[dict[str, str]] = []
    per_holding: list[dict[str, object]] = []
    generated_count = 0
    local_store_read_only = bool(getattr(args, "local_store_read_only", False))
    previous_local_store_read_only = os.environ.get("CHANLUN_LOCAL_STORE_READ_ONLY")
    if local_store_read_only:
        os.environ["CHANLUN_LOCAL_STORE_READ_ONLY"] = "1"

    try:
        if worker_count == 1:
            for index, holding in enumerate(holdings, start=1):
                started = time.perf_counter()
                try:
                    bundle = generate_report_bundle(
                        holding,
                        skip_gen_base=args.skip_gen_base,
                        trust_existing_base=args.trust_existing_base,
                        skip_gen_fund=args.skip_gen_fund,
                        pending_reverse_mode=args.pending_reverse_mode,
                        day_bars=args.day_bars,
                        m60_bars=args.m60_bars,
                        m30_bars=args.m30_bars,
                        m15_bars=args.m15_bars,
                        m5_bars=args.m5_bars,
                        m1_bars=args.m1_bars,
                        zhongshu_level=args.zhongshu_level,
                        tech_timeframes=tuple(args.tech_timeframes),
                        export_structure_images=bool(args.export_structure_images),
                    )
                    print(
                        f"generated {index}/{len(holdings)} {holding.market} {holding.symbol} {holding.name} "
                        f"bucket={bundle.combined_bucket} chart={bundle.chart_jpg} seconds={time.perf_counter() - started:.2f}",
                        flush=True,
                    )
                    generated_count += 1
                    per_holding.append(
                        {
                            "index": index,
                            "market": holding.market,
                            "symbol": holding.symbol,
                            "name": holding.name,
                            "status": "generated",
                            "bucket": bundle.combined_bucket,
                            "chart_jpg": str(bundle.chart_jpg) if bundle.chart_jpg else None,
                            "seconds": _round_seconds(time.perf_counter() - started),
                        }
                    )
                except Exception as exc:  # noqa: BLE001
                    failures.append({"market": holding.market, "symbol": holding.symbol, "name": holding.name, "error": str(exc)})
                    print(
                        f"failed {index}/{len(holdings)} {holding.market} {holding.symbol} {holding.name}: {exc}",
                        flush=True,
                    )
                    per_holding.append(
                        {
                            "index": index,
                            "market": holding.market,
                            "symbol": holding.symbol,
                            "name": holding.name,
                            "status": "failed",
                            "error": str(exc),
                            "seconds": _round_seconds(time.perf_counter() - started),
                        }
                    )
        else:
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = {
                    executor.submit(
                        generate_report_bundle,
                        holding,
                        skip_gen_base=args.skip_gen_base,
                        trust_existing_base=args.trust_existing_base,
                        skip_gen_fund=args.skip_gen_fund,
                        pending_reverse_mode=args.pending_reverse_mode,
                        day_bars=args.day_bars,
                        m60_bars=args.m60_bars,
                        m30_bars=args.m30_bars,
                        m15_bars=args.m15_bars,
                        m5_bars=args.m5_bars,
                        m1_bars=args.m1_bars,
                        zhongshu_level=args.zhongshu_level,
                        tech_timeframes=tuple(args.tech_timeframes),
                        export_structure_images=bool(args.export_structure_images),
                    ): (idx, holding, time.perf_counter())
                    for idx, holding in enumerate(holdings, start=1)
                }

                for future in as_completed(futures):
                    index, holding, started = futures[future]
                    elapsed = time.perf_counter() - started
                    try:
                        bundle = future.result()
                        print(
                            f"generated {index}/{len(holdings)} {holding.market} {holding.symbol} {holding.name} "
                            f"bucket={bundle.combined_bucket} chart={bundle.chart_jpg} seconds={elapsed:.2f}",
                            flush=True,
                        )
                        generated_count += 1
                        per_holding.append(
                            {
                                "index": index,
                                "market": holding.market,
                                "symbol": holding.symbol,
                                "name": holding.name,
                                "status": "generated",
                                "bucket": bundle.combined_bucket,
                                "chart_jpg": str(bundle.chart_jpg) if bundle.chart_jpg else None,
                                "seconds": _round_seconds(elapsed),
                            }
                        )
                    except Exception as exc:  # noqa: BLE001
                        failures.append({"market": holding.market, "symbol": holding.symbol, "name": holding.name, "error": str(exc)})
                        print(
                            f"failed {index}/{len(holdings)} {holding.market} {holding.symbol} {holding.name}: {exc}",
                            flush=True,
                        )
                        per_holding.append(
                            {
                                "index": index,
                                "market": holding.market,
                                "symbol": holding.symbol,
                                "name": holding.name,
                                "status": "failed",
                                "error": str(exc),
                                "seconds": _round_seconds(elapsed),
                            }
                        )
    finally:
        if local_store_read_only:
            if previous_local_store_read_only is None:
                os.environ.pop("CHANLUN_LOCAL_STORE_READ_ONLY", None)
            else:
                os.environ["CHANLUN_LOCAL_STORE_READ_ONLY"] = previous_local_store_read_only
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
        "per_holding": sorted(per_holding, key=lambda item: int(item["index"])),
    }


def rebuild_publish_bundle(args: argparse.Namespace, regeneration_summary: dict[str, object] | None = None) -> dict[str, object]:
    failed_symbols = {
        str(item.get("symbol") or "")
        for item in (regeneration_summary or {}).get("failed_holdings", [])
        if isinstance(item, dict) and str(item.get("symbol") or "").strip()
    }
    outputs = build_publish_bundle(
        holdings_path=Path(args.holdings_file),
        reports_root=Path(args.reports_root),
        publish_root=Path(args.publish_root),
        snapshot_stamp=args.snapshot_stamp,
        latest_only=args.latest_only,
        publish_timeframes=tuple(args.publish_timeframes) if args.publish_timeframes else None,
        include_chart_images=not bool(args.publish_json_only),
        expected_tech_timeframes=tuple(getattr(args, "tech_timeframes", []) or []) or None,
        skip_regenerate_context=bool(getattr(args, "skip_regenerate", False)),
        skip_gen_fund_context=bool(getattr(args, "skip_gen_fund", False)),
        failed_symbols=failed_symbols,
    )
    print(f"latest= {outputs['latest']}", flush=True)
    print(f"missing_artifact_alert_count= {outputs['missing_artifact_alert_count']}", flush=True)
    print(f"missing_artifact_alert_path= {outputs['missing_artifact_alert_path']}", flush=True)
    if not args.latest_only:
        print(f"snapshot= {outputs['snapshot']}", flush=True)
    return outputs


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
    if bool(getattr(args, "force_upload", False)):
        command.append("--force-upload")
    if args.upload_dry_run:
        command.append("--dry-run")
    try:
        _run_command(command)
    except RuntimeError as exc:
        print(f"upload attempt 1 failed: {exc}", flush=True)
        print("retrying upload once...", flush=True)
        _run_command(command)


def _print_upload_verification_summary(manifest_path: Path, focus_symbols: list[str] | None) -> None:
    if not manifest_path.exists():
        print(f"upload_verification_manifest_missing={manifest_path}", flush=True)
        return

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"upload_verification_manifest_read_error={error}", flush=True)
        return

    verification = payload.get("verification")
    if not isinstance(verification, list):
        print("upload_verification_summary=not_available", flush=True)
        return

    total = len(verification)
    matched = sum(1 for item in verification if isinstance(item, dict) and bool(item.get("matched")))
    mismatched = total - matched
    print(
        f"upload_verification_summary total={total} matched={matched} mismatched={mismatched}",
        flush=True,
    )

    if total == 0:
        return

    normalized_focus = {
        str(symbol).strip().zfill(5)
        for symbol in (focus_symbols or [])
        if str(symbol).strip()
    }

    chart_entries: list[dict[str, object]] = []
    for item in verification:
        if not isinstance(item, dict):
            continue
        relative_path = str(item.get("relative_path") or "")
        if not relative_path.endswith("/charts/1m.json"):
            continue
        chart_entries.append(item)

    if normalized_focus:
        focused_entries: list[dict[str, object]] = []
        for item in chart_entries:
            relative_path = str(item.get("relative_path") or "")
            parts = relative_path.split("/")
            symbol = parts[1] if len(parts) > 2 and parts[0] == "stocks" else ""
            if symbol in normalized_focus:
                focused_entries.append(item)
        if focused_entries:
            chart_entries = focused_entries

    for item in chart_entries[:3]:
        relative_path = str(item.get("relative_path") or "")
        local_summary = str(item.get("local_summary") or "")
        cloud_summary = str(item.get("cloud_summary") or "")
        matched_flag = bool(item.get("matched"))
        print(
            f"upload_verification_1m path={relative_path} matched={matched_flag} local=({local_summary}) cloud=({cloud_summary})",
            flush=True,
        )


def _resolve_kline_cache_source_dir(args: argparse.Namespace) -> Path:
    requested = Path(args.kline_cache_source_dir)
    candidates = [
        requested,
        ROOT / "data" / "cache" / "kline",
        ROOT / "data" / "stock-kline-cache",
        Path("/data/stock-kline-cache"),
    ]
    seen: set[str] = set()
    for candidate in candidates:
        normalized = str(candidate.resolve()) if candidate.is_absolute() else str((ROOT / candidate).resolve())
        if normalized in seen:
            continue
        seen.add(normalized)
        path = Path(normalized)
        if path.exists() and path.is_dir():
            if path != requested:
                print(f"kline_cache_source_dir_fallback={path}", flush=True)
            return path
    raise RuntimeError(
        "No available kline cache source dir found. "
        f"Tried: {', '.join(sorted(seen))}. "
        "Provide --kline-cache-source-dir explicitly."
    )


def sync_kline_cache_backup(args: argparse.Namespace) -> None:
    source_dir = _resolve_kline_cache_source_dir(args)
    command = [
        sys.executable,
        str(Path(args.sync_kline_cache_script)),
        "backup",
        "--source-dir",
        str(source_dir),
        "--cloud-prefix",
        args.kline_cache_cloud_prefix,
        "--manifest-path",
        str(Path(args.kline_cache_manifest_path)),
        "--pointer-path",
        str(Path(args.kline_cache_pointer_path)),
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
    if bool(getattr(args, "force_upload", False)):
        command.append("--force-upload")
    if args.upload_dry_run:
        command.append("--dry-run")
    _run_command(command)


def sync_kline_cache_restore(args: argparse.Namespace) -> None:
    command = [
        sys.executable,
        str(Path(args.sync_kline_cache_script)),
        "restore",
        "--target-dir",
        str(Path(args.kline_cache_target_dir)),
        "--cloud-prefix",
        args.kline_cache_cloud_prefix,
        "--manifest-path",
        str(Path(args.kline_cache_manifest_path)),
        "--pointer-path",
        str(Path(args.kline_cache_pointer_path)),
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
    if bool(getattr(args, "kline_cache_clean_target_before_restore", False)):
        command.append("--clean-target")
    if args.upload_dry_run:
        command.append("--dry-run")
    _run_command(command)


def main() -> None:
    args = parse_args()

    started_total = time.perf_counter()
    started_at = datetime.now()
    stage_seconds: dict[str, float] = {}
    regeneration_summary: dict[str, object] | None = None
    build_summary: dict[str, object] | None = None
    if bool(getattr(args, "sync_kline_cache_restore_before_regenerate", False)):
        started_restore_kline = time.perf_counter()
        sync_kline_cache_restore(args)
        stage_seconds["restore_kline_cache_seconds"] = time.perf_counter() - started_restore_kline
        print(f"timing restore_kline_cache_seconds={stage_seconds['restore_kline_cache_seconds']:.2f}", flush=True)

    if not args.skip_regenerate:
        started_regenerate = time.perf_counter()
        regeneration_summary = regenerate_holdings(args)
        stage_seconds["regenerate_seconds"] = time.perf_counter() - started_regenerate
        print(f"timing regenerate_seconds={stage_seconds['regenerate_seconds']:.2f}", flush=True)

    latest_dir = Path(args.publish_root) / "latest"
    if not args.skip_build:
        started_build = time.perf_counter()
        build_summary = rebuild_publish_bundle(args, regeneration_summary)
        latest_dir = Path(str(build_summary["latest"]))
        stage_seconds["build_seconds"] = time.perf_counter() - started_build
        print(f"timing build_seconds={stage_seconds['build_seconds']:.2f}", flush=True)

    if not args.skip_upload:
        if bool(getattr(args, "sync_kline_cache", False)):
            started_sync_kline = time.perf_counter()
            sync_kline_cache_backup(args)
            stage_seconds["sync_kline_cache_seconds"] = time.perf_counter() - started_sync_kline
            print(f"timing sync_kline_cache_seconds={stage_seconds['sync_kline_cache_seconds']:.2f}", flush=True)
        started_upload = time.perf_counter()
        upload_publish_bundle(args, latest_dir)
        stage_seconds["upload_seconds"] = time.perf_counter() - started_upload
        print(f"timing upload_seconds={stage_seconds['upload_seconds']:.2f}", flush=True)
        _print_upload_verification_summary(
            DEFAULT_UPLOAD_MANIFEST_PATH,
            list(args.symbols) if args.symbols else None,
        )
    stage_seconds["total_seconds"] = time.perf_counter() - started_total
    print(f"timing total_seconds={stage_seconds['total_seconds']:.2f}", flush=True)

    timing_report = _write_timing_report(
        args,
        started_at=started_at,
        completed_at=datetime.now(),
        stage_seconds=stage_seconds,
        regeneration_summary=regeneration_summary,
        latest_dir=latest_dir,
        build_summary=build_summary,
    )
    print(f"timing_report= {timing_report}", flush=True)


if __name__ == "__main__":
    main()