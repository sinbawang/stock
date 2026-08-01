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
    "run_day_incremental_probe",
    SCRIPTS / "run_day_incremental_probe.py",
)
if module_spec is None or module_spec.loader is None:
    raise RuntimeError("failed to load run_day_incremental_probe.py for tests")
module = importlib.util.module_from_spec(module_spec)
sys.modules[module_spec.name] = module
module_spec.loader.exec_module(module)


def test_derive_metrics_computes_saved_ratio_and_warm_hit() -> None:
    metrics = module._derive_metrics(
        {
            "local_rows_before": 1200,
            "remote_rows": 82,
            "analysis_rows": 1200,
            "added_rows": 3,
            "updated_rows": 24,
            "requested_start": "2021-01-01",
            "effective_start": "2026-04-01",
            "overlap_bars": 120,
        },
        run_elapsed_seconds=3.2,
    )

    assert metrics["local_rows_before"] == 1200
    assert metrics["saved_rows"] == 1118
    assert metrics["saved_rows_ratio"] == round(1118 / 1200, 4)
    assert metrics["warm_cache_hit"] is True
    assert metrics["run_elapsed_seconds"] == 3.2


def test_build_trend_aggregates_history_rows() -> None:
    trend = module._build_trend(
        [
            {"warm_cache_hit": True, "saved_rows_ratio": 0.5, "run_elapsed_seconds": 3.0},
            {"warm_cache_hit": False, "saved_rows_ratio": 0.0, "run_elapsed_seconds": 4.0},
            {"warm_cache_hit": True, "saved_rows_ratio": 0.9, "run_elapsed_seconds": 2.0},
        ]
    )

    assert trend["sample_count"] == 3
    assert trend["warm_cache_ratio"] == round(2 / 3, 4)
    assert trend["avg_saved_rows_ratio"] == round((0.5 + 0.0 + 0.9) / 3, 4)
    assert trend["avg_elapsed_seconds"] == 3.0


def test_run_probe_writes_reports_without_execute_run(monkeypatch, tmp_path: Path) -> None:
    reports_root = tmp_path / "reports"
    symbol = "000651"
    day_dir = reports_root / symbol / "day"
    day_dir.mkdir(parents=True, exist_ok=True)
    (day_dir / "tech.json").write_text(
        json.dumps(
            {
                "data_fetch": {
                    "local_store": {
                        "local_rows_before": 1200,
                        "remote_rows": 120,
                        "analysis_rows": 1200,
                        "added_rows": 0,
                        "updated_rows": 0,
                        "requested_start": "2021-01-01",
                        "effective_start": "2026-04-01",
                        "overlap_bars": 120,
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "REPORTS_DIR", reports_root)

    result = module.run_probe(
        symbol=symbol,
        name="格力电器",
        market="CN",
        day_bars=1200,
        overlap_bars=120,
        history_window=5,
        execute_run=False,
        meta_dir=tmp_path / "_meta",
    )

    assert result.archive_json_path.exists()
    assert result.latest_json_path.exists()
    assert result.archive_text_path.exists()

    payload = json.loads(result.latest_json_path.read_text(encoding="utf-8"))
    assert payload["symbol"] == symbol
    assert payload["metrics"]["saved_rows_ratio"] == round((1200 - 120) / 1200, 4)
    assert payload["history_trend"]["sample_count"] == 1
