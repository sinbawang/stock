from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import importlib.util
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

from storage_layout import REPORTS_META_DIR, holdings_file


@dataclass(frozen=True)
class Target:
    symbol: str
    name: str
    market: str


@dataclass(frozen=True)
class BatchProbeResult:
    archive_json_path: Path
    latest_json_path: Path
    archive_text_path: Path


def _load_probe_module():
    module_spec = importlib.util.spec_from_file_location(
        "run_day_incremental_probe",
        SCRIPTS / "run_day_incremental_probe.py",
    )
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError("failed to load run_day_incremental_probe.py")
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = module
    module_spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按持仓批量执行 day 增量探针并输出对比榜单")
    parser.add_argument("--holdings-file", default=str(holdings_file()), help="持仓文件路径")
    parser.add_argument("--market", choices=("ALL", "CN", "HK"), default="ALL", help="市场过滤")
    parser.add_argument("--symbols", nargs="+", default=None, help="可选代码过滤")
    parser.add_argument("--limit", type=int, default=None, help="可选数量限制")
    parser.add_argument("--day-bars", type=int, default=1200, help="day 级别目标根数")
    parser.add_argument("--incremental-overlap-bars", type=int, default=120, help="增量回看根数")
    parser.add_argument("--history-window", type=int, default=10, help="历史趋势窗口")
    parser.add_argument(
        "--execute-run",
        dest="execute_run",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="是否先触发每个标的 day 刷新；默认 false 仅读取现有 tech.json。",
    )
    parser.add_argument("--meta-dir", default=str(REPORTS_META_DIR), help="输出目录")
    return parser.parse_args()


def _normalize_symbol(symbol: str, market: str) -> str:
    text = str(symbol).strip()
    if market == "HK":
        return text.zfill(5)
    return text.zfill(6) if text.isdigit() else text


def _load_targets(holdings_path: Path) -> list[Target]:
    payload = json.loads(holdings_path.read_text(encoding="utf-8"))
    raw_entries: list[tuple[str, dict]] = []

    markets = payload.get("markets")
    if isinstance(markets, dict):
        for market_code, entries in markets.items():
            if not isinstance(entries, list):
                continue
            for item in entries:
                if isinstance(item, dict):
                    raw_entries.append((str(market_code).upper(), item))
    else:
        default_market = str(payload.get("market") or "CN").upper()
        for item in payload.get("holdings", []):
            if isinstance(item, dict):
                raw_entries.append((default_market, item))

    targets: list[Target] = []
    for market, item in raw_entries:
        symbol = str(item.get("symbol") or "").strip()
        name = str(item.get("name") or "").strip()
        if not symbol:
            continue
        resolved_market = "HK" if market == "HK" else "CN"
        targets.append(Target(symbol=_normalize_symbol(symbol, resolved_market), name=name or symbol, market=resolved_market))
    return targets


def _filter_targets(targets: list[Target], args: argparse.Namespace) -> list[Target]:
    selected = list(targets)
    if args.market != "ALL":
        selected = [item for item in selected if item.market == args.market]

    if args.symbols:
        expected = {str(value).strip() for value in args.symbols if str(value).strip()}
        expanded = expected | {value.zfill(5) for value in expected} | {value.zfill(6) for value in expected}
        selected = [item for item in selected if item.symbol in expanded]

    if args.limit is not None and args.limit >= 0:
        selected = selected[: args.limit]
    return selected


def _build_summary_rows(rows: list[dict[str, object]]) -> dict[str, object]:
    count = len(rows)
    if count == 0:
        return {
            "count": 0,
            "warm_cache_hits": 0,
            "warm_cache_ratio": None,
            "avg_saved_rows_ratio": None,
            "avg_elapsed_seconds": None,
            "top_saved_rows_ratio": [],
            "bottom_saved_rows_ratio": [],
        }

    warm_hits = sum(1 for row in rows if bool(row.get("warm_cache_hit")))
    saved_ratios = [float(row.get("saved_rows_ratio")) for row in rows if isinstance(row.get("saved_rows_ratio"), (int, float))]
    elapsed_values = [float(row.get("run_elapsed_seconds")) for row in rows if isinstance(row.get("run_elapsed_seconds"), (int, float))]

    sorted_by_saved = sorted(
        rows,
        key=lambda row: float(row.get("saved_rows_ratio")) if isinstance(row.get("saved_rows_ratio"), (int, float)) else -1.0,
        reverse=True,
    )
    top_rows = [
        {
            "symbol": row["symbol"],
            "name": row["name"],
            "market": row["market"],
            "saved_rows_ratio": row.get("saved_rows_ratio"),
            "remote_rows": row.get("remote_rows"),
            "analysis_rows": row.get("analysis_rows"),
        }
        for row in sorted_by_saved[:3]
    ]
    bottom_rows = [
        {
            "symbol": row["symbol"],
            "name": row["name"],
            "market": row["market"],
            "saved_rows_ratio": row.get("saved_rows_ratio"),
            "remote_rows": row.get("remote_rows"),
            "analysis_rows": row.get("analysis_rows"),
        }
        for row in sorted_by_saved[-3:]
    ]

    return {
        "count": count,
        "warm_cache_hits": warm_hits,
        "warm_cache_ratio": round(warm_hits / count, 4),
        "avg_saved_rows_ratio": round(sum(saved_ratios) / len(saved_ratios), 4) if saved_ratios else None,
        "avg_elapsed_seconds": round(sum(elapsed_values) / len(elapsed_values), 2) if elapsed_values else None,
        "top_saved_rows_ratio": top_rows,
        "bottom_saved_rows_ratio": bottom_rows,
    }


