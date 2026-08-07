from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from storage_layout import REPORTS_DIR, REPORTS_META_DIR


@dataclass(frozen=True)
class ProbeResult:
    archive_json_path: Path
    latest_json_path: Path
    archive_text_path: Path


def _load_batch_module():
    module_spec = importlib.util.spec_from_file_location(
        "batch_prepare_chanlun_reports",
        SCRIPTS / "batch_prepare_chanlun_reports.py",
    )
    if module_spec is None or module_spec.loader is None:
        raise RuntimeError("failed to load batch_prepare_chanlun_reports.py")
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = module
    module_spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Day 级别本地历史仓库与增量抓取对比探针")
    parser.add_argument("symbol", help="标的代码，例如 000651 或 00700")
    parser.add_argument("--name", default="", help="标的名称，可选")
    parser.add_argument("--market", choices=("CN", "HK"), default="CN", help="市场，默认 CN")
    parser.add_argument("--day-bars", type=int, default=1200, help="day 级别分析目标根数")
    parser.add_argument("--incremental-overlap-bars", type=int, default=120, help="增量回看根数")
    parser.add_argument("--history-window", type=int, default=10, help="历史趋势窗口")
    parser.add_argument(
        "--execute-run",
        dest="execute_run",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="是否先执行一次 day 级别批处理，再读取 tech.json 生成对比报告。",
    )
    parser.add_argument("--meta-dir", default=str(REPORTS_META_DIR), help="报告输出目录")
    return parser.parse_args()


def _normalize_symbol(symbol: str, market: str) -> str:
    s = symbol.strip()
    if market == "HK":
        return s.zfill(5)
    return s.zfill(6) if s.isdigit() else s


def _build_temp_holdings(symbol: str, name: str, market: str) -> Path:
    payload = {
        "markets": {
            market: [
                {
                    "symbol": symbol,
                    "name": name or symbol,
                }
            ]
        }
    }
    handle = tempfile.NamedTemporaryFile(prefix="day_probe_", suffix=".json", delete=False, dir=str(ROOT / "build"))
    path = Path(handle.name)
    handle.close()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _run_day_prepare(*, symbol: str, name: str, market: str, day_bars: int, overlap_bars: int) -> dict[str, object]:
    batch = _load_batch_module()
    holdings_file = _build_temp_holdings(symbol, name, market)
    started = time.perf_counter()
    try:
        result = batch.run_batch_prepare(
            holdings_path=holdings_file,
            day_bars=day_bars,
            pending_reverse_mode="effective_only",
            zhongshu_level="bi",
            timeframes=("day",),
            use_local_store=True,
            incremental_overlap_bars=overlap_bars,
        )
    finally:
        try:
            holdings_file.unlink(missing_ok=True)
        except OSError:
            pass
    elapsed = round(time.perf_counter() - started, 2)
    return {
        "elapsed_seconds": elapsed,
        "security_count": result.security_count,
        "manifest_path": str(result.manifest_path),
    }


