from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
if str(BUILD) not in sys.path:
    sys.path.insert(0, str(BUILD))

from probe_intraday_prebreak_sample import _load_rows, _replay, _select_auto_cutoffs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay all available 1m raw CSV reports and find historical confirmed buy-side cutoffs.")
    parser.add_argument("--symbols", nargs="*", default=None, help="Optional symbol allow-list. Defaults to all symbols with 1m tech.json.")
    parser.add_argument("--start", default=None, help="Optional lower bound timestamp for replay scan")
    parser.add_argument("--end", default=None, help="Optional upper bound timestamp for replay scan")
    parser.add_argument("--step", type=int, default=5, help="Only inspect every Nth timestamp to speed up scans. Defaults to 5.")
    parser.add_argument("--per-symbol-limit", type=int, default=3, help="Maximum confirmed-buy cutoffs to keep per symbol.")
    parser.add_argument("--output", default=None, help="Optional JSON output path")
    return parser.parse_args()


def _iter_symbol_dirs(symbol_filters: set[str] | None) -> list[Path]:
    report_roots = sorted((ROOT / "data" / "reports").glob("*/1m/tech.json"))
    symbol_dirs: list[Path] = []
    for tech_path in report_roots:
        symbol = tech_path.parent.parent.name
        if symbol_filters and symbol not in symbol_filters:
            continue
        symbol_dirs.append(tech_path.parent.parent)
    return symbol_dirs


def _load_name(symbol_dir: Path) -> str:
    tech_path = symbol_dir / "1m" / "tech.json"
    try:
        payload = json.loads(tech_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return symbol_dir.name
    if isinstance(payload, dict):
        return str(payload.get("name") or symbol_dir.name)
    return symbol_dir.name


def _is_confirmed_buy_match(result: dict[str, Any]) -> bool:
    if result.get("same_level_consumption_level") != "confirmed":
        return False
    buy_points = list(result.get("buy_points") or [])
    return bool(buy_points)


def _scan_symbol(symbol: str, name: str, start: str | None, end: str | None, step: int, per_symbol_limit: int) -> dict[str, Any]:
    rows = _load_rows(symbol, "1m")
    cutoffs = _select_auto_cutoffs(rows, start, end)
    cutoffs = cutoffs[:: max(step, 1)]
    matches: list[dict[str, Any]] = []
    for cutoff in cutoffs:
        result = _replay(symbol, name, cutoff, rows)
        if not _is_confirmed_buy_match(result):
            continue
        matches.append(result)
        if len(matches) >= max(per_symbol_limit, 0):
            break
    return {
        "symbol": symbol,
        "name": name,
        "scanned": len(cutoffs),
        "matches": matches,
    }


def main() -> int:
    args = parse_args()
    symbol_filters = {item.strip() for item in args.symbols if item.strip()} if args.symbols else None
    symbol_dirs = _iter_symbol_dirs(symbol_filters)
    results = [
        _scan_symbol(symbol_dir.name, _load_name(symbol_dir), args.start, args.end, args.step, args.per_symbol_limit)
        for symbol_dir in symbol_dirs
    ]
    matched = [item for item in results if item["matches"]]
    output_payload = {
        "symbols_scanned": len(results),
        "matched_symbols": len(matched),
        "start": args.start,
        "end": args.end,
        "step": args.step,
        "per_symbol_limit": args.per_symbol_limit,
        "results": results,
    }
    output_path = Path(args.output) if args.output else ROOT / "build" / "scan_real_1m_confirmed_buy_samples.json"
    output_path.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"symbols_scanned={len(results)} matched_symbols={len(matched)} step={args.step}")
    for item in matched:
        first = item["matches"][0]
        print(
            "MATCH "
            f"{item['symbol']} {item['name']} count={len(item['matches'])} "
            f"first_cutoff={first.get('cutoff')} buy_points={first.get('buy_points')}"
        )
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())