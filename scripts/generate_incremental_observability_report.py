from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from statistics import median
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from storage_layout import REPORTS_DIR, REPORTS_META_DIR


DEFAULT_TIMEFRAMES = ("day", "60m", "30m", "15m", "5m", "1m")


@dataclass(frozen=True)
class ObservabilityReportResult:
    archive_json_path: Path
    latest_json_path: Path
    archive_text_path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="汇总本地 K 线仓库增量命中率与耗时趋势")
    parser.add_argument("--reports-root", default=str(REPORTS_DIR), help="技术报告根目录")
    parser.add_argument("--meta-dir", default=str(REPORTS_META_DIR), help="观测报告输出目录")
    parser.add_argument(
        "--timeframes",
        nargs="+",
        choices=DEFAULT_TIMEFRAMES,
        default=list(DEFAULT_TIMEFRAMES),
        help="统计的技术级别",
    )
    parser.add_argument(
        "--timing-window",
        type=int,
        default=7,
        help="耗时基线窗口（从最近历史中取 N 个样本计算中位数，默认 7）",
    )
    return parser.parse_args()


def _safe_int(value: object) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _infer_market(symbol: str) -> str:
    text = symbol.strip()
    if len(text) == 5 and text.isdigit():
        return "HK"
    return "CN"


def _list_target_tech_json_paths(reports_root: Path, timeframes: tuple[str, ...]) -> list[Path]:
    paths: list[Path] = []
    for symbol_dir in reports_root.iterdir():
        if not symbol_dir.is_dir() or symbol_dir.name.startswith("_"):
            continue
        for timeframe in timeframes:
            tech_path = symbol_dir / timeframe / "tech.json"
            if tech_path.exists():
                paths.append(tech_path)
    return sorted(paths)


def _build_timeframe_bucket() -> dict[str, int]:
    return {
        "report_count": 0,
        "local_store_count": 0,
        "warm_cache_count": 0,
        "remote_rows": 0,
        "analysis_rows": 0,
        "saved_rows": 0,
        "added_rows": 0,
        "updated_rows": 0,
    }


def _load_timing_trend(meta_dir: Path, window: int) -> dict[str, object] | None:
    files = sorted(
        [
            path
            for path in meta_dir.glob("holdings_refresh_timing_*.json")
            if path.name != "holdings_refresh_timing_latest.json"
        ],
        key=lambda item: item.stat().st_mtime,
    )
    if not files:
        return None

    series: list[tuple[Path, float]] = []
    for file_path in files:
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        total_seconds = payload.get("stages", {}).get("total_seconds")
        if isinstance(total_seconds, (int, float)):
            series.append((file_path, float(total_seconds)))

    if not series:
        return None

    latest_path, latest_total = series[-1]
    baseline_values = [value for _path, value in series[:-1]][-max(0, window):]
    baseline_median = median(baseline_values) if baseline_values else None
    improvement_pct = None
    if baseline_median and baseline_median > 0:
        improvement_pct = round((baseline_median - latest_total) / baseline_median * 100, 2)

    return {
        "latest_path": str(latest_path),
        "latest_total_seconds": round(latest_total, 2),
        "baseline_window": max(0, window),
        "baseline_sample_count": len(baseline_values),
        "baseline_median_total_seconds": round(float(baseline_median), 2) if baseline_median is not None else None,
        "improvement_pct_vs_baseline": improvement_pct,
    }