def _load_day_tech_json(symbol: str) -> dict[str, object]:
    path = REPORTS_DIR / symbol / "day" / "tech.json"
    if not path.exists():
        raise FileNotFoundError(f"day tech.json not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _derive_metrics(local_store: dict[str, object], run_elapsed_seconds: float | None) -> dict[str, object]:
    remote_rows = _safe_int(local_store.get("remote_rows"))
    analysis_rows = _safe_int(local_store.get("analysis_rows"))
    local_rows_before = _safe_int(local_store.get("local_rows_before"))
    saved_rows = max(0, analysis_rows - remote_rows)
    saved_ratio = round(saved_rows / analysis_rows, 4) if analysis_rows > 0 else None

    return {
        "local_rows_before": local_rows_before,
        "remote_rows": remote_rows,
        "analysis_rows": analysis_rows,
        "added_rows": _safe_int(local_store.get("added_rows")),
        "updated_rows": _safe_int(local_store.get("updated_rows")),
        "saved_rows": saved_rows,
        "saved_rows_ratio": saved_ratio,
        "requested_start": local_store.get("requested_start"),
        "effective_start": local_store.get("effective_start"),
        "overlap_bars": _safe_int(local_store.get("overlap_bars")),
        "warm_cache_hit": local_rows_before > 0,
        "run_elapsed_seconds": run_elapsed_seconds,
    }


def _history_path(meta_dir: Path) -> Path:
    return meta_dir / "day_incremental_probe_history.jsonl"


def _append_history(meta_dir: Path, record: dict[str, object]) -> None:
    path = _history_path(meta_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _load_history(meta_dir: Path, *, symbol: str, window: int) -> list[dict[str, object]]:
    path = _history_path(meta_dir)
    if not path.exists():
        return []

    rows: list[dict[str, object]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(payload.get("symbol")) == symbol:
            rows.append(payload)
    if window <= 0:
        return rows
    return rows[-window:]


def _build_trend(history_rows: list[dict[str, object]]) -> dict[str, object]:
    if not history_rows:
        return {
            "sample_count": 0,
            "warm_cache_ratio": None,
            "avg_saved_rows_ratio": None,
            "avg_elapsed_seconds": None,
        }

    warm_hits = 0
    saved_ratio_sum = 0.0
    elapsed_sum = 0.0
    elapsed_count = 0
    for row in history_rows:
        if bool(row.get("warm_cache_hit")):
            warm_hits += 1
        saved_ratio = row.get("saved_rows_ratio")
        if isinstance(saved_ratio, (int, float)):
            saved_ratio_sum += float(saved_ratio)
        elapsed = row.get("run_elapsed_seconds")
        if isinstance(elapsed, (int, float)):
            elapsed_sum += float(elapsed)
            elapsed_count += 1

    sample_count = len(history_rows)
    return {
        "sample_count": sample_count,
        "warm_cache_ratio": round(warm_hits / sample_count, 4),
        "avg_saved_rows_ratio": round(saved_ratio_sum / sample_count, 4),
        "avg_elapsed_seconds": round(elapsed_sum / elapsed_count, 2) if elapsed_count > 0 else None,
    }


def _render_text(payload: dict[str, object]) -> str:
    metrics = payload.get("metrics") or {}
    trend = payload.get("history_trend") or {}
    lines = [
        "【Day 增量探针】",
        "",
        f"symbol: {payload.get('symbol')} {payload.get('name')}",
        f"generated_at: {payload.get('generated_at')}",
        f"local_rows_before: {metrics.get('local_rows_before')}",
        f"remote_rows: {metrics.get('remote_rows')}",
        f"analysis_rows: {metrics.get('analysis_rows')}",
        f"saved_rows_ratio: {metrics.get('saved_rows_ratio')}",
        f"warm_cache_hit: {metrics.get('warm_cache_hit')}",
        f"requested_start: {metrics.get('requested_start')}",
        f"effective_start: {metrics.get('effective_start')}",
        "",
        "最近趋势:",
        f"- sample_count: {trend.get('sample_count')}",
        f"- warm_cache_ratio: {trend.get('warm_cache_ratio')}",
        f"- avg_saved_rows_ratio: {trend.get('avg_saved_rows_ratio')}",
        f"- avg_elapsed_seconds: {trend.get('avg_elapsed_seconds')}",
    ]
    return "\n".join(lines) + "\n"


def run_probe(
    *,
    symbol: str,
    name: str,
    market: str,
    day_bars: int,
    overlap_bars: int,
    history_window: int,
    execute_run: bool,
    meta_dir: Path,
) -> ProbeResult:
    normalized_symbol = _normalize_symbol(symbol, market)
    run_info = None
    if execute_run:
        run_info = _run_day_prepare(
            symbol=normalized_symbol,
            name=name,
            market=market,
            day_bars=day_bars,
            overlap_bars=overlap_bars,
        )

    tech_payload = _load_day_tech_json(normalized_symbol)
    local_store = (((tech_payload.get("data_fetch") or {}) if isinstance(tech_payload.get("data_fetch"), dict) else {}).get("local_store") or {})
    if not isinstance(local_store, dict):
        raise RuntimeError("day tech.json does not contain data_fetch.local_store")

    metrics = _derive_metrics(local_store, run_info.get("elapsed_seconds") if run_info else None)
    record = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "symbol": normalized_symbol,
        "name": name,
        "market": market,
        "day_bars": day_bars,
        **metrics,
    }
    _append_history(meta_dir, record)

    history_rows = _load_history(meta_dir, symbol=normalized_symbol, window=history_window)
    trend = _build_trend(history_rows)

    payload = {
        "report_type": "day_incremental_probe",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "symbol": normalized_symbol,
        "name": name,
        "market": market,
        "day_bars": day_bars,
        "run_info": run_info,
        "metrics": metrics,
        "history_trend": trend,
    }

    meta_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_json_path = meta_dir / f"day_incremental_probe_{normalized_symbol}_{stamp}.json"
    latest_json_path = meta_dir / f"day_incremental_probe_{normalized_symbol}_latest.json"
    archive_text_path = meta_dir / f"day_incremental_probe_{normalized_symbol}_{stamp}.txt"

    archive_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    latest_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    archive_text_path.write_text(_render_text(payload), encoding="utf-8")

    return ProbeResult(
        archive_json_path=archive_json_path,
        latest_json_path=latest_json_path,
        archive_text_path=archive_text_path,
    )


def main() -> None:
    args = parse_args()
    result = run_probe(
        symbol=args.symbol,
        name=args.name,
        market=args.market,
        day_bars=args.day_bars,
        overlap_bars=args.incremental_overlap_bars,
        history_window=args.history_window,
        execute_run=bool(args.execute_run),
        meta_dir=Path(args.meta_dir),
    )
    print(f"day_probe_report= {result.archive_json_path}", flush=True)
    print(f"day_probe_report_latest= {result.latest_json_path}", flush=True)
    print(f"day_probe_summary= {result.archive_text_path}", flush=True)


if __name__ == "__main__":
    main()
