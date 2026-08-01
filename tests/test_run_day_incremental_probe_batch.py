from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

module_spec = importlib.util.spec_from_file_location(
    "run_day_incremental_probe_batch",
    SCRIPTS / "run_day_incremental_probe_batch.py",
)
if module_spec is None or module_spec.loader is None:
    raise RuntimeError("failed to load run_day_incremental_probe_batch.py for tests")
module = importlib.util.module_from_spec(module_spec)
sys.modules[module_spec.name] = module
module_spec.loader.exec_module(module)


def test_build_summary_rows_aggregates_metrics() -> None:
    summary = module._build_summary_rows(
        [
            {
                "symbol": "000651",
                "name": "格力电器",
                "market": "CN",
                "saved_rows_ratio": 0.9,
                "warm_cache_hit": True,
                "remote_rows": 80,
                "analysis_rows": 1200,
                "run_elapsed_seconds": 3.0,
            },
            {
                "symbol": "00700",
                "name": "腾讯",
                "market": "HK",
                "saved_rows_ratio": 0.1,
                "warm_cache_hit": False,
                "remote_rows": 1000,
                "analysis_rows": 1200,
                "run_elapsed_seconds": 8.0,
            },
        ]
    )

    assert summary["count"] == 2
    assert summary["warm_cache_hits"] == 1
    assert summary["warm_cache_ratio"] == 0.5
    assert summary["avg_saved_rows_ratio"] == 0.5
    assert summary["avg_elapsed_seconds"] == 5.5
    assert summary["top_saved_rows_ratio"][0]["symbol"] == "000651"


def test_run_batch_probe_writes_reports(monkeypatch, tmp_path: Path) -> None:
    holdings = tmp_path / "holdings.json"
    holdings.write_text(
        json.dumps(
            {
                "markets": {
                    "CN": [{"symbol": "000651", "name": "格力电器"}],
                    "HK": [{"symbol": "00700", "name": "腾讯"}],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    counter = {"value": 0}

    def fake_run_probe(**kwargs):
        counter["value"] += 1
        latest_path = tmp_path / f"latest_{counter['value']}.json"
        archive_path = tmp_path / f"archive_{counter['value']}.json"
        latest_path.write_text(
            json.dumps(
                {
                    "metrics": {
                        "saved_rows_ratio": 0.9 if kwargs["market"] == "CN" else 0.2,
                        "warm_cache_hit": kwargs["market"] == "CN",
                        "remote_rows": 80 if kwargs["market"] == "CN" else 900,
                        "analysis_rows": 1200,
                        "run_elapsed_seconds": 3.1 if kwargs["market"] == "CN" else 6.2,
                    }
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        archive_path.write_text("{}", encoding="utf-8")
        return SimpleNamespace(
            archive_json_path=archive_path,
            latest_json_path=latest_path,
            archive_text_path=tmp_path / f"summary_{counter['value']}.txt",
        )

    monkeypatch.setattr(module, "_load_probe_module", lambda: SimpleNamespace(run_probe=fake_run_probe))

    args = SimpleNamespace(
        holdings_file=str(holdings),
        market="ALL",
        symbols=None,
        limit=None,
        day_bars=1200,
        incremental_overlap_bars=120,
        history_window=10,
        execute_run=False,
        meta_dir=str(tmp_path / "_meta"),
    )

    result = module.run_batch_probe(args)

    assert result.archive_json_path.exists()
    assert result.latest_json_path.exists()
    assert result.archive_text_path.exists()

    payload = json.loads(result.latest_json_path.read_text(encoding="utf-8"))
    assert payload["summary"]["count"] == 2
    assert payload["summary"]["warm_cache_hits"] == 1