def build_observability_payload(
    reports_root: Path,
    *,
    timeframes: tuple[str, ...],
    meta_dir: Path,
    timing_window: int,
) -> dict[str, object]:
    by_timeframe = {timeframe: _build_timeframe_bucket() for timeframe in timeframes}
    by_market = {"CN": _build_timeframe_bucket(), "HK": _build_timeframe_bucket()}

    scanned = 0
    local_store_enabled = 0
    warm_cache = 0
    json_errors: list[str] = []

    for tech_path in _list_target_tech_json_paths(reports_root, timeframes):
        scanned += 1
        try:
            payload = json.loads(tech_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            json_errors.append(str(tech_path))
            continue

        symbol = str(payload.get("symbol") or tech_path.parent.parent.name)
        timeframe = str(payload.get("timeframe") or tech_path.parent.name).strip().lower()
        if timeframe not in by_timeframe:
            continue
        market = _infer_market(symbol)
        timeframe_bucket = by_timeframe[timeframe]
        market_bucket = by_market[market]

        timeframe_bucket["report_count"] += 1
        market_bucket["report_count"] += 1

        data_fetch = payload.get("data_fetch") or {}
        local_store = data_fetch.get("local_store") if isinstance(data_fetch, dict) else None
        if not isinstance(local_store, dict):
            continue

        local_store_enabled += 1
        timeframe_bucket["local_store_count"] += 1
        market_bucket["local_store_count"] += 1

        remote_rows = _safe_int(local_store.get("remote_rows"))
        analysis_rows = _safe_int(local_store.get("analysis_rows"))
        added_rows = _safe_int(local_store.get("added_rows"))
        updated_rows = _safe_int(local_store.get("updated_rows"))
        local_rows_before = _safe_int(local_store.get("local_rows_before"))
        saved_rows = max(0, analysis_rows - remote_rows)

        if local_rows_before > 0:
            warm_cache += 1
            timeframe_bucket["warm_cache_count"] += 1
            market_bucket["warm_cache_count"] += 1

        timeframe_bucket["remote_rows"] += remote_rows
        timeframe_bucket["analysis_rows"] += analysis_rows
        timeframe_bucket["saved_rows"] += saved_rows
        timeframe_bucket["added_rows"] += added_rows
        timeframe_bucket["updated_rows"] += updated_rows

        market_bucket["remote_rows"] += remote_rows
        market_bucket["analysis_rows"] += analysis_rows
        market_bucket["saved_rows"] += saved_rows
        market_bucket["added_rows"] += added_rows
        market_bucket["updated_rows"] += updated_rows

    total_remote_rows = sum(bucket["remote_rows"] for bucket in by_timeframe.values())
    total_analysis_rows = sum(bucket["analysis_rows"] for bucket in by_timeframe.values())
    total_saved_rows = sum(bucket["saved_rows"] for bucket in by_timeframe.values())

    timeframe_metrics = []
    for timeframe in timeframes:
        bucket = by_timeframe[timeframe]
        saved_ratio = round(bucket["saved_rows"] / bucket["analysis_rows"], 4) if bucket["analysis_rows"] > 0 else None
        timeframe_metrics.append(
            {
                "timeframe": timeframe,
                **bucket,
                "saved_rows_ratio": saved_ratio,
            }
        )

    market_metrics = []
    for market in ("CN", "HK"):
        bucket = by_market[market]
        saved_ratio = round(bucket["saved_rows"] / bucket["analysis_rows"], 4) if bucket["analysis_rows"] > 0 else None
        market_metrics.append(
            {
                "market": market,
                **bucket,
                "saved_rows_ratio": saved_ratio,
            }
        )

    timing_trend = _load_timing_trend(meta_dir, timing_window)
    return {
        "report_type": "incremental_observability",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "reports_root": str(reports_root),
        "timeframes": list(timeframes),
        "scan": {
            "scanned_tech_json_count": scanned,
            "local_store_enabled_count": local_store_enabled,
            "warm_cache_count": warm_cache,
            "parse_error_count": len(json_errors),
            "parse_error_files": json_errors,
        },
        "aggregate": {
            "saved_rows": total_saved_rows,
            "remote_rows": total_remote_rows,
            "analysis_rows": total_analysis_rows,
            "saved_rows_ratio": round(total_saved_rows / total_analysis_rows, 4) if total_analysis_rows > 0 else None,
            "local_store_coverage_ratio": round(local_store_enabled / scanned, 4) if scanned > 0 else None,
            "warm_cache_ratio": round(warm_cache / local_store_enabled, 4) if local_store_enabled > 0 else None,
        },
        "metrics_by_timeframe": timeframe_metrics,
        "metrics_by_market": market_metrics,
        "timing_trend": timing_trend,
    }


def _render_summary_text(payload: dict[str, object]) -> str:
    scan = payload.get("scan") or {}
    aggregate = payload.get("aggregate") or {}
    lines = [
        "【增量观测日报】",
        "",
        f"生成时间: {payload.get('generated_at')}",
        f"扫描 tech.json: {scan.get('scanned_tech_json_count', 0)}",
        f"启用本地仓库: {scan.get('local_store_enabled_count', 0)}",
        f"热缓存命中: {scan.get('warm_cache_count', 0)}",
        f"行数节省占比: {aggregate.get('saved_rows_ratio')}",
        "",
        "按周期统计:",
    ]

    for item in payload.get("metrics_by_timeframe") or []:
        lines.append(
            "- {timeframe}: reports={report_count}, local_store={local_store_count}, warm={warm_cache_count}, "
            "remote_rows={remote_rows}, analysis_rows={analysis_rows}, saved_ratio={saved_rows_ratio}".format(**item)
        )

    timing_trend = payload.get("timing_trend")
    lines.append("")
    if isinstance(timing_trend, dict):
        lines.append("耗时趋势:")
        lines.append(
            f"- latest_total_seconds={timing_trend.get('latest_total_seconds')} "
            f"baseline_median={timing_trend.get('baseline_median_total_seconds')} "
            f"improvement_pct={timing_trend.get('improvement_pct_vs_baseline')}"
        )
    else:
        lines.append("耗时趋势: 未找到可用的 holdings_refresh_timing 历史样本")

    return "\n".join(lines) + "\n"


def run_observability_report(
    *,
    reports_root: Path,
    meta_dir: Path,
    timeframes: tuple[str, ...],
    timing_window: int,
) -> ObservabilityReportResult:
    payload = build_observability_payload(
        reports_root,
        timeframes=timeframes,
        meta_dir=meta_dir,
        timing_window=timing_window,
    )

    meta_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_json_path = meta_dir / f"incremental_observability_{stamp}.json"
    latest_json_path = meta_dir / "incremental_observability_latest.json"
    archive_text_path = meta_dir / f"incremental_observability_{stamp}.txt"

    archive_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    latest_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    archive_text_path.write_text(_render_summary_text(payload), encoding="utf-8")

    return ObservabilityReportResult(
        archive_json_path=archive_json_path,
        latest_json_path=latest_json_path,
        archive_text_path=archive_text_path,
    )


def main() -> None:
    args = parse_args()
    result = run_observability_report(
        reports_root=Path(args.reports_root),
        meta_dir=Path(args.meta_dir),
        timeframes=tuple(args.timeframes),
        timing_window=args.timing_window,
    )
    print(f"observability_report= {result.archive_json_path}", flush=True)
    print(f"observability_report_latest= {result.latest_json_path}", flush=True)
    print(f"observability_summary= {result.archive_text_path}", flush=True)


if __name__ == "__main__":
    main()
