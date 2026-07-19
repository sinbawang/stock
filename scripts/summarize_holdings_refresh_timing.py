from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from storage_layout import REPORTS_META_DIR


DEFAULT_TIMING_PATH = REPORTS_META_DIR / "holdings_refresh_timing_latest.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a readable bottleneck summary from holdings refresh timing JSON.")
    parser.add_argument("--timing-file", default=str(DEFAULT_TIMING_PATH), help="Timing JSON path. Defaults to reports/_meta/holdings_refresh_timing_latest.json")
    parser.add_argument("--top", type=int, default=8, help="How many slowest holdings to print")
    return parser.parse_args()


def read_payload(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def format_seconds(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "-"
    return f"{float(value):.2f}s"


def format_percent(numerator: object, denominator: object) -> str:
    if not isinstance(numerator, (int, float)) or not isinstance(denominator, (int, float)):
        return "-"
    total = float(denominator)
    if total <= 0:
        return "-"
    return f"{float(numerator) / total * 100:.1f}%"


def print_stage_summary(payload: dict[str, object]) -> None:
    stages = payload.get("stages") or {}
    if not isinstance(stages, dict):
        print("Stages: missing")
        return

    total_seconds = stages.get("total_seconds")
    print("== Stage Summary ==")
    for key in ("regenerate_seconds", "build_seconds", "upload_seconds", "total_seconds"):
        if key not in stages:
            continue
        value = stages.get(key)
        suffix = ""
        if key != "total_seconds":
            suffix = f"  ({format_percent(value, total_seconds)})"
        print(f"{key:20} {format_seconds(value):>10}{suffix}")


def print_request_summary(payload: dict[str, object]) -> None:
    request = payload.get("request") or {}
    if not isinstance(request, dict):
        return

    tech_timeframes = request.get("tech_timeframes")
    symbols = request.get("symbols")
    print("== Request ==")
    print(f"market                {request.get('market') or '-'}")
    print(f"parallelism           {request.get('parallelism')}")
    print(f"skip_regenerate       {request.get('skip_regenerate')}")
    print(f"skip_build            {request.get('skip_build')}")
    print(f"skip_upload           {request.get('skip_upload')}")
    print(f"tech_timeframes       {','.join(tech_timeframes) if isinstance(tech_timeframes, list) else '-'}")
    print(f"symbols               {','.join(symbols) if isinstance(symbols, list) and symbols else 'ALL'}")


def print_market_summary(payload: dict[str, object]) -> None:
    regeneration = payload.get("regeneration") or {}
    if not isinstance(regeneration, dict):
        print("== Market Summary ==")
        print("regeneration data not present")
        return

    per_market = regeneration.get("per_market") or []
    print("== Market Summary ==")
    if not isinstance(per_market, list) or not per_market:
        print("regeneration data not present")
        return

    header = f"{'market':<8} {'count':>5} {'ok':>5} {'fail':>5} {'avg':>10} {'min':>10} {'max':>10} {'sum':>10}"
    print(header)
    for item in per_market:
        if not isinstance(item, dict):
            continue
        print(
            f"{str(item.get('market') or '-'): <8}"
            f"{int(item.get('count') or 0):>5}"
            f"{int(item.get('generated_count') or 0):>5}"
            f"{int(item.get('failed_count') or 0):>5}"
            f"{format_seconds(item.get('avg_seconds')):>10}"
            f"{format_seconds(item.get('min_seconds')):>10}"
            f"{format_seconds(item.get('max_seconds')):>10}"
            f"{format_seconds(item.get('total_seconds')):>10}"
        )


def print_slowest_holdings(payload: dict[str, object], top_n: int) -> None:
    regeneration = payload.get("regeneration") or {}
    if not isinstance(regeneration, dict):
        print("== Slowest Holdings ==")
        print("regeneration data not present")
        return

    per_holding = regeneration.get("per_holding") or []
    if not isinstance(per_holding, list):
        print("== Slowest Holdings ==")
        print("regeneration data not present")
        return

    rows = [item for item in per_holding if isinstance(item, dict) and item.get("status") == "generated"]
    rows.sort(key=lambda item: float(item.get("seconds") or 0.0), reverse=True)

    print("== Slowest Holdings ==")
    if not rows:
        print("no generated holdings in timing file")
        return

    header = f"{'rank':<6} {'market':<8} {'symbol':<8} {'seconds':>10} {'bucket':<12} name"
    print(header)
    for index, item in enumerate(rows[: max(top_n, 1)], start=1):
        print(
            f"{index:<6}"
            f"{str(item.get('market') or '-'): <8}"
            f"{str(item.get('symbol') or '-'): <8}"
            f"{format_seconds(item.get('seconds')):>10} "
            f"{str(item.get('combined_bucket') or '-'): <12}"
            f"{str(item.get('name') or '-') }"
        )


def print_failures(payload: dict[str, object]) -> None:
    regeneration = payload.get("regeneration") or {}
    if not isinstance(regeneration, dict):
        return

    failed = regeneration.get("failed_holdings") or []
    if not isinstance(failed, list) or not failed:
        return

    print("== Failures ==")
    for item in failed:
        if not isinstance(item, dict):
            continue
        print(f"{item.get('market')} {item.get('symbol')} {item.get('name')}: {item.get('error')}")


def main() -> None:
    args = parse_args()
    timing_path = Path(args.timing_file)
    if not timing_path.exists():
        raise FileNotFoundError(f"Timing file not found: {timing_path}")

    payload = read_payload(timing_path)
    print(f"Timing file: {timing_path}")
    print(f"Generated at: {payload.get('generated_at') or '-'}")
    print()
    print_request_summary(payload)
    print()
    print_stage_summary(payload)
    print()
    print_market_summary(payload)
    print()
    print_slowest_holdings(payload, args.top)
    print_failures(payload)


if __name__ == "__main__":
    main()