def _render_text(payload: dict[str, object]) -> str:
    summary = payload.get("summary") or {}
    lines = [
        "【Day 批量增量探针】",
        "",
        f"generated_at: {payload.get('generated_at')}",
        f"count: {summary.get('count')}",
        f"warm_cache_ratio: {summary.get('warm_cache_ratio')}",
        f"avg_saved_rows_ratio: {summary.get('avg_saved_rows_ratio')}",
        f"avg_elapsed_seconds: {summary.get('avg_elapsed_seconds')}",
        "",
        "Top3 saved_rows_ratio:",
    ]

    for row in summary.get("top_saved_rows_ratio") or []:
        lines.append(
            f"- {row.get('market')} {row.get('symbol')} {row.get('name')}: "
            f"saved_rows_ratio={row.get('saved_rows_ratio')} remote={row.get('remote_rows')} analysis={row.get('analysis_rows')}"
        )

    lines.append("")
    lines.append("Bottom3 saved_rows_ratio:")
    for row in summary.get("bottom_saved_rows_ratio") or []:
        lines.append(
            f"- {row.get('market')} {row.get('symbol')} {row.get('name')}: "
            f"saved_rows_ratio={row.get('saved_rows_ratio')} remote={row.get('remote_rows')} analysis={row.get('analysis_rows')}"
        )

    return "\n".join(lines) + "\n"


def run_batch_probe(args: argparse.Namespace) -> BatchProbeResult:
    probe_module = _load_probe_module()
    targets = _filter_targets(_load_targets(Path(args.holdings_file)), args)
    if not targets:
        raise RuntimeError("no targets selected")

    rows: list[dict[str, object]] = []
    for target in targets:
        result = probe_module.run_probe(
            symbol=target.symbol,
            name=target.name,
            market=target.market,
            day_bars=args.day_bars,
            overlap_bars=args.incremental_overlap_bars,
            history_window=args.history_window,
            execute_run=bool(args.execute_run),
            meta_dir=Path(args.meta_dir),
        )
        latest_payload = json.loads(result.latest_json_path.read_text(encoding="utf-8"))
        metrics = latest_payload.get("metrics") or {}
        rows.append(
            {
                "symbol": target.symbol,
                "name": target.name,
                "market": target.market,
                "saved_rows_ratio": metrics.get("saved_rows_ratio"),
                "warm_cache_hit": metrics.get("warm_cache_hit"),
                "remote_rows": metrics.get("remote_rows"),
                "analysis_rows": metrics.get("analysis_rows"),
                "run_elapsed_seconds": metrics.get("run_elapsed_seconds"),
                "report_path": str(result.archive_json_path),
            }
        )

    payload = {
        "report_type": "day_incremental_probe_batch",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "request": {
            "holdings_file": str(args.holdings_file),
            "market": args.market,
            "symbols": list(args.symbols) if args.symbols else None,
            "limit": args.limit,
            "day_bars": args.day_bars,
            "incremental_overlap_bars": args.incremental_overlap_bars,
            "history_window": args.history_window,
            "execute_run": bool(args.execute_run),
        },
        "summary": _build_summary_rows(rows),
        "rows": rows,
    }

    meta_dir = Path(args.meta_dir)
    meta_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_json_path = meta_dir / f"day_incremental_probe_batch_{stamp}.json"
    latest_json_path = meta_dir / "day_incremental_probe_batch_latest.json"
    archive_text_path = meta_dir / f"day_incremental_probe_batch_{stamp}.txt"

    archive_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    latest_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    archive_text_path.write_text(_render_text(payload), encoding="utf-8")

    return BatchProbeResult(
        archive_json_path=archive_json_path,
        latest_json_path=latest_json_path,
        archive_text_path=archive_text_path,
    )


def main() -> None:
    args = parse_args()
    result = run_batch_probe(args)
    print(f"day_batch_probe_report= {result.archive_json_path}", flush=True)
    print(f"day_batch_probe_report_latest= {result.latest_json_path}", flush=True)
    print(f"day_batch_probe_summary= {result.archive_text_path}", flush=True)


if __name__ == "__main__":
    main()
