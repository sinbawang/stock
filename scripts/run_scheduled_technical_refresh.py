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
    parser.add_argument("--publish-json-only", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--upload-dry-run", action=argparse.BooleanOptionalAction, default=False)
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


def main() -> int:
    args = parse_args()
    request = build_request(args)
    print("scheduled_technical_refresh_request", json.dumps(request.model_dump(), ensure_ascii=False), flush=True)
    result = _run_technical_refresh(request)
    print("scheduled_technical_refresh_result", json.dumps(result, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())