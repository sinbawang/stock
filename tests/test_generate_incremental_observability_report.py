from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

module_spec = importlib.util.spec_from_file_location(
    "generate_incremental_observability_report",
    SCRIPTS / "generate_incremental_observability_report.py",
)
if module_spec is None or module_spec.loader is None:
    raise RuntimeError("failed to load generate_incremental_observability_report.py for tests")
module = importlib.util.module_from_spec(module_spec)
sys.modules[module_spec.name] = module
module_spec.loader.exec_module(module)


def _write_tech_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_build_observability_payload_aggregates_local_store_metrics(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports"
    meta_dir = reports_root / "_meta"
    meta_dir.mkdir(parents=True)

    _write_tech_json(
        reports_root / "00700" / "5m" / "tech.json",
        {
            "symbol": "00700",
            "timeframe": "5m",
            "data_fetch": {
                "local_store": {
                    "local_rows_before": 500,
                    "remote_rows": 80,
                    "analysis_rows": 600,
                    "added_rows": 20,
                    "updated_rows": 3,
                }
            },
        },
    )
    _write_tech_json(
        reports_root / "300124" / "5m" / "tech.json",
        {
            "symbol": "300124",
            "timeframe": "5m",
            "data_fetch": {
                "local_store": {
                    "local_rows_before": 0,
                    "remote_rows": 600,
                    "analysis_rows": 600,
                    "added_rows": 600,
                    "updated_rows": 0,
                }
            },
        },
    )

    payload = module.build_observability_payload(
        reports_root,
        timeframes=("5m",),
        meta_dir=meta_dir,
        timing_window=5,
    )

    assert payload["scan"]["scanned_tech_json_count"] == 2
    assert payload["scan"]["local_store_enabled_count"] == 2
    assert payload["scan"]["warm_cache_count"] == 1
    assert payload["aggregate"]["saved_rows"] == 520
    assert payload["aggregate"]["analysis_rows"] == 1200
    assert payload["aggregate"]["saved_rows_ratio"] == round(520 / 1200, 4)

    timeframe_bucket = payload["metrics_by_timeframe"][0]
    assert timeframe_bucket["timeframe"] == "5m"
    assert timeframe_bucket["saved_rows"] == 520
    assert timeframe_bucket["local_store_count"] == 2


def test_load_timing_trend_uses_latest_and_median_baseline(tmp_path: Path) -> None:
    meta_dir = tmp_path / "_meta"
    meta_dir.mkdir(parents=True)

    samples = [
        ("20260701_100000", 120.0),
        ("20260702_100000", 100.0),
        ("20260703_100000", 80.0),
    ]
    for stamp, total_seconds in samples:
        payload = {
            "report_type": "holdings_refresh_timing",
            "stages": {"total_seconds": total_seconds},
        }
        (meta_dir / f"holdings_refresh_timing_{stamp}.json").write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )

    trend = module._load_timing_trend(meta_dir, window=7)

    assert trend is not None
    assert trend["latest_total_seconds"] == 80.0
    assert trend["baseline_sample_count"] == 2
    assert trend["baseline_median_total_seconds"] == 110.0
    assert trend["improvement_pct_vs_baseline"] == round((110.0 - 80.0) / 110.0 * 100, 2)


def test_load_timing_trend_excludes_latest_alias_file(tmp_path: Path) -> None:
    meta_dir = tmp_path / "_meta"
    meta_dir.mkdir(parents=True)

    for stamp, total_seconds in (("20260701_100000", 120.0), ("20260702_100000", 100.0)):
        payload = {"report_type": "holdings_refresh_timing", "stages": {"total_seconds": total_seconds}}
        (meta_dir / f"holdings_refresh_timing_{stamp}.json").write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )

    alias_payload = {"report_type": "holdings_refresh_timing", "stages": {"total_seconds": 999.0}}
    (meta_dir / "holdings_refresh_timing_latest.json").write_text(
        json.dumps(alias_payload, ensure_ascii=False),
        encoding="utf-8",
    )

    trend = module._load_timing_trend(meta_dir, window=7)

    assert trend is not None
    assert trend["latest_total_seconds"] == 100.0
    assert trend["baseline_sample_count"] == 1
    assert trend["baseline_median_total_seconds"] == 120.0
