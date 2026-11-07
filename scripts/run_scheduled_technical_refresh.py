from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from chanlun_api.app import TechnicalRefreshRequest, _run_technical_refresh
from notify.feishu import FeishuConfigError
from notify.signal_notifier import notify_from_reports
from storage_layout import REPORTS_DIR, REPORTS_META_DIR

DEFAULT_NOTIFY_STATE_FILE = REPORTS_META_DIR / "notify_state.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a local technical refresh request without going through HTTP.")
    parser.add_argument("--holdings-file", default=None)
    parser.add_argument("--market", choices=("ALL", "CN", "HK"), default="ALL")
    parser.add_argument("--symbols", nargs="+", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--parallelism", type=int, default=max(1, min(4, os.cpu_count() or 1)))
    parser.add_argument("--refresh-mode", choices=("m30_intraday", "m5_intraday"), required=True)
    parser.add_argument("--tech-timeframes", nargs="+", choices=("day", "60m", "30m", "15m", "5m", "1m"), default=None)
    parser.add_argument("--publish-timeframes", nargs="+", choices=("day", "60m", "30m", "15m", "5m", "1m"), default=None)
    parser.add_argument("--publish-root", default=None)
    parser.add_argument("--reports-root", default=None)
    parser.add_argument("--cloud-prefix", default=None)
    parser.add_argument("--skip-build", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--skip-upload", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--latest-only", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--publish-json-only", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--export-structure-images", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--upload-dry-run", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--notify", action=argparse.BooleanOptionalAction, default=False, help="刷新完扫描买卖点并推送飞书")
    parser.add_argument("--notify-state-file", default=None, help="买卖点通知去重状态文件；缺省 data/_meta/notify_state.json")
    parser.add_argument("--notify-timeframes", nargs="+", default=None, help="仅推送指定周期；缺省用本次刷新的 --tech-timeframes")
    parser.add_argument("--notify-no-forming", action=argparse.BooleanOptionalAction, default=False, help="只推确认买卖点，不推预备/迹象")
    parser.add_argument("--notify-dry-run", action=argparse.BooleanOptionalAction, default=False, help="只预览将推送的买卖点，不发送、不改状态")
    parser.add_argument("--notify-seed-only", action=argparse.BooleanOptionalAction, default=False, help="只把当前买卖点记为基线，不实际推送")
    return parser.parse_args()


def build_request(args: argparse.Namespace) -> TechnicalRefreshRequest:
    payload: dict[str, object] = {
        "market": args.market,
        "symbols": args.symbols,
        "limit": args.limit,
        "parallelism": args.parallelism,
        "refresh_mode": args.refresh_mode,
        "skip_build": args.skip_build,
        "skip_upload": args.skip_upload,
        "latest_only": args.latest_only,
        "publish_json_only": args.publish_json_only,
        "export_structure_images": args.export_structure_images,
        "upload_dry_run": args.upload_dry_run,
    }
    if args.holdings_file:
        payload["holdings_file"] = args.holdings_file
    if args.tech_timeframes:
        payload["tech_timeframes"] = args.tech_timeframes
    if args.publish_timeframes:
        payload["publish_timeframes"] = args.publish_timeframes
    if args.publish_root:
        payload["publish_root"] = args.publish_root
    if args.reports_root:
        payload["reports_root"] = args.reports_root
    if args.cloud_prefix:
        payload["cloud_prefix"] = args.cloud_prefix
    return TechnicalRefreshRequest(**payload)


def maybe_notify_signals(args: argparse.Namespace) -> None:
    """刷新完成后扫描买卖点并推送飞书（默认仅推本次刷新的周期；缺凭据时告警不中断）。"""

    if not args.notify:
        return
    reports_dir = Path(args.reports_root) if args.reports_root else REPORTS_DIR
    state_file = Path(args.notify_state_file) if args.notify_state_file else DEFAULT_NOTIFY_STATE_FILE
    timeframes = args.notify_timeframes or args.tech_timeframes
    try:
        new_events = notify_from_reports(
            reports_dir,
            state_path=state_file,
            timeframes=timeframes,
            include_forming=not args.notify_no_forming,
            dry_run=args.notify_dry_run,
            seed_only=args.notify_seed_only,
        )
    except FeishuConfigError as error:
        print(f"scheduled_technical_refresh_notify_skip {error}", flush=True)
        return
    summary = {
        "new": len(new_events),
        "dry_run": args.notify_dry_run,
        "seed_only": args.notify_seed_only,
        "timeframes": list(timeframes) if timeframes else None,
    }
    print("scheduled_technical_refresh_notify", json.dumps(summary, ensure_ascii=False), flush=True)


def main() -> int:
    args = parse_args()
    request = build_request(args)
    print("scheduled_technical_refresh_request", json.dumps(request.model_dump(), ensure_ascii=False), flush=True)
    result = _run_technical_refresh(request)
    print("scheduled_technical_refresh_result", json.dumps(result, ensure_ascii=False), flush=True)
    maybe_notify_signals(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